// UpdateTextFromPlayerPrefs.cs
using UnityEngine;
using TMPro; // Essencial para trabalhar com componentes TextMeshPro

/// <summary>
/// Este script atualiza um componente TextMeshProUGUI com um valor
/// guardado no PlayerPrefs. É ideal para exibir informações como
/// o nome do jogador, pontuações, ou IPs de configuração.
/// </summary>
public class UpdateTextFromPlayerPrefs : MonoBehaviour
{
    [Header("Referências")]
    [Tooltip("Arraste para aqui o componente de texto (TMP) que pretende atualizar.")]
    public TextMeshProUGUI textToUpdate;

    [Header("Configuração")]
    [Tooltip("A chave (nome) do valor que será procurado no PlayerPrefs. Ex: 'PlayerName', 'MiddlewareIP'")]
    public string playerPrefsKey;

    [Tooltip("O valor a ser exibido se a chave não for encontrada no PlayerPrefs.")]
    public string defaultValue = "N/D"; // N/D = Não disponível

    /// <summary>
    /// O método Start é chamado uma vez quando o script é ativado.
    /// Perfeito para configurar o estado inicial do texto.
    /// </summary>
    void Start()
    {
        UpdateText();
    }
    private void OnEnable()
    {
        UpdateText();
    }

    /// <summary>
    /// Procura o valor no PlayerPrefs e atualiza o componente de texto.
    /// </summary>
    public void UpdateText()
    {
        // --- 1. Validação ---
        // Verifica se o campo de texto foi atribuído no Inspector para evitar erros.
        if (textToUpdate == null)
        {
            Debug.LogError($"[UpdateTextFromPlayerPrefs] O campo 'Text To Update' não foi atribuído no Inspector!", this.gameObject);
            return;
        }

        // Verifica se a chave do PlayerPrefs foi definida.
        if (string.IsNullOrEmpty(playerPrefsKey))
        {
            Debug.LogWarning($"[UpdateTextFromPlayerPrefs] A 'Player Prefs Key' não foi definida. A exibir o valor padrão.", this.gameObject);
            textToUpdate.text = defaultValue;
            return;
        }

        // --- 2. Obter e Exibir o Valor ---
        // PlayerPrefs.GetString() tem uma funcionalidade muito útil: se a chave
        // não for encontrada, ele retorna automaticamente o valor padrão que passamos.
        string savedValue = PlayerPrefs.GetString(playerPrefsKey, defaultValue);

        // Atualiza o texto na UI.
        textToUpdate.text = savedValue;

        Debug.Log($"Texto atualizado com o valor da chave '{playerPrefsKey}': '{savedValue}'", this.gameObject);
    }
}