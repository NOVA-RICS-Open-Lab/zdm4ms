using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

public class PrintingUIManager : MonoBehaviour
{
    [Header("UI Panels")]
    public GameObject printingPanel;
    public GameObject removePartPanel;

    [Header("Buttons")]
    public Button pauseButton;
    public Button resumeButton;
    public Button stopButton;
    public Button removePartOkButton;

    [Header("G-Code Commands")]
    public string startCommand = "M24";  // Comando para Resume/Start
    public string pauseCommand = "M25";  // Comando para Pause
    public string stopCommand = "M524";  // Comando para Stop

    [Header("API Settings")]
    private const string ApiPort = "1880";
    private const string ApiCommandPath = "/printer/command";

    [System.Serializable]
    private class CommandRequestBody
    {
        public string destination;
        public string msg; // String direta para o Middleware
        public string key;
    }

    void Start()
    {
        // Atribui os comandos das vari�veis p�blicas aos bot�es
        pauseButton.onClick.AddListener(() => SendCommand(pauseCommand));
        resumeButton.onClick.AddListener(() => SendCommand(startCommand));
        stopButton.onClick.AddListener(() => SendCommand(stopCommand));

        removePartOkButton.onClick.AddListener(CloseRemovePartPanel);

        printingPanel.SetActive(false);
        removePartPanel.SetActive(false);
        resumeButton.gameObject.SetActive(false);
    }

    public void ShowPrintingPanel()
    {
        printingPanel.SetActive(true);
        pauseButton.gameObject.SetActive(true);
        resumeButton.gameObject.SetActive(false);
    }

    public void HidePrintingPanel()
    {
        printingPanel.SetActive(false);
    }

    public void ShowRemovePartPanel()
    {
        removePartPanel.SetActive(true);
    }

    public void CloseRemovePartPanel()
    {
        removePartPanel.SetActive(false);
    }

    private void SendCommand(string command)
    {
        Debug.Log($"A preparar envio do comando: {command}");

        // L�gica visual dos bot�es de Pause/Resume
        if (command == pauseCommand)
        {
            pauseButton.gameObject.SetActive(false);
            resumeButton.gameObject.SetActive(true);
        }
        else if (command == startCommand)
        {
            resumeButton.gameObject.SetActive(false);
            pauseButton.gameObject.SetActive(true);
        }

        StartCoroutine(SendCommandCoroutine(command));
    }

    private IEnumerator SendCommandCoroutine(string command)
    {
        string middlewareIP = PlayerPrefs.GetString("MiddlewareIP", "192.168.2.90");
        string printerIP = PlayerPrefs.GetString("PrinterIP", "192.168.6.1");
        string apiKey = PlayerPrefs.GetString("APIKey", "QL3SCr7AwEO8tBTnvPsWEORjOCctfQEWAqwes_m0fko");

        string apiUrl = $"http://{middlewareIP}:{ApiPort}{ApiCommandPath}";

        CommandRequestBody body = new CommandRequestBody
        {
            destination = printerIP,
            msg = command, // Envia a string (ex: "M524")
            key = apiKey
        };

        string requestBody = JsonUtility.ToJson(body);
        Debug.Log($"A enviar para o Middleware: {requestBody}");

        using (UnityWebRequest webRequest = new UnityWebRequest(apiUrl, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(requestBody);
            webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
            webRequest.downloadHandler = new DownloadHandlerBuffer();
            webRequest.SetRequestHeader("Content-Type", "application/json");

            yield return webRequest.SendWebRequest();

            if (webRequest.result != UnityWebRequest.Result.Success)
            {
                Debug.LogError($"Erro ao enviar {command}: {webRequest.error}");
            }
            else
            {
                Debug.Log($"Comando {command} aceite pelo Middleware.");
            }
        }
    }
}