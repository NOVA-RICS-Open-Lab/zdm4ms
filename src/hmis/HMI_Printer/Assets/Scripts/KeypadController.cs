using TMPro;
using UnityEngine;

public class KeypadController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI displayText; // Internal display for the keypad

    [HideInInspector]
    public TextMeshProUGUI targetDisplayText; // The text field to update

    public PrintController printController; // Reference to the PrintController

    private string currentInput = "";
    private KeypadInputType currentInputType; // Stores the current input type
    private string currentPlayerPrefsKey; // Stores the PlayerPrefs key for the current input

    // Called when the keypad is activated
    void OnEnable()
    {
        currentInput = "";
        UpdateDisplayText();
    }

    public void SetInputType(KeypadInputType type, string playerPrefsKey)
    {
        currentInputType = type;
        currentPlayerPrefsKey = playerPrefsKey;
        // Optionally, you can change keypad UI elements based on type here
    }

    public void OnNumberPressed(int number)
    {
        if (currentInputType == KeypadInputType.IPAddress)
        {
            // Basic IP validation: max 3 digits per segment, max 4 segments
            string[] segments = currentInput.Split('.');
            if (segments.Length > 4) return; // Max 4 segments

            string lastSegment = segments[segments.Length - 1];
            if (lastSegment.Length >= 3) return; // Max 3 digits per segment
        }
        else
        {
            if (currentInput.Length >= 20) return; // Generic limit
        }

        currentInput += number.ToString();
        UpdateDisplayText();
    }

    public void OnSymbolPressed(string symbol)
    {
        if (symbol == ".")
        {
            if (currentInputType == KeypadInputType.IPAddress)
            {
                // Allow dot only if it's an IP and not already at the end or too many dots
                if (!currentInput.EndsWith(".") && currentInput.Split('.').Length < 4)
                {
                    currentInput += symbol;
                }
            }
            // Else, do not allow dot for generic input
        }
        else
        {
            // For other symbols, if any are ever added
            if (currentInput.Length >= 20) return; // Generic limit
            currentInput += symbol;
        }
        UpdateDisplayText();
    }

    public void OnDeletePressed()
    {
        if (currentInput.Length > 0)
        {
            currentInput = currentInput.Substring(0, currentInput.Length - 1);
        }
        UpdateDisplayText();
    }

    public void OnOKPressed()
    {
        // Se o campo de texto alvo for o da velocidade, chama o PrintController para tratar da lógica.
        if (printController != null && targetDisplayText == printController.speedFactorValueText)
        {
            printController.SetSpeedFactorFromText(currentInput);
        }
        // Para todos os outros campos de texto...
        else if (targetDisplayText != null)
        {
            // Atualiza o texto diretamente
            targetDisplayText.text = currentInput;

            // E salva nos PlayerPrefs se a chave existir
            if (!string.IsNullOrEmpty(currentPlayerPrefsKey))
            {
                Debug.Log($"KeypadController: A tentar guardar nos PlayerPrefs. Chave: {currentPlayerPrefsKey}, Valor: {currentInput}");
                if (currentInputType == KeypadInputType.Generic && int.TryParse(currentInput, out int intValue))
                {
                    PlayerPrefs.SetInt(currentPlayerPrefsKey, intValue);
                    Debug.Log($"KeypadController: Guardado como INT. Chave: {currentPlayerPrefsKey}, Valor: {intValue}");
                }
                else
                {
                    PlayerPrefs.SetString(currentPlayerPrefsKey, currentInput);
                    Debug.Log($"KeypadController: Guardado como STRING. Chave: {currentPlayerPrefsKey}, Valor: {currentInput}");
                }
                PlayerPrefs.Save(); // Save changes immediately
                Debug.Log("KeypadController: PlayerPrefs.Save() chamado.");
            }
            else
            {
                Debug.LogWarning("KeypadController: currentPlayerPrefsKey é NULO ou vazio. Não foi guardado nos PlayerPrefs.");
            }
        }
        
        gameObject.SetActive(false);
    }

    public void OnCancelPressed()
    {
        gameObject.SetActive(false);
    }

    private void UpdateDisplayText()
    {
        if (displayText != null)
        {
            displayText.text = currentInput;
        }
    }
}
