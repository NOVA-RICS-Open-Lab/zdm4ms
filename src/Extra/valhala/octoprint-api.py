import os
import requests
import time
from datetime import datetime
import csv
import websocket
import json
import threading
import re
import logging

# Configurações do OctoPrint
BASE_URL = "http://192.168.6.1" 
API_KEY = "Yfvanr37vlCxeQCFi8_pdyrz-GrqYFIYh2RpYKYtQ0I" 
USERNAME = "rics" 
PASSWORD = "ricsricsjabjab"
UPDATE_INTERVAL_M114 = 5
UPDATE_INTERVAL_M220 = 30
TIMEOUT_LIMIT = 90
CSV_FILE = "/app/data/printer_dataZDM2.csv" 
LOG_FILE = "/app/data/octoprint_monitor6.log"
CHECK_INTERVAL = 5
CHECK_STATE_INTERVAL = 30
CHECK_WAIT_IMPRESSION_INTERVAL = 60
HTTP_TIMEOUT = 30
FILENAME_WARNING_INTERVAL = 300  

# Configurações de Retry
MAX_RETRIES = 5
RETRY_WAIT = 10

# Configurações do Serviço de Predict
PREDICTION_SERVICE_URL = "http://prediction-service:5000/predict"
OK_PREDICTION_SERVICE_URL = "http://ok-pred-service:5002/predict"

HEADERS = {
    "X-Api-Key": API_KEY,
    "Content-Type": "application/json"
}

# Configurações do AASX Server
AAS_URL = "http://192.168.250.224:5001/submodels/aHR0cHM6Ly9leGFtcGxlLmNvbS9pZHMvc20vNjA1MF8zMTMwXzYwNTJfODY2MA==/submodel-elements/"
AAS_HEADERS = {"Content-Type": "application/json"}

# Dados base para o corpo da requisição da AAS
AAS_BASE_DATA = {
    "category": "",
    "idShort": "value",
    "semanticId": {"type": "ModelReference", "keys": [{"type": "ConceptDescription", "value": "https://example.com/ids/cd/1162_4162_5052_4762"}]},
    "valueType": "xs:string",
    "modelType": "Property"
}

# Variaveis a serem atualizadas na AAS
AAS_VARIABLES = {
    "timestamp": {"id_short": "timestamp"},       # Timestamp
    "nozzle_temp": {"id_short": "nozzle_temp"},   # NozzleTemp
    "nozzle_target": {"id_short": "nozzle_target"}, # NozzleTarget
    "bed_temp": {"id_short": "bed_temp"},         # BedTemp
    "bed_target": {"id_short": "bed_target"},     # BedTarget
    "x": {"id_short": "x"},                       # X
    "y": {"id_short": "y"},                       # Y
    "z": {"id_short": "z"},                       # Z
    "extrusion_level": {"id_short": "extrusion_level"}, # ExtrusionLevel
    "filename": {"id_short": "filename"},         # Filename
    "nozzle_delta": {"id_short": "nozzle_delta"}, # NozzleDelta
    "bed_delta": {"id_short": "bed_delta"},       # BedDelta
    "nozzle_pwm": {"id_short": "nozzle_pwm"},     # NozzlePWM
    "bed_pwm": {"id_short": "bed_pwm"},           # BedPWM
    "speed_factor": {"id_short": "speed_factor"}  # SpeedFactor
}

# Criar a pasta para os logs e o dataset, cria se não existir
log_dir = "/app/data"
try:
    os.makedirs(log_dir, exist_ok=True)
except Exception as e:
    print(f"Erro ao criar diretório {log_dir}: {e}")
    exit(1)

# Configurar ficheiros de log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


#Classes 
class PrinterData:
    def __init__(self):
        self.nozzle_temp = None
        self.nozzle_target = None
        self.nozzle_delta = None
        self.bed_temp = None
        self.bed_target = None
        self.bed_delta = None
        self.nozzle_pwm = None
        self.bed_pwm = None
        self.x = None
        self.y = None
        self.z = None
        self.extrusion_level = None
        self.speed_factor = None

    def to_dict(self):
        return {
            "NozzleTemp": self.nozzle_temp,
            "NozzleTarget": self.nozzle_target,
            "NozzleDelta": self.nozzle_delta,
            "BedTemp": self.bed_temp,
            "BedTarget": self.bed_target,
            "BedDelta": self.bed_delta,
            "NozzlePWM": self.nozzle_pwm,
            "BedPWM": self.bed_pwm,
            "X": self.x,
            "Y": self.y,
            "Z": self.z,
            "ExtrusionLevel": self.extrusion_level,
            "SpeedFactor": self.speed_factor
        }

