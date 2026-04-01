using UnityEngine;

public class Selectable : MonoBehaviour
{
    void Start()
    {
        // Garante que o ObjectSelector existe na cena
        if (ObjectSelector.Instance != null)
        {
            ObjectSelector.Instance.RegisterObject(gameObject);
        }
        else
        {
            Debug.LogError("Selectable: Instância do ObjectSelector não encontrada. Adicione o script ObjectSelector a um objeto na cena.");
        }
    }
}
