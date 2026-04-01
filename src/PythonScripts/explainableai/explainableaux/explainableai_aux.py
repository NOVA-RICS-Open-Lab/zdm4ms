# -*- coding: utf-8 -*-
# models_aux.py
from flask import Flask, request, jsonify
import pandas as pd
import joblib
import os
import lime
import lime.lime_tabular
from sklearn.model_selection import train_test_split

from dataclasses import dataclass
from typing import List
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.decomposition import PCA

import traceback

import base64

PORT = int(os.getenv("PORT", 5005))

Z1RAWDATA = os.getenv("TRANINING_DATA_CSV_Z_1", "modelstrainingdata/processed_z_lower_1.csv")
Z4RAWDATA = os.getenv("TRANINING_DATA_CSV_Z_4", "modelstrainingdata/processed_10percent.csv")
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
df_z1 = pd.read_csv(Z1RAWDATA, encoding="utf-8")
if df_z1.empty:
    raise ValueError("Erro: O dataset está vazio.")
le = LabelEncoder()
y_z1 = le.fit_transform(df_z1["Resultado"])
x_z1 = df_z1[features_z1].values.copy()
X_train_z1, X_test_z1, y_train_z1, y_test_z1 = train_test_split(
    x_z1, y_z1, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y_z1
)

lime_explainer_z1 = lime.lime_tabular.LimeTabularExplainer(
    training_data=X_train_z1,
    feature_names=features_z1,
    class_names=['NOK', 'OK'],
    mode='classification'
)

def prediction_z1(x):
    return pipe_z1.predict_proba(pd.DataFrame(x, columns=features_z1))

def explanation_z1(y):
    return lime_explainer_z1.explain_instance(
        data_row=y,
        predict_fn=prediction_z1,
        num_features=5
    )

#--------------------------------//--------------------------------#
# Z = 4

# Dimensões por tipo de peça
dimensions_by_type_z_4 = {
    'QUADRADO': ['d1', 'd2', 'd3'],
    'RETANGULO': ['d1', 'd2', 'd3'],
    'L': ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7']
}

feature_columns_z_4 = [
        'Speed Factor', 'Média Delta temp_nozzle', 'Máximo Delta temp_nozzle',
        'Média Delta Mesa (°C)', 'Tempo Fora do Intervalo Extrusora (%)',
        'Taxa de Extrusão (mm/min)', 'Tempo Ativo de Extrusão (%)',
        'Variação X', 'Variação Y', 'Variação Z', 'X_max', 'X_min',
        'Y_max', 'Y_min', 'Média PWM Extrusora', 'Desvio Padrão PWM Extrusora',
        'Média PWM Bed', 'Desvio Padrão PWM Bed'
    ]

# pipe_z4 = joblib.load(Z4PIPE)
df_z4 = pd.read_csv(Z4RAWDATA, encoding="utf-8")

if df_z4.empty:
    raise ValueError("Erro: O dataset está vazio.")

lime_explainers_z4 = {}

for piece_type in dimensions_by_type_z_4.keys():

    df_piece = df_z4[df_z4['Tipo de Peça'] == piece_type].copy()
    if df_piece.empty:
        print(f"Nenhum dado encontrado para {piece_type}.")

    x = df_piece[feature_columns_z_4]
    y = df_piece[dimensions_by_type_z_4[piece_type]]
    if y.isna().any().any():
        print(f"Dados inválidos encontrados para {piece_type}.")
        break

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(x)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)
    
    lime_explainers_z4[piece_type]= lime.lime_tabular.LimeTabularExplainer(
            training_data=X_train,
            feature_names=feature_columns_z_4,
            class_names=dimensions_by_type_z_4[piece_type],
            mode='regression'
        )


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

@app.route('/explain1', methods=['POST'])
def explain1():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")

        if not isinstance(data, list):
            return jsonify({"error": "Esperado uma lista de amostras JSON"}), 400

        df = pd.DataFrame(data)
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Calcula TODAS as features de z=1 
        features_full = compute_features(df, mode='z1')
        # print("[INFO] Features calculadas com sucesso.")
        # print("[INFO] Features:\n", features_full.to_string(index=False))

        X_in = features_full.reindex(columns=features_z1).astype(float).fillna(0.0)

        explanation = explanation_z1(X_in.values[0])

        clean_dict = {
            "NOK" : float(explanation.predict_proba[0]),
            "OK" : float(explanation.predict_proba[1])
        }

        return jsonify({
            "explanationhtml": base64.b64encode(explanation.as_html().encode('utf-8')).decode('utf-8'),
            "explanationdict": {
                "features": explanation.as_list(),
                "prediction": clean_dict
            }
        }), 200

    except Exception as e:
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route('/explain4', methods=['POST'])
def explain4():
    try:
        data = request.get_json()
        print("[INFO] Dados recebidos com sucesso.")

        # Verificar se é uma lista de amostras
        if not isinstance(data.get("data"), list):
            return jsonify({"error": "Esperado uma lista de amostras JSON"}), 400

        productType = data.get("productType").upper()

        # Converter para DataFrame
        df = pd.DataFrame(data.get("data"))

        # Garantir que timestamp está no formato datetime
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])

        # Calcular features
        features_df = compute_features(df, mode='z4')
        # print("[INFO] Features calculadas com sucesso.")    
        # print("[INFO] Features:\n", features_df.to_string(index=False))

        X_scaled = z_4_scalers[productType].transform(features_df)

        print(f"Fazer explanation LIME para {productType}")
        
        if productType in ['QUADRADO', 'RETANGULO']:
            output_names = ['Comprimento', 'Largura', 'Altura']
        elif productType == 'L':
            output_names = [
                'Comprimento Externo', 'Largura Externa', 
                'Comprimento Interno 1', 'Comprimento Interno 2', 
                'Largura Interna 1', 'Largura Interna 2', 
                'Altura'
            ]

        explanationsDataDict = {}
        predictions = {}
        
        html_content = "<html><head><title>Combined LIME Explanations</title></head><body>"
            
        for i, target_name in enumerate(output_names):
            
            def pred_z4(x):
                preds = z_4_models[productType].predict(pd.DataFrame(x, columns=feature_columns_z_4))
                return preds[:, i]

            explanation = lime_explainers_z4[productType].explain_instance(
                data_row=X_scaled[0],
                predict_fn=pred_z4,
                num_features=18
            )
            
            explanationsDataDict[target_name] = explanation.as_list()
            predictions[target_name] = explanation.predicted_value
            
            html_content += f"<hr style='border-top: 2px solid #bbb; margin: 30px 0;'>"
            html_content += f"<h2 style='font-family:sans-serif; padding-left: 10px;'>Measurement: {target_name}</h2>"
            
            html_content += explanation.as_html(predict_proba=False)

        html_content += "</body></html>"
                        
        print(f"[INFO] Successfully created combined explanations to HTML file")
        
        clean_dict = {}

        for target_name, features_list in explanationsDataDict.items():
             
            clean_dict[target_name] = {
                "features": [ [f, float(w)] for f, w in features_list ],
                "predicted_value": float(predictions[target_name])
            }
        
        print(f"[INFO] Successfully created explanations data dictionary")

        return jsonify({
            "explanationhtml": base64.b64encode(html_content.encode('utf-8')).decode('utf-8'),
            "explanationdict": clean_dict,
        }), 200

    except Exception as e:
        traceback.print_exc()
        print(f"[ERRO] {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
