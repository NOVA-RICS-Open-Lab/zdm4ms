import os
import requests
import time
import json
import threading
import re
import websocket
import asyncio
import random
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from queue import Queue
from flask import Flask, jsonify
from asyncua import Server, ua

# --- Configurações ---
PRINTER_URL = "http://192.168.6.1"
API_KEY = "QL3SCr7AwEO8tBTnvPsWEORjOCctfQEWAqwes_m0fko"
OPC_PORT = 4842
FLASK_PORT = 5003
TIMEZONE_UTC = ZoneInfo("UTC")
LOCAL_LOG_FILE = "log_impressora.jsonl"

app = Flask(__name__)
data_queue = Queue()


class PrinterControl:
    def __init__(self):
        self.m114_pending = False
        self.last_send_time = 0
        self.nodes = {}
        self.running_event = threading.Event()
        self.buffer = []
        self.buffer_lock = threading.Lock()
        self.speed_factor_fixed = None


control = PrinterControl()


def get_log_ts():
    return datetime.now().strftime('%H:%M:%S.%f')[:-3]


def save_to_local_storage(data):
    if not data: return
    entry = {
        "call_time": datetime.now(TIMEZONE_UTC).isoformat(),
        "total_messages": len(data),
        "messages": data
    }
    with open(LOCAL_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ----------------- OPC UA SERVER ----------------- #

async def opc_server_task():
    server = Server()
    await server.init()
    server.set_endpoint(f"opc.tcp://0.0.0.0:{OPC_PORT}/freeopcua/server/")

    # Namespace e Objeto Principal
    uri = "http://printer.system.local"
    idx = await server.register_namespace(uri)
    obj = await server.nodes.objects.add_object(idx, "Printer3D")

    vars_list = ["nozzle_temp", "nozzle_target", "nozzle_delta", "nozzle_pwm",
                 "bed_temp", "bed_target", "bed_delta", "bed_pwm",
                 "x", "y", "z", "extrusion_level", "speed_factor"]

    for name in vars_list:
        # Formata "nozzle_temp" para "Nozzle_Temp"
        node_name = "_".join([word.capitalize() for word in name.split("_")])

        # Cria o nó (Node ID resultará em algo como ns=2;s=Printer3D.Nozzle_Temp)
        control.nodes[name] = await obj.add_variable(idx, node_name, 0.0)
        await control.nodes[name].set_writable()

    print(f"[{get_log_ts()}] ✅ [OPC-UA] Ativo em opc.tcp://0.0.0.0:{OPC_PORT}")
    print(f"[{get_log_ts()}] ℹ️  Namespace Index (ns) para a tabela: {idx}")

    async with server:
        while True:
            while not data_queue.empty():
                updates = data_queue.get()
                for key, val in updates.items():
                    if key in control.nodes:
                        try:
                            # Envia como Double para manter precisão decimal
                            await control.nodes[key].write_value(ua.Variant(float(val), ua.VariantType.Double))
                        except Exception as e:
                            print(f"[{get_log_ts()}] ❌ Erro OPC: {key} -> {e}")
            await asyncio.sleep(0.1)


# ----------------- WEBSOCKET LÓGICA ----------------- #

def send_sockjs(ws, data):
    ws.send(json.dumps([json.dumps(data)]))


def authenticate_ws(ws):
    try:
        res = requests.post(f"{PRINTER_URL}/api/login", json={"passive": True},
                            headers={"X-Api-Key": API_KEY}, timeout=5)
        if res.status_code == 200:
            login_data = res.json()
            send_sockjs(ws, {"auth": f"{login_data['name']}:{login_data['session']}"})
            send_sockjs(ws, {"throttle": 0})
    except:
        pass


def on_message(ws, message):
    if message.startswith('a'):
        try:
            payloads = json.loads(message[1:])
            for p in payloads:
                data = json.loads(p) if isinstance(p, str) else p
                if control.running_event.is_set():
                    now_utc = datetime.now(TIMEZONE_UTC)
                    ts = now_utc.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                    with control.buffer_lock:
                        control.buffer.append({"ts": ts, "msg": data})

                if "connected" in data: authenticate_ws(ws)

                if "current" in data:
                    current = data["current"]
                    updates = {}
                    if current.get("temps"):
                        t = current["temps"][0]
                        if "tool0" in t:
                            act, tar = float(t["tool0"].get("actual", 0)), float(t["tool0"].get("target", 0))
                            updates["nozzle_temp"], updates["nozzle_target"], updates[
                                "nozzle_delta"] = act, tar, act - tar
                        if "bed" in t:
                            act_b, tar_b = float(t["bed"].get("actual", 0)), float(t["bed"].get("target", 0))
                            updates["bed_temp"], updates["bed_target"], updates[
                                "bed_delta"] = act_b, tar_b, act_b - tar_b

                    for log_line in current.get("logs", []):
                        if "X:" in log_line and "Y:" in log_line and control.m114_pending:
                            pos = re.search(r"X:([-\d.]+)\s+Y:([-\d.]+)\s+Z:([-\d.]+)\s+E:([-\d.]+)", log_line)
                            if pos:
                                updates["x"], updates["y"], updates["z"], updates["extrusion_level"] = map(float,
                                                                                                           pos.groups())
                                control.m114_pending = False

                        speed = re.search(r"(?:FR|Flow|Speed):\s*([\d.]+)%", log_line, re.IGNORECASE)
                        if speed:
                            val = float(speed.group(1))
                            updates["speed_factor"] = val
                            if control.speed_factor_fixed is None:
                                control.speed_factor_fixed = val

                    if updates: data_queue.put(updates)
        except Exception as e:
            print(f"[{get_log_ts()}] ❌ Erro WS: {e}")


def start_ws():
    sid = f"{random.randrange(0, 1000):03d}"
    uid = str(uuid.uuid4())[:8]
    ws_url = f"ws://{PRINTER_URL.replace('http://', '')}/sockjs/{sid}/{uid}/websocket"
    ws = websocket.WebSocketApp(ws_url, on_message=on_message)
    threading.Thread(target=ws.run_forever, daemon=True).start()


# ----------------- LOOP DE COMANDOS ----------------- #

def command_loop():
    headers = {"X-Api-Key": API_KEY}
    while control.running_event.is_set():
        try:
            control.m114_pending = True
            requests.post(f"{PRINTER_URL}/api/printer/command", json={"command": "M114"}, headers=headers, timeout=5)
            if control.speed_factor_fixed is None:
                requests.post(f"{PRINTER_URL}/api/printer/command", json={"command": "M220"}, headers=headers,
                              timeout=5)

            # Espera resposta ou timeout de 5s
            start_wait = time.time()
            while control.m114_pending and (time.time() - start_wait) < 5:
                if not control.running_event.is_set(): return
                time.sleep(0.1)

            time.sleep(5)  # Intervalo entre pedidos M114
        except:
            time.sleep(2)


# ----------------- FLASK ROUTES ----------------- #

@app.route('/start', methods=['POST'])
def start():
    if not control.running_event.is_set():
        with control.buffer_lock: control.buffer.clear()
        control.speed_factor_fixed = None
        control.running_event.set()
        threading.Thread(target=command_loop, name="PrinterLoop", daemon=True).start()
        return jsonify({"status": "Started"}), 200
    return jsonify({"status": "Already running"}), 200


@app.route('/stop', methods=['POST'])
def end():
    control.running_event.clear()
    return jsonify({"status": "Stopped"}), 200


@app.route('/get_buffer', methods=['GET'])
def get_buffer():
    with control.buffer_lock:
        data_to_send = list(control.buffer)
        # save_to_local_storage(data_to_send) TODO Debug purposes
        control.buffer.clear()
    return jsonify(data_to_send), 200


if __name__ == "__main__":
    start_ws()
    threading.Thread(target=lambda: asyncio.run(opc_server_task()), daemon=True).start()
    app.run(host='0.0.0.0', port=FLASK_PORT, debug=False, use_reloader=False)