using UnityEngine;
using UnityEngine.EventSystems;
using TMPro;

public enum KeypadInputType
{
    Generic,
    Decimal,
    IPAddress
}

public class KeypadTrigger : MonoBehaviour, IPointerClickHandler
{
    [Tooltip("O controlador do teclado numérico a ser ativado.")]
    public KeypadController keypadController;
    [Tooltip("O tipo de dado que este campo aceita.")]
    public KeypadInputType inputType = KeypadInputType.Decimal;

    [Tooltip("A chave (opcional) para salvar este valor no PlayerPrefs.")]
    public string playerPrefsKey;

    private TextMeshProUGUI textMeshPro;

    void Awake()
    {
        textMeshPro = GetComponent<TextMeshProUGUI>();
        if (keypadController == null)
        {
            keypadController = FindObjectOfType<KeypadController>(true);
        }
    }

    void Start()
    {
        if (textMeshPro != null && inputType != KeypadInputType.IPAddress && inputType != KeypadInputType.Generic)
        {
            textMeshPro.text = "0";
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (keypadController != null && textMeshPro != null)
        {
            keypadController.targetDisplayText = textMeshPro;
            keypadController.SetInputType(inputType, playerPrefsKey);
            keypadController.gameObject.SetActive(true);
        }
        else
        {
            Debug.LogError("KeypadController ou TextMeshProUGUI não encontrado em " + gameObject.name);
        }
    }
}
