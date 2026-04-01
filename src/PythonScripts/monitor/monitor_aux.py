from flask import Flask, request, jsonify
import requests
import time
import threading
import re
from datetime import datetime, timezone, timedelta
import os

API_KEY = os.getenv("PRINTER_API_KEY", "QL3SCr7AwEO8tBTnvPsWEORjOCctfQEWAqwes_m0fko")
MIDDLEWARE_URL = "http://" + os.getenv("MIDDLEWARE_URL", "192.168.2.90")
CSV_URL = os.getenv("CSV_URL", "192.168.2.90:5004")
AAS_URL = os.getenv("AAS_URL", "192.168.2.90:5011")
MODELS_URL = os.getenv("MODELS_URL", "192.168.2.90:5002")
EXPLAINERS_URL = os.getenv("EXPLAINERS_URL", "192.168.2.90:5005")
MONITOR_PORT = int(os.getenv("PORT", 5000))

print(f"URL Middleware: {MIDDLEWARE_URL}")
print(f"PRINTER_API_KEY: {API_KEY}")
print(f"CSV_URL: {CSV_URL}")
print(f"AAS_URL: {AAS_URL}")
print(f"MODELS_URL: {MODELS_URL}")
print(f"EXPLAINERS_URL: {EXPLAINERS_URL}")
print(f"MONITOR_PORT: {MONITOR_PORT}")

# Configuration constants
CHECK_INTERVAL = 5  # Interval for checking printer status (seconds)
CHECK_STATE_INTERVAL = 60  # Interval for periodic state logging (seconds)
UPDATE_INTERVAL_M114 = 0.5  # Interval for sending M114 commands (seconds)
UPDATE_INTERVAL_M220 = 0.5  # Interval for sending M220 commands (seconds)
TIMEOUT_LIMIT = 5  # Timeout for M114/M220 responses (seconds)
CHECK_WAIT_IMPRESSION_INTERVAL = 60  # Interval for logging waiting state (seconds)
FILENAME_WARNING_INTERVAL = 300  # Interval for periodic filename warnings (seconds)
CHECK_PRINTER_STATE_INTERVAL = 60  # Interval for logging printer state in wait loop (seconds)

ALLOWED_FILENAMES = {"zdm4ms~4.gco", "zd5b20~1.gco", "zd2c72~1.gco"}

def log(tipo, origem, msg):
    timestamp =  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{tipo.upper()}] [{origem}] {msg}")
    
class Control:
    def __init__(self):
        self.filename = None
        self.product_id = None
        self.product_type = None
        self.speed_factor = None
        self.start_time = None
        self.prediction_z1_done = False
        self.prediction_z4_done = False
        self.printer_ip = None
        self.hmi_ip = None
    
    def __reset__(self):
        self.filename = None
        self.product_id = None
        self.product_type = None
        self.speed_factor = None
        self.start_time = None
        self.prediction_z1_done = False
        self.prediction_z4_done = False
        self.printer_ip = None
        self.hmi_ip = None

def SendCommand(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
        "key": API_KEY
    }
    log("INFO", "SEND_CMD", f"Enviando comando '{msg}' para {destination}")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/command", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "SEND_CMD", f"Comando '{msg}' enviado com sucesso para {destination}")
    return response

def GetStatus(destination):
    payload = {
        "destination": destination,
        "key": API_KEY
    }
    try:
        response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/status", json=payload, timeout=10)
        response.raise_for_status()
        job_data = response.json()
        state = job_data.get("state", "").lower()
        return state
    except requests.exceptions.ReadTimeout:
        log("ERRO", "STATUS", f"Timeout ao verificar status de {destination}")
        return None
    except Exception as e:
        log("ERRO", "STATUS", f"Erro inesperado: {e}")
        return None

def PrinterSub(destination):
    payload = {
        "destination": destination,
        "username": "rics",
        "key": API_KEY
    }
    response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/sub", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "SUB", f"Subscrito com sucesso ao middleware")
    return response

