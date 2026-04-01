using UnityEngine;

public class SettingsManager : MonoBehaviour
{
    public static SettingsManager Instance { get; private set; }

    public string MiddlewareIP 
    { 
        get { return PlayerPrefs.GetString("MiddlewareIP", "127.0.0.1"); } 
    }
    
    public string InspectionIP 
    { 
        get { return PlayerPrefs.GetString("InspectionIP", "127.0.0.1"); } 
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
            ProductID = PlayerPrefs.GetInt("ProductID", 0);
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public void SetProductID(int id)
    {
        ProductID = id;
        PlayerPrefs.SetInt("ProductID", id);
        PlayerPrefs.Save();
    }

    public void SaveSettings(string middlewareIP, string inspectionIP, int productID)
    {
        PlayerPrefs.SetString("MiddlewareIP", middlewareIP.Replace("http://", "").Replace("https://", ""));
        PlayerPrefs.SetString("InspectionIP", inspectionIP);
        PlayerPrefs.SetInt("ProductID", productID);
        PlayerPrefs.Save();
        Debug.Log("Settings saved manually via SettingsManager!");
    }
}
