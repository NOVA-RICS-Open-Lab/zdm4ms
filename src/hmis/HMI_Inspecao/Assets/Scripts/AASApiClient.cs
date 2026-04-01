using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;
using System;

public class AASApiClient : MonoBehaviour
{
    private const string MiddlewareIPKey = "MiddlewareIP";
    private const string InspectionIPKey = "InspectionIP";

    // --- Estruturas para Peças Standard ---
    [System.Serializable]
    public class StandardMeasurements
    {
        public double largura;
        public double altura;
        public double comprimento;
    }

    [System.Serializable]
    public class StandardProductMsg
    {
        public int id;
        public string type;
        public StandardMeasurements measurements;
    }

    [System.Serializable]
    private class StandardInspectionRequest
    {
        public string destination;
        public StandardProductMsg msg;
    }

    // --- Estruturas para Peças em L ---
    [System.Serializable]
    public class LShapeMeasurements
    {
        public double largura;
        public double altura;
        public double comprimento;
        public double largura_ext1;
        public double largura_ext2;
        public double comprimento_ext1;
        public double comprimento_ext2;
    }

    [System.Serializable]
    public class LShapeProductMsg
    {
        public int id;
        public string type;
        public LShapeMeasurements measurements;
    }

    [System.Serializable]
    private class LShapeInspectionRequest
    {
        public string destination;
        public LShapeProductMsg msg;
    }

    // --- Métodos Públicos ---
    public void SendStandardInspection(StandardProductMsg msg, Action onSuccess, Action<string> onError)
    {
        string destinationIp = SettingsManager.Instance != null ? SettingsManager.Instance.InspectionIP : PlayerPrefs.GetString(InspectionIPKey, "127.0.0.1");
        
        var request = new StandardInspectionRequest
        {
            destination = destinationIp + ":5007",
            msg = msg
        };

        StartCoroutine(PostRequest(JsonUtility.ToJson(request, true), onSuccess, onError));
    }

    public void SendLShapeInspection(LShapeProductMsg msg, Action onSuccess, Action<string> onError)
    {
        string destinationIp = SettingsManager.Instance != null ? SettingsManager.Instance.InspectionIP : PlayerPrefs.GetString(InspectionIPKey, "127.0.0.1");
        
        var request = new LShapeInspectionRequest
        {
            destination = destinationIp + ":5007",
            msg = msg
        };

        StartCoroutine(PostRequest(JsonUtility.ToJson(request, true), onSuccess, onError));
    }

    [System.Serializable]
    private class MiddlewareResponse
    {
        public string error;
    }

    private IEnumerator PostRequest(string jsonBody, Action onSuccess, Action<string> onError)
    {
        string baseUrl = SettingsManager.Instance != null ? SettingsManager.Instance.MiddlewareIP : PlayerPrefs.GetString(MiddlewareIPKey, "127.0.0.1");
        string url = baseUrl.StartsWith("http") ? $"{baseUrl}:1880/inspection" : $"http://{baseUrl}:1880/inspection";

        Debug.Log($"<color=cyan>[POST SEND]</color> URL: {url}\nBody: {jsonBody}");

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonBody);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                // Mostra sempre a resposta bruta para debug
                string responseText = request.downloadHandler.text;
                Debug.Log($"<color=yellow>[POST RESPONSE]</color> {responseText}");

                MiddlewareResponse res = null;

                try {
                    res = JsonUtility.FromJson<MiddlewareResponse>(responseText);
                } catch { }

                if (res != null && !string.IsNullOrEmpty(res.error))
                {
                    Debug.LogError($"<color=red>[POST LOGIC ERROR]</color> {res.error}");
                    onError?.Invoke(res.error);
                }
                else
                {
                    Debug.Log("<color=green>[POST SUCCESS]</color> Enviado com sucesso.");
                    onSuccess?.Invoke();
                }
            }
            else
            {
                Debug.LogError($"<color=red>[POST HTTP ERROR]</color> {request.error}\nResponse: {request.downloadHandler.text}");
                onError?.Invoke(request.error);
            }
        }
    }
}
