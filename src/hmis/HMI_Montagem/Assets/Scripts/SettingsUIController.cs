
using UnityEngine;
using TMPro;

public class SettingsUIController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI productID_Text;
    public GameObject settingsPanel;

    private ProductViewManager _currentProductViewManager;

    private void Start()
    {
        settingsPanel.SetActive(false);
    }

    // Chamado pelo ProductViewManager para mostrar o painel
    public void ShowSettingsPanel(ProductViewManager manager)
    {
        _currentProductViewManager = manager;
        LoadSettingsToUI();
        settingsPanel.SetActive(true);
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
        SettingsManager.Instance.SetProductID(productID);

        // 3. Chamar o ProductViewManager para enviar o POST
        if (_currentProductViewManager != null)
        {
            _currentProductViewManager.ConfirmAndSend();
        }

        // 4. Fechar o painel
        settingsPanel.SetActive(false);
    }

    public void Cancel()
    {
        settingsPanel.SetActive(false);
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
