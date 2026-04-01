using Unity.Cinemachine;
using UnityEngine;

public class CinemachineSelector : MonoBehaviour
{
    [Header("Configuração Comum")]
    public GameObject[] allSelectableObjects;
    public CinemachineCamera[] allVirtualCameras;
    public CinemachineCamera initialCamera; // A câmara principal/inicial
    public GameObject backButton; // O botão para voltar

    [Header("Configuração Específica do Objeto")]
    public string filename;
    public CinemachineCamera associatedVirtualCamera;
    public GameObject uiPanelToActivate;

    private PrintController printController;

    private const int activePriority = 100;
    private const int inactivePriority = 10;

    void Start()
    {
        uiPanelToActivate.SetActive(true);

        // Garante que o botão "Back" começa desativado
        if (backButton != null)
        {
            backButton.SetActive(false);
        }

        // Encontra a referência para o PrintController
        printController = FindAnyObjectByType<PrintController>();
        if (printController == null)
        {
            Debug.LogError("PrintController não encontrado na cena!");
        }
        uiPanelToActivate.SetActive(false);
    }

    public void SelectThisObject()
    {
        Debug.Log($"Selecionando objeto: {gameObject.name}");

        // Ativa o painel de UI específico deste objeto
        if (uiPanelToActivate != null)
        {
            Debug.Log($"Ativando painel de UI: {uiPanelToActivate.name}");
            uiPanelToActivate.SetActive(true);
        }

        // Ativa o botão de voltar
        if (backButton != null)
        {
            Debug.Log($"Ativando botão de voltar: {backButton.name}");
            backButton.SetActive(true);
        }

        // Esconde os outros objetos selecionáveis
        foreach (GameObject obj in allSelectableObjects)
        {
            if (obj != this.gameObject)
            {
                obj.SetActive(false);
            }
        }

        // Ativa a câmara virtual associada a este objeto
        foreach (CinemachineCamera vcam in allVirtualCameras)
        {
            vcam.Priority = (vcam == associatedVirtualCamera) ? activePriority : inactivePriority;
        }
        if (initialCamera != null) initialCamera.Priority = inactivePriority;

        // Atualiza o nome do arquivo no PrintController
        if (printController != null)
        {
            Debug.Log($"Atualizando o nome do arquivo para: {filename}");
            printController.UpdateFilename(filename);
        }
    }

    // Função pública para ser chamada pelo botão "Back"
    public void ReturnToInitialView()
    {
        // Desativa o botão de voltar
        if (backButton != null)
        {
            backButton.SetActive(false);
        }

        // Desativa todos os painéis de UI específicos
        // (Encontra todos os seletores para garantir que todos os painéis são desativados)
        CinemachineSelector[] allSelectors = FindObjectsByType<CinemachineSelector>(FindObjectsSortMode.None);
        foreach (var selector in allSelectors)
        {
            if (selector.uiPanelToActivate != null)
            {
                selector.uiPanelToActivate.SetActive(false);
            }
        }

        // Reativa todos os objetos selecionáveis
        foreach (GameObject obj in allSelectableObjects)
        {
            obj.SetActive(true);
        }

        // Desativa todas as câmaras virtuais de objetos
        foreach (CinemachineCamera vcam in allVirtualCameras)
        {
            vcam.Priority = inactivePriority;
        }

        // Ativa a câmara inicial
        if (initialCamera != null)
        {
            initialCamera.Priority = activePriority;
        }
    }
}
