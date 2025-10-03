from flask import Flask, request, jsonify
import requests
import time
import threading
import re
from datetime import datetime, timezone, timedelta

import os

PRINTER_API_KEY = os.getenv("PRINTER_API_KEY", "93c4GJTZNz1XIwUrLHEzofv5DdBNSPWLUd-FjCXFwsYQ")
MIDDLEWARE_URL = os.getenv("MIDDLEWARE_URL", "192.168.250.102")
CSV_URL = os.getenv("CSV_URL", "192.168.250.102:5004")
AAS_URL = os.getenv("AAS_URL", "192.168.250.102:5001")
MODELS_URL = os.getenv("MODELS_URL", "192.168.250.102:5002")
MONITOR_PORT = int(os.getenv("PORT", 5000))

# Configuration constants
CHECK_INTERVAL = 5  # Interval for checking printer status (seconds)
CHECK_STATE_INTERVAL = 60  # Interval for periodic state logging (seconds)
UPDATE_INTERVAL_M114 = 0.5  # Interval for sending M114 commands (seconds)
UPDATE_INTERVAL_M220 = 0.5  # Interval for sending M220 commands (seconds)
TIMEOUT_LIMIT = 5  # Timeout for M114/M220 responses (seconds)
CHECK_WAIT_IMPRESSION_INTERVAL = 60  # Interval for logging waiting state (seconds)
FILENAME_WARNING_INTERVAL = 300  # Interval for periodic filename warnings (seconds)
CHECK_PRINTER_STATE_INTERVAL = 60  # Interval for logging printer state in wait loop (seconds)

# PRINTER_API_KEY = "-cqzgIHdAaLvW-9EbK6dXW5019dvLPgNyxP7tEwscFw"
# AAS_URL = "192.168.250.102:5001"
# MIDDLEWARE_URL = 'http://192.168.250.102'  # URL do middleware
# CSV_URL = '192.168.250.102:5004'  # URL do CSV
# MODELS_URL = '192.168.250.102:5002'

ALLOWED_FILENAMES = {"zdm4ms~4.gco", "zd5b20~1.gco", "zd2c72~1.gco"}

stop_m114 = threading.Event()
stop_m220 = threading.Event()
stop_info_loop = threading.Event()
m114_response_received = threading.Event()
m220_response_received = threading.Event()
m114_response_received.set()
m220_response_received.set()

def log(tipo, origem, msg):
    timestamp =  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{tipo.upper()}] [{origem}] {msg}")

class Control:
    def __init__(self):
        self._lock = threading.Lock()
        self.filename = None
        self.filename_obtained = False
        self.filename_warning_logged = False
        self.last_filename_warning = 0
        self.was_printing = False
        self.first_m114 = True
        self.first_m220 = True
        self.m114_waiting = False
        self.m220_waiting = False
        self.m114_last_time = 0
        self.m220_last_time = 0
        self.start_time = None
        self.prediction_done = False
        self.prediction4_done = False

    def set_prediction_done(self, value):
        with self._lock:
            self.prediction_done = value

    def get_prediction_done(self):
        with self._lock:
            return self.prediction_done

    def set_prediction4_done(self, value):
        with self._lock:
            self.prediction4_done = value

    def get_prediction4_done(self):
        with self._lock:
            return self.prediction4_done

control = Control()

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

data = PrinterData()
app = Flask(__name__)

def reset_control_state():
    locked = control._lock.acquire(timeout=5)
    if not locked:
        print("Não consegui pegar o lock em reset_control_state! Deadlock possível.")
        return
    try:
        control.filename = None
        control.filename_obtained = False
        control.filename_warning_logged = False
        control.last_filename_warning = 0
        control.first_m114 = True
        control.first_m220 = True
        control.m114_waiting = False
        control.m220_waiting = False
        control.m114_last_time = 0
        control.m220_last_time = 0
        control.start_time = None
        control.set_prediction_done(False)
        control.set_prediction4_done(False)
        control.was_printing = False
    finally:
        control._lock.release()

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

def send_command(destination, msg):
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

