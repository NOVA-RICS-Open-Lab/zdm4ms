from flask import Flask, request, jsonify
import requests
import numpy as np
from datetime import datetime, timezone, timedelta
import os

# Constantes da montagem
BOX_LENGTH = float(os.getenv("BOX_LENGTH", 99.5))
BOX_WIDTH = float(os.getenv("BOX_WIDTH", 100))
SLOT_SIZE = float(os.getenv("SLOT_SIZE", 50))
MIN_GAP = float(os.getenv("MIN_GAP", 0.3))
FIT_GAP = float(os.getenv("FIT_GAP", 0.2))


PORT = int(os.getenv("PORT", 5006))

# Initialize Flask application
app = Flask(__name__)

# Constants for URLs and API keys
AAS_URL = os.getenv("AAS_URL", "192.168.0.10:5011") # Casa
AAS_URL = os.getenv("AAS_URL", "192.168.2.90:5011") # Lab
MIDDLEWARE_URL = "http://" + os.getenv("MIDDLEWARE_URL", "192.168.0.10") # Casa
MIDDLEWARE_URL = "http://" + os.getenv("MIDDLEWARE_URL", "192.168.2.90") # Lab

TYPE_QUADRADO = "Quadrado"
TYPE_L = "L"
TYPE_RETANGULO = "Retangulo"
TYPE_CAIXA = "Caixa"
TYPE_TAMPA = "Tampa"

def log(tipo, origem, msg):
    timestamp =  datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{tipo.upper()}] [{origem}] {msg}")

def ParseMeasurementsFromAAS(measurements):
    parsed = []

    for entry in measurements:
        for piece_id_str, info in entry.items():
            piece_id = int(piece_id_str)
            piece_type = info["type"]
            dims = []

            for dim in info["dimensions"]:
                for value in dim.values():
                    if value == "Undefined":
                        dims.append("Undefined")
                    else:
                        dims.append(float(value))

            parsed.append({
                "id_peça": piece_id,
                "tipo": piece_type,
                "dimensoes": dims
            })

    return parsed

