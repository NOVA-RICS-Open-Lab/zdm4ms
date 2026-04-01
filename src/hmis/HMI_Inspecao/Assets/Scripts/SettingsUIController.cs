using UnityEngine;
using TMPro;

public class SettingsUIController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI productID_Text;
    public GameObject settingsPanel;

    private SummaryManager _currentSummaryManager;

    private void Start()
    {
        if (settingsPanel != null)
            settingsPanel.SetActive(false);
    }

    // Chamado pelo SummaryManager para mostrar o painel
    public void ShowSettingsPanel(SummaryManager manager)
    {
        _currentSummaryManager = manager;
        LoadSettingsToUI();
        settingsPanel.SetActive(true);
        TouchManager.IsBlockedByUI = true; // BLOQUEIA
    }

    // Chamado pelo botão "Finish" na UI
    public void FinishAndSend()
    {
        // 1. Obter o ProductID do texto da UI (pois este muda conforme o contexto)
        int productID = 0;
        if (productID_Text != null)
        {
            int.TryParse(productID_Text.text, out productID);
        }

        // 2. Atualizar o ProductID no SettingsManager antes de enviar
        if (SettingsManager.Instance != null)
        {
            SettingsManager.Instance.SetProductID(productID);
        }

        // 3. Chamar o SummaryManager para enviar o POST
        if (_currentSummaryManager != null)
        {
            _currentSummaryManager.ConfirmAndSend();
        }

        // 4. Fechar o painel
        if (settingsPanel != null)
        {
            settingsPanel.SetActive(false);
            TouchManager.IsBlockedByUI = false; // DESBLOQUEIA
        }
    }

    public void Cancel()
    {
        if (settingsPanel != null)
        {
            settingsPanel.SetActive(false);
            TouchManager.IsBlockedByUI = false; // DESBLOQUEIA
        }
    }

    private void LoadSettingsToUI()
    {
        if (SettingsManager.Instance == null)
        {
            Debug.LogError("SettingsManager.Instance is null! Make sure there is a SettingsManager in the scene.");
            return;
        }

        // O ProductID é o único que carregamos para a UI para poder ser editado/confirmado
        if (productID_Text != null)
        {
            productID_Text.text = SettingsManager.Instance.ProductID.ToString();
        }
        else
        {
            Debug.LogError("productID_Text is not assigned in the Inspector!", this);
        }

        // Nota: Os IPs já não precisam de referências de texto aqui, 
        // pois são geridos diretamente pelo SettingsManager e pelo Keypad via PlayerPrefs.
    }
}