class Control:
    def __init__(self):
        self.m114_waiting = False 
        self.m220_waiting = False
        self.m114_last_time = None
        self.m220_last_time = None
        self.session_key = None
        self.printer_state = None
        self.filename = None
        self.filename_obtained = False
        self.ws = None
        self.filename_warning_logged = False  
        self.last_filename_warning = 0  
        self.first_save_done = False
        self.start_time = None
        self.prediction_called = False
        self.ok_prediction_called = False

data = PrinterData()
control = Control()

def login():
    url = f"{BASE_URL}/api/login"
    payload = {"user": USERNAME, "pass": PASSWORD, "remember": True}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            control.session_key = response.json().get("session")
            logger.info("Login bem-sucedido")
            return True
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro no login (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                logger.error("Falha ao fazer login após %d tentativas", MAX_RETRIES)
                return False

def check_printing_status():
    url = f"{BASE_URL}/api/job"
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            job_data = response.json()
            state = job_data["state"]
            control.printer_state = state
            return state
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao verificar estado da impressora (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                control.printer_state = "Unknown"
                return "Unknown"

def get_current_filename_from_api():
    url = f"{BASE_URL}/api/job"
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.get(url, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            job_data = response.json()
            file_info = job_data.get("job", {}).get("file", {})
            filename = file_info.get("name", "(no file)")
            if filename and filename.lower().endswith(".gco"):
                filename = filename[:-4]
            logger.info("Nome do arquivo obtido: %s", filename)
            return filename
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao obter nome do arquivo (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                logger.warning("Falha ao obter nome do arquivo após %d tentativas, retornando valor padrão", MAX_RETRIES)
                return "(no file)"

def send_m114():
    url = f"{BASE_URL}/api/printer/command"
    payload = {"command": "M114"}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            logger.info("Comando M114 enviado")
            control.m114_waiting = True
            control.m114_last_time = time.time()
            return
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao enviar M114 (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                control.m114_waiting = False
                control.m114_last_time = None

def send_m220():
    url = f"{BASE_URL}/api/printer/command"
    payload = {"command": "M220"}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            logger.info("Comando M220 enviado")
            control.m220_waiting = True
            control.m220_last_time = time.time()
            return
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao enviar M220 (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                control.m220_waiting = False
                control.m220_last_time = None

def send_m524():
    url = f"{BASE_URL}/api/printer/command"
    payload = {"command": "M524"}
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(url, json=payload, headers=HEADERS, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            logger.info("Comando M524 enviado")
            return
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao enviar M524 (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
                
def call_prediction_service(start_time, filename):
    payload = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename
    }
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(PREDICTION_SERVICE_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            logger.debug("Resposta do serviço de predict: %s", json.dumps(result, indent=2))
            return result
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao chamar serviço de predict (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                logger.error("Falha ao chamar serviço de predict após %d tentativas", MAX_RETRIES)
                return None
            
def call_ok_prediction_service(start_time, filename):
    payload = {
        "start_time": start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "filename": filename
    }
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.post(OK_PREDICTION_SERVICE_URL, json=payload, headers={"Content-Type": "application/json"}, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            logger.debug("Resposta do serviço de predict: %s", json.dumps(result, indent=2))
            return result
        except requests.exceptions.RequestException as e:
            retries += 1
            logger.error("Erro ao chamar serviço de predict (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                logger.error("Falha ao chamar serviço de predict após %d tentativas", MAX_RETRIES)
                return None

def update_aas_variable(variable_key, value):
    if value is None:
        return  
    config = AAS_VARIABLES.get(variable_key)
    if not config:
        logger.error(f"Variável {variable_key} não encontrada no mapeamento AAS_VARIABLES")
        return
    id_short = config["id_short"]
    url = f"{AAS_URL}{id_short}.value"
    data = AAS_BASE_DATA.copy()
    data["value"] = str(value)
    retries = 0
    while retries < MAX_RETRIES:
        try:
            response = requests.put(url, headers=AAS_HEADERS, json=data, timeout=HTTP_TIMEOUT)
            if response.status_code in [200, 204]: 
                logger.debug(f"Atualizado {id_short}.value ({variable_key}) para {value} às {time.strftime('%H:%M:%S')}")
                return True
            else:
                logger.error(f"Erro ao atualizar {id_short}.value ({variable_key}): {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Erro na requisição ao AAS para {variable_key} (tentativa {retries+1}/{MAX_RETRIES}): {e}")

def save_data(timestamp, is_m114=True):
    allowed_filenames = {"zdm4ms~4", "zd5b20~1", "zd2c72~1", "ZDM4MS~1"}
    
    
    if control.filename is None or control.filename not in allowed_filenames:
        logger.info("Nome de ficheiro %s não está na lista permitida ou é None. Dados não salvos", control.filename)
        return


    try:
        if not os.path.exists(CSV_FILE):
            with open(CSV_FILE, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)
                writer.writerow(["timestamp", "temp_nozzle", "temp_target_nozzle", "temp_delta_nozzle",
                                 "pwm_nozzle", "temp_bed", "temp_target_bed", "temp_delta_bed", "pwm_bed",
                                 "X", "Y", "Z", "E", "speed_factor", "filename"])

        timestamp_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            

        if is_m114:
            row = [timestamp_str, data.nozzle_temp, data.nozzle_target, data.nozzle_delta,
                   data.nozzle_pwm, data.bed_temp, data.bed_target, data.bed_delta, data.bed_pwm,
                   data.x, data.y, data.z, data.extrusion_level, data.speed_factor, control.filename]
        
            nozzle_temp = data.nozzle_temp if data.nozzle_temp is not None else 0.0
            nozzle_target = data.nozzle_target if data.nozzle_target is not None else 0.0
            bed_temp = data.bed_temp if data.bed_temp is not None else 0.0
            bed_target = data.bed_target if data.bed_target is not None else 0.0
            nozzle_pwm = data.nozzle_pwm if data.nozzle_pwm is not None else 0
            bed_pwm = data.bed_pwm if data.bed_pwm is not None else 0
            x = data.x if data.x is not None else 0.0
            y = data.y if data.y is not None else 0.0
            z = data.z if data.z is not None else 0.0
            extrusion_level = data.extrusion_level if data.extrusion_level is not None else 0.0
            speed_factor = data.speed_factor if data.speed_factor is not None else 0.0
            if not control.first_save_done:
                control.start_time = timestamp
                control.first_save_done = True
                logger.info("Primeiro save_data registrado. Start_time definido como: %s", timestamp.strftime("%Y-%m-%d %H:%M:%S"))

            logger.info("Dados M114 salvos: %s, X=%.2f, Y=%.2f, Z=%.2f, E=%.2f, SpeedFactor=%.0f%%, Nozzle=%.2f/%.2f, Bed=%.2f/%.2f, PWM(Nozzle:Bed)=(%d:%d), Filename=%s",
                        timestamp_str, x, y, z, extrusion_level, speed_factor,
                        nozzle_temp, nozzle_target, bed_temp, bed_target, nozzle_pwm, bed_pwm, control.filename)
            
            updates = [
                update_aas_variable("timestamp", timestamp_str),
                update_aas_variable("nozzle_temp", data.nozzle_temp),
                update_aas_variable("nozzle_target", data.nozzle_target),
                update_aas_variable("nozzle_delta", data.nozzle_delta),
                update_aas_variable("bed_temp", data.bed_temp),
                update_aas_variable("bed_target", data.bed_target),
                update_aas_variable("bed_delta", data.bed_delta),
                update_aas_variable("nozzle_pwm", data.nozzle_pwm),
                update_aas_variable("bed_pwm", data.bed_pwm),
                update_aas_variable("x", data.x),
                update_aas_variable("y", data.y),
                update_aas_variable("z", data.z),
                update_aas_variable("extrusion_level", data.extrusion_level),
                update_aas_variable("speed_factor", data.speed_factor),
                update_aas_variable("filename", control.filename)
            ]
            if all(updates):
                logger.info("M114 | Todos os nós foram atualizados na Asset Administration Shell às %s", time.strftime('%H:%M:%S'))
        else:
            row = [timestamp_str, data.nozzle_temp, data.nozzle_target, data.nozzle_delta,
                   data.nozzle_pwm, data.bed_temp, data.bed_target, data.bed_delta, data.bed_pwm,
                   None, None, None, None, data.speed_factor, control.filename]
            
            nozzle_temp = data.nozzle_temp if data.nozzle_temp is not None else 0.0
            nozzle_target = data.nozzle_target if data.nozzle_target is not None else 0.0
            bed_temp = data.bed_temp if data.bed_temp is not None else 0.0
            bed_target = data.bed_target if data.bed_target is not None else 0.0
            nozzle_pwm = data.nozzle_pwm if data.nozzle_pwm is not None else 0
            bed_pwm = data.bed_pwm if data.bed_pwm is not None else 0
            speed_factor = data.speed_factor if data.speed_factor is not None else 0.0
            logger.info("Dados M220 salvos: %s, SpeedFactor=%.0f%%, Nozzle=%.2f/%.2f, Bed=%.2f/%.2f, PWM(Nozzle:Bed)=(%d:%d), Filename=%s",
                        timestamp_str, speed_factor, nozzle_temp, nozzle_target, bed_temp, bed_target, nozzle_pwm, bed_pwm, control.filename)
            
            updates2 = [
                update_aas_variable("timestamp", timestamp_str),
                update_aas_variable("nozzle_temp", data.nozzle_temp),
                update_aas_variable("nozzle_target", data.nozzle_target),
                update_aas_variable("nozzle_delta", data.nozzle_delta),
                update_aas_variable("bed_temp", data.bed_temp),
                update_aas_variable("bed_target", data.bed_target),
                update_aas_variable("bed_delta", data.bed_delta),
                update_aas_variable("nozzle_pwm", data.nozzle_pwm),
                update_aas_variable("bed_pwm", data.bed_pwm),
                update_aas_variable("speed_factor", data.speed_factor),
                update_aas_variable("filename", control.filename)
            ]
            if all(updates2):
                logger.info("M220 | Todos os nós foram atualizados na Asset Administration Shell às %s", time.strftime('%H:%M:%S'))
        with open(CSV_FILE, "a", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(row)
    except Exception as e:
        logger.error("Erro ao salvar dados no CSV %s: %s", CSV_FILE, e)

def on_message(ws, message):
    try:
        logger.debug("Mensagem WebSocket recebida: %s", message)
        message_data = json.loads(message)
        if "connected" in message_data:
            logger.info("Conexão WebSocket confirmada")
            return

        if "current" in message_data:
            current = message_data["current"]
            logs = current.get("logs", [])
            logger.debug("Logs recebidos: %s", logs)

            for log in logs:
                logger.debug("Processando log: %s", log)

                temp_match = re.search(r"T:([\d.]+)\s*/([\d.]+)\s*B:([\d.]+)\s*/([\d.]+)\s*@:(\d+)\s*B@:(\d+)", log)
                if temp_match:
                    data.nozzle_temp = float(temp_match.group(1))
                    data.nozzle_target = float(temp_match.group(2))
                    data.bed_temp = float(temp_match.group(3))
                    data.bed_target = float(temp_match.group(4))
                    data.nozzle_pwm = int(temp_match.group(5))
                    data.bed_pwm = int(temp_match.group(6))
                    data.nozzle_delta = data.nozzle_temp - data.nozzle_target if data.nozzle_temp is not None and data.nozzle_target is not None else None
                    data.bed_delta = data.bed_temp - data.bed_target if data.bed_temp is not None and data.bed_target is not None else None

                pos_match = re.search(r"X:([-\d.]+)\s+Y:([-\d.]+)\s+Z:([-\d.]+)\s+E:([-\d.]+)", log)
                if pos_match and control.m114_waiting:
                    data.x = float(pos_match.group(1))
                    data.y = float(pos_match.group(2))
                    data.z = float(pos_match.group(3))
                    data.extrusion_level = float(pos_match.group(4))
                    nozzle_target = data.nozzle_target if data.nozzle_target is not None else 0.0
                    bed_target = data.bed_target if data.bed_target is not None else 0.0
                    if nozzle_target != 0 and bed_target != 0:
                        timestamp = datetime.now()
                        save_data(timestamp, is_m114=True)

                        if data.z == 1.0 and not control.ok_prediction_called and control.start_time and control.filename:
                            ok_prediction_result = call_ok_prediction_service(control.start_time, control.filename)
                            if ok_prediction_result:
                                control.ok_prediction_called = True
                                ok_piece_type = ok_prediction_result.get("piece_type")
                                ok_prediction = ok_prediction_result.get("prediction")
                                logger.info(f"Segundo previsão a peça {ok_piece_type} que está a ser produzida sairá {ok_prediction}")
                                if ok_prediction == "NOK":
                                    logger.info(f"A parar a impressão...")
                                    send_m524()


                        if data.z == 4.0 and not control.prediction_called and control.start_time and control.filename:
                            prediction_result = call_prediction_service(control.start_time, control.filename)
                            if prediction_result:
                                control.prediction_called = True
                                piece_type = prediction_result.get("piece_type")
                                predictions = prediction_result.get("predictions", [])
                                if piece_type in ["QUADRADO", "RETANGULO"]:
                                    log_message = (
                                        f"predict para {piece_type}: "
                                        f"Comprimento={predictions[0]:.2f}mm, "
                                        f"Largura={predictions[1]:.2f}mm, "
                                        f"Altura={predictions[2]:.2f}mm"
                                    )
                                elif piece_type == "L":
                                    log_message = (
                                        f"predict para {piece_type}: "
                                        f"Comprimento Externo={predictions[0]:.2f}mm, "
                                        f"Largura Externa={predictions[1]:.2f}mm, "
                                        f"Comprimento Interno 1={predictions[2]:.2f}mm, "
                                        f"Comprimento Interno 2={predictions[3]:.2f}mm, "
                                        f"Largura Interna 1={predictions[4]:.2f}mm, "
                                        f"Largura Interna 2={predictions[5]:.2f}mm, "
                                        f"Altura={predictions[6]:.2f}mm"
                                    )
                                logger.info(log_message)
                    else:
                        logger.info("M114 ignorado após fim da impressão: X=%.2f, Y=%.2f, Z=%.2f, E=%.2f", data.x, data.y, data.z, data.extrusion_level)
                    control.m114_waiting = False

                speed_match = re.search(r"FR:([\d.]+)%", log)
                if speed_match and control.m220_waiting:
                    data.speed_factor = float(speed_match.group(1))
                    nozzle_target = data.nozzle_target if data.nozzle_target is not None else 0.0
                    bed_target = data.bed_target if data.bed_target is not None else 0.0
                    if nozzle_target != 0 and bed_target != 0:
                        timestamp = datetime.now()
                        save_data(timestamp, is_m114=False)
                    else:
                        logger.info("M220 ignorado após fim da impressão: SpeedFactor=%.0f%%", data.speed_factor)
                    control.m220_waiting = False

    except json.JSONDecodeError as e:
        logger.error("Erro ao decodificar mensagem WebSocket: %s", e)
    except ValueError as e:
        logger.error("Erro ao processar mensagem: %s", e)
    except Exception as e:
        logger.error("Erro inesperado: %s", e)

def on_error(ws, error):
    logger.error("Erro no WebSocket: %s", error)

def on_close(ws, close_status_code, close_msg):
    logger.info("Conexão WebSocket fechada. Tentando reconectar...")
    control.ws = None
    time.sleep(RETRY_WAIT)
    control.ws = start_websocket()

def on_open(ws):
    logger.info("Conexão WebSocket aberta")
    ws.send(json.dumps({"auth": f"{USERNAME}:{control.session_key}"}))

def start_websocket():
    ws_url = f"ws://{BASE_URL.split('http://')[1]}/sockjs/websocket"
    retries = 0
    while retries < MAX_RETRIES:
        try:
            ws = websocket.WebSocketApp(ws_url, on_open=on_open, on_message=on_message,
                                        on_error=on_error, on_close=on_close)
            ws_thread = threading.Thread(target=ws.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            logger.info("Conexão WebSocket iniciada")
            return ws
        except Exception as e:
            retries += 1
            logger.error("Erro ao iniciar WebSocket (tentativa %d/%d): %s", retries, MAX_RETRIES, e)
            if retries < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                logger.error("Falha ao iniciar WebSocket após %d tentativas", MAX_RETRIES)
                return None

def main():
    while not login():
        logger.warning("Falha no login, esperando %ds antes de tentar novamente", RETRY_WAIT)
        time.sleep(RETRY_WAIT)


    control.ws = start_websocket()
    time.sleep(2) 

    last_check_time = 0
    last_check_time_state = 0
    last_m114_time = 0
    last_m220_time = 0
    first_m114 = True
    first_m220 = True
    was_printing = False
    last_wait_impression = 0
    try:
        while True:
            current_time = time.time()
            logger.debug("Loop principal rodando, current_time: %s", datetime.fromtimestamp(current_time).strftime("%Y-%m-%d %H:%M:%S"))

            if current_time - last_check_time >= CHECK_INTERVAL:
                try:
                    state = check_printing_status()
                    if current_time - last_check_time_state >= CHECK_STATE_INTERVAL:
                        logger.info("Estado da impressora verificado: %s", state)
                        last_check_time_state = current_time
                    is_printing = state in ["Printing from SD", "Starting print from SD"]
                    is_operational = state == "Operational"

                    if is_operational and not was_printing:
                        if current_time - last_wait_impression >= CHECK_WAIT_IMPRESSION_INTERVAL:
                            logger.info("Impressora em estado Operational, aguardando impressão")
                            last_wait_impression = current_time

                    if is_printing and not was_printing:
                        logger.info("Impressora iniciando impressão: %s", state)
                        control.filename = get_current_filename_from_api()
                        control.filename_obtained = True
                        control.filename_warning_logged = False 
                        control.last_filename_warning = 0  
                        first_m114 = True
                        first_m220 = True
                        control.first_save_done = False
                        control.prediction_called = False
                        control.ok_prediction_called = False

                    if not is_printing and was_printing and is_operational:
                        logger.info("Impressora voltou ao estado Operational após impressão")
                        control.m114_waiting = False
                        control.m220_waiting = False
                        first_m220 = True
                        first_m114 = True
                        control.filename_obtained = False
                        control.filename = None
                        control.filename_warning_logged = False  
                        control.last_filename_warning = 0  
                        control.first_save_done = False
                        control.start_time = None
                        control.prediction_called = False
                        control.ok_prediction_called = False

                    allowed_filenames = {"zdm4ms~4", "zd5b20~1", "zd2c72~1", "ZDM4MS~1"}
                    filename_allowed = control.filename is not None and control.filename in allowed_filenames

                    if is_printing:
                        if filename_allowed:
                            if not control.m114_waiting and first_m114:
                                send_m114()
                                first_m114 = False
                                last_m114_time = current_time
                            if not control.m220_waiting and first_m220:
                                send_m220()
                                first_m220 = False
                                last_m220_time = current_time
                        else:
                            
                            if not control.filename_warning_logged:
                                logger.info("Nome de ficheiro %s não está na lista permitida ou é None. Comandos M114 e M220 não serão enviados", control.filename)
                                control.filename_warning_logged = True
                                control.last_filename_warning = current_time
                            elif current_time - control.last_filename_warning >= FILENAME_WARNING_INTERVAL:
                                logger.info("Nome de ficheiro %s ainda não está na lista permitida ou é None. Comandos M114 e M220 não serão enviados (log periódico)", control.filename)
                                control.last_filename_warning = current_time

                    was_printing = is_printing
                    last_check_time = current_time
                except Exception as e:
                    logger.error("Erro ao verificar estado da impressora: %s", e)
                    time.sleep(RETRY_WAIT)
                    continue

            allowed_filenames = {"zdm4ms~4", "zd5b20~1", "zd2c72~1", "ZDM4MS~1"}
            filename_allowed = control.filename is not None and control.filename in allowed_filenames

            if was_printing:
                if filename_allowed:
                    if not control.m114_waiting and (current_time - last_m114_time >= UPDATE_INTERVAL_M114):
                        send_m114()
                        last_m114_time = current_time
                    if not control.m220_waiting and (current_time - last_m220_time >= UPDATE_INTERVAL_M220):
                        send_m220()
                        last_m220_time = current_time
                else:
                    
                    if not control.filename_warning_logged:
                        logger.info("Nome de ficheiro %s não está na lista permitida ou é None. Comandos M114 e M220 não serão enviados", control.filename)
                        control.filename_warning_logged = True
                        control.last_filename_warning = current_time
                    elif current_time - control.last_filename_warning >= FILENAME_WARNING_INTERVAL:
                        logger.info("Nome de ficheiro %s ainda não está na lista permitida ou é None. Comandos M114 e M220 não serão enviados (log periódico)", control.filename)
                        control.last_filename_warning = current_time

            if control.m114_waiting and control.m114_last_time and (current_time - control.m114_last_time > TIMEOUT_LIMIT) and was_printing:
                logger.warning("Timeout de %ds para M114. Reenviando", TIMEOUT_LIMIT)
                send_m114()
                last_m114_time = current_time

            if control.m220_waiting and control.m220_last_time and (current_time - control.m220_last_time > TIMEOUT_LIMIT) and was_printing:
                logger.warning("Timeout de %ds para M220. Reenviando", TIMEOUT_LIMIT)
                send_m220()
                last_m220_time = current_time

            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Programa encerrado pelo usuário")
        if control.ws is not None:
            control.ws.close()
    except Exception as e:
        logger.error("Erro no loop principal: %s", e)
        time.sleep(RETRY_WAIT)
        main()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Programa encerrado pelo usuário")