def CheckAssembly(products, box_length, box_width):
    # --- BOX DIMENSION CLEANING ---
    # If Flask/Middleware sends {'value': 200}, extract the number
    if isinstance(box_length, dict):
        box_length = float(list(box_length.values())[0])
    else:
        box_length = float(box_length)
        
    if isinstance(box_width, dict):
        box_width = float(list(box_width.values())[0])
    else:
        box_width = float(box_width)
    # ------------------------------

    VALID_COMBINATIONS = [
        (TYPE_QUADRADO, 4),
        (TYPE_RETANGULO, 2),
        (TYPE_RETANGULO, 1, TYPE_QUADRADO, 2),
        (TYPE_L, 1, TYPE_QUADRADO, 1)
    ]
    
    piece_counts = {}
    for piece in products:
        t = piece["type"]
        piece_counts[t] = piece_counts.get(t, 0) + 1

    print(f"QUADRADOS: {piece_counts.get(TYPE_QUADRADO)}, RETANGULOS: {piece_counts.get(TYPE_RETANGULO)}, LS: {piece_counts.get(TYPE_L)}")
    if piece_counts.get(TYPE_QUADRADO) == 4:
        montagem_tipo = "4 QUADRADOS"
    elif piece_counts.get(TYPE_RETANGULO) == 2:
        montagem_tipo = "2 RETANGULOS"
    elif piece_counts.get(TYPE_RETANGULO) == 1 and piece_counts.get(TYPE_QUADRADO) == 2:
        montagem_tipo = "1 RETANGULO + 2 QUADRADOS"
    elif piece_counts.get(TYPE_L) == 1 and piece_counts.get(TYPE_QUADRADO) == 1:
        montagem_tipo = "1L + 1 QUADRADO"
    else:
        montagem_tipo = "Unknown"

    piece_counts = {}
    piece_types = {}
    dimensions = {}

    for piece in products:
        p_id = piece['id']
        p_type = piece['type']
        
        # --- PIECE DIMENSION CLEANING ---
        raw_dims = piece['dimensions']
        clean_dims = []
        for d_dict in raw_dims:
            if isinstance(d_dict, dict):
                clean_dims.append(float(list(d_dict.values())[0]))
            else:
                clean_dims.append(float(d_dict))
        
        piece_types[p_id] = p_type
        dimensions[p_id] = clean_dims
        piece_counts[p_type] = piece_counts.get(p_type, 0) + 1

    # 1. Slot Validation
    total_slots = 0
    for p_type, count in piece_counts.items():
        if p_type == TYPE_QUADRADO: total_slots += count * 1
        elif p_type == TYPE_RETANGULO: total_slots += count * 2
        elif p_type == TYPE_L: total_slots += count * 3

    if total_slots != 4:
        return False, f"Total de slots ({total_slots}) diferente de 4.", montagem_tipo

    # 2. Pattern Matching
    is_valid = any(
        (len(combo) == 2 and piece_counts.get(combo[0], 0) == combo[1]) or
        (len(combo) == 4 and piece_counts.get(combo[0], 0) == combo[1] and piece_counts.get(combo[2], 0) == combo[3])
        for combo in VALID_COMBINATIONS
    )
    if not is_valid:
        return False, f"Combinação de peças {piece_counts} não é válida.", montagem_tipo

    # 3. Grid Allocation
    grid = np.zeros((2, 2), dtype=int)
    piece_positions = {}
    sorted_pieces = sorted(dimensions.items(), key=lambda x: -({TYPE_L: 3, TYPE_RETANGULO: 2, TYPE_QUADRADO: 1}[piece_types[x[0]]]))

    for p_id, dims in sorted_pieces:
        p_type = piece_types[p_id]
        fits = False
        d0, d1 = dims[0], dims[1]

        if p_type == TYPE_QUADRADO:
            for i in range(2):
                for j in range(2):
                    if grid[i, j] == 0 and d0 <= (SLOT_SIZE - MIN_GAP) and d1 <= (SLOT_SIZE - MIN_GAP):
                        grid[i, j], piece_positions[p_id], fits = 1, [(i, j)], True
                        break
                if fits: break

        elif p_type == TYPE_RETANGULO:
            for i in range(2): # Horizontal
                if grid[i, 0] == 0 and grid[i, 1] == 0 and d0 <= (box_length - MIN_GAP) and d1 <= (SLOT_SIZE - MIN_GAP):
                    grid[i, 0] = grid[i, 1] = 1
                    piece_positions[p_id], fits = [(i, 0), (i, 1)], True
                    break
            if not fits: # Vertical
                for j in range(2):
                    if grid[0, j] == 0 and grid[1, j] == 0 and d1 <= (box_width - MIN_GAP) and d0 <= (SLOT_SIZE - MIN_GAP):
                        grid[0, j] = grid[1, j] = 1
                        piece_positions[p_id], fits = [(0, j), (1, j)], True
                        break

        elif p_type == TYPE_L:
            if grid[0, 0] == 0 and grid[0, 1] == 0 and grid[1, 0] == 0:
                grid[0, 0] = grid[0, 1] = grid[1, 0] = 1
                piece_positions[p_id], fits = [(0, 0), (0, 1), (1, 0)], True
            elif grid[0, 0] == 0 and grid[0, 1] == 0 and grid[1, 1] == 0:
                grid[0, 0] = grid[0, 1] = grid[1, 1] = 1
                piece_positions[p_id], fits = [(0, 0), (0, 1), (1, 1)], True

        if not fits: return False, f"Sem espaço para {p_type} {p_id}", montagem_tipo

    # 4. Final Clearance Check
    row_lengths = np.zeros((2, 2))
    col_widths = np.zeros((2, 2))

    for p_id, positions in piece_positions.items():
        dims = dimensions[p_id]
        p_type = piece_types[p_id]
        d0, d1 = dims[0], dims[1]

        if p_type == TYPE_QUADRADO:
            i, j = positions[0]
            row_lengths[i, j], col_widths[i, j] = d0, d1
        elif p_type == TYPE_RETANGULO:
            if positions[0][0] == positions[1][0]:
                i = positions[0][0]
                row_lengths[i, 0] = row_lengths[i, 1] = d0 / 2
                col_widths[i, 0] = col_widths[i, 1] = d1
            else:
                j = positions[0][1]
                row_lengths[0, j] = row_lengths[1, j] = d0
                col_widths[0, j] = col_widths[1, j] = d1 / 2
        elif p_type == TYPE_L:
            d2 = dims[2] if len(dims) > 2 else d0/2
            row_lengths[0, 0] = row_lengths[0, 1] = d0 / 2
            col_widths[0, 0] = col_widths[0, 1] = d2
            idx = 0 if (1, 0) in positions else 1
            row_lengths[1, idx], col_widths[1, idx] = d2, d1 - d2

    # Calculation of total side dimensions
    sides = [
        row_lengths[0, :].sum(), row_lengths[1, :].sum(),
        col_widths[:, 0].sum(), col_widths[:, 1].sum()
    ]
    
    limit_x, limit_y = box_length - FIT_GAP, box_width - FIT_GAP
    if any(s > limit_x for s in sides[:2]) or any(s > limit_y for s in sides[2:]):
        return False, "Montagem não cabe na caixa com a folga exigida.", montagem_tipo

    return True, None, montagem_tipo

