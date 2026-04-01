// PostReceiver.cs
using UnityEngine;
using UnityEngine.UI;
using UnityEngine.Networking;
using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Net.NetworkInformation;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Collections;
using System.Collections.Generic;
using TMPro;

public class PostReceiver : MonoBehaviour
{
    [Header("Configurações do Servidor")]
    public int serverPort = 8080;

    [Header("Configuração dos GameObjects")]
    public GameObject postTemplatePrefab;
    public Transform contentParent;

    [Header("UI de Status e Interação")]
    public TextMeshProUGUI serverStatusText;
    public GameObject postsPanel; 
    public Button togglePostsButton;

    [Header("UI de Notificações")]
    public Image notificationIndicatorImage;
    public TextMeshProUGUI notificationCountText;

    private int _newPostsCount = 0;
    private HttpListener _listener;
    private Task _listenerTask;
    private static Queue<PostData> _receivedDataQueue = new Queue<PostData>();

    private void Start()
    {
        if (postTemplatePrefab == null || contentParent == null || postsPanel == null || togglePostsButton == null)
        {
            Debug.LogError("Campos não atribuídos no PostReceiver!");
            return;
        }

        postsPanel.SetActive(false); 
        ResetNotifications();

        togglePostsButton.onClick.RemoveAllListeners();
        togglePostsButton.onClick.AddListener(TogglePostsPanel);

        StartCoroutine(FetchAllProductsFromAAS());

        string localIp = GetLocalIPAddress();
        if (string.IsNullOrEmpty(localIp)) return;

        string listenerUrl = $"http://{localIp}:{serverPort}/";
        try
        {
            _listener = new HttpListener();
            _listener.Prefixes.Add(listenerUrl);
            _listener.Start();
            _listenerTask = Task.Run(() => ListenForRequests());
            if (serverStatusText != null) serverStatusText.text = listenerUrl;
        }
        catch (Exception ex)
        {
            if (serverStatusText != null) serverStatusText.text = "Erro Servidor";
            Debug.LogError(ex.Message);
        }
    }

    private IEnumerator FetchAllProductsFromAAS()
    {
        string middlewareIP = PlayerPrefs.GetString("MiddlewareIP", "192.168.2.90");
        string aasIP = PlayerPrefs.GetString("AASIP", "192.168.2.90:5011");
        string url = $"http://{middlewareIP}:1880/aas/getproducts";

        string jsonBody = "{\"destination\":\"" + aasIP + "\"}";
        byte[] bodyRaw = Encoding.UTF8.GetBytes(jsonBody);

        using (UnityWebRequest request = new UnityWebRequest(url, "POST"))
        {
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            yield return request.SendWebRequest();

            if (request.result == UnityWebRequest.Result.Success)
            {
                ParseAndCreateInitialPosts(request.downloadHandler.text);
            }
        }
    }

    private void ParseAndCreateInitialPosts(string json)
    {
        int startIdx = json.IndexOf("[{");
        int endIdx = json.LastIndexOf("}]");
        if (startIdx == -1 || endIdx == -1) return;

        string innerList = json.Substring(startIdx + 1, (endIdx - startIdx)); 
        string[] items = innerList.Split(new string[] { "}, {" }, StringSplitOptions.None);

        foreach (var item in items)
        {
            string cleaned = item.Replace("{", "").Replace("}", "").Trim();
            int colonIdx = cleaned.IndexOf(":");
            if (colonIdx == -1) continue;
            string id = cleaned.Substring(0, colonIdx).Replace("'", "").Replace("\"", "").Trim();
            CreateGameObjectFromPost(new PostData { id = id }, true); // Permitir notificar carga inicial
        }
    }

    private void Update()
    {
        lock (_receivedDataQueue)
        {
            while (_receivedDataQueue.Count > 0)
            {
                CreateGameObjectFromPost(_receivedDataQueue.Dequeue(), true); // Notificar novos posts
            }
        }
    }

    public void TogglePostsPanel()
    {
        if (postsPanel == null) return;
        bool active = !postsPanel.activeSelf;
        postsPanel.SetActive(active);
        if (active) ResetNotifications();
        else UpdateNotificationUI();
    }

    private void CreateGameObjectFromPost(PostData data, bool incrementCount)
    {
        // Verificar duplicados por ID para evitar chamadas de API redundantes
        foreach (Transform child in contentParent)
        {
            HistoricDisplay childDisplay = child.GetComponent<HistoricDisplay>();
            if (childDisplay != null && childDisplay.idText != null && childDisplay.idText.text == data.id)
            {
                // Se já existe, mandamos atualizar para procurar novos testes (ex: se tinha Z1 e agora veio Z4)
                StartCoroutine(FetchDataAndNotify(childDisplay, incrementCount));
                return;
            }
        }

        GameObject newPostObject = Instantiate(postTemplatePrefab, contentParent);
        HistoricDisplay display = newPostObject.GetComponent<HistoricDisplay>();
        if (display != null)
        {
            display.SetData(data);
            
            // Iniciamos a corrotina que aguarda os dados ANTES de notificar
            StartCoroutine(FetchDataAndNotify(display, incrementCount));
        }
    }

