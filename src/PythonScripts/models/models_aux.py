from flask import Flask, request, jsonify
import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split

from dataclasses import dataclass
from typing import List
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.decomposition import PCA

import traceback

PORT = int(os.getenv("PORT", 5002))

Z1DATA = os.getenv("TRANINING_DATA_CSV_Z_1", "modelstrainingdata/processed_z_lower_1.csv")
Z4DATA = os.getenv("TRANINING_DATA_CSV_Z_4", "modelstrainingdata/processed_10percent.csv")
Z1PIPE = os.getenv("PIPELINE_Z_1", "models/ok_nok_top5_pca_aug.joblib")
Z4MODELL = os.getenv("MODEL_Z_4_L", "models/model_l.joblib")
Z4MODELQUADRADO = os.getenv("MODEL_Z_4_QUADRADO", "models/model_quadrado.joblib")
Z4MODELRETANGULO = os.getenv("MODEL_Z_4_RETANGULO", "models/model_retangulo.joblib")
Z4SCALERL = os.getenv("SCALER_Z_4_L", "models/scaler_l.joblib")
Z4SCALERQUADRADO = os.getenv("SCALER_Z_4_QUADRADO", "models/scaler_quadrado.joblib")
Z4SCALERRETANGULO = os.getenv("SCALER_Z_4_RETANGULO", "models/scaler_retangulo.joblib")

z_4_models = {
    'QUADRADO': joblib.load(Z4MODELQUADRADO),
    'RETANGULO': joblib.load(Z4MODELRETANGULO),
    'L': joblib.load(Z4MODELL)
}

z_4_scalers = {
    'QUADRADO': joblib.load(Z4SCALERQUADRADO),
    'RETANGULO': joblib.load(Z4SCALERRETANGULO),
    'L': joblib.load(Z4SCALERL)
}

RANDOM_STATE = 42
TEST_SIZE = 0.15

app = Flask(__name__)

#--------------------------------//--------------------------------#
# Z = 1

@dataclass
class OKNOKPipeline:
    selected_features: List[str]
    scaler: StandardScaler
    pca: PCA
    model: object  # sklearn estimator

    def predict(self, X_df: pd.DataFrame):
        X_sel = X_df[self.selected_features].copy()
        X_scaled = self.scaler.transform(X_sel)
        X_pca = self.pca.transform(X_scaled)
        return self.model.predict(X_pca)

    def predict_proba(self, X_df: pd.DataFrame):
        if hasattr(self.model, "predict_proba"):
            X_sel = X_df[self.selected_features].copy()
            X_scaled = self.scaler.transform(X_sel)
            X_pca = self.pca.transform(X_scaled)
            return self.model.predict_proba(X_pca)
        raise AttributeError("O modelo não suporta predict_proba.")

pipe_z1 = joblib.load(Z1PIPE)
features_z1 = pipe_z1.selected_features

#--------------------------------//--------------------------------#

def calculate_t_out_of_range(df, threshold=2.0):
    """Calcula o percentual de tempo com temperatura fora do intervalo."""
    out_of_range = df['temp_delta_nozzle'].abs() > threshold
    if len(df) == 0:
        return 0.0
    return (out_of_range.sum() / len(df)) * 100

def calculate_e_active_time(df):
    """Calcula o percentual de tempo com extrusão ativa."""
    if len(df) <= 1:
        return 0.0
    e_changes = (df['E'].diff() != 0) & (df['E'].notna())
    active_intervals = e_changes.sum()
    total_intervals = len(df) - 1
    if total_intervals == 0:
        return 0.0
    return (active_intervals / total_intervals) * 100

def compute_features(samples, mode):
    
    feature_columns_z_4 = [
        'Speed Factor', 'Média Delta temp_nozzle', 'Máximo Delta temp_nozzle',
        'Média Delta Mesa (°C)', 'Tempo Fora do Intervalo Extrusora (%)',
        'Taxa de Extrusão (mm/min)', 'Tempo Ativo de Extrusão (%)',
        'Variação X', 'Variação Y', 'Variação Z', 'X_max', 'X_min',
        'Y_max', 'Y_min', 'Média PWM Extrusora', 'Desvio Padrão PWM Extrusora',
        'Média PWM Bed', 'Desvio Padrão PWM Bed'
    ]
    
    df = pd.DataFrame(samples)
    metrics = {}

    #metricas de z=1  
    metrics['Desvio Padrão temp_nozzle'] = df['temp_delta_nozzle'].std() if df['temp_delta_nozzle'].notna().any() else 0.0
    metrics['Máximo Delta temp_nozzle'] = df['temp_delta_nozzle'].max() if df['temp_delta_nozzle'].notna().any() else 0.0
    metrics['Tempo Fora do Intervalo Extrusora (%)'] = calculate_t_out_of_range(df, threshold=2.0)
    metrics['Média PWM Extrusora'] = df['pwm_nozzle'].mean() if df['pwm_nozzle'].notna().any() else 0.0
    metrics['Média PWM Bed'] = df['pwm_bed'].mean() if df['pwm_bed'].notna().any() else 0.0

    #metricas para z=4
    metrics['Speed Factor'] = df['speed_factor'].mean() if df['speed_factor'].notna().any() else 0.0
    metrics['Média Delta temp_nozzle'] = df['temp_delta_nozzle'].mean() if df['temp_delta_nozzle'].notna().any() else 0.0
    metrics['Média Delta Mesa (°C)'] = df['temp_delta_bed'].mean() if df['temp_delta_bed'].notna().any() else 0.0

    if df['E'].notna().any() and len(df) > 1:
        e_initial = df['E'].iloc[0]
        e_final = df['E'].iloc[-1]
        time_initial = df['timestamp'].iloc[0] if pd.notna(df['timestamp'].iloc[0]) else None
        time_final = df['timestamp'].iloc[-1] if pd.notna(df['timestamp'].iloc[-1]) else None
        if time_initial and time_final:
            time_diff_minutes = (time_final - time_initial).total_seconds() / 60
            metrics['Taxa de Extrusão (mm/min)'] = (e_final - e_initial) / time_diff_minutes if time_diff_minutes > 0 else 0.0
        else:
            metrics['Taxa de Extrusão (mm/min)'] = 0.0
        metrics['Tempo Ativo de Extrusão (%)'] = calculate_e_active_time(df)
    else:
        metrics['Taxa de Extrusão (mm/min)'] = 0.0
        metrics['Tempo Ativo de Extrusão (%)'] = 0.0

    # ADD missing features from old service
    metrics['Variação X'] = df['X'].std() if df['X'].notna().any() else 0.0
    metrics['Variação Y'] = df['Y'].std() if df['Y'].notna().any() else 0.0
    metrics['Variação Z'] = df['Z'].std() if df['Z'].notna().any() else 0.0
    metrics['X_max'] = df['X'].max() if df['X'].notna().any() else 0.0
    metrics['X_min'] = df['X'].min() if df['X'].notna().any() else 0.0
    metrics['Y_max'] = df['Y'].max() if df['Y'].notna().any() else 0.0
    metrics['Y_min'] = df['Y'].min() if df['Y'].notna().any() else 0.0
    metrics['Desvio Padrão PWM Extrusora'] = df['pwm_nozzle'].std() if df['pwm_nozzle'].notna().any() else 0.0
    metrics['Desvio Padrão PWM Bed'] = df['pwm_bed'].std() if df['pwm_bed'].notna().any() else 0.0

    # Seleciona colunas
    if mode == 'z1':
        # Em z1 devolve TODAS as métricas calculadas
        return pd.DataFrame([metrics])
    else:  # z4
        return pd.DataFrame([metrics], columns=feature_columns_z_4)

