# -*- coding: utf-8 -*-
# models_aux.py
import pandas as pd
import joblib
import lime
import lime.lime_tabular
from sklearn.model_selection import train_test_split

from dataclasses import dataclass
from typing import List
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.decomposition import PCA

import traceback

Z1RAWDATA = "modelstrainingdata/processed_z_lower_1.csv"
Z4RAWDATA = "modelstrainingdata/processed_10percent.csv"
Z1PIPE = "models/ok_nok_top5_pca_aug.joblib"
Z4MODELL = "models/model_l.joblib"
Z4MODELQUADRADO = "models/model_l.joblib"
Z4MODELRETANGULO = "models/model_l.joblib"

RANDOM_STATE = 42
TEST_SIZE = 0.15

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

joblib.dump(lime_explainer_z1, "limexaimodels/lime_explainer_z1.joblib")

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

    joblib.dump(lime_explainers_z4[piece_type], f"limexaimodels/lime_explainer_z4_{piece_type.lower()}.joblib")

# lime_explainers_z4 = {
#     'QUADRADO': lime explainer para quadrado,
#     'RETANGULO': lime explainer para retangulo,
#     'L': lime explainer para l
# }
