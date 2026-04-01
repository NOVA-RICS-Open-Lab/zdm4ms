using System.Collections;
using TMPro;
using UnityEngine;
using UnityEngine.Networking;
using UnityEngine.UI;

public class PrintController : MonoBehaviour
{
    [Header("UI Elements")]
    public Slider speedFactorSlider;
    public TextMeshProUGUI speedFactorValueText;
    public TextMeshProUGUI filenameText;
    public TextMeshProUGUI idText; // Para mostrar o ID
    public Button printButton;
    public GameObject keypadObject; // O GameObject do seu keypad

    [Header("Popups")]
    public GameObject waitingPopup; // O popup de "Aguarde..."
    public GameObject statusPopup;
    public Image statusPopupImage;
    public TextMeshProUGUI statusPopupText;
    public Button closePopupButton;
    public Sprite successSprite;
    public Sprite errorSprite;

    [Header("Dependencies")]
    public PrinterStatusController printerStatusController; // Arraste o objeto com este script aqui

    [Header("API Settings")]
    private const string ApiPort = "1880";
    private const string DestinationPort = "5000";
    private const string ApiPath = "/monitoring/start";

    private TextMeshProUGUI activeTargetText; // Guarda qual texto está a ser editado

    // --- Classes internas para construir o JSON ---
    [System.Serializable]
    private class PrintJobMessage
    {
        public string filename;
        public float speed_factor;
        public string ip_printer;
        public string ip_hmi; // Novo campo para o IP do HMI
        public int id;
    }

    [System.Serializable]
    private class PrintRequestBody
    {
        public string destination;
        public PrintJobMessage msg;
    }

    void Start()
    {
        // Configurar o Slider
        speedFactorSlider.minValue = 10;
        speedFactorSlider.maxValue = 999;

        idText.text = PlayerPrefs.GetInt("ProductID", 1).ToString();

        // Sincronizar o valor inicial
        UpdateSpeedFactor(PlayerPrefs.GetFloat("SpeedFactor", 100f));

        // Adicionar listeners para os eventos da UI
        speedFactorSlider.onValueChanged.AddListener(UpdateSpeedFactor);
        printButton.onClick.AddListener(StartPrintRequest);
        closePopupButton.onClick.AddListener(CloseStatusPopup);

        // Garantir que o keypad e os popups começam desativados
        if (keypadObject != null) keypadObject.SetActive(false);
        if (statusPopup != null) statusPopup.SetActive(false);
        if (waitingPopup != null) waitingPopup.SetActive(false);
    }

    // --- Função Central de Sincronização da Velocidade ---
    public void UpdateSpeedFactor(float newValue)
    {
        float roundedValue = Mathf.Round(newValue);
        float clampedValue = Mathf.Clamp(roundedValue, speedFactorSlider.minValue, speedFactorSlider.maxValue);

        speedFactorSlider.onValueChanged.RemoveListener(UpdateSpeedFactor);
        speedFactorSlider.value = clampedValue;
        speedFactorSlider.onValueChanged.AddListener(UpdateSpeedFactor);
        
        speedFactorValueText.text = clampedValue.ToString("F0");

        PlayerPrefs.SetFloat("SpeedFactor", clampedValue);
        PlayerPrefs.Save();
    }

    public void SetSpeedFactorFromText(string value)
    {
        if (float.TryParse(value, out float speed))
        {
            UpdateSpeedFactor(speed);
        }
        else
        {
            Debug.LogWarning($"PrintController: Não foi possível converter o fator de velocidade do texto: {value}");
        }
    }

    public void UpdateFilename(string newFilename)
    {
        if (filenameText != null)
        {
            filenameText.text = newFilename;
        }
        else
        {
            Debug.LogError("PrintController: filenameText é NULO. Por favor, atribua-o no Inspector.");
        }
    }

    // --- Funções para o Keypad ---
    public void OpenKeypadFor(TextMeshProUGUI targetText)
    {
        activeTargetText = targetText;
        if (keypadObject != null) keypadObject.SetActive(true);
    }

