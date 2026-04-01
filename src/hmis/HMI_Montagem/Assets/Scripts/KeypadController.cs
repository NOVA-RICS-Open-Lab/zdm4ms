using TMPro;
using UnityEngine;

public class KeypadController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI displayText; // Internal display for the keypad

    [HideInInspector]
    public TextMeshProUGUI targetDisplayText; // The text field to update

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
    }

    public void OnNumberPressed(int number)
    {
        if (currentInputType == KeypadInputType.IPAddress)
        {
            string[] segments = currentInput.Split('.');
            if (segments.Length > 4) return;

            string lastSegment = segments[segments.Length - 1];
            if (lastSegment.Length >= 3) return;
        }
        else
        {
            if (currentInput.Length >= 20) return;
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
                if (!currentInput.EndsWith(".") && currentInput.Split('.').Length < 4)
                {
                    currentInput += symbol;
                }
            }
        }
        else
        {
            if (currentInput.Length >= 20) return;
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
        if (targetDisplayText != null)
        {
            targetDisplayText.text = currentInput;

            // Notifica o ProductViewManager para atualizar o estado de fade se for um campo de peça
            if (ProductViewManager.Instance != null)
            {
                ProductViewManager.Instance.ReevaluateFadedState(targetDisplayText);
            }

            if (!string.IsNullOrEmpty(currentPlayerPrefsKey))
            {
                // Se for um ID numérico, tentamos guardar como INT, caso contrário como STRING
                if (int.TryParse(currentInput, out int intValue))
                {
                    PlayerPrefs.SetInt(currentPlayerPrefsKey, intValue);
                }
                else
                {
                    PlayerPrefs.SetString(currentPlayerPrefsKey, currentInput);
                }
                PlayerPrefs.Save();
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
