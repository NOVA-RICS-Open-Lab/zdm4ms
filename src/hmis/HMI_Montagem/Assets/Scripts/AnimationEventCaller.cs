using UnityEngine;

public class AnimationEventCaller : MonoBehaviour
{
    public ProductViewManager productViewManager; // Arraste o GameObject com o ProductViewManager para aqui no Inspector

    // Este método será chamado pelo Animation Event
    public void CallShowProductView(int productId)
    {
        if (productViewManager != null)
        {
            productViewManager.ShowProductView(productId);
            Debug.Log($"Animation Event called ShowProductView for Product ID: {productId}");
        }
        else
        {
            Debug.LogWarning("ProductViewManager not assigned in AnimationEventCaller.");
        }
    }

    // Opcional: Se o ProductViewManager estiver sempre na cena e for único, pode encontrá-lo automaticamente
    void Awake()
    {
        if (productViewManager == null)
        {
            productViewManager = FindObjectOfType<ProductViewManager>();
            if (productViewManager == null)
            {
                Debug.LogError("ProductViewManager not found in scene. Please assign it manually or ensure it exists.");
            }
        }
    }
}