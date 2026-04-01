// ExplanationRequester.cs
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;
using System.IO;
using System;
using System.Collections.Generic;

[System.Serializable]
public class PostData
{
    public string id;
}

public class ExplanationRequester : MonoBehaviour
{
    [Header("Configuração de Rede")]
    private string middlewareIP;
    private string aasIP;

    #region Estruturas de Dados para JSON do AAS
    [System.Serializable]
    public class AASResponse
    {
        [SerializeField] private string message;
        public string messageField => message;
        
        [SerializeField] private string _responseFromSwagger;
        public string ResponseFromSwagger
        {
            get { return _responseFromSwagger; }
            set { _responseFromSwagger = value; }
        }

        public static AASResponse FromJson(string json)
        {
            string fixedJson = json.Replace("\"Response from Swagger\":", "\"_responseFromSwagger\":");
            return JsonUtility.FromJson<AASResponse>(fixedJson);
        }
    }

    [System.Serializable]
    public class ProductDataSummary
    {
        public string id;
        public string timestamp;
        public string productType;
        public string predictType; // Z1 ou Z4
        public string result;
        public string explanationDict;
        public string explanationHtml;
        public bool isExplainable;
    }
    [System.Serializable]
    public class SetupResponse
    {
        public string explanationpage;
    }
    #endregion

    public void RequestExplanation(ProductDataSummary summary, Action<string> onExplanationReady)
    {
        if (summary == null) return;
        
        string jsonPayload = CreateExplanationJsonContent(summary);
        StartCoroutine(PostToSetupCoroutine(jsonPayload, summary.id, summary.predictType, onExplanationReady));
    }

    public void OpenExplanation(string path)
    {
        Debug.Log($"[ExplanationRequester] A tentar abrir explicação. Caminho original: {path}");
        
        string fileName = Path.GetFileName(path);
        string localIp = PostReceiver.GetLocalIPAddress();
        
        // Abrimos via servidor HTTP local para contornar restrições de segurança de iframes/Gradio
        string serverUrl = $"http://{localIp}:8080/explanations/{fileName}";
        
        Debug.Log($"[ExplanationRequester] A abrir via URL do servidor: {serverUrl}");
        Application.OpenURL(serverUrl);
    }

    private string CreateExplanationJsonContent(ProductDataSummary s)
    {
        string jsonDict = (s.explanationDict == "N/D" || string.IsNullOrEmpty(s.explanationDict)) ? "{}" : s.explanationDict.Replace("'", "\"");
        
        // Novo formato flat JSON conforme pedido
        return $"{{\"predict_type\":\"{s.predictType}\",\"result\":\"{s.result}\",\"id\":\"{s.id}\",\"type\":\"{s.productType}\",\"explanationdict\": {jsonDict}, \"explanationhtml\": \"{s.explanationHtml}\"}}";
    }

    private IEnumerator PostToSetupCoroutine(string jsonBody, string id, string predictType, Action<string> onExplanationReady)
    {
        string setupUrl = "http://192.168.2.90:5015/setup";
        Debug.Log($"[ExplanationRequester] A enviar POST para: {setupUrl}");
        
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonBody);

