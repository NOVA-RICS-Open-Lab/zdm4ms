using System.Collections.Generic;
using System.Linq;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

// Estrutura unificada para uma peça individual
[System.Serializable]
public class ProductPart
{
    public TextMeshProUGUI idField;
    public GameObject objectToFade;
    public Material defaultMaterial;
    public Material fadedMaterial;
}

// Estrutura unificada para a configuração de um produto completo
[System.Serializable]
public class ProductConfig
{
    public int productId;
    public List<GameObject> canvasesToEnable;
    public Animator assemblyAnimator;
    public List<ProductPart> parts;
}

// Estrutura para o painel de notificação reutilizável
[System.Serializable]
public class NotificationPanel
{
    public GameObject panel;
    public Image iconImage;
    public TextMeshProUGUI messageText;
    public Button closeButton;
}

public class ProductViewManager : MonoBehaviour
{
    public static ProductViewManager Instance { get; private set; }

    [Header("Product Configuration")]
    public List<ProductConfig> productConfigurations;

    [Header("Scene References")]
    public List<GameObject> allCanvases;
    public ViewSwitcher viewSwitcher;

    [Header("Notification Settings")]
    public NotificationPanel notificationPanel;
    public Sprite successSprite;
    public Sprite failureSprite;
    public Sprite waitSprite;

    [Header("Animation Triggers")]
    public string successAnimatorTrigger = "AssemblySuccess";
    public string failureAnimatorTrigger = "AssemblyFailure";

    private ProductConfig _currentProductConfig;
    private SettingsUIController _settingsUIController;
    private bool _pendingReset = false;

    const string urlAppend = ":1880/assembly";

    private void Start()
    {
        if (Instance == null) Instance = this;
        _settingsUIController = FindObjectOfType<SettingsUIController>();
        if (_settingsUIController == null) Debug.LogError("SettingsUIController not found in scene!");

        DisableAllCanvases();
        if (notificationPanel.panel != null) notificationPanel.panel.SetActive(false);
    }

    public void ShowProductView(int selectedProductId)
    {
        DisableAllCanvases();
        _currentProductConfig = productConfigurations.FirstOrDefault(p => p.productId == selectedProductId);

        if (_currentProductConfig != null)
        {
            foreach (var canvasGO in _currentProductConfig.canvasesToEnable)
            {
                if (canvasGO != null) canvasGO.SetActive(true);
            }
            UpdateFadedStates();
        }
        else
        {
            Debug.LogWarning("No configuration found for product ID: " + selectedProductId);
        }
    }

    private void DisableAllCanvases()
    {
        foreach (var canvasGO in allCanvases)
        {
            if (canvasGO != null) canvasGO.SetActive(false);
        }
    }

    private void UpdateFadedStates()
    {
        if (_currentProductConfig == null) return;
        foreach (var part in _currentProductConfig.parts)
        {
            ApplyFade(part, PartHasValue(part));
        }
    }

    private void ApplyFade(ProductPart part, bool hasValue)
    {
        if (part.objectToFade == null) return;
        MeshRenderer meshRenderer = part.objectToFade.GetComponent<MeshRenderer>();
        if (meshRenderer != null)
        {
            meshRenderer.material = hasValue ? part.defaultMaterial : part.fadedMaterial;
        }
    }

    private bool PartHasValue(ProductPart part)
    {
        return part.idField != null && !string.IsNullOrEmpty(part.idField.text) && part.idField.text != "0";
    }

    public void ReevaluateFadedState(TextMeshProUGUI changedField)
    {
        if (_currentProductConfig == null) return;
        var part = _currentProductConfig.parts.FirstOrDefault(p => p.idField == changedField);
        if (part != null) ApplyFade(part, PartHasValue(part));
    }

    public void SubmitAssembly()
    {
        if (_currentProductConfig == null) return;

        // 1. Verificar se há IDs duplicados
        if (HasDuplicateIds())
        {
            ShowNotification(failureSprite, "Existem IDs duplicados. Por favor, corrija-os.");
            return;
        }

        // 2. Verificar se todos os campos estão preenchidos
        if (!AllIdsFilled())
        {
            ShowNotification(failureSprite, "Faltam IDs. Por favor, preencha todos os campos.");
            return;
        }

        // 3. Se tudo estiver correto, mostrar o painel de configurações
        if (_settingsUIController != null) _settingsUIController.ShowSettingsPanel(this);
    }

    public void ConfirmAndSend()
    {
        string jsonPayload = BuildJsonPayload();
        if (jsonPayload == null) return;
        string url = SettingsManager.Instance.MiddlewareURL + urlAppend;
        StartCoroutine(WebService.Instance.SendPostRequest(url, jsonPayload, HandleServerResponse));
    }

    private bool AllIdsFilled()
    {
        return _currentProductConfig.parts.All(PartHasValue);
    }

