import os
import requests
from flask import Flask, request, jsonify

AAS_URL = os.getenv("AAS_URL", "192.168.2.90:5011")
MIDDLEWARE_URL = "http://" + os.getenv("MIDDLEWARE_URL", "192.168.2.90")
PORT = int(os.getenv("PORT", "5007"))

app = Flask(__name__)

# Body Template
# {
#     "destination": "192.168.2.90:5007",
#     "msg": {
#         "id": 1,
#         "type": "Quadrado",
#         "measurements": {
#             "largura": 5,
#             "altura": 10,
#             "comprimento": 15
#         }
#     }
# }
@app.route('/inspect', methods=['POST'])
def inspection():
    try:
        data = request.get_json()
        
        id = str(data.get("id"))
        type = data.get("type")
        measurements = data.get("measurements")
        
        if(len(measurements) == 3):        
            payload = {
                "destination": AAS_URL,
                "msg": {
                    "id": id,
                    "type": type,
                    "qualitytest": "OK",
                    "valorlargura": measurements["largura"],
                    "valorcomprimento": measurements["comprimento"],
                    "valoraltura": measurements["altura"]
                }
            }
        else:
            payload = {
                "destination": AAS_URL,
                "msg": {
                    "id": id,
                    "type": type,
                    "qualitytest": "OK",
                    "valorlargura": measurements["largura"],
                    "valorcomprimento": measurements["comprimento"],
                    "valoraltura": measurements["altura"]
                }
            }
        
        # DEBUG print(payload)
        
        response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/addmeasurements", json=payload, timeout=10)
        
        print(response.json())
        
        response.raise_for_status()
        
        if response.status_code != 200:
            return jsonify({"error": f"Error sending request with code: {response.status_code}"}), 200
        
        return jsonify({"message": "Measurements added to AAS with success"}), 200

    except requests.RequestException as e:
        return jsonify({"error": "Failed to connect to the AAS Services."}), 502
    except Exception as e:
        return jsonify({"error": f"Internal error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)