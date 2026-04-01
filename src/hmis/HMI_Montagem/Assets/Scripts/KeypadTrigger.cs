using UnityEngine;
using UnityEngine.EventSystems;
using TMPro;

public enum KeypadInputType
{
    Generic,
    IPAddress
}

public class KeypadTrigger : MonoBehaviour, IPointerClickHandler
{
    public KeypadController keypadController; // Assign the KeypadController in the Inspector
    public KeypadInputType inputType = KeypadInputType.Generic; // New field to specify input type
    public string playerPrefsKey; // New field for PlayerPrefs key
    private TextMeshProUGUI textMeshPro;

    void Awake()
    {
        textMeshPro = GetComponent<TextMeshProUGUI>();
        if (keypadController == null)
        {
            // Try to find it in the scene if not assigned
            keypadController = FindFirstObjectByType<KeypadController>(FindObjectsInactive.Include); // include inactive
        }
    }

    public void OnPointerClick(PointerEventData eventData)
    {
        if (keypadController != null && textMeshPro != null)
        {
            keypadController.targetDisplayText = textMeshPro;
            keypadController.SetInputType(inputType, playerPrefsKey); // Pass the input type and key to the keypad
            keypadController.gameObject.SetActive(true);
        }
        else
        {
            Debug.LogError("KeypadController or TextMeshProUGUI not found on " + gameObject.name);
        }
    }
}