    public void UpdateTextFromKeypad(string newText)
    {
        if (activeTargetText != null)
        {
            activeTargetText.text = newText;
        }
        if (keypadObject != null) keypadObject.SetActive(false);
    }

    // --- Lógica de Impressão ---
    public void StartPrintRequest()
    {
        // --- VERIFICAÇÃO DO ESTADO DA IMPRESSORA ---
        if (printerStatusController == null)
        {
            Debug.LogError("PrintController: A referência ao PrinterStatusController não está definida!");
            ShowErrorPopup("Erro de configuração interna.\nFalta a referência ao controlador de estado.");
            return;
        }

        if (printerStatusController.CurrentState != "Online")
        {
            Debug.LogWarning($"Impressão bloqueada. Estado da impressora: {printerStatusController.CurrentState}");
            ShowErrorPopup($"A impressora não está pronta.\nEstado atual: {printerStatusController.CurrentState}");
            return;
        }
        // --- FIM DA VERIFICAÇÃO ---

        StartCoroutine(SendPrintRequestCoroutine());
    }

    public void CloseStatusPopup()
    {
        if (statusPopup != null)
        {
            statusPopup.SetActive(false);
        }
    }

    private IEnumerator SendPrintRequestCoroutine()
    {
        if (waitingPopup != null) waitingPopup.SetActive(true);
        string middlewareIPText= PlayerPrefs.GetString("MiddlewareIP", "127.0.0.1");
        string apiUrl = $"http://{middlewareIPText}:{ApiPort}{ApiPath}";

        if (!int.TryParse(idText.text, out int currentId))
        {
            Debug.LogError($"ID inválido: '{idText.text}'. Por favor, insira um número válido.");
            ShowErrorPopup($"ID inválido: '{idText.text}'.");
            yield break;
        }
        string ipPrinterText= PlayerPrefs.GetString("PrinterIP", "127.0.0.1");
        string ipHmiText = PostReceiver.GetLocalIPAddress(); // Obtém o IP atual do HMI

        PrintJobMessage message = new PrintJobMessage
        {
            filename = filenameText.text,
            speed_factor = speedFactorSlider.value,
            ip_printer = ipPrinterText,
            ip_hmi = ipHmiText+":8080",
            id = currentId
        };

        string destinationIPText = PlayerPrefs.GetString("DestinationIP", "127.0.0.1");
        PrintRequestBody body = new PrintRequestBody
        {
            destination = destinationIPText+":"+DestinationPort,
            msg = message
        };

        string requestBody = JsonUtility.ToJson(body);
        Debug.Log("A enviar pedido: " + requestBody);

        using (UnityWebRequest webRequest = new UnityWebRequest(apiUrl, "POST"))
        {
            byte[] bodyRaw = System.Text.Encoding.UTF8.GetBytes(requestBody);
            webRequest.uploadHandler = new UploadHandlerRaw(bodyRaw);
            webRequest.downloadHandler = new DownloadHandlerBuffer();
            webRequest.SetRequestHeader("Content-Type", "application/json");

            yield return webRequest.SendWebRequest();

            if (waitingPopup != null) waitingPopup.SetActive(false);

            if (webRequest.responseCode == 200 || webRequest.responseCode == 201)
            {
                statusPopup.SetActive(true);
                Debug.Log("Pedido de impressão enviado com sucesso!");
                statusPopupImage.sprite = successSprite;
                statusPopupText.text = webRequest.downloadHandler.text;
            }
            else
            {
                ShowErrorPopup($"Erro {webRequest.responseCode}:\n{webRequest.downloadHandler.text}");
            }
        }
    }

    // --- Função auxiliar para mostrar popups de erro ---
    private void ShowErrorPopup(string message)
    {
        if (statusPopup != null)
        {
            statusPopupImage.sprite = errorSprite;
            statusPopupText.text = message;
            statusPopup.SetActive(true);
        }
        // Garante que o popup de espera (se estiver ativo) seja desativado
        if (waitingPopup != null && waitingPopup.activeSelf)
        {
            waitingPopup.SetActive(false);
        }
    }
}