        using (UnityWebRequest request = new UnityWebRequest(setupUrl, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                try {
                    string jsonResponse = request.downloadHandler.text;
                    SetupResponse setupRes = JsonUtility.FromJson<SetupResponse>(jsonResponse);
                    
                    if (setupRes != null && !string.IsNullOrEmpty(setupRes.explanationpage))
                    {
                        Debug.Log($"[ExplanationRequester] Sucesso! A descodificar Base64 HTML (tamanho: {setupRes.explanationpage.Length})");
                        
                        // Decode Base64 to HTML string
                        byte[] htmlBytes = System.Convert.FromBase64String(setupRes.explanationpage);
                        string decodedHtml = Encoding.UTF8.GetString(htmlBytes);

                        string directoryPath = Path.Combine(Application.persistentDataPath, "Explanations");
                        if (!Directory.Exists(directoryPath)) Directory.CreateDirectory(directoryPath);
                        
                        // Nome de ficheiro único para evitar problemas de cache e servir o ficheiro correto
                        string safeId = id.Replace(":", "_").Replace("/", "_");
                        string fileName = $"explanation_{safeId}_{predictType}.html";
                        string filePath = Path.Combine(directoryPath, fileName);
                        
                        if (File.Exists(filePath)) File.Delete(filePath);
                        File.WriteAllText(filePath, decodedHtml, Encoding.UTF8);
                        
                        Debug.Log($"[ExplanationRequester] Ficheiro escrito em: {filePath}. Tamanho: {decodedHtml.Length} bytes.");
                        onExplanationReady?.Invoke(filePath);
                    }
                    else 
                    {
                        Debug.LogError("[ExplanationRequester] explanationpage em falta na resposta JSON.");
                    }
                }
                catch (Exception e) {
                    Debug.LogError($"[ExplanationRequester] Erro ao processar resposta de configuração: {e.Message}");
                }
            }
            else
            {
                Debug.LogError($"[ExplanationRequester] Erro ao enviar para configuração. Código: {request.responseCode}. Erro: {request.error}");
                if (!string.IsNullOrEmpty(request.downloadHandler.text))
                    Debug.LogError($"[ExplanationRequester] Corpo da Resposta de Erro: {request.downloadHandler.text}");
            }
        }
    }

    public IEnumerator GetProductDataCoroutine(string productId, Action<List<ProductDataSummary>> onResult)
    {
        middlewareIP = PlayerPrefs.GetString("MiddlewareIP", "192.168.2.90");
        aasIP = PlayerPrefs.GetString("AASIP", "192.168.2.90:5011");
        
        string targetUrl = $"http://{middlewareIP}:1880/aas/getproductdata";
        string jsonBody = "{\"destination\":\"" + aasIP + "\",\"msg\":{\"id\":" + productId + "}}";
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonBody);

        using (UnityWebRequest request = new UnityWebRequest(targetUrl, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                string rawJson = request.downloadHandler.text;
                Debug.Log($"[ExplanationRequester] JSON bruto recebido: {rawJson}");

                AASResponse aasRes = AASResponse.FromJson(rawJson);
                if (aasRes != null && !string.IsNullOrEmpty(aasRes.ResponseFromSwagger))
                {
                    Debug.Log($"[ExplanationRequester] ResponseFromSwagger: {aasRes.ResponseFromSwagger}");
                    List<ProductDataSummary> summaries = ParseAASInternalData(productId, aasRes.ResponseFromSwagger);
                    Debug.Log($"[ExplanationRequester] Processados {summaries.Count} resumos.");
                    foreach(var s in summaries) {
                        Debug.Log($"[ExplanationRequester] Resumo: ID={s.id}, Tipo={s.predictType}, Resultado={s.result}, Explicável={s.isExplainable}");
                    }
                    onResult?.Invoke(summaries);
                }
                else {
                    Debug.LogWarning("[ExplanationRequester] Resposta AAS ou ResponseFromSwagger está vazia.");
                    onResult?.Invoke(null);
                }
            }
            else
            {
                Debug.LogError($"[ExplanationRequester] Erro ao obter dados do produto: {request.error}");
                onResult?.Invoke(null);
            }
        }
    }

    private List<ProductDataSummary> ParseAASInternalData(string productId, string internalJson)
    {
        List<ProductDataSummary> summaries = new List<ProductDataSummary>();

        string rawTimestamp = ExtractValuePython(internalJson, "'idShort': 'timestamp'", "'value': '", "'");
        string formattedTimestamp = FormatTimestamp(rawTimestamp);

        string typeVal = ExtractValuePython(internalJson, "'productType':", "'value': '", "'");
        if (typeVal == "N/D" || typeVal.Length > 20) {
             typeVal = ExtractValuePython(internalJson, "'idShort': 'Name'", "'value': '", "'");
        }
        string typeUpper = typeVal.ToUpper();
        string finalProductType = "N/D";
        if (typeUpper.Contains("QUADRADO")) finalProductType = "Quadrado";
        else if (typeUpper.Contains("RETANGULO")) finalProductType = "Retangulo";
        else if (typeUpper.Contains("L")) finalProductType = "L";
        else finalProductType = typeUpper;

        string searchToken = "'idShort': 'Quality_Test_";
        int lastPos = 0;
        while ((lastPos = internalJson.IndexOf(searchToken, lastPos)) != -1)
        {
            int nextPos = internalJson.IndexOf(searchToken, lastPos + 1);
            string testBlock = (nextPos == -1) ? internalJson.Substring(lastPos) : internalJson.Substring(lastPos, nextPos - lastPos);

            ProductDataSummary s = new ProductDataSummary();
            s.id = productId;
            s.timestamp = formattedTimestamp;
            s.productType = finalProductType;

            if (testBlock.Contains("Quality_Test_Z1")) s.predictType = "Z1";
            else if (testBlock.Contains("Quality_Test_Z4")) s.predictType = "Z4";
            else s.predictType = "N/D";

            string resVal = ExtractValuePython(testBlock, "'idShort': 'Result'", "'value': '", "'");
            if (resVal.ToLower() == "ok") s.result = "OK";
            else if (resVal.ToLower().Contains("nok")) s.result = "NOK";
            else if (resVal.Contains("[") && resVal.Contains("]")) 
            {
                string cleaned = resVal.Replace("[", "").Replace("]", "").Replace(" ", "");
                string[] parts = cleaned.Split(',');
                for(int p=0; p<parts.Length; p++) {
                    if (float.TryParse(parts[p], System.Globalization.NumberStyles.Any, System.Globalization.CultureInfo.InvariantCulture, out float val))
                        parts[p] = val.ToString("F1", System.Globalization.CultureInfo.InvariantCulture); 
                }
                s.result = string.Join("|", parts);
            }
            else s.result = resVal.ToUpper();

            s.isExplainable = testBlock.Contains("AssociatedExplainer");
            if (s.isExplainable)
            {
                int explanationsIdx = testBlock.IndexOf("'idShort': 'AssociatedExplanations'");
                if (explanationsIdx != -1)
                {
                    string explanationsBlock = testBlock.Substring(explanationsIdx);
                    
                    string nestedJsonStr = ExtractValuePython(explanationsBlock, "'idShort': 'Result'", "'value': \"", "\"");
                    if (nestedJsonStr == "N/D")
                        nestedJsonStr = ExtractValuePython(explanationsBlock, "'idShort': 'Result'", "'value': '", "'");

                    if (nestedJsonStr != "N/D")
                    {
                        s.explanationDict = ExtractValuePython(nestedJsonStr, "'explanationdict'", "'explanationdict': ", ", 'explanationhtml'");
                        if (s.explanationDict == "N/D")
                            s.explanationDict = ExtractValuePython(nestedJsonStr, "'explanationdict'", "'explanationdict':", ", 'explanationhtml'");

                        s.explanationHtml = ExtractValuePython(nestedJsonStr, "'explanationhtml'", "'explanationhtml' : '", "'");
                        if (s.explanationHtml == "N/D")
                             s.explanationHtml = ExtractValuePython(nestedJsonStr, "'explanationhtml'", "'explanationhtml': '", "'");
                    }
                }

                if (s.explanationHtml == "N/D")
                {
                    s.explanationHtml = ExtractValuePython(testBlock, "'idShort': 'explanationhtml'", "'value': '", "'");
                }
            }

            summaries.Add(s);
            lastPos++;
        }

        if (summaries.Count == 0)
        {
            ProductDataSummary s = new ProductDataSummary();
            s.id = productId;
            s.timestamp = formattedTimestamp;
            s.productType = finalProductType;
            s.predictType = "N/D";
            s.result = "N/D";
            s.isExplainable = false;
            summaries.Add(s);
        }

        return summaries;
    }

    private string FormatTimestamp(string raw)
    {
        if (string.IsNullOrEmpty(raw) || raw == "N/D") return "N/D";
        try {
            DateTime dt = DateTime.Parse(raw, null, System.Globalization.DateTimeStyles.RoundtripKind);
            return dt.ToString("dd/MM/yyyy HH:mm");
        } catch { return raw; }
    }

    private string ExtractValuePython(string json, string anchor, string key, string closeQuote)
    {
        try {
            int anchorIdx = json.IndexOf(anchor);
            int searchStart = (anchorIdx == -1) ? 0 : anchorIdx;
            int start = json.IndexOf(key, searchStart);
            if (start == -1) return "N/D";
            start += key.Length;
            int end = json.IndexOf(closeQuote, start);
            if (end == -1) return "N/D";
            return json.Substring(start, end - start);
        } catch { return "N/D"; }
    }

    public bool IsValidHtml(string html)
    {
        return !string.IsNullOrEmpty(html) && html != "N/D" && html.Length > 20;
    }

