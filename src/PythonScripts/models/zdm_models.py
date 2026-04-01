import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from xgboost import XGBRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')

# === Carregamento do dataset ===
input_file = 'modelstrainingdata/processed_10percent.csv'
try:
    df = pd.read_csv(input_file)
except FileNotFoundError:
    print(f"Arquivo {input_file} não encontrado.")
    exit(1)

# Filtra apenas impressões OK
df = df[df['Resultado'] == 'OK'].copy()
if df.empty:
    print("Nenhum dado com Resultado = OK encontrado.")
    exit(1)

# Dimensões por tipo de peça
dimensions_by_type = {
    'QUADRADO': ['d1', 'd2', 'd3'],
    'RETANGULO': ['d1', 'd2', 'd3'],
    'L': ['d1', 'd2', 'd3', 'd4', 'd5', 'd6', 'd7']
}

# Features
feature_columns = ['Speed Factor', 'Média Delta temp_nozzle', 'Máximo Delta temp_nozzle', 
                   'Média Delta Mesa (°C)', 'Tempo Fora do Intervalo Extrusora (%)', 
                   'Taxa de Extrusão (mm/min)', 'Tempo Ativo de Extrusão (%)', 'Média PWM Extrusora', 
                   'Desvio Padrão PWM Extrusora', 'Média PWM Bed', 'Desvio Padrão PWM Bed']

# Função para avaliar modelos
def avaliar_modelos(X_train, X_test, y_train, y_test):
    resultados = {}
    
    modelos = {
        'Random Forest': RandomForestRegressor(n_estimators=100, random_state=42),
        'XGBoost': XGBRegressor(n_estimators=100, random_state=42),
        'Linear Regression': LinearRegression()
    }
    
    for nome, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        y_pred = modelo.predict(X_test)
        
        # Métricas
        mse = mean_squared_error(y_test, y_pred)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)
        
        resultados[nome] = {
            'MSE': mse,
            'MAE': mae,
            'R2': r2,
            'modelo': modelo
        }
    
    return resultados

def mostrar_resultados(nome_cenario, resultados):
    print(f"\n{nome_cenario}")
    for modelo, metricas in resultados.items():
        print(f"{modelo}: MSE={metricas['MSE']:.4f}, MAE={metricas['MAE']:.4f}, R²={metricas['R2']:.4f}")


# Função simples de Data Augmentation (adiciona ruído gaussiano a X)
def augment_data(X, y, factor=2, noise=0.01):
    X_aug, y_aug = [], []
    for i in range(len(X)):
        for _ in range(factor):
            X_noisy = X[i] + np.random.normal(0, noise, size=X.shape[1])
            X_aug.append(X_noisy)
            y_aug.append(y.iloc[i].values)  # mantém target original
    X_aug = np.array(X_aug)
    y_aug = np.array(y_aug)
    return np.vstack([X, X_aug]), np.vstack([y.values, y_aug])

# Itera sobre cada tipo de peça
for piece_type in ['QUADRADO', 'RETANGULO', 'L']:
    print(f"\n=== Resultados para {piece_type} ===")
    df_piece = df[df['Tipo de Peça'] == piece_type].copy()
    if df_piece.empty:
        print(f"Nenhum dado encontrado para {piece_type}.")
        continue

    X = df_piece[feature_columns]
    y = df_piece[dimensions_by_type[piece_type]]
    if y.isna().any().any():
        print(f"Dados inválidos encontrados para {piece_type}. Ignorando.")
        continue

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=0.2, random_state=42)

    # === 1. Baseline (todas as features) ===
    print("\n-- Baseline (todas as features) --")
    res_baseline = avaliar_modelos(X_train, X_test, y_train, y_test)
    mostrar_resultados("-- Baseline (todas as features) --", res_baseline)

        # === 2. Feature Importance + Top 5 ===
    rf = res_baseline['Random Forest']['modelo']
    xgb = res_baseline['XGBoost']['modelo']
    importances_rf = rf.feature_importances_
    importances_xgb = xgb.feature_importances_

    # Normalização individual
    importances_rf_norm = importances_rf / np.sum(importances_rf)
    importances_xgb_norm = importances_xgb / np.sum(importances_xgb)

    # Soma normalizada (ranking agregado)
    importances = importances_rf_norm + importances_xgb_norm

    feature_ranking = sorted(zip(feature_columns, importances), key=lambda x: x[1], reverse=True)
    top5 = [f[0] for f in feature_ranking[:5]]
    
    print("\n=== Aggregated feature ranking (normalized sum) ===")
    for i, (f, imp) in enumerate(feature_ranking, 1):
        print(f"{i}. {f}: {imp:.4f}")
    
    print("\nTop 5 Features:")
    for f, imp in feature_ranking[:5]:
        print(f"{f}: {imp:.4f}")

    # Plots das importâncias
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    fig.suptitle(f"Feature Importances - {piece_type}", fontsize=14, fontweight='bold')
    axes[0].barh(feature_columns, importances_rf)
    axes[0].set_title("Random Forest")
    axes[0].invert_yaxis()
    axes[1].barh(feature_columns, importances_xgb)
    axes[1].set_title("XGBoost")
    axes[1].invert_yaxis()
    plt.tight_layout()
    plt.show()

    # --- Top 5 ---
    X_top5 = df_piece[top5]
    X_top5_scaled = scaler.fit_transform(X_top5)
    X_train, X_test, y_train, y_test = train_test_split(X_top5_scaled, y, test_size=0.2, random_state=42)

    print("\n-- Feature Selection (Top 5) --")
    res_top5 = avaliar_modelos(X_train, X_test, y_train, y_test)
    mostrar_resultados("-- Feature Selection (Top 5) --", res_top5)

    # --- 3. Data Augmentation (Top 5) ---
    X_aug, y_aug = augment_data(X_top5_scaled, y, factor=3, noise=0.05)
    X_train, X_test, y_train, y_test = train_test_split(X_aug, y_aug, test_size=0.2, random_state=42)

    print("\n-- Data Augmentation (Top 5) --")
    res_da_top5 = avaliar_modelos(X_train, X_test, y_train, y_test)
    mostrar_resultados("-- Data Augmentation (Top 5) --", res_da_top5)

    # --- 4. Data Augmentation + PCA (Top 5) ---
    pca = PCA(n_components=min(len(top5), X_aug.shape[0]))
    X_pca_top5 = pca.fit_transform(X_aug)
    X_train, X_test, y_train, y_test = train_test_split(X_pca_top5, y_aug, test_size=0.2, random_state=42)

    print("\n-- Data Augmentation + PCA (Top 5) --")
    res_da_pca_top5 = avaliar_modelos(X_train, X_test, y_train, y_test)
    mostrar_resultados("-- Data Augmentation + PCA (Top 5) --", res_da_pca_top5)

    # --- 5. Data Augmentation + PCA (Todas as features) ---
    X_aug_all, y_aug_all = augment_data(X_scaled, y, factor=3, noise=0.05)
    pca = PCA(n_components=min(len(feature_columns), X_aug_all.shape[0]))
    X_pca_all = pca.fit_transform(X_aug_all)
    X_train, X_test, y_train, y_test = train_test_split(X_pca_all, y_aug_all, test_size=0.2, random_state=42)

    print("\n-- Data Augmentation + PCA (todas as features) --")
    res_da_pca_all = avaliar_modelos(X_train, X_test, y_train, y_test)
    mostrar_resultados("-- Data Augmentation + PCA (todas as features) --", res_da_pca_all)
