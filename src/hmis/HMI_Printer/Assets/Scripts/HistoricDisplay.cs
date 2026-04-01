// HistoricDisplay.cs
using UnityEngine;
using UnityEngine.UI;
using System.Collections;
using TMPro;

[RequireComponent(typeof(ExplanationRequester))]
public class HistoricDisplay : MonoBehaviour
{
    [Header("Referências de Texto")]
    public TextMeshProUGUI idText;
    public TextMeshProUGUI startTimeText;
    public TextMeshProUGUI typeText;
    public TextMeshProUGUI predictTypeText;
    public TextMeshProUGUI resultText;

    [Header("Referências de Interação")]
    public Button getExplanationButton;

    private PostData _currentData;
    private ExplanationRequester.ProductDataSummary _currentSummary;
    private ExplanationRequester _explanationRequester;
    private string _explanationFilePath; 

    private void Awake()
    {
        _explanationRequester = GetComponent<ExplanationRequester>();
        if (_explanationRequester == null) _explanationRequester = gameObject.AddComponent<ExplanationRequester>();
        HistoricDisplayManager.Register(this);
    }

    private void OnDestroy()
    {
        HistoricDisplayManager.Unregister(this);
    }

    public void SetData(PostData data)
    {
        if (data == null) return;
        _currentData = data;

        // Feedback visual imediato: A carregar
        idText.text = data.id;
        startTimeText.text = "A carregar...";
        typeText.text = "A carregar...";
        predictTypeText.text = "Z1/Z4";
        resultText.text = "A carregar...";

        if (getExplanationButton != null)
        {
            getExplanationButton.interactable = false;
            var txt = getExplanationButton.GetComponentInChildren<TextMeshProUGUI>();
            if (txt != null) txt.text = "Aguarde";
        }
    }

    public IEnumerator FetchDetailedDataExternal(System.Action<int> onLinesCounted = null)
    {
        if (_explanationRequester == null)
        {
            _explanationRequester = GetComponent<ExplanationRequester>();
            if (_explanationRequester == null) _explanationRequester = gameObject.AddComponent<ExplanationRequester>();
        }

        if (_currentData == null)
        {
            Debug.LogError("[HistoricDisplay] _currentData é nulo em FetchDetailedDataExternal!");
            onLinesCounted?.Invoke(0);
            yield break;
        }

        yield return _explanationRequester.GetProductDataCoroutine(_currentData.id, (summaries) => {
            if (summaries != null && summaries.Count > 0)
            {
                // Filtrar apenas os explicáveis para exibir no histórico
                var explainableSummaries = summaries.FindAll(s => s.isExplainable);
                int totalLines = explainableSummaries.Count;
                int actuallyCreated = 0;

                if (totalLines > 0)
                {
                    // O primeiro resumo atualiza este objeto
                    // Se ele estava "A carregar...", consideramos como uma nova notificação
                    bool firstWasNew = (startTimeText.text == "A carregar...");
                    UpdateUIWithSummary(explainableSummaries[0]);
                    if (firstWasNew) actuallyCreated++;

                    // Se houver mais, criamos novos objetos (réplicas)
                    for (int i = 1; i < totalLines; i++)
                    {
                        // Evitar duplicados no mesmo parent
                        bool alreadyExists = false;
                        foreach (Transform child in this.transform.parent)
                        {
                            HistoricDisplay childDisplay = child.GetComponent<HistoricDisplay>();
                            if (childDisplay != null && childDisplay.idText.text == explainableSummaries[i].id && childDisplay.predictTypeText.text == explainableSummaries[i].predictType)
                            {
                                alreadyExists = true;
                                break;
                            }
                        }

                        if (!alreadyExists)
                        {
                            GameObject newDisplay = Instantiate(this.gameObject, this.transform.parent);
                            HistoricDisplay script = newDisplay.GetComponent<HistoricDisplay>();
                            if (script != null)
                            {
                                script._currentData = this._currentData;
                                script.UpdateUIWithSummary(explainableSummaries[i]);
                                actuallyCreated++;
                            }
                        }
                    }
                    onLinesCounted?.Invoke(actuallyCreated);
                }
                else
                {
                    Debug.Log($"[HistoricDisplay] Produto {_currentData.id} não tem nenhum Quality_Test explicável. A remover.");
                    onLinesCounted?.Invoke(0);
                    Destroy(this.gameObject);
                }
            }
            else
            {
                Debug.Log($"[HistoricDisplay] Produto {_currentData.id} sem dados. A remover.");
                onLinesCounted?.Invoke(0);
                Destroy(this.gameObject);
            }
        });
    }

    public void UpdateUIWithSummary(ExplanationRequester.ProductDataSummary summary)
    {
        if (summary == null) return;
        _currentSummary = summary;

        idText.text = summary.id;
        startTimeText.text = summary.timestamp;
        typeText.text = summary.productType;
        predictTypeText.text = summary.predictType;
        resultText.text = summary.result;

        if (getExplanationButton != null)
        {
            getExplanationButton.interactable = true;
            var txt = getExplanationButton.GetComponentInChildren<TextMeshProUGUI>();
            if (txt != null) txt.text = "Criar";
            getExplanationButton.onClick.RemoveAllListeners();
            getExplanationButton.onClick.AddListener(OnCreateOrOpenClicked);
        }
    }

    private void OnCreateOrOpenClicked()
    {
        Debug.Log($"[HistoricDisplay] Clique detectado no botão de explicação. Estado atual: {getExplanationButton.GetComponentInChildren<TextMeshProUGUI>().text}");
        var buttonText = getExplanationButton.GetComponentInChildren<TextMeshProUGUI>();
        if (buttonText == null) return;

        if (buttonText.text == "Criar")
        {
            HistoricDisplayManager.NotifyCreateStarted(this);
            buttonText.text = "Aguarde...";
            getExplanationButton.interactable = false;
            _explanationRequester.RequestExplanation(_currentSummary, OnExplanationReady);
        }
        else // "Abrir"
        {
            if (!string.IsNullOrEmpty(_explanationFilePath))
            {
                _explanationRequester.OpenExplanation(_explanationFilePath);
            }
            else
            {
                ResetToCreateState();
            }
        }
        }
    private void OnExplanationReady(string filePath)
    {
        _explanationFilePath = filePath;
        getExplanationButton.interactable = true;
        var buttonText = getExplanationButton.GetComponentInChildren<TextMeshProUGUI>();
        if (buttonText != null) buttonText.text = "Abrir";
    }

    public void ResetToCreateState()
    {
        if (getExplanationButton == null) return;
        var buttonText = getExplanationButton.GetComponentInChildren<TextMeshProUGUI>();
        if (buttonText != null && buttonText.text == "Abrir")
        {
            buttonText.text = "Criar";
            getExplanationButton.interactable = true;
        }
    }
}