@app.route('/predict1', methods=['POST'])
def start1():
    
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")

        if not isinstance(data, list):
            return jsonify({"error": "Esperado uma lista de amostras JSON"}), 400

        df = pd.DataFrame(data)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # 1) Calcula TODAS as features de z=1 
        features_full = compute_features(df, mode='z1')
        print("[INFO] Features calculadas com sucesso.")
        print("[INFO] Features:\n", features_full.to_string(index=False))

        X_in = features_full.reindex(columns=features_z1).astype(float).fillna(0.0)
        try:
            proba_ok = float(pipe_z1.predict_proba(X_in)[0][1])
        except AttributeError:
            proba_ok = None

        pred = pipe_z1.predict(X_in)[0]
        print(f"[DEBUG] Pred raw: {pred}, Prob OK: {proba_ok}")

        # Se tens o LabelEncoder guardado e queres texto OK/NOK:
        try:
            le = joblib.load("models/label_encoderv2.joblib")
            pred_label = le.inverse_transform([pred])[0]
        except Exception:
            pred_label = int(pred)

        #Quero inverter o resultado do pred_label, se for OK deve retornar NOK e vice-versa
        if pred_label == "OK":
            pred_label = "NOK"
        elif pred_label == "NOK":
            pred_label = "OK"
            
        return jsonify({
            "prediction": pred_label
        }), 200

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/predict4', methods=['POST'])
def start4():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")

        # Verificar se é uma lista de amostras
        if not isinstance(data, list):
            return jsonify({"error": "Esperado uma lista de amostras JSON"}), 400

        # Converter para DataFrame
        df = pd.DataFrame(data)

        # Garantir que timestamp está no formato datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        filename = df['filename'].iloc[0] if 'filename' in df.columns else "unknown"

        # Mapear filename para tipo de peça (para log)
        if filename.lower() == 'zdm4ms~4':
            piece_type = 'QUADRADO'
        elif filename.lower() == 'zd5b20~1':
            piece_type = 'L'
        elif filename.lower() == 'zd2c72~1':
            piece_type = 'RETANGULO'
        else:
            print(f"Tipo de peça inválido: {filename}")
            return jsonify({"error": "Invalid piece type"}), 400

        # Calcular features
        features_df = compute_features(df, mode='z4')
        print("[INFO] Features calculadas com sucesso.")    
        print("[INFO] Features:\n", features_df.to_string(index=False))

        # Fazer previsão
        X_scaled = z_4_scalers[piece_type].transform(features_df)
        predictions = z_4_models[piece_type].predict(X_scaled)[0]

        # Formatar mensagem de log com dimensões previstas
        if piece_type in ['QUADRADO', 'RETANGULO']:
            log_message = (
                f"Previsão para {piece_type}: "
                f"Comprimento={predictions[0]:.1f}mm, "
                f"Largura={predictions[1]:.1f}mm, "
                f"Altura={predictions[2]:.1f}mm"
            )
        elif piece_type == 'L':
            log_message = (
                f"Previsão para {piece_type}: "
                f"Comprimento Externo={predictions[0]:.1f}mm, "
                f"Largura Externa={predictions[1]:1f}mm, "
                f"Comprimento Interno 1={predictions[2]:.1f}mm, "
                f"Comprimento Interno 2={predictions[3]:.1f}mm, "
                f"Largura Interna 1={predictions[4]:.1f}mm, "
                f"Largura Interna 2={predictions[5]:.1f}mm, "
                f"Altura={predictions[6]:.1f}mm"
            )

        print(log_message)

        return jsonify({
                "prediction": predictions.tolist(),
            }), 200

    except Exception as e:
        traceback.print_exc()
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
