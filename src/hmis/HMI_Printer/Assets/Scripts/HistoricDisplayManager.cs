using System.Collections.Generic;
using System.IO;
using UnityEngine;

public class HistoricDisplayManager : MonoBehaviour
{
    private static List<HistoricDisplay> _activeDisplays = new List<HistoricDisplay>();

    // --- Static Methods for Instance Management ---

    public static void Register(HistoricDisplay display)
    {
        if (!_activeDisplays.Contains(display))
        {
            _activeDisplays.Add(display);
        }
    }

    public static void Unregister(HistoricDisplay display)
    {
        if (_activeDisplays.Contains(display))
        {
            _activeDisplays.Remove(display);
        }
    }

    // --- Logic for State Reset ---

    public static void NotifyCreateStarted(HistoricDisplay creatingInstance)
    {
        // Reset any other display that is currently in the "Abrir" state
        foreach (var display in _activeDisplays)
        {
            if (display != creatingInstance)
            {
                display.ResetToCreateState();
            }
        }
    }

    // --- Cleanup Logic ---

    private void OnApplicationQuit()
    {
        Debug.Log("[HistoricDisplayManager] Application is quitting. Cleaning up generated HTML files...");
        string directoryPath = Path.Combine(Application.persistentDataPath, "Explanations");
        
        if (Directory.Exists(directoryPath))
        {
            try
            {
                string[] files = Directory.GetFiles(directoryPath, "*.html");
                foreach (string file in files)
                {
                    File.Delete(file);
                    Debug.Log($"[HistoricDisplayManager] Deleted file: {file}");
                }
            }
            catch (System.Exception e)
            {
                Debug.LogError($"[HistoricDisplayManager] Failed to cleanup explanations directory: {e.Message}");
            }
        }
    }
}
