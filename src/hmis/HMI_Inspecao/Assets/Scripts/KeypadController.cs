using TMPro;
using UnityEngine;
using System.Collections;

public class KeypadController : MonoBehaviour
{
    [Header("UI Elements")]
    public TextMeshProUGUI displayText; // Display interno do teclado

    [HideInInspector]
    public TextMeshProUGUI targetDisplayText; // O campo de texto a ser atualizado

    // Vari�veis de estado
    private string currentInput = "";
    private KeypadInputType currentInputType;
    private string currentPlayerPrefsKey; // Chave para salvar nos PlayerPrefs (opcional)

    /// <summary>
    /// Configura o teclado para uma nova tarefa. � aqui que a "m�gica" da reutiliza��o acontece.
    /// </summary>
    /// <param name="type">O tipo de entrada (Gen�rico, IP, Decimal).</param>
    /// <param name="playerPrefsKey">Opcional: A chave para salvar nos PlayerPrefs.</param>
    public void SetInputType(KeypadInputType type, string playerPrefsKey = null)
    {
        currentInputType = type;
        currentPlayerPrefsKey = playerPrefsKey;

        currentInput = "";
        UpdateDisplayText();
        TouchManager.IsBlockedByUI = true;
    }

    public void OnNumberPressed(int number)
    {
        // Valida��o de IP: n�o permite mais de 3 d�gitos por segmento.
        if (currentInputType == KeypadInputType.IPAddress)
        {
            string[] segments = currentInput.Split('.');
            if (segments.Length > 0)
            {
                string lastSegment = segments[segments.Length - 1];
                if (lastSegment.Length >= 3) return; // Bloqueia se o segmento atual j� tem 3 d�gitos
            }
        }
        // Valida��es de comprimento geral
        else if (currentInputType == KeypadInputType.Decimal && currentInput.Length >= 6) return;
        else if (currentInputType == KeypadInputType.Generic && currentInput.Length >= 20) return;

        currentInput += number.ToString();
        UpdateDisplayText();
    }

    public void OnSymbolPressed(string symbol)
    {
        if (symbol == ".")
        {
            if (currentInputType == KeypadInputType.Decimal && !currentInput.Contains("."))
            {
                currentInput += symbol;
            }
            else if (currentInputType == KeypadInputType.IPAddress)
            {
                // Valida��o robusta para o ponto no IP
                if (!string.IsNullOrEmpty(currentInput) && !currentInput.EndsWith(".") && currentInput.Split('.').Length < 4)
                {
                    currentInput += symbol;
                }
            }
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
        // Mant�m sua l�gica original para valores vazios
        if (string.IsNullOrEmpty(currentInput) && currentInputType != KeypadInputType.IPAddress && currentInputType != KeypadInputType.Generic)
        {
            currentInput = "0";
        }

        // 1. Atualiza o texto na interface
        if (targetDisplayText != null)
        {
            targetDisplayText.text = currentInput;
        }

        // 2. Salva nos PlayerPrefs, se uma chave foi fornecida
        if (!string.IsNullOrEmpty(currentPlayerPrefsKey))
        {
            PlayerPrefs.SetString(currentPlayerPrefsKey, currentInput);
            PlayerPrefs.Save();
        }

        // 3. Desativa o teclado usando o seu m�todo original
        StartCoroutine(DeactivateAfterFrame());
    }

    public void OnCancelPressed()
    {
        TouchManager.IsBlockedByUI = false;
        StartCoroutine(DeactivateAfterFrame());
    }

    // Seu mtodo de desativao foi mantido
    private IEnumerator DeactivateAfterFrame()
    {
        TouchManager.IsBlockedByUI = false;
        yield return new WaitForEndOfFrame();
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