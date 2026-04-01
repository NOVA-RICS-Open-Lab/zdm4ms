using UnityEngine;
using UnityEngine.UI;
using TMPro;

public class StatusFeedbackManager : MonoBehaviour
{
    public static StatusFeedbackManager Instance;

    [Header("UI Components")]
    public GameObject feedbackPanel; // O painel único para todo o feedback
    public Image statusImage;
    public TextMeshProUGUI statusText;
    public Button closeButton;

    [Header("Status Assets")]
    public Sprite waitingSprite;
    public Sprite successSprite;
    public Sprite errorSprite;

    private CinemachineSelector lastProductSelector;

    void Awake()
    {
        if (Instance == null) Instance = this; else Destroy(gameObject);
    }

    void Start()
    {
        feedbackPanel.SetActive(false); // Garante que começa escondido
        closeButton.onClick.AddListener(CloseFeedbackAndReset);
    }

    public void ShowWaiting(CinemachineSelector productSelector)
    {
        lastProductSelector = productSelector;

        statusImage.sprite = waitingSprite;
        statusText.text = "A enviar dados...";

        closeButton.gameObject.SetActive(false); // Esconde o botão durante a espera
        feedbackPanel.SetActive(true);
    }

    public void ShowSuccess()
    {
        statusImage.sprite = successSprite;
        statusText.text = "Dados enviados com sucesso!";

        closeButton.gameObject.SetActive(true); // Mostra o botão para fechar
        feedbackPanel.SetActive(true);
    }

    public void ShowError(string message)
    {
        statusImage.sprite = errorSprite;
        statusText.text = $"Erro no envio:\n{message}";

        closeButton.gameObject.SetActive(true); // Mostra o botão para fechar
        feedbackPanel.SetActive(true);
    }

    private void CloseFeedbackAndReset()
    {
        feedbackPanel.SetActive(false);
        if (lastProductSelector != null)
        {
            lastProductSelector.ResetToInitialView();
        }
    }
}
