import os
import csv
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status, Query
from pydantic import BaseModel, validator
import uvicorn

app = FastAPI()

# Diretório para armazenar os arquivos CSV
CSV_DIR = "data"
if not os.path.exists(CSV_DIR):
    os.makedirs(CSV_DIR)

CSV_FILENAME = os.getenv("CSV_FILENAME", "test.csv")
PORT = int(os.getenv("PORT", "5004"))
    

# Nome do arquivo CSV "hardcoded"

CSV_FILE_PATH = os.path.join(CSV_DIR, CSV_FILENAME)

# Ordem das colunas no CSV
CSV_FIELDNAMES = [
    "timestamp",
    "temp_nozzle",
    "temp_target_nozzle",
    "temp_delta_nozzle",
    "pwm_nozzle",
    "temp_bed",
    "temp_target_bed",
    "temp_delta_bed",
    "pwm_bed",
    "X",
    "Y",
    "Z",
    "E",
    "speed_factor",
    "filename"
]

class PrintData(BaseModel):
    timestamp: str
    temp_nozzle: float
    temp_target_nozzle: float
    temp_delta_nozzle: float
    pwm_nozzle: int
    temp_bed: float
    temp_target_bed: float
    temp_delta_bed: float
    pwm_bed: int
    X: Optional[float] = None
    Y: Optional[float] = None
    Z: Optional[float] = None
    E: Optional[float] = None
    speed_factor: Optional[float] = None
    filename: str

    @validator('filename', pre=True)
    def strip_extension(cls, v):
        if isinstance(v, str):
            return v.rsplit('.', 1)[0] if '.' in v else v
        return v

@app.post("/append")
async def append_to_csv(data: PrintData):
    """
    Adiciona dados ao arquivo CSV fixo (test.csv).
    Cria o arquivo e o cabeçalho se não existirem, usando a ordem de colunas definida.
    O 'filename' no JSON é o nome da impressão, não do arquivo.
    O timestamp é armazenado como string (YYYY-MM-DD HH:MM:SS).
    """
    try:
        # Valida o formato do timestamp
        datetime.strptime(data.timestamp, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de timestamp inválido. Use YYYY-MM-DD HH:MM:SS."
        )

    try:
        file_exists = os.path.isfile(CSV_FILE_PATH)
        
        # Converte o modelo Pydantic para um dicionário para o csv.DictWriter
        data_dict = data.dict(by_alias=True)

        with open(CSV_FILE_PATH, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_dict)
            
        return {"success": True, "message": f"Dados adicionados a {CSV_FILENAME}"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

class GetRequest(BaseModel):
    start_time: str

@app.post("/get")
async def get_from_csv(request_data: GetRequest):
    start_time = request_data.start_time

    try:
        start_time_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'start_time' deve ser uma string no formato YYYY-MM-DD HH:MM:SS."
        )

    if not os.path.isfile(CSV_FILE_PATH):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Arquivo de dados '{CSV_FILENAME}' não encontrado.")

    results = []
    try:
        with open(CSV_FILE_PATH, 'r', newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Verifica se a linha corresponde ao timestamp
                if 'timestamp' in row and row['timestamp']:
                    try:
                        row_timestamp_dt = datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S")
                        if row_timestamp_dt > start_time_dt:
                            # Processa cada linha para conversão de tipo e tratamento de nulos
                            processed_row = {}
                            numeric_keys = [
                                "temp_nozzle", "temp_target_nozzle", "temp_delta_nozzle", "pwm_nozzle",
                                "temp_bed", "temp_target_bed", "temp_delta_bed", "pwm_bed",
                                "X", "Y", "Z", "E", "speed_factor"
                            ]
                            for key, value in row.items():
                                # Converte string vazia ou None para None (que se torna null em JSON)
                                if value is None or value == '':
                                    processed_row[key] = None
                                    continue
                                
                                # Tenta converter para float se a chave for numérica
                                if key in numeric_keys:
                                    try:
                                        processed_row[key] = float(value)
                                    except (ValueError, TypeError):
                                        processed_row[key] = value # Mantém o valor original se a conversão falhar
                                else:
                                    processed_row[key] = value # Mantém o valor para chaves não numéricas
                            results.append(processed_row)
                    except (ValueError, TypeError):
                        # Ignora linhas com timestamp mal formatado ou que não podem ser convertidas
                        continue
        return results
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=PORT)