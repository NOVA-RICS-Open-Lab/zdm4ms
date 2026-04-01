
using UnityEngine;
using System.Collections.Generic;
using System.Linq;

public class ObjectSelector : MonoBehaviour
{
    public static ObjectSelector Instance;

    private List<GameObject> selectableObjects = new List<GameObject>();
    private Vector3 initialPosition;
    private Quaternion initialRotation;
    private Vector3 initialScale;

    void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public void RegisterObject(GameObject obj)
    {
        if (!selectableObjects.Contains(obj))
        {
            selectableObjects.Add(obj);
        }
    }

    public void SelectObject(GameObject selectedObject)
    {
        // Guarda a transformação inicial do objeto selecionado se for a primeira seleção
        if (selectableObjects.Any(obj => obj.activeSelf) && selectedObject.activeSelf)
        {
             // Se já há um objeto ativo, não faz nada para evitar guardar a posição de um objeto já movido
        } else {
            initialPosition = selectedObject.transform.position;
            initialRotation = selectedObject.transform.rotation;
            initialScale = selectedObject.transform.localScale;
        }


        foreach (GameObject obj in selectableObjects)
        {
            // Desativa todos os outros objetos
            if (obj != selectedObject)
            {
                obj.SetActive(false);
            }
        }
        // Garante que o objeto selecionado está ativo
        selectedObject.SetActive(true);
    }

    public void ResetSelection()
    {
        // Reativa todos os objetos
        foreach (GameObject obj in selectableObjects)
        {
            obj.SetActive(true);
            // Opcional: Resetar a posição do objeto que foi movido
            // Se precisar que o objeto volte à sua posição original, adicione essa lógica aqui.
        }
    }
}