#if UNITY_ANDROID && !UNITY_EDITOR
    private void OpenAndroidFile(string path)
    {
        try
        {
            AndroidJavaClass unityPlayer = new AndroidJavaClass("com.unity3d.player.UnityPlayer");
            AndroidJavaObject currentActivity = unityPlayer.GetStatic<AndroidJavaObject>("currentActivity");
            AndroidJavaObject context = currentActivity.Call<AndroidJavaObject>("getApplicationContext");
            
            string packageName = context.Call<string>("getPackageName");
            // Usamos o padrão mais comum e robusto
            string authority = "com.zdm4ms.printer.fileprovider";
            Debug.Log($"[ExplanationRequester] Android: PackageName={packageName}, Authority={authority}");
            
            AndroidJavaObject fileObject = new AndroidJavaObject("java.io.File", path);
            bool fileExists = fileObject.Call<bool>("exists");
            long fileSize = fileObject.Call<long>("length");
            Debug.Log($"[ExplanationRequester] Android: File exists={fileExists}, Size={fileSize}");
            
            AndroidJavaClass fileProviderClass = new AndroidJavaClass("androidx.core.content.FileProvider");
            AndroidJavaObject uri = fileProviderClass.CallStatic<AndroidJavaObject>("getUriForFile", currentActivity, authority, fileObject);
            
            AndroidJavaObject intent = new AndroidJavaObject("android.content.Intent", "android.intent.action.VIEW");
            intent.Call<AndroidJavaObject>("setDataAndType", uri, "text/html");
            intent.Call<AndroidJavaObject>("addFlags", 1); // FLAG_GRANT_READ_URI_PERMISSION
            intent.Call<AndroidJavaObject>("addFlags", 268435456); // FLAG_ACTIVITY_NEW_TASK

            currentActivity.Call("startActivity", intent);
            Debug.Log("[ExplanationRequester] Android: Intent disparado com sucesso.");
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[ExplanationRequester] Erro ao abrir arquivo no Android: {e.Message}");
            // Fallback
            Application.OpenURL("file://" + path);
        }
    }
#endif
}