def create_aas_product(filename, id):
    piece_type = {
        'zdm4ms~4.gco': 'QUADRADO',
        'zd5b20~1.gco': 'L',
        'zd2c72~1.gco': 'RETANGULO',
        'zdm4ms~1.gco': 'QUADRADO'
    }.get(filename.lower())
    if not piece_type:
        log("ERRO", "CREATE_PRODUCT", f"Tipo de peça inválido para o arquivo {filename}")
        with app.app_context():
            return jsonify({"error": "Invalid piece type"}), 400

    payload = {
        "type": piece_type,
        "id": id
    }
    log("INFO", "CREATE_PRODUCT", f"Criando produto do tipo {piece_type} com o id '{id}'")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/create", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code in (200, 201):
        log("INFO", "CREATE_PRODUCT", f"Produto do tipo {piece_type} com o id '{id}' criado com sucesso")
    else:
        log("ERRO", "CREATE_PRODUCT", f"Falha ao criar produto: {response.text}")
        with app.app_context():
            return jsonify({"error": "Failed to create product"}), 500
    return response

def update_aas_product_state(destination, state, id):
    payload = {
        "destination": destination,
        "shellid": id,
        "value": state,
    }
    log("INFO", "UPDATE_PRODUCT", f"Atualizando produto com o id '{id}' para o estado '{state}'.")
    try:
        response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/update/state", json=payload, timeout=10)
        response.raise_for_status()
        if response.status_code in (200, 201, 204):
            log("INFO", "UPDATE_PRODUCT", f"Produto com o id '{id}' atualizado com o estado '{state}'.")
        else:
            log("ERRO", "UPDATE_PRODUCT", f"Falha ao atualizar produto: {response.text}")
    except Exception as e:
        log("ERRO", "UPDATE_PRODUCT", f"Falha ao atualizar produto: {e}")

def update_aas_product_dimensions(destination, dimensions, id):

    #se dimensions tiver 7 elementos o payload é diferente do que se tiver só 3
    if len(dimensions) == 7:
        payload = {
            "destination": destination,
            "shellid": id,
            "msg": {
                "comprimento": dimensions[0],
                "comprimento_ext1": dimensions[2],
                "comprimento_ext2": dimensions[3],
                "largura": dimensions[1],
                "largura_ext1": dimensions[4],
                "largura_ext2": dimensions[5],
                "altura": dimensions[6]
            }
        }
    elif len(dimensions) == 3:
        payload = {
            "destination": destination,
            "shellid": id,
            "msg": {
                "comprimento": dimensions[0],
                "largura": dimensions[1],
                "altura": dimensions[2]
            }
        }
    log("INFO", "UPDATE_PRODUCT", f"Atualizando produto com o id '{id}' para as dimensões '{dimensions}'.")
    try:
        response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/update/dimensions", json=payload, timeout=10)
        response.raise_for_status()
        if response.status_code in (200, 201):
            log("INFO", "UPDATE_PRODUCT", f"Produto com o id '{id}' atualizado para as dimensões '{dimensions}'.")
        else:
            log("ERRO", "UPDATE_PRODUCT", f"Falha ao atualizar produto: {response.text}")
    except Exception as e:
        log("ERRO", "UPDATE_PRODUCT", f"Falha ao atualizar produto: {e}")

def csv_get_1(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
    }
    log("INFO", "CSV_GET", f"Pedido de CSV enviado: {msg}")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/csv/get", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "CSV_GET", f"CSV recebido com sucesso de {destination}")
    return response

# def send_print_completed(destination, filename, id):
#     payload = {
#         "destination": destination,
#         "filename": filename,
#         "id": id,
#         "status": "completed",
#         "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     }
#     log("INFO", "PRINT_COMPLETED", f"Notificando middleware sobre conclusão da impressão: {filename} (ID: {id})")
#     try:
#         response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/completed", json=payload, timeout=10)
#         response.raise_for_status()
#         if response.status_code == 200:
#             log("INFO", "PRINT_COMPLETED", f"Notificação de conclusão enviada com sucesso para {destination}")
#         return response
#     except Exception as e:
#         log("ERRO", "PRINT_COMPLETED", f"Falha ao enviar notificação de conclusão: {e}")
#         return None