def CSVGet(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
    }
    log("INFO", "CSV", f"Pedido de CSV enviado: {msg}")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/csv/get", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "CSV", f"CSV recebido com sucesso de {destination}")
    return response

def CSVSend(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
    }
    response = requests.post(f"{MIDDLEWARE_URL}:1880/csv/append", json=payload, timeout=10)
    # log("INFO", "CSV", f"Dados enviados para CSV")
    response.raise_for_status()
    return response

def PredictZ1(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    # Para debug escreve o payload num ficheiro z4.txt para teste posterior
    # try:
    #     with open('z4.txt', 'w', encoding='utf-8') as file:
    #         json.dump(payload, file, indent=4, ensure_ascii=False)
        
    #     print(f"Dados escritos com sucesso em z4.txt")

    # except IOError as e:
    #     print(f"Erro ao escrever no ficheiro: {e}")
    # except Exception as e:
    #     print(f"Ocorreu um erro inesperado: {e}")
    
    log("INFO", "MODEL", "Enviando dados para inferência do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/predict1", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def PredictZ4(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    # Para debug escreve o payload num ficheiro z4.txt para teste posterior
    # try:
    #     with open('z4.txt', 'w', encoding='utf-8') as file:
    #         json.dump(payload, file, indent=4, ensure_ascii=False)
        
    #     print(f"Dados escritos com sucesso em z4.txt")

    # except IOError as e:
    #     print(f"Erro ao escrever no ficheiro: {e}")
    # except Exception as e:
    #     print(f"Ocorreu um erro inesperado: {e}")

    log("INFO", "MODEL", "Enviando dados para inferência do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/predict4", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def ExplainZ1(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }

    # Para debug escreve o payload num ficheiro z4.txt para teste posterior
    # try:
    #     with open('z1.txt', 'w', encoding='utf-8') as file:
    #         json.dump(payload, file, indent=4, ensure_ascii=False)
        
    #     print(f"Dados escritos com sucesso em z1.txt")

    # except IOError as e:
    #     print(f"Erro ao escrever no ficheiro: {e}")
    # except Exception as e:
    #     print(f"Ocorreu um erro inesperado: {e}")
    
    log("INFO", "EXPLAIN", "Enviando dados para explicacao do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/explain1", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "EXPLAIN", f"Dados enviados com sucesso para {destination}")
    return response

def ExplainZ4(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }

    # Para debug escreve o payload num ficheiro z4.txt para teste posterior
    # try:
    #     with open('z4.txt', 'w', encoding='utf-8') as file:
    #         json.dump(payload, file, indent=4, ensure_ascii=False)
        
    #     print(f"Dados escritos com sucesso em z4.txt")

    # except IOError as e:
    #     print(f"Erro ao escrever no ficheiro: {e}")
    # except Exception as e:
    #     print(f"Ocorreu um erro inesperado: {e}")
    
    log("INFO", "EXPLANATION", "Enviando dados para explanation do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/explain4", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "EXPLANATION", f"Dados enviados com sucesso para {destination}")
    return response

def AASCreateProduct(destination, control):

    payload = {
        "destination": destination,    
        "msg": {
            "id": control.product_id,
            "type": control.product_type,
            "speed": control.speed_factor,
            "gcode": control.filename
        }
    }
    
    log("INFO", "CREATE_PRODUCT", f"Criando produto do tipo {control.product_type} com o id '{control.product_id}'")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/createproduct", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code in (200, 201):
        log("INFO", "CREATE_PRODUCT", f"Produto do tipo {control.product_type} com o id '{control.product_id}' criado com sucesso")
    else:
        log("ERRO", "CREATE_PRODUCT", f"Falha ao criar produto: {response.text}")
        with app.app_context():
            return jsonify({"error": "Failed to create product"}), 500
    return response

def AASUpdateProductState(destination, control, state):
    payload = {
        "destination": destination,
        "msg": {
            "id": control.product_id,
            "state": state
        }
    }
    
    log("INFO", "UPDATE_PRODUCT_STATE", f"Atualizando estado do produto com o id '{control.product_id}' para '{state}'")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/setproductstate", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code in (200, 201):
        log("INFO", "UPDATE_PRODUCT_STATE", f"Estado do produto com o id '{control.product_id}' atualizado com sucesso para '{state}'")
    else:
        log("ERRO", "UPDATE_PRODUCT_STATE", f"Falha ao atualizar estado do produto: {response.text}")
        with app.app_context():
            return jsonify({"error": "Failed to update product state"}), 500
    return response

def AASAddPredictZ1(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    log("INFO", "MODEL", "A adicionar dados de z1 nas AASs")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/addz1", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def AASAddPredictZ4(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    log("INFO", "MODEL", "A adicionar dados de z4 nas AASs")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/addz4", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def AASAddExplanations(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    log("INFO", "MODEL", "A adicionar dados de explanations nas AASs")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/addexplanation", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def AASUpdateOperationValues(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    
    # log("INFO", "OPERATIONVALUES", "A atualizar os operationvalues nas AASs")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/append", json=payload, timeout=10)
    response.raise_for_status()
    return response

def UpdateNoticeHMI(control):
    payload = {
        "destination": control.hmi_ip,
        "msg": {
                "id": control.product_id
            }
    }
    
    response = requests.post(f"{MIDDLEWARE_URL}:1880/hmi/updatenotice", json=payload, timeout=10)
    response.raise_for_status()
    log("INFO", "HMIUPDATENOTICE", f"Noticed update to HMI")
    if response.status_code not in (200, 201):
        log("ERRO", "HMIUPDATENOTICE", f"Failed to notice update to the HMI: {response.text}")
        with app.app_context():
            return jsonify({"error": "Failed to create product"}), 500
    return response

def SetupAndStartPrintingProcess(id, filename, speed_factor, ip_printer, ip_hmi):
    
    control = Control()
    
    if filename.lower() not in ALLOWED_FILENAMES:
        log("ERRO", "REQUEST", f"Nome de ficheiro {filename} não está na lista permitida")
        return jsonify({"error": "Invalid filename"}), 400
    
    response = SendCommand(ip_printer, "M27 S0")
    if response.status_code not in (200, 201, 202, 203, 204):
        return response
    
    response = SendCommand(ip_printer, f"M23 {filename}")
    if response.status_code not in (200, 201, 202, 203, 204):
        return response
    
    response = SendCommand(ip_printer, "M24")
    if response.status_code not in (200, 201, 202, 203, 204):
        return response
    
    response = SendCommand(ip_printer, f"M220 S{speed_factor}")
    if response.status_code not in (200, 201, 202, 203, 204):
        return response
    
    productType = {
        'zdm4ms~4.gco': 'QUADRADO',
        'zd5b20~1.gco': 'L',
        'zd2c72~1.gco': 'RETANGULO',
        'zdm4ms~1.gco': 'QUADRADO'
    }.get(filename.lower())

    if not productType:
        log("ERRO", "CREATE_PRODUCT", f"Tipo de peça inválido para o arquivo {filename}")
        with app.app_context():
            return jsonify({"error": "Invalid piece type"}), 400
        
    
    control.filename = filename
    control.product_id = id
    control.product_type = productType
    control.speed_factor = speed_factor
    control.printer_ip = ip_printer
    control.hmi_ip = ip_hmi
    
    response = AASCreateProduct(AAS_URL, control)
    if response.status_code not in (200, 201, 202, 203, 204):
        return response
    
    threading.Thread(
        target=WaitForPrintingAndStartMonitoring,
        args=(control,),
        daemon=True
    ).start()
    
    return jsonify({"status": "Começo do processo de monitorização da impressão do produto"}), 200

def WaitForPrintingAndStartMonitoring(control):
    try:
        laststate = ""
        
        while True:
            state = GetStatus(control.printer_ip)
            
            if state is None:
                log("WARN", "PRINTER", "Estado da impressora retornou None, continuando verificação")
                time.sleep(2)
                continue
            
            if state == "printing from sd" and laststate != "printing from sd":
                log("INFO", "PRINTER", "Impressora acabou de aquecer, a iniciar impressão e monitorização.")
                control.start_time = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                requests.post("http://192.168.200.100:5003/start", timeout=10)
                #PrinterSub(control.printer_ip)
                
            elif state == "printing from sd" and laststate == "printing from sd":
                # log("INFO", "PRINTER", "A monitorizar a imressão")
                ProductPrintingLoop(control)
            
            elif state == "operational" and laststate != "printing from sd":
                log("INFO", "PRINTER", "Impressora ainda está a aquecer...")
            
            elif state == "operational" and laststate == "printing from sd":
                log("INFO", "PRINTER", "Impressora acabou de imprimir")
                AASUpdateProductState(AAS_URL, control, "Printed")
                requests.post("http://192.168.200.100:5003/stop", timeout=10)
                break
            
            elif state == "starting print from sd":
                log("INFO", "PRINTER", "Impressora esta mesmo quase a imprimir")
            
            else:
                log("INFO", "PRINTER", f"Estado inesperado: {state}")
            
            laststate = state
            time.sleep(2)
    except Exception as e:
        log("ERRO", "PRINTER", f"Falha na thread de monitorização: {e}")

def is_timestamp_after_stdlib(timestamp_str: str, start_time_str: str) -> bool:
    try:
        # 1. Lidar com o timestamp (com 'Z')
        # Removemos o 'Z' do final da string para usar strptime
        if timestamp_str.endswith('Z'):
            ts_to_parse = timestamp_str[:-1]
        else:
            raise ValueError("Timestamp string não termina com 'Z'.")
        
        # O formato '%f' lida com os microsegundos (que incluem milissegundos)
        naive_timestamp = datetime.strptime(ts_to_parse, "%Y-%m-%dT%H:%M:%S.%f")
        # Associamos o fuso UTC, pois a string original tinha 'Z'
        aware_timestamp = naive_timestamp.replace(tzinfo=timezone.utc)

        # 2. Lidar com o start_time (implícito GMT+1)
        tz_gmt1 = timezone(timedelta(hours=1))
        naive_start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        aware_start_time = naive_start_time.replace(tzinfo=tz_gmt1)

        # 3. Comparar
        return aware_timestamp > aware_start_time

    except ValueError as e:
        print(f"Erro ao converter uma das datas: {e}")
        return False

def ProductPrintingLoop(control):
    
    filename = control.filename
    speed = control.speed_factor
    startTime = control.start_time
    
    
    try:
        # payload = {
        #     "destination": control.printer_ip,
        #     "filename": filename,
        # }
        # response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/info", json=payload, timeout=10)
        response = requests.get("http://192.168.200.100:5003/get_buffer", timeout=10)
        
        response.raise_for_status()
        
        message_data = response.json()
    
    except Exception as e:
        log("ERRO", "MIDDLEWARE", f"Erro ao contactar middleware: {e}")
        return

    # log("INFO", "PREDICTION", f"Aqui recebi {len(message_data)} mensagens do middleware para processar")
    
    for item in message_data:
        
        timestamp = item.get("ts")
    
        if is_timestamp_after_stdlib(timestamp, control.start_time):

            temps = item.get("msg", {}).get("current", {}).get("temps", [])
            positionsmsg = item.get("msg", {}).get("event", {})
            
            if positionsmsg.get("type") == "PositionUpdate":                
                
                positions = positionsmsg.get("payload", {})
                
                posData = {
                    "x": float(positions.get("x")),
                    "y": float(positions.get("y")),
                    "z": float(positions.get("z")),
                    "e": float(positions.get("e")),
                }
                
                data = {
                    "timestamp": timestamp,
                    "temp_nozzle": None,
                    "temp_target_nozzle": None,
                    "temp_delta_nozzle": None,
                    "pwm_nozzle": None,
                    "temp_bed": None,
                    "temp_target_bed": None,
                    "temp_delta_bed": None,
                    "pwm_bed": None,
                    "X": posData["x"],
                    "Y": posData["y"],
                    "Z": posData["z"],
                    "E": posData["e"],
                    "speed_factor": speed,
                    "filename": filename
                }
                
                datatoAAS = data.copy()
                datatoAAS["id"] = control.product_id
                
                AASUpdateOperationValues(AAS_URL, datatoAAS)
                CSVSend(CSV_URL, data)
                
                if posData["z"] == 1 and control.prediction_z1_done is False:
                    log("INFO", "PREDICTION", f"Iniciando previsão do modelo com: {startTime}")
                    
                    csvResponse = CSVGet(CSV_URL, {"start_time": startTime})
                    
                    if csvResponse is not None:
                        try:
                            csvData = csvResponse.json()
                            modelResponse = PredictZ1(MODELS_URL, csvData)                            
                            
                            if modelResponse is not None:

                                prediction = modelResponse.json().get("prediction")
                                
                                log("INFO", "MODEL", f"Previsão do modelo recebida: {prediction}")
                                
                                if prediction is None:
                                    log("ERRO", "MODEL", "Previsão do modelo não encontrada na resposta")
                                    continue
                                else:
                                    # update_aas_product_state(AAS_URL, "Predicted NOK, production Stopped", control.product_id)
                                    
                                    aasData ={
                                        "id": control.product_id,
                                        "inference": prediction,
                                        "qualitytest": prediction,
                                        "metrics": "muita metrica" # TODO substituir por métricas reais csvData
                                    }
                                    
                                    AASAddPredictZ1(AAS_URL,aasData)
                            
                            explanationResponse = ExplainZ1(EXPLAINERS_URL, csvData)
                                
                            if explanationResponse is not None:

                                explanation = explanationResponse.json()
                                
                                log("INFO", "EXPLANATION", f"Explicacao do modelo recebida")
                                # log("INFO", "EXPLANATION", f"Explicacao do modelo recebida: {explanation}")
                                if explanation is None:
                                    log("ERRO", "EXPLANATION", "Explicacao do modelo não encontrada na resposta")
                                    continue
                                else:
                                    aasData ={
                                        "id": control.product_id,
                                        "inferencetype": "z1",
                                        "producttype": control.product_type,
                                        "result": explanation
                                    }
                                    
                                    AASAddExplanations(AAS_URL,aasData)
                                    UpdateNoticeHMI(control=control)
                            
                            control.prediction_z1_done =True
                                
                        except Exception as e:
                            log("ERRO", "MODEL", f"Falha ao processar previsão do modelo: {e}")
                    else:
                        log("WARN", "CSV", "Nenhuma resposta do CSV obtida.")
                        
                elif posData["z"] == 4 and control.prediction_z4_done is False:
                    log("INFO", "PREDICTION", "Iniciando previsão do modelo de regressão")
                    
                    csvResponse = CSVGet(CSV_URL, {"start_time": startTime, "filename": filename})
                    
                    if csvResponse is not None:
                        try:
                            csvData = csvResponse.json()
                            modelResponse = PredictZ4(MODELS_URL, csvData)
                            
                            if modelResponse is not None:
                                predictions = modelResponse.json().get("prediction")
                                
                                log("INFO", "MODEL", f"Previsão do modelo recebida: {predictions}")
                                if predictions is None:
                                    log("ERRO", "MODEL", "Previsão do modelo não encontrada na resposta")
                                    continue
                                else:
                                    aasData ={
                                        "id": control.product_id,
                                        "type": control.product_type,
                                        "inference": predictions,
                                        "qualitytest": "Ok",
                                        "metrics": "muita metrica" # TODO substituir por métricas reais csvData
                                    }
                                    
                                    AASAddPredictZ4(AAS_URL,aasData)
                            
                            explanationResponse = ExplainZ4(EXPLAINERS_URL, {"data": csvData, "productType": control.product_type})
                                
                            if explanationResponse is not None:

                                explanation = explanationResponse.json()
                                
                                log("INFO", "EXPLANATION", f"Explicacao do modelo recebida")
                                # log("INFO", "EXPLANATION", f"Explicacao do modelo recebida: {explanation}")
                                if explanation is None:
                                    log("ERRO", "EXPLANATION", "Explicacao do modelo não encontrada na resposta")
                                    continue
                                else:
                                    aasData ={
                                        "id": control.product_id,
                                        "inferencetype": "z4",
                                        "producttype": control.product_type,
                                        "result": explanation
                                    }
                                    
                                    AASAddExplanations(AAS_URL,aasData)
                                    UpdateNoticeHMI(control=control)
                                
                            control.prediction_z4_done = True
                            
                        except Exception as e:
                            log("ERRO", "MODEL", f"Falha ao processar previsão do modelo: {e}")
                    else:
                        log("WARN", "CSV", "Nenhuma resposta do CSV obtida.")
                
            elif temps:
                
                messages = item.get("msg", {}).get("current", {}).get("messages", "ERRO")
                
                if messages != "ERRO":
                
                    if len(messages) == 0:
                        continue
                
                    for logLine in messages:
                        temp_match = re.search(r"T:([\d.]+)\s*/([\d.]+)\s*B:([\d.]+)\s*/([\d.]+)\s*@:(\d+)\s*B@:(\d+)", logLine.strip())
                        if temp_match:
                            break
                    
                    if not temp_match:
                        continue
                    
                    last_temp = {
                        "nozzle_temp": float(temp_match.group(1)),
                        "nozzle_target": float(temp_match.group(2)),
                        "bed_temp": float(temp_match.group(3)),
                        "bed_target": float(temp_match.group(4)),
                        "nozzle_pwm": int(temp_match.group(5)),
                        "bed_pwm": int(temp_match.group(6)),
                    }
                    
                    data = {
                        "timestamp": timestamp,
                        "temp_nozzle": last_temp["nozzle_temp"],
                        "temp_target_nozzle": last_temp["nozzle_target"],
                        "temp_delta_nozzle": last_temp["nozzle_temp"] - last_temp["nozzle_target"],
                        "pwm_nozzle": last_temp["nozzle_pwm"],
                        "temp_bed": last_temp["bed_temp"],
                        "temp_target_bed": last_temp["bed_target"],
                        "temp_delta_bed": last_temp["bed_temp"] - last_temp["bed_target"],
                        "pwm_bed": last_temp["bed_pwm"],
                        "X": None,
                        "Y": None,
                        "Z": None,
                        "E": None,
                        "speed_factor": speed,
                        "filename": filename
                    }
                    
                    datatoAAS = data.copy()
                    datatoAAS["id"] = control.product_id
                    
                    AASUpdateOperationValues(AAS_URL, datatoAAS)
                    CSVSend(CSV_URL, data)  

app = Flask(__name__)

@app.route('/start', methods=['POST'])
def start():
    try:
        data = request.get_json()
        id = data["id"]
        filename = data["filename"]
        speed_factor = data["speed_factor"]
        ip_printer = data["ip_printer"]
        ip_hmi = data["ip_hmi"]
        
        log("INFO", "REQUEST", f"filename: {filename}")
        log("INFO", "REQUEST", f"speed_factor: {speed_factor}")
        log("INFO", "REQUEST", f"ip_printer: {ip_printer}")
        log("INFO", "REQUEST", f"ip_hmi: {ip_hmi}")
        log("INFO", "REQUEST", f"id: {id}")
        
        return SetupAndStartPrintingProcess(id, filename, speed_factor, ip_printer, ip_hmi)
        
    except Exception as e:
        log("ERRO", "REQUEST", f"Falha ao processar requisição: {e}")
        return jsonify({"error": "erro interno"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=MONITOR_PORT)