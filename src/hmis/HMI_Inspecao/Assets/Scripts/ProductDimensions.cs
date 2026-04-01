using UnityEngine;
using TMPro;
using System.Collections.Generic;

[System.Serializable]
public class DimensionField
{
    [Tooltip("O nome da dimensão, ex: Comprimento")]
    public string label;
    [Tooltip("O campo de TextMeshPro que contém o valor desta dimensão.")]
    public TextMeshProUGUI valueText;
}

public class ProductDimensions : MonoBehaviour
{
    [Header("Campos de Dimensão")]
    [Tooltip("A lista de todas as dimensões para este produto.")]
    public List<DimensionField> dimensions;
}
