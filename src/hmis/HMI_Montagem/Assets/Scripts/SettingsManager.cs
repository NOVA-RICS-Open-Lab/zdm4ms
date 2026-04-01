
using UnityEngine;

public class SettingsManager : MonoBehaviour
{
    public static SettingsManager Instance { get; private set; }

    public string MiddlewareIP 
    { 
        get { return PlayerPrefs.GetString("MiddlewareIP", "127.0.0.1"); } 
    }
    
    public string AssemblyIP 
    { 
        get { return PlayerPrefs.GetString("AssemblyIP", "127.0.0.1"); } 
    }
    
    public int ProductID { get; private set; }

    public string MiddlewareURL
    {
        get { return "http://" + MiddlewareIP; }
    }

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
            // ProductID não é mais carregado do PlayerPrefs
            ProductID = 0;
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public void SetProductID(int id)
    {
        ProductID = id;
        // Removido PlayerPrefs.SetInt para ProductID
    }

    public void ClearProductID()
    {
        ProductID = 0;
        // Removido PlayerPrefs.SetInt para ProductID
    }

    // Mantemos este método para compatibilidade, mas agora o Keypad guarda diretamente no PlayerPrefs
    public void SaveSettings(string middlewareIP, string assemblyIP, int productID)
    {
        PlayerPrefs.SetString("MiddlewareIP", middlewareIP.Replace("http://", "").Replace("https://", ""));
        PlayerPrefs.SetString("AssemblyIP", assemblyIP);
        // Removido PlayerPrefs.SetInt para ProductID aqui também
        PlayerPrefs.Save();
        ProductID = productID; // Atualiza apenas em memória
        Debug.Log("Settings saved manually via SettingsManager (ProductID in memory only)!");
    }
}
