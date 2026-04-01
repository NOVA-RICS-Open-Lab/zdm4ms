using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.EnhancedTouch; 

public class TouchManager : MonoBehaviour
{
    private Camera mainCamera;

    // Flag estática para bloquear toques a partir de qualquer script
    public static bool IsBlockedByUI = false;

    void Awake()
    {
        mainCamera = Camera.main;
    }

    void OnEnable()
    {
        EnhancedTouchSupport.Enable();
    }

    void OnDisable()
    {
        EnhancedTouchSupport.Disable();
    }

    void Update()
    {
        // Se estiver explicitamente bloqueado, não processa nada
        if (IsBlockedByUI) return;

        // 1. Verificar Toque
        var activeTouches = UnityEngine.InputSystem.EnhancedTouch.Touch.activeTouches;
        if (activeTouches.Count > 0)
        {
            foreach (var touch in activeTouches)
            {
                if (touch.phase == UnityEngine.InputSystem.TouchPhase.Began)
                {
                    HandleInput(touch.screenPosition);
                }
            }
        }
        // 2. Verificar Rato
        else if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame)
        {
            HandleInput(Mouse.current.position.ReadValue());
        }
    }

    private void HandleInput(Vector2 screenPosition)
    {
        Ray ray = mainCamera.ScreenPointToRay(screenPosition);
        RaycastHit hit;

        if (Physics.Raycast(ray, out hit))
        {
            Selectable selectable = hit.collider.GetComponent<Selectable>();
            CinemachineSelector cinemachineSelector = hit.collider.GetComponent<CinemachineSelector>();

            if (selectable != null || cinemachineSelector != null)
            {
                if (ObjectSelector.Instance != null)
                {
                    ObjectSelector.Instance.SelectObject(hit.collider.gameObject);
                }
            }
        }
    }
}
