using UnityEngine;
using System.IO;
using System.Text;

public class DebugHtmlCreator : MonoBehaviour
{
    void Start()
    {
        CreateAndOpenTestHtml();
    }

    public void CreateAndOpenTestHtml()
    {
        string directoryPath = Path.Combine(Application.persistentDataPath, "Explanations");
        if (!Directory.Exists(directoryPath)) Directory.CreateDirectory(directoryPath);

        string filePath = Path.Combine(directoryPath, "debug_test.html");
        
        string debugHtml = @"
<!DOCTYPE html>
<html>
<head>
    <title>Teste de Abertura</title>
    <style>
        body { font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #f0f0f0; }
        .card { background: white; padding: 20px; border-radius: 10px; display: inline-block; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h1 { color: #2ecc71; }
    </style>
</head>
<body>
    <div class='card'>
        <h1> HTML Aberto com Sucesso! </h1>
        <p> Se você está lendo isso, o FileProvider está funcionando corretamente. </p>
        <p> Caminho: " + filePath + @" </p>
        <p> Horário: " + System.DateTime.Now.ToString() + @" </p>
    </div>
</body>
</html>";

        try
        {
            File.WriteAllText(filePath, debugHtml, Encoding.UTF8);
            Debug.Log($"[DebugHtml] Arquivo de teste criado em: {filePath}");

            // Tenta usar o ExplanationRequester para abrir, se ele existir na cena
            ExplanationRequester requester = FindFirstObjectByType<ExplanationRequester>();
            if (requester != null)
            {
                Debug.Log("[DebugHtml] Usando ExplanationRequester para abrir o arquivo.");
                requester.OpenExplanation(filePath);
            }
            else
            {
                Debug.LogWarning("[DebugHtml] ExplanationRequester não encontrado na cena. Usando fallback direto.");
                Application.OpenURL("file://" + filePath);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[DebugHtml] Erro ao criar ou abrir arquivo de teste: {e.Message}");
        }
    }
}
