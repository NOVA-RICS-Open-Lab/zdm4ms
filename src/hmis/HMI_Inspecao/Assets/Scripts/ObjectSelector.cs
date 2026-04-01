using UnityEngine;
using System.Collections.Generic;

public class ObjectSelector : MonoBehaviour
{
    public static ObjectSelector Instance;

    private List<GameObject> selectableObjects = new List<GameObject>();
    private GameObject currentlySelectedObject = null;

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
        // Se um objeto já estiver selecionado, não faz nada.
        if (currentlySelectedObject != null)
        {
            return;
        }

        currentlySelectedObject = selectedObject;

        foreach (GameObject obj in selectableObjects)
        {
            if (obj != selectedObject)
            {
                obj.SetActive(false);
            }
        }
        selectedObject.SetActive(true);

        CinemachineSelector cinemachineSelector = selectedObject.GetComponent<CinemachineSelector>();
        if (cinemachineSelector != null)
        {
            cinemachineSelector.SelectThisObject();
        }
    }

    public void ResetSelection()
    {
        currentlySelectedObject = null;

        foreach (GameObject obj in selectableObjects)
        {
            obj.SetActive(true);
        }
    }

    public void ClearSelectionState()
    {
        currentlySelectedObject = null;
    }
}
