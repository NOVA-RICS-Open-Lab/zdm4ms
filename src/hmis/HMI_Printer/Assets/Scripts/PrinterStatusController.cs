using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

public class PrinterStatusController : MonoBehaviour
{
    [Header("UI Elements")]
    public GameObject statusUIParent; // Parent GameObject for status UI elements
    public Image statusImage;
    public TextMeshProUGUI statusText;

    [Header("Status Sprites")]
    public Sprite onlineSprite;
    public Sprite offlineSprite;
    public Sprite busySprite;

    [Header("Dependencies")]
    public PrintingUIManager printingUIManager; // Referência ao novo script

    [Header("API Settings")]
    private string middlewareIP;
    private string destination;
    private string apiKey;
    private const string ApiPort = "1880";
    private const string ApiPath = "/printer/status";

    [Header("Refresh Rate")]
    public float refreshInterval = 5f;

    public string CurrentState { get; private set; } = "MW Offline"; // Estado inicial
    private bool wasPreviouslyPrinting = false; // Flag para controlar o estado de impressão anterior

    // Internal class to parse the JSON response
    [System.Serializable]
    private class PrinterStatusResponse
    {
        public string state;
    }

    // Internal class for the request body
    [System.Serializable]
    private class PrinterRequestBody
    {
        public string destination;
        public string key;
    }

    void Awake()
    {
        // Disable UI elements initially
        if (statusUIParent != null) statusUIParent.gameObject.SetActive(false);
    }

    void Start()
    {
        Debug.Log("PrinterStatusController: Início chamado.");

        // Load values from PlayerPrefs or use default
        SetMWOfflineStatus();

        // Start checking the status repeatedly
        StartCoroutine(FetchPrinterStatusRoutine());
        }

    private IEnumerator FetchPrinterStatusRoutine()
    {
        Debug.Log("PrinterStatusController: Rotina de verificação de estado iniciada.");
        while (true)
        {
            middlewareIP = PlayerPrefs.GetString("MiddlewareIP", "192.168.2.90");
            destination = PlayerPrefs.GetString("PrinterIP", "192.168.6.1");
            apiKey = PlayerPrefs.GetString("APIKey", "QL3SCr7AwEO8tBTnvPsWEORjOCctfQEWAqwes_m0fko"); // You might want to set a proper default API key
            Debug.Log($"PrinterStatusController: MiddlewareIP carregado: {middlewareIP}, Destino: {destination}, APIKey: {apiKey}");

            yield return StartCoroutine(FetchPrinterStatus());
            yield return new WaitForSeconds(refreshInterval);
        }
    }

    private IEnumerator FetchPrinterStatus()
    {
        string apiUrl = $"http://{middlewareIP}:{ApiPort}{ApiPath}";
        Debug.Log($"PrinterStatusController: A obter estado do URL: {apiUrl}");

        PrinterRequestBody body = new PrinterRequestBody
        {
            destination = this.destination,
            key = this.apiKey
        };
        string requestBody = JsonUtility.ToJson(body);
        Debug.Log($"PrinterStatusController: Corpo do pedido: {requestBody}");

        using (UnityWebRequest webRequest = new UnityWebRequest(apiUrl, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(requestBody);
            webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
            webRequest.downloadHandler = new DownloadHandlerBuffer();
            webRequest.SetRequestHeader("Content-Type", "application/json");

            yield return webRequest.SendWebRequest();

            if (webRequest.result == UnityWebRequest.Result.ConnectionError)
            {
                Debug.LogError($"PrinterStatusController: Erro de ligação: {webRequest.error}");
                SetMWOfflineStatus();
            }
            else if (webRequest.result == UnityWebRequest.Result.ProtocolError)
            {
                Debug.LogError($"PrinterStatusController: Erro de protocolo: {webRequest.error} - {webRequest.downloadHandler.text}");
                SetPrinterOfflineStatus();
            }
            else
            {
                try
                {
                    string responseJson = webRequest.downloadHandler.text;
                    // Debug.Log($"PrinterStatusController: Response: {responseJson}");
                    PrinterStatusResponse response = JsonUtility.FromJson<PrinterStatusResponse>(responseJson);

                    Debug.Log("PrinterStatusController: "+response.state);

                    if (response != null && !string.IsNullOrEmpty(response.state))
                    {
                        if (response.state.Equals("Operational", System.StringComparison.OrdinalIgnoreCase))
                        {
                            SetOnlineStatus();
                        }
                        else
                        {
                            SetBusyStatus();
                        }
                    }
                    else
                    {
                        Debug.LogWarning("PrinterStatusController: Estado inválido ou vazio na resposta.");
                        SetPrinterOfflineStatus();
                    }
                }
                catch (System.Exception e)
                {
                    Debug.LogError($"PrinterStatusController: Falha ao processar resposta JSON: {e.Message}");
                    SetPrinterOfflineStatus();
                }
            }
        }
    }

    private void UpdateUI(string text, Sprite sprite)
    {
        if (statusUIParent != null)
        {
            if (!statusUIParent.activeSelf)
                statusUIParent.SetActive(true);
        }
        else
        {
            Debug.LogError("PrinterStatusController: statusUIParent é NULO. Por favor, atribua-o no Inspector.");
        }

        if (statusText != null)
        {
            statusText.text = text;
        }
        else
        {
            Debug.LogError("PrinterStatusController: statusText é NULO. Por favor, atribua-o no Inspector.");
        }

        if (statusImage != null)
        {
            statusImage.sprite = sprite;
        }
        else
        {
            Debug.LogError("PrinterStatusController: statusImage é NULO. Por favor, atribua-o no Inspector.");
        }
    }

    private void SetMWOfflineStatus()
    {
        UpdateUI("MW Offline", offlineSprite);
        CurrentState = "MW Offline";
        HandlePrintEnd();
    }

    private void SetPrinterOfflineStatus()
    {
        UpdateUI("Offline", offlineSprite);
        CurrentState = "Offline";
        HandlePrintEnd();
    }

    private void SetOnlineStatus()
    {
        UpdateUI("Online", onlineSprite);
        CurrentState = "Online";
        HandlePrintEnd();
    }

    private void SetBusyStatus()
    {
        UpdateUI("Ocupada", busySprite);
        CurrentState = "Ocupada";
        HandlePrintStart();
    }

    private void HandlePrintStart()
    {
        wasPreviouslyPrinting = true;
        if (printingUIManager != null)
        {
            printingUIManager.ShowPrintingPanel();
        }
    }

    private void HandlePrintEnd()
    {
        if (wasPreviouslyPrinting)
        {
            if (printingUIManager != null)
            {
                printingUIManager.HidePrintingPanel();
                printingUIManager.ShowRemovePartPanel();
            }
            wasPreviouslyPrinting = false;
        }
    }
}
