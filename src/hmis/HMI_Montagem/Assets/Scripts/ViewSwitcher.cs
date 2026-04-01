using Unity.Cinemachine;
using UnityEngine;

public class ViewSwitcher : MonoBehaviour
{
    [SerializeField]
    private GameObject[] focusObjects;

    [SerializeField]
    private CinemachineCamera[] virtualCameras;

    [SerializeField]
    private Animator[] animators;

    [SerializeField]
    private GameObject backButton;
    [SerializeField]
    private GameObject[] keyPads;

    private const string EnterTrigger = "Enter";
    private const string ExitTrigger = "Exit";

    private int currentViewIndex = -1; // Guarda o índice da vista ativa

    public void SwitchToView(int viewIndex)
    {
        if (viewIndex < 0 || viewIndex >= focusObjects.Length)
        {
            Debug.LogError("Índice de visão inválido: " + viewIndex);
            return;
        }

        currentViewIndex = viewIndex; // Guarda a vista que está a ser ativada

        for (int i = 0; i < focusObjects.Length; i++)
        {
            if (i == viewIndex)
            {
                focusObjects[i].SetActive(true);
                virtualCameras[i].Priority = 10;
                if (i < animators.Length && animators[i] != null)
                {
                    animators[i].SetTrigger(EnterTrigger);
                }
            }
            else
            {
                focusObjects[i].SetActive(false);
                virtualCameras[i].Priority = 0;
            }
        }

        backButton.SetActive(true);
    }

    public void SwitchToMainView()
    {
        // Ativa o trigger "Exit" apenas no animator da vista que estava ativa
        if (currentViewIndex != -1 && currentViewIndex < animators.Length && animators[currentViewIndex] != null)
        {
            animators[currentViewIndex].SetTrigger(ExitTrigger);
        }

        currentViewIndex = -1; // Limpa o estado

        foreach (GameObject obj in focusObjects)
        {
            obj.SetActive(true);
        }

        foreach (CinemachineCamera vcam in virtualCameras)
        {
            vcam.Priority = 0;
        }

        backButton.SetActive(false);
        foreach (GameObject keypad in keyPads)
        {
            keypad.SetActive(false);
        }
        Debug.Log("A mudar para a Vista Principal. Todos os objetos ativos, todas as câmaras virtuais com prioridade baixa.");
    }
}
