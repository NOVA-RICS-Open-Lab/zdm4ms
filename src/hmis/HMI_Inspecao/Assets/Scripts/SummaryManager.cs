using UnityEngine;
using UnityEngine.UI;
using TMPro;
using System.Collections.Generic;
using System.Linq;

public class SummaryManager : MonoBehaviour
{
    public static SummaryManager Instance;

    [Header("UI da Tela de Resumo")]
    public GameObject summaryPanel;
    public Button backButton;
    public Button finishButton;

    [Header("Referências")]
    public AASApiClient aasApiClient;
    public SettingsUIController settingsUIController;
    public TextMeshProUGUI globalProductIDText; // O campo único de ID para todos os produtos

    private CinemachineSelector lastProductSelector;
    private ProductDimensions currentProductDimensions;

    void Awake()
    {
        if (Instance == null) Instance = this; else Destroy(gameObject);
        if (aasApiClient == null) aasApiClient = FindObjectOfType<AASApiClient>();
        if (settingsUIController == null) settingsUIController = FindObjectOfType<SettingsUIController>(true);
    }

    void Start()
    {
        summaryPanel.SetActive(false);
        backButton.onClick.AddListener(GoBackToProduct);
        finishButton.onClick.AddListener(OnFinishPressed);
    }

    public void ShowSummary(CinemachineSelector productSelector)
    {
        lastProductSelector = productSelector;
        currentProductDimensions = productSelector.GetComponent<ProductDimensions>();
        summaryPanel.SetActive(true);
        TouchManager.IsBlockedByUI = true; // BLOQUEIA
    }

    private void GoBackToProduct()
    {
        summaryPanel.SetActive(false);
        TouchManager.IsBlockedByUI = false; // DESBLOQUEIA
        if (lastProductSelector != null) lastProductSelector.ActivateLastStep();
    }

    private void OnFinishPressed()
    {
        if (settingsUIController != null)
        {
            settingsUIController.ShowSettingsPanel(this);
        }
        else
        {
            ConfirmAndSend();
        }
    }

    public void ConfirmAndSend()
    {
        summaryPanel.SetActive(false);
        if (StatusFeedbackManager.Instance != null)
        {
            StatusFeedbackManager.Instance.ShowWaiting(lastProductSelector);
            SendProductDataViaApiClient();
        }
    }

    private void SendProductDataViaApiClient()
    {
        if (aasApiClient == null || currentProductDimensions == null) return;

        var culture = System.Globalization.CultureInfo.InvariantCulture;
        var style = System.Globalization.NumberStyles.Any;

        List<string> inputDimensions = currentProductDimensions.dimensions.Select(d => d.valueText.text.Replace(",", ".")).ToList();
        
        string productType = lastProductSelector.transform.parent != null ? 
                             lastProductSelector.transform.parent.name : 
                             lastProductSelector.name;

        // Tenta ler o ID do campo global fixo
        int pID = 0;
        if (globalProductIDText != null)
        {
            int.TryParse(globalProductIDText.text, out pID);
        }

        // Se pID continuar a 0, podes adicionar um fallback opcional para a UI de confirmação
        if (pID == 0 && settingsUIController != null && settingsUIController.productID_Text != null)
        {
            int.TryParse(settingsUIController.productID_Text.text, out pID);
        }

        if (inputDimensions.Count == 5)
        {
            var lMsg = new AASApiClient.LShapeProductMsg
            {
                id = pID,
                type = "L-Shape",
                measurements = new AASApiClient.LShapeMeasurements()
            };
            
            double.TryParse(inputDimensions[0], style, culture, out double c);
            double.TryParse(inputDimensions[1], style, culture, out double l);
            double.TryParse(inputDimensions[2], style, culture, out double a);
            double.TryParse(inputDimensions[3], style, culture, out double ce1);
            double.TryParse(inputDimensions[4], style, culture, out double le1);

            lMsg.measurements.comprimento = System.Math.Round(c, 2);
            lMsg.measurements.largura = System.Math.Round(l, 2);
            lMsg.measurements.altura = System.Math.Round(a, 2);
            lMsg.measurements.comprimento_ext1 = System.Math.Round(ce1, 2);
            lMsg.measurements.largura_ext1 = System.Math.Round(le1, 2);
            
            lMsg.measurements.comprimento_ext2 = System.Math.Round(lMsg.measurements.comprimento - lMsg.measurements.comprimento_ext1, 2);
            lMsg.measurements.largura_ext2 = System.Math.Round(lMsg.measurements.largura - lMsg.measurements.largura_ext1, 2);

            aasApiClient.SendLShapeInspection(lMsg, 
                () => {
                    TouchManager.IsBlockedByUI = false; // DESBLOQUEIA NO SUCESSO
                    StatusFeedbackManager.Instance.ShowSuccess();
                }, 
                (err) => {
                    TouchManager.IsBlockedByUI = false; // DESBLOQUEIA NO ERRO
                    StatusFeedbackManager.Instance.ShowError(err);
                });
        }
        else
        {
            // ... (dentro do else do Standard)
            var sMsg = new AASApiClient.StandardProductMsg
            {
                id = pID,
                type = productType.Contains("Quadrado") ? "Quadrado" : productType,
                measurements = new AASApiClient.StandardMeasurements()
            };

            double.TryParse(inputDimensions[0], style, culture, out double c);
            double.TryParse(inputDimensions[1], style, culture, out double l);
            double.TryParse(inputDimensions[2], style, culture, out double a);

            sMsg.measurements.comprimento = System.Math.Round(c, 2);
            sMsg.measurements.largura = System.Math.Round(l, 2);
            sMsg.measurements.altura = System.Math.Round(a, 2);

            aasApiClient.SendStandardInspection(sMsg, 
                () => {
                    TouchManager.IsBlockedByUI = false; // DESBLOQUEIA NO SUCESSO
                    StatusFeedbackManager.Instance.ShowSuccess();
                }, 
                (err) => {
                    TouchManager.IsBlockedByUI = false; // DESBLOQUEIA NO ERRO
                    StatusFeedbackManager.Instance.ShowError(err);
                });
        }
    }
}
