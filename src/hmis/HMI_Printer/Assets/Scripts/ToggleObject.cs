using UnityEngine;

public class ToggleObject : MonoBehaviour
{
    [SerializeField] GameObject go;
    public void ToggleGameObject()
    {
        go.SetActive(!go.activeSelf);
    }
}