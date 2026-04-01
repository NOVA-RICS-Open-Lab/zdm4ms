using UnityEngine;
using Unity.Cinemachine;
using UnityEngine.UI;
using TMPro;

public class CinemachineSelector : MonoBehaviour
{
    [Header("Configuração Comum")]
    public GameObject[] allSelectableObjects;
    public CinemachineCamera[] allVirtualCameras;
    public CinemachineCamera initialCamera;
    public GameObject backButton;

    [Header("Configuração Específica do Objeto")]
    public CinemachineCamera[] associatedVirtualCameras;
    public GameObject[] uiPanelsToActivate;
    public GameObject nextButton;
    public GameObject finishButton;

    private int currentStep = 0;

    private const int activePriority = 100;
    private const int inactivePriority = 10;

    void Start()
    {
        SetupInitialState();
    }

    private void SetupInitialState()
    {
        if (backButton != null) backButton.SetActive(false);
        if (nextButton != null) nextButton.SetActive(false);
        if (finishButton != null) finishButton.SetActive(false);

        foreach (var panel in uiPanelsToActivate) panel.SetActive(false);
    }

    public void SelectThisObject()
    {
        currentStep = 0;
        
        ConfigureButtonsForObject();
        ActivateCurrentStep();
        
        foreach (var obj in allSelectableObjects)
        {
            if (obj != gameObject) obj.SetActive(false);
        }
    }

    private void ConfigureButtonsForObject()
    {
        if (backButton != null)
        {
            backButton.SetActive(true);
            backButton.GetComponent<Button>().onClick.AddListener(GoBackStep);
        }

        if (nextButton != null)
        {
            nextButton.GetComponent<Button>().onClick.AddListener(NextStep);
        }

        if (finishButton != null)
        {
            finishButton.GetComponent<Button>().onClick.AddListener(ShowSummaryScreen);
        }
    }

    // Chamado automaticamente pelo Unity quando o GameObject é desativado
    void OnDisable()
    {
        // Remove os listeners específicos deste objeto para evitar que ele reaja a cliques quando não está selecionado.
        // Esta é a correção crucial para o bug do "objeto fantasma".
        if (backButton != null) backButton.GetComponent<Button>().onClick.RemoveListener(GoBackStep);
        if (nextButton != null) nextButton.GetComponent<Button>().onClick.RemoveListener(NextStep);
        if (finishButton != null) finishButton.GetComponent<Button>().onClick.RemoveListener(ShowSummaryScreen);
    }

    public void ResetToInitialView()
    {
        if (ObjectSelector.Instance != null)
        {
            ObjectSelector.Instance.ClearSelectionState();
        }

        SetupInitialState();

        foreach (var obj in allSelectableObjects) obj.SetActive(true);

        foreach (var vcam in allVirtualCameras) vcam.Priority = inactivePriority;

        if (initialCamera != null) initialCamera.Priority = activePriority;

        ResetAllKeypadTriggers();
    }

    private void ResetAllKeypadTriggers()
    {
        var allKeypadTriggers = FindObjectsOfType<KeypadTrigger>(true);
        foreach (var trigger in allKeypadTriggers)
        {
            var textMesh = trigger.GetComponent<TextMeshProUGUI>();
            if (textMesh != null && trigger.inputType != KeypadInputType.IPAddress) textMesh.text = "0";
        }
    }

    public void ActivateCurrentStep()
    {
        if (backButton != null) backButton.SetActive(true);

        for (int i = 0; i < uiPanelsToActivate.Length; i++)
        {
            uiPanelsToActivate[i].SetActive(i == currentStep);
        }

        foreach (var vcam in allVirtualCameras) vcam.Priority = inactivePriority;
        if (initialCamera != null) initialCamera.Priority = inactivePriority;

        if (currentStep < associatedVirtualCameras.Length)
        {
            associatedVirtualCameras[currentStep].Priority = activePriority;
        }

        if (nextButton != null) nextButton.SetActive(currentStep < uiPanelsToActivate.Length - 1);
        if (finishButton != null) finishButton.SetActive(currentStep == uiPanelsToActivate.Length - 1);
    }
    
    // Ativa o último passo (usado pelo botão Back da tela de resumo)
    public void ActivateLastStep()
    {
        gameObject.SetActive(true);
        ActivateCurrentStep();
    }

    public void NextStep()
    {
        if (currentStep < uiPanelsToActivate.Length - 1)
        {
            currentStep++;
            ActivateCurrentStep();
        }
    }

    public void GoBackStep()
    {
        currentStep--;
        if (currentStep < 0)
        {
            ResetToInitialView();
        }
        else
        {
            ActivateCurrentStep();
        }
    }

    private void ShowSummaryScreen()
    {
        if (SummaryManager.Instance != null)
        {
            // Desativa os painéis e botões de UI do produto
            foreach (var panel in uiPanelsToActivate) panel.SetActive(false);
            if (nextButton != null) nextButton.SetActive(false);
            if (finishButton != null) finishButton.SetActive(false);
            if (backButton != null) backButton.SetActive(false);

            // Volta para a câmara inicial
            foreach (var vcam in allVirtualCameras) vcam.Priority = inactivePriority;
            if (initialCamera != null) initialCamera.Priority = activePriority;

            // Mostra a tela de resumo, passando a referência deste objeto
            SummaryManager.Instance.ShowSummary(this);
        }
        else
        {
            Debug.LogError("Instância do SummaryManager não encontrada!");
        }
    }
}