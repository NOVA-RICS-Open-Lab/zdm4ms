// TouchManager.cs
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch; // Usando o sistema de toque avançado
using System.Collections.Generic; // Necessário para usar List<>

public class TouchManager : MonoBehaviour
{
    private Camera mainCamera;

    [Header("UI a Monitorizar")]
    [Tooltip("Arraste para aqui todos os painéis de UI que, quando ativos, devem bloquear o toque no mundo do jogo.")]
    public List<GameObject> uiPanelsToMonitor; // NOVO: A nossa lista de painéis de UI

    void Awake()
    {
        EnsureCamera();
    }

    private void EnsureCamera()
    {
        if (mainCamera == null)
        {
            mainCamera = Camera.main;
        }
    }

    void OnEnable()
    {
        if (!EnhancedTouchSupport.enabled)
        {
            EnhancedTouchSupport.Enable();
        }
        UnityEngine.InputSystem.EnhancedTouch.Touch.onFingerDown += HandleFingerDown;
    }

    void OnDisable()
    {
        UnityEngine.InputSystem.EnhancedTouch.Touch.onFingerDown -= HandleFingerDown;
        // Não desativamos globalmente o EnhancedTouchSupport para não afetar outros scripts
    }

    private void HandleFingerDown(Finger finger)
    {
        EnsureCamera();
        if (mainCamera == null) return;

        // --- NOVA LÓGICA DE VERIFICAÇÃO DA UI ---
        // Verifica se algum dos painéis de UI na nossa lista está ativo.
        if (IsAnyUIPanelActive())
        {
            Debug.Log("Toque ignorado: Um painel de UI monitorizado está ativo.");
            return; // Sai da função imediatamente, ignorando o toque.
        }

        // Se chegarmos aqui, significa que nenhuma UI importante está ativa,
        // então podemos processar o toque no mundo do jogo.

        Ray ray = mainCamera.ScreenPointToRay(finger.currentTouch.screenPosition);
        RaycastHit hit;

        if (Physics.Raycast(ray, out hit))
        {
            Debug.Log("Raycast atingiu: " + hit.collider.name);

            // Primeiro, verifica se o objeto é um seletor de cinemachine
            CinemachineSelector cinemachineSelector = hit.collider.GetComponent<CinemachineSelector>();
            if (cinemachineSelector != null)
            {
                Debug.Log("Script CinemachineSelector encontrado, executando a seleção de câmera.");
                cinemachineSelector.SelectThisObject();
                return;
            }

            // Se não for um seletor de câmera, verifica se é um objeto selecionável
            Selectable selectable = hit.collider.GetComponent<Selectable>();
            if (selectable != null)
            {
                Debug.Log("Script Selectable encontrado, executando a seleção de objeto.");
                if (ObjectSelector.Instance != null)
                {
                    ObjectSelector.Instance.SelectObject(selectable.gameObject);
                }
            }
            else
            {
                Debug.Log("O objeto atingido não possui um script 'Selectable' ou 'CinemachineSelector'.");
            }
        }
        else
        {
            Debug.Log("Raycast não atingiu nenhum objeto com Collider.");
        }
    }

    /// <summary>
    /// Percorre a lista de painéis de UI e retorna verdadeiro se algum deles estiver ativo.
    /// </summary>
    /// <returns>Verdadeiro se um painel estiver ativo, falso caso contrário.</returns>
    private bool IsAnyUIPanelActive()
    {
        // Percorre cada GameObject na nossa lista
        foreach (var panel in uiPanelsToMonitor)
        {
            // Verifica se o painel não é nulo e se está ativo na hierarquia
            if (panel != null && panel.activeSelf)
            {
                return true; // Encontrou um painel ativo, retorna verdadeiro imediatamente
            }
        }

        return false; // Nenhum painel ativo foi encontrado
    }
}