def send_csv_models_1(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    log("INFO", "MODEL", "Enviando dados para inferência do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/predict1", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def send_csv_models_4(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg
    }
    log("INFO", "MODEL", "Enviando dados para inferência do modelo")
    response = requests.post(f"{MIDDLEWARE_URL}:1880/model/predict4", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MODEL", f"Dados enviados com sucesso para {destination}")
    return response

def get_status(destination):
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

def start_m114_loop(ip_printer):
    def loop_m114():
        while not stop_m114.is_set():
            try:
                status = get_status(ip_printer)
                if status != "printing from sd":
                    time.sleep(1)
                    continue
                if m114_response_received.wait(timeout=10):
                    m114_response_received.clear()
                    send_command(ip_printer, "M114")
                else:
                    log("WARN", "M114", f"Timeout esperando resposta do M114. Reenviando.")
                    m114_response_received.set()
            except Exception as e:
                log("ERRO", "M114", f"Erro inesperado: {e}")
                m114_response_received.set()
            time.sleep(UPDATE_INTERVAL_M114)
    threading.Thread(target=loop_m114, daemon=True).start()

def start_m220_loop(ip_printer):
    def loop_m220():
        while not stop_m220.is_set():
            try:
                status = get_status(ip_printer)
                if status != "printing from sd":
                    time.sleep(1)
                    continue
                if m220_response_received.wait(timeout=10):
                    m220_response_received.clear()
                    send_command(ip_printer, "M220")
                else:
                    log("WARN", "M220", f"Timeout esperando resposta do M220. Reenviando.")
                    m220_response_received.set()
            except Exception as e:
                log("ERRO", "M220", f"Erro inesperado: {e}")
                m220_response_received.set()
            time.sleep(UPDATE_INTERVAL_M220)
    threading.Thread(target=loop_m220, daemon=True).start()

def printer_sub(destination):
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

def send_to_aas(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
    }
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/append", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "AAS", f"Enviando DADOS da aas para middleware")
    return response

def send_to_csv(destination, msg):
    payload = {
        "destination": destination,
        "msg": msg,
    }
    response = requests.post(f"{MIDDLEWARE_URL}:1880/csv/append", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "CSV", f"Enviando DADOS do csv para middleware")
    return response

def get_printer_info(destination, filename, start_time, id):
    payload = {
        "destination": destination,
        "filename": filename,
    }
    try:
        response = requests.post(f"{MIDDLEWARE_URL}:1880/printer/info", json=payload, timeout=10)
        response.raise_for_status()
        message_data = response.json()
    except Exception as e:
        log("ERRO", "MIDDLEWARE", f"Erro ao contactar middleware: {e}")
        return

    last_temp = None
    for item in message_data:
        ts = item.get("ts" , "")

        if is_timestamp_after_stdlib(ts, start_time):
            msg = item.get("msg", {})
            current = msg.get("current", {})
            logs = current.get("logs", [])
            for log_line in logs:
                log_line = log_line.strip()
                temp_match = re.search(r"(?:Recv:\s*)?T:([\d.]+)\s*/([\d.]+)\s*B:([\d.]+)\s*/([\d.]+)\s*@:(\d+)\s*B@:(\d+)", log_line)
                if temp_match:
                    last_temp = {
                        "nozzle_temp": float(temp_match.group(1)),
                        "nozzle_target": float(temp_match.group(2)),
                        "bed_temp": float(temp_match.group(3)),
                        "bed_target": float(temp_match.group(4)),
                        "nozzle_pwm": int(temp_match.group(5)),
                        "bed_pwm": int(temp_match.group(6)),
                    }
                    continue
                pos_match = re.search(r"X:([-\d.]+)\s+Y:([-\d.]+)\s+Z:([-\d.]+)\s+E:([-\d.]+)", log_line)
                if pos_match and last_temp:
                    x = float(pos_match.group(1))
                    y = float(pos_match.group(2))
                    z = float(pos_match.group(3))
                    if x == 0 and y == 0 and z == 5:
                        log("INFO", "MONITORING", f"Mensagem com 005 ignorada")
                        continue
                    if last_temp["nozzle_target"] != 200:
                        log("INFO", "MONITORING", f"Mensagem com target diferente de 200 ignorada")
                        continue
                    
                    log("INFO", "M114", f"M114 encontrada: {pos_match.group(0)}")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    pos_data = {
                        "X": x,
                        "Y": y,
                        "Z": z,
                        "E": float(pos_match.group(4)),
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
                        "X": pos_data["X"],
                        "Y": pos_data["Y"],
                        "Z": pos_data["Z"],
                        "E": pos_data["E"],
                        "speed_factor": None,
                        "filename": filename
                    }
                    m114_response_received.set()
                    control.m114_waiting = False
                    send_to_aas(AAS_URL, data)
                    send_to_csv(CSV_URL, data)
                    if pos_data["Z"] == 1 and not control.get_prediction_done():
                        log("INFO", "PREDICTION", "Iniciando previsão do modelo")
                        csv_response = csv_get_1(CSV_URL, {"start_time": start_time, "filename": filename})
                        if csv_response is not None:
                            try:
                                csv_data = csv_response.json()
                                model_response = send_csv_models_1(MODELS_URL, csv_data)
                                if model_response is not None:
                                    model_data = model_response.json()
                                    prediction = model_data.get("prediction")
                                    log("INFO", "MODEL", f"Previsão do modelo recebida: {prediction}")
                                    if prediction is None:
                                        log("ERRO", "MODEL", "Previsão do modelo não encontrada na resposta")
                                        break
                                    if prediction == "NOK":
                                        #send_command(destination, "M524")
                                        log("INFO", "MODEL", "Previsão do modelo: NOK")
                                        #log("INFO", "MODEL", "Enviando comando M524 para cancelar impressão")
                                        update_aas_product_state(AAS_URL, "predicted NOK", id)
                                        # control.set_prediction_done(True)
                                        # stop_info_loop.set()
                                        # stop_m114.set()
                                        # stop_m220.set()
                                        break
                                    elif prediction == "OK":
                                        update_aas_product_state(AAS_URL, "predicted OK", id)
                                        log("INFO", "MODEL", "Previsão do modelo: OK")
                                control.set_prediction_done(True)
                            except Exception as e:
                                log("ERRO", "MODEL", f"Falha ao processar previsão do modelo: {e}")
                        else:
                            log("WARN", "CSV", "Nenhuma resposta do CSV obtida.")
                    if pos_data["Z"] == 4 and not control.get_prediction4_done():
                        log("INFO", "PREDICTION", "Iniciando previsão do modelo de regressão")
                        csv_response = csv_get_1(CSV_URL, {"start_time": start_time, "filename": filename})
                        if csv_response is not None:
                            try:
                                csv_data = csv_response.json()
                                model_response = send_csv_models_4(MODELS_URL, csv_data)
                                if model_response is not None:
                                    model_data = model_response.json()
                                    predictions = model_data.get("predictions")
                                    update_aas_product_dimensions(AAS_URL, predictions, id)
                                    log("INFO", "MODEL", f"Previsão do modelo recebida: {predictions}")
                                    if predictions is None:
                                        log("ERRO", "MODEL", "Previsão do modelo não encontrada na resposta")
                                        continue
                                control.set_prediction4_done(True)
                            except Exception as e:
                                log("ERRO", "MODEL", f"Falha ao processar previsão do modelo: {e}")
                        else:
                            log("WARN", "CSV", "Nenhuma resposta do CSV obtida.")
                speed_match = re.search(r"FR:([\d.]+)%", log_line)
                if speed_match and last_temp:
                    log("INFO", "M220", f"M220 encontrada: {speed_match.group(0)}")
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    speed_factor = float(speed_match.group(1))
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
                        "speed_factor": speed_factor,
                        "filename": filename
                    }
                    m220_response_received.set()
                    control.m220_waiting = False
                    send_to_aas(AAS_URL, data)
                    send_to_csv(CSV_URL, data)

def start_printer_info_loop(ip_printer, filename, start_time, id):
    def loop():
        last_check_time = 0
        last_state_log_time = 0
        last_wait_log = 0
        while not stop_info_loop.is_set():
            current_time = time.time()
            try:
                state = get_status(ip_printer)
                if state is None:
                    log("WARN", "PRINTER", "Estado da impressora retornou None, tentando novamente...")
                    time.sleep(2)
                    continue

                # Log periódico do estado da impressora
                if current_time - last_state_log_time >= CHECK_STATE_INTERVAL:
                    log("INFO", "PRINTER", f"Estado atual: {state}")
                    last_state_log_time = current_time

                # Impressão ativa
                if state == "printing from sd":
                    if current_time - last_check_time >= CHECK_INTERVAL:
                        get_printer_info(ip_printer, filename, start_time, id)
                        last_check_time = current_time
                    with control._lock:
                        control.was_printing = True

                # Impressão pausada
                elif state == "paused":
                    log("INFO", "PRINTER", "Impressora pausada. A aguardar retomada da impressão...")
                    time.sleep(3)
                    continue

                # Impressão terminada
                elif state == "operational" and control.was_printing:
                    log("INFO", "PRINTER", "Impressão concluída. Aguardando novo comando do HMI.")
                    control.filename = None
                    control.filename_obtained = False
                    control.filename_warning_logged = False
                    control.last_filename_warning = 0
                    control.first_m114 = True
                    control.first_m220 = True
                    control.m114_waiting = False
                    control.m220_waiting = False
                    control.m114_last_time = 0
                    control.m220_last_time = 0
                    control.start_time = None
                    control.set_prediction_done(False)
                    control.set_prediction4_done(False)
                    control.was_printing = False
                    stop_info_loop.set()
                    stop_m114.set()
                    stop_m220.set()
                    break

                # Antes da impressão iniciar
                elif state == "operational" and not control.was_printing:
                    if current_time - last_wait_log >= CHECK_WAIT_IMPRESSION_INTERVAL:
                        log("INFO", "PRINTER", "Aguardando início da impressão...")
                        last_wait_log = current_time

            except Exception as e:
                log("ERRO", "PRINTER", f"Erro no loop de monitorização: {e}")

            time.sleep(CHECK_INTERVAL)

    threading.Thread(target=loop, daemon=True).start()

def wait_for_printing_and_start_monitoring(ip_printer, filename, id):
    try:
        last_state_log_time = 0
        while True:
            current_time = time.time()
            state = get_status(ip_printer)
            if state is None:
                log("WARN", "PRINTER", "Estado da impressora retornou None, continuando verificação")
                time.sleep(2)
                continue
            state = state.lower()
            if current_time - last_state_log_time >= CHECK_PRINTER_STATE_INTERVAL:
                log("INFO", "PRINTER", f"Estado atual da impressora: {state}")
                last_state_log_time = current_time
            filename_allowed = filename.lower() in ALLOWED_FILENAMES
            if not filename_allowed:
                log("ERRO", "PRINTER", f"Nome de ficheiro {filename} não está na lista permitida. Monitorização não iniciada")
                break
            if state == "printing from sd":
                log("INFO", "PRINTER", "Impressora iniciou impressão. Iniciando monitorização...")
                with control._lock:
                    control.filename = filename
                    control.filename_obtained = True
                    control.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    control.was_printing = True
                printer_sub(ip_printer)
                start_printer_info_loop(ip_printer, filename, control.start_time, id)
                start_m114_loop(ip_printer)
                start_m220_loop(ip_printer)
                break
            elif state == "operational":
                if current_time - last_state_log_time >= CHECK_PRINTER_STATE_INTERVAL:
                    log("INFO", "PRINTER", "Impressora ainda está a aquecer...")
            else:
                log("INFO", "PRINTER", f"Estado inesperado: {state}")
            time.sleep(2)
    except Exception as e:
        log("ERRO", "PRINTER", f"Falha na thread de monitorização: {e}")

@app.route('/start', methods=['POST'])
def start():
    try:
        #reset_control_state()
        data = request.get_json()
        print(data)
        log("INFO", "REQUEST", f"Dados recebidos: {data}")
        filename = data["filename"]
        speed_factor = data["speed_factor"]
        ip_printer = data["ip_printer"]
        id = data["id"]
        log("INFO", "REQUEST", f"filename: {filename}")
        log("INFO", "REQUEST", f"speed_factor: {speed_factor}")
        log("INFO", "REQUEST", f"ip_printer: {ip_printer}")
        log("INFO", "REQUEST", f"id: {id}")
        if filename.lower() not in ALLOWED_FILENAMES:
            log("ERRO", "REQUEST", f"Nome de ficheiro {filename} não está na lista permitida")
            return jsonify({"error": "Invalid filename"}), 400
        send_command(ip_printer, "M27 S0")
        send_command(ip_printer, f"M23 {filename}")
        send_command(ip_printer, "M24")
        send_command(ip_printer, f"M220 S{speed_factor}")
        response = create_aas_product(filename, id)
        if response.status_code not in (200, 201):
            return response
        stop_info_loop.clear()
        stop_m114.clear()
        stop_m220.clear()
        with control._lock:
            control.filename = filename
            control.filename_obtained = True
        threading.Thread(
            target=wait_for_printing_and_start_monitoring,
            args=(ip_printer, filename, id),
            daemon=True
        ).start()
        return jsonify({"status": "mensagem encaminhada com sucesso"}), 200
    except Exception as e:
        log("ERRO", "REQUEST", f"Falha ao processar requisição: {e}")
        return jsonify({"error": "erro interno"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=MONITOR_PORT)