def AASCreateProduct(destination, msg):

    payload = {
        "destination": destination,    
        "msg": msg
    }
    
    print(payload)
    
    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/createproduct", json=payload, timeout=10)
    response.raise_for_status()
    if not response.status_code in (200, 201):
        log("ERRO", "CREATE_PRODUCT", f"Falha ao criar produto: {response.text}")
        with app.app_context():
            return jsonify({"error": "Failed to create product"}), 500
    return response

def AASGetProductMeasurements(destination, id):
    payload = {
        "destination": destination,
        "msg": {
            "id": id
        },
    }

    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/getmeasurements", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code != 200:
        log("ERRO", "MEASUREMENTS", f"Erro a pedir medidas, codigo retornado: {response.status_code}")
    
    if(response.json()['message'] == "Product still printing"):
        return response.json()['message']
        
    return response.json()['Response from Swagger']

def AASGetProductType(destination, id):
    payload = {
        "destination": destination,
        "msg": {
            "id": id
        },
    }

    response = requests.post(f"{MIDDLEWARE_URL}:1880/aas/getproducttype", json=payload, timeout=10)
    response.raise_for_status()
    if response.status_code == 200:
        log("INFO", "MEASUREMENTS", f"Tipo do produto com id {id}, recebido: {response}")
    else:
        log("ERRO", "MEASUREMENTS", f"Erro a pedir tipo de produto, codigo retornado: {response.status_code}")
    return response.json()['Response from Swagger']

# Post template
# {
#     "destination": "192.168.2.90:5011"
#     "msg": {
#         "productid": "80",
#         "ids": [1, 2, 3, 4, 5, 6]
#     }
# }
@app.route('/assembly', methods=['POST'])
def assembly():
    data = request.json
    # DEBUG print(f"Received assembly request with data: {data}")
    subProductsids = data.get("ids", [])
    newCompleteProductid = data.get("productid", None)

    products = []
    
    productsAreDonePrinting = True
    
    for id in subProductsids:
        
        measurements = AASGetProductMeasurements(AAS_URL, id)
        
        print(measurements)
        
        if (measurements == "Product still printing"):
            if (productsAreDonePrinting):
                productsAreDonePrinting = False
                products = []
                
            products.append(id)        
        
        if (productsAreDonePrinting):        
            products.append({
                "id": id,
                "type": AASGetProductType(AAS_URL, id),
                "dimensions": AASGetProductMeasurements(AAS_URL, id)
            })

    if (not productsAreDonePrinting):    
        # return jsonify({"message": f"Products {products} are in early printing (z<4)"}), 200
        return jsonify({"message": f" Os Produtos {products} ainda estao em impressao (z<4)"}), 200
    
    # DEBUG print(f"\n\nProducts debug: {products}\n\n")

    boxDimensions = None
    filteredProducts = []
    tampaExists = False

    for product in products:
        if product["type"] == "Caixa":
            boxDimensions = product["dimensions"]
            if boxDimensions is None:
                return jsonify({"error": "No box product was introduced"}), 200
        elif product["type"] != "Tampa":
            filteredProducts.append(product)
        else:
            tampaExists = True
    
    if(not tampaExists):
        return jsonify({"error": "No tampa product was introduced"}), 200

    box_length = boxDimensions[0]
    box_width = boxDimensions[1]
    box_height = boxDimensions[2]

    # DEBUG print(f"\n\n Filtered Products debug: {filteredProducts}\n\n")

    # Verifica se a montagem cabe
    assemblyCheck, reason, assemblyType = CheckAssembly(filteredProducts, box_length, box_width)

    # DEBUG print(f"{assemblyCheck, reason}")
       
    # # Se a montagem for inválida
    if not assemblyCheck:
        return jsonify({"message": f"ERROR {assemblyCheck} with assembly {assemblyType} with reason: {reason}"}), 200
    
    # Caso OK
    msg = {
        "id": newCompleteProductid,
        "type": "Complete",
        "subproducts": subProductsids
    }

    AASCreateProduct(AAS_URL, msg)

    return jsonify({"message": f"New Complete product: {newCompleteProductid} with assembly: {assemblyType}"}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True)