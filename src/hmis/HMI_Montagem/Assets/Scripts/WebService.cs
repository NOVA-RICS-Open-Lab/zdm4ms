
using UnityEngine;
using UnityEngine.Networking;
using System.Collections;
using System.Text;
using System;

public class WebService : MonoBehaviour
{
    public static WebService Instance { get; private set; }

    private void Awake()
    {
        if (Instance == null)
        {
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }
        else
        {
            Destroy(gameObject);
        }
    }

    public IEnumerator SendPostRequest(string url, string jsonData, Action<string> callback)
    {
        // --- DEBUG LOGS ---
        Debug.Log("Sending POST request to URL: " + url);
        Debug.Log("Request Body (JSON): " + jsonData);
        // ------------------

        using (UnityWebRequest webRequest = new UnityWebRequest(url, "POST"))
        {
            byte[] jsonToSend = new UTF8Encoding().GetBytes(jsonData);
            webRequest.uploadHandler = new UploadHandlerRaw(jsonToSend);
            webRequest.downloadHandler = new DownloadHandlerBuffer();
            webRequest.SetRequestHeader("Content-Type", "application/json");

            yield return webRequest.SendWebRequest();

            if (webRequest.result == UnityWebRequest.Result.ConnectionError ||
                webRequest.result == UnityWebRequest.Result.DataProcessingError ||
                webRequest.result == UnityWebRequest.Result.ProtocolError)
            {
                Debug.LogError("Error sending POST request: " + webRequest.error);
                callback?.Invoke(null);
            }
            else
            {
                Debug.Log("Received response: " + webRequest.downloadHandler.text);
                callback?.Invoke(webRequest.downloadHandler.text);
            }
        }
    }
}