    private IEnumerator FetchDataAndNotify(HistoricDisplay display, bool incrementCount)
    {
        int linesCreated = 0;
        // Agora o FetchDetailedDataExternal devolve o número de linhas criadas
        yield return StartCoroutine(display.FetchDetailedDataExternal((count) => {
            linesCreated = count;
        }));

        // Incrementamos se for um post novo com linhas válidas. 
        // O UpdateNotificationUI tratará de esconder a bolinha se o painel estiver aberto.
        if (incrementCount && linesCreated > 0)
        {
            _newPostsCount += linesCreated;
            UpdateNotificationUI();
        }

        SortPostsByTime();
    }

    public void SortPostsByTime()
    {
        if (contentParent == null) return;

        List<Transform> children = new List<Transform>();
        foreach (Transform child in contentParent)
        {
            children.Add(child);
        }

        children.Sort((a, b) =>
        {
            HistoricDisplay displayA = a.GetComponent<HistoricDisplay>();
            HistoricDisplay displayB = b.GetComponent<HistoricDisplay>();
            
            if (displayA == null || displayB == null) return 0;
            
            DateTime timeA = ParseDisplayTime(displayA.startTimeText.text);
            DateTime timeB = ParseDisplayTime(displayB.startTimeText.text);
            
            int timeComparison = timeB.CompareTo(timeA);
            if (timeComparison != 0) return timeComparison;

            // Se a hora for igual, Z1 vem antes de Z4
            string typeA = displayA.predictTypeText.text;
            string typeB = displayB.predictTypeText.text;
            return typeA.CompareTo(typeB); // "Z1" vem antes de "Z4" alfabeticamente
        });

        for (int i = 0; i < children.Count; i++)
        {
            children[i].SetSiblingIndex(i);
        }
    }

    private DateTime ParseDisplayTime(string timeStr)
    {
        if (string.IsNullOrEmpty(timeStr) || timeStr == "A carregar..." || timeStr == "N/D")
            return DateTime.MinValue;
            
        if (DateTime.TryParseExact(timeStr, "dd/MM/yyyy HH:mm", null, System.Globalization.DateTimeStyles.None, out DateTime dt))
            return dt;
            
        return DateTime.MinValue;
    }

    private void ResetNotifications()
    {
        _newPostsCount = 0;
        UpdateNotificationUI();
    }

    private void UpdateNotificationUI()
    {
        if (notificationCountText != null) notificationCountText.text = _newPostsCount.ToString();
        if (notificationIndicatorImage != null)
        {
            bool shouldShow = _newPostsCount > 0 && !postsPanel.activeSelf;
            
            // Garantir que a bolinha ativa/desativa conforme necessário
            if (notificationIndicatorImage.gameObject.activeSelf != shouldShow)
            {
                notificationIndicatorImage.gameObject.SetActive(shouldShow);
            }
        }
    }

    private async void ListenForRequests()
    {
        while (_listener != null && _listener.IsListening)
        {
            try
            {
                var context = await _listener.GetContextAsync();
                string path = context.Request.Url.AbsolutePath.ToLower();

                if (context.Request.HttpMethod == "POST" && path == "/updatenotice")
                {
                    using (var reader = new StreamReader(context.Request.InputStream))
                    {
                        string body = await reader.ReadToEndAsync();
                        PostData data = JsonUtility.FromJson<PostData>(body);
                        lock (_receivedDataQueue) { _receivedDataQueue.Enqueue(data); }
                    }
                    context.Response.StatusCode = 200;
                }
                else if (context.Request.HttpMethod == "GET" && path.StartsWith("/explanations/"))
                {
                    // Lógica para servir ficheiros HTML
                    string fileName = path.Replace("/explanations/", "");
                    string filePath = Path.Combine(Application.persistentDataPath, "Explanations", fileName);

                    if (File.Exists(filePath))
                    {
                        byte[] buffer = File.ReadAllBytes(filePath);
                        context.Response.ContentType = "text/html";
                        context.Response.ContentLength64 = buffer.Length;
                        await context.Response.OutputStream.WriteAsync(buffer, 0, buffer.Length);
                        context.Response.StatusCode = 200;
                    }
                    else
                    {
                        context.Response.StatusCode = 404;
                    }
                }
                else
                {
                    context.Response.StatusCode = 404;
                }
                
                context.Response.Close();
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"Erro no servidor: {ex.Message}");
            }
        }
    }

    public static string GetLocalIPAddress()
    {
        return NetworkInterface.GetAllNetworkInterfaces()
            .SelectMany(i => i.GetIPProperties().UnicastAddresses)
            .FirstOrDefault(a => a.Address.AddressFamily == AddressFamily.InterNetwork)?.Address.ToString();
    }

    private void OnDestroy()
    {
        if (_listener != null) { _listener.Stop(); _listener.Close(); }
    }
}