    private bool HasDuplicateIds()
    {
        var filledIds = _currentProductConfig.parts
            .Where(PartHasValue) // Considera apenas as peças com valor preenchido
            .Select(p => p.idField.text)
            .ToList();

        // Se o número de IDs preenchidos for diferente do número de IDs únicos, há duplicados
        return filledIds.Count != new HashSet<string>(filledIds).Count;
    }

    private string BuildJsonPayload()
    {
        var idList = _currentProductConfig.parts.Select(p => p.idField.text).ToList();
        string assemblyIP = SettingsManager.Instance.AssemblyIP;
        int productID = SettingsManager.Instance.ProductID;
        string idsJson = string.Join(", ", idList.ToArray());
        string msgJson = string.Format("{{\"productid\":\"{0}\", \"ids\":[{1}]}}", productID, idsJson);
        return string.Format("{{\"destination\":\"{0}\", \"msg\":{1}}}", assemblyIP + ":5006", msgJson);
    }

    private void HandleServerResponse(string response)
    {
        if (string.IsNullOrEmpty(response))
        {
            ShowNotification(failureSprite, "Erro de comunicação. O servidor não respondeu.");
            return;
        }

        Debug.Log("Server Response: " + response);

        // --- 1. CASO DE SUCESSO ---
        if (response.Contains("New Complete product") || response.Contains("OK"))
        {
            ShowNotification(successSprite, "Montagem bem-sucedida!");
            if (_currentProductConfig.assemblyAnimator != null) 
                _currentProductConfig.assemblyAnimator.SetTrigger(successAnimatorTrigger);
            _pendingReset = true;
        }
        // --- 2. CASO DE ERRO/FALHA ---
        else if (response.Contains("ERROR False") || response.Contains("NOK"))
        {
            string errorMessage = "Falha na montagem.";
            
            // Tenta extrair a razão do erro se vier no formato "...reason: Mensagem"
            if (response.Contains("reason:"))
            {
                int reasonIndex = response.IndexOf("reason:") + "reason:".Length;
                errorMessage = response.Substring(reasonIndex).Trim().Replace("\"", "").Replace("}", "");
            }

            ShowNotification(failureSprite, errorMessage);
            
            if (_currentProductConfig.assemblyAnimator != null) 
                _currentProductConfig.assemblyAnimator.SetTrigger(failureAnimatorTrigger);
            
            // Opcional: Não fazemos ResetPartIDs aqui para o user poder corrigir o erro se quiser
            // ResetPartIDs(); 
        }
        // --- 3. CASO DE ESPERA ---
        else if (response.Contains("WAIT") || response.Contains("early printing") || response.Contains("ainda estao em impressao"))
        {
            string waitMessage = "A aguardar peças. Tente novamente mais tarde.";
            
            // Tenta extrair a mensagem específica: "message": "Texto"
            if (response.Contains("\"message\":"))
            {
                int msgStartIndex = response.IndexOf("\"message\":") + "\"message\":".Length;
                int firstQuote = response.IndexOf("\"", msgStartIndex) + 1;
                int lastQuote = response.LastIndexOf("\"");
                if (lastQuote > firstQuote)
                {
                    waitMessage = response.Substring(firstQuote, lastQuote - firstQuote);
                }
            }

            ShowNotification(waitSprite, waitMessage);
        }
        // --- 4. RESPOSTA DESCONHECIDA ---
        else
        {
            ShowNotification(failureSprite, "Resposta inesperada do servidor.");
        }
    }

    private void ShowNotification(Sprite icon, string message)
    {
        if (notificationPanel.panel == null) return;
        notificationPanel.iconImage.sprite = icon;
        notificationPanel.messageText.text = message;
        notificationPanel.panel.SetActive(true);
    }

    public void CloseNotificationPanel()
    {
        if (notificationPanel.panel != null) notificationPanel.panel.SetActive(false);
    }

    private void ResetPartIDs()
    {
        if (_currentProductConfig == null) return;
        foreach (var part in _currentProductConfig.parts)
        {
            if (part.idField != null) part.idField.text = "";
        }
        UpdateFadedStates();
    }

    public void GoBack()
    {
        if (_currentProductConfig != null)
        {
            foreach (var canvasGO in _currentProductConfig.canvasesToEnable) if (canvasGO != null) canvasGO.SetActive(false);

            // Sempre limpa os IDs e restaura os materiais ao sair
            ResetPartIDs();
            foreach (var part in _currentProductConfig.parts) ApplyFade(part, true);
        }

        // Limpa o ID do produto global para não persistir
        if (SettingsManager.Instance != null) SettingsManager.Instance.ClearProductID();

        _pendingReset = false;
        DisableAllCanvases();
        _currentProductConfig = null;
        if (notificationPanel.panel != null) notificationPanel.panel.SetActive(false);
        if (viewSwitcher != null) viewSwitcher.SwitchToMainView();
    }
}