import os
import csv
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, field_validator, ConfigDict
import uvicorn

app = FastAPI()

CSV_DIR = "data"
if not os.path.exists(CSV_DIR):
    os.makedirs(CSV_DIR)

CSV_FILENAME = os.getenv("CSV_FILENAME", "test.csv")
PORT = int(os.getenv("PORT", "5004"))
CSV_FILE_PATH = os.path.join(CSV_DIR, CSV_FILENAME)

CSV_FIELDNAMES = [
    "timestamp", "temp_nozzle", "temp_target_nozzle", "temp_delta_nozzle",
    "pwm_nozzle", "temp_bed", "temp_target_bed", "temp_delta_bed",
    "pwm_bed", "X", "Y", "Z", "E", "speed_factor", "filename"
]

class PrintData(BaseModel):
    # Permite que o modelo aceite objetos datetime ou strings
    timestamp: str
    temp_nozzle: Optional[float] = None
    temp_target_nozzle: Optional[float] = None
    temp_delta_nozzle: Optional[float] = None
    pwm_nozzle: Optional[int] = None
    temp_bed: Optional[float] = None
    temp_target_bed: Optional[float] = None
    temp_delta_bed: Optional[float] = None
    pwm_bed: Optional[int] = None
    X: Optional[float] = None
    Y: Optional[float] = None
    Z: Optional[float] = None
    E: Optional[float] = None
    speed_factor: float
    filename: str

    # --- ATUALIZAÇÃO PYDANTIC V2: Migração do @validator para @field_validator ---
    @field_validator('filename', mode='before')
    @classmethod
    def strip_extension(cls, v):
        if isinstance(v, str):
            return v.rsplit('.', 1)[0] if '.' in v else v
        return v

@app.post("/append")
async def append_to_csv(data: PrintData):
    try:
        # Validação de timestamp compatível com o que vimos antes
        # Tenta o formato simples, se falhar tenta o ISO que tinha o 'T' e 'Z'
        try:
            datetime.strptime(data.timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            try:
                # Converte ISO (2026-03-05T19:41:15.866Z) para o formato do seu CSV
                dt = datetime.fromisoformat(data.timestamp.replace('Z', '+00:00'))
                data.timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Formato de timestamp inválido. Use YYYY-MM-DD HH:MM:SS ou ISO8601."
                )

        file_exists = os.path.isfile(CSV_FILE_PATH)
        
        # --- ATUALIZAÇÃO PYDANTIC V2: Substituição de .dict() por .model_dump() ---
        data_dict = data.model_dump(by_alias=True)

        with open(CSV_FILE_PATH, 'a', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=CSV_FIELDNAMES)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data_dict)
            
        return {"success": True, "message": f"Dados adicionados a {CSV_FILENAME}"}
    except HTTPException as he:
        raise he
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
                if 'timestamp' in row and row['timestamp']:
                    try:
                        row_timestamp_dt = datetime.strptime(row['timestamp'], "%Y-%m-%d %H:%M:%S")
                        if row_timestamp_dt > start_time_dt:
                            processed_row = {}
                            numeric_keys = [
                                "temp_nozzle", "temp_target_nozzle", "temp_delta_nozzle", "pwm_nozzle",
                                "temp_bed", "temp_target_bed", "temp_delta_bed", "pwm_bed",
                                "X", "Y", "Z", "E", "speed_factor"
                            ]
                            for key, value in row.items():
                                if value is None or value == '':
                                    processed_row[key] = None
                                    continue
                                
                                if key in numeric_keys:
                                    try:
                                        processed_row[key] = float(value)
                                    except (ValueError, TypeError):
                                        processed_row[key] = value 
                                else:
                                    processed_row[key] = value 
                            results.append(processed_row)
                    except (ValueError, TypeError):
                        continue
        print(results)
        return results
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=PORT)