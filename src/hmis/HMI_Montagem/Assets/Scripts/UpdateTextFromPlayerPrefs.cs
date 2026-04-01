using UnityEngine;
using TMPro;

/// <summary>
/// Este script atualiza um componente TextMeshProUGUI com um valor
/// guardado no PlayerPrefs. É ideal para exibir informações como
/// IPs de configuração ou IDs.
/// </summary>
public class UpdateTextFromPlayerPrefs : MonoBehaviour
{
    [Header("Referências")]
    [Tooltip("Arraste para aqui o componente de texto (TMP) que pretende atualizar.")]
    public TextMeshProUGUI textToUpdate;

    [Header("Configuração")]
    [Tooltip("A chave (nome) do valor que será procurado no PlayerPrefs. Ex: 'MiddlewareIP', 'DestinationIP'")]
    public string playerPrefsKey;

    [Tooltip("O valor a ser exibido se a chave não for encontrada no PlayerPrefs.")]
    public string defaultValue = "N/D";

    void Awake()
    {
        if (textToUpdate == null) textToUpdate = GetComponent<TextMeshProUGUI>();
    }

    void Start()
    {
        UpdateText();
    }

    private void OnEnable()
    {
        UpdateText();
    }

    public void UpdateText()
    {
        if (textToUpdate == null)
        {
            Debug.LogError($"[UpdateTextFromPlayerPrefs] O campo 'Text To Update' não foi atribuído!", this.gameObject);
            return;
        }

        if (string.IsNullOrEmpty(playerPrefsKey))
        {
            textToUpdate.text = defaultValue;
            return;
        }

        string savedValue = PlayerPrefs.GetString(playerPrefsKey, defaultValue);
        textToUpdate.text = savedValue;
    }
}