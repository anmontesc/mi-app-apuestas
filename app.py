import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import requests
from io import StringIO
import difflib

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Hybrid", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    .stButton button {width: 100%; border: 1px solid #444; color: white; text-align: left; padding: 15px; margin-bottom: 5px;}
    .stButton button:hover {border-color: #d4af37; color: #d4af37;}
    .scientific-card {background-color: #1e2130; border-left: 5px solid #00b4d8; padding: 15px; margin-bottom: 10px; border-radius: 5px;}
    .math-title {color: #00b4d8; font-weight: bold; font-size: 16px;}
    .math-val {color: white; font-size: 20px; font-weight: bold;}
    .math-desc {color: #aaa; font-size: 12px; font-style: italic;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. MOTOR DE DATOS HISTÓRICOS (Base de Datos)
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_db_historica():
    dfs = []
    temporadas = ['2324', '2425'] 
    ligas_codes = {"🇪🇸 La Liga": "SP1", "🇬🇧 Premier": "E0", "🇮🇹 Serie A": "I1", "🇩🇪 Bundesliga": "D1", "🇫🇷 Ligue 1": "F1"}
    base_url = "https://www.football-data.co.uk/mmz4281/"
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'Referee']
    
    for season in temporadas:
        for nombre_liga, codigo in ligas_codes.items():
            try:
                df = pd.read_csv(f"{base_url}{season}/{codigo}.csv", usecols=lambda c: c in cols)
                df['League'] = nombre_liga
                dfs.append(df)
            except: continue
    
    if not dfs: return None, []
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.dropna(subset=['HomeTeam'])
    return df, df['League'].unique()

# ==========================================
# 2. MOTOR DE PARTIDOS DE HOY (Scraper Robusto)
# ==========================================
@st.cache_data(ttl=1800)
def cargar_partidos_hoy():
    # Intento conectar con FBref usando headers de navegador real
    try:
        url = "https://fbref.com/en/matches/"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Usamos lxml para mayor compatibilidad
            tables = pd.read_html(StringIO(response.text))
            
            # Buscamos la tabla correcta iterando
            for df in tables:
                # FBref suele tener columnas Home y Away
                if 'Home' in df.columns and 'Away' in df.columns:
                    df_clean = df[['Time', 'Home', 'Away', 'Competition']].copy()
                    df_clean = df_clean.dropna(subset=['Home', 'Away'])
                    # Filtramos filas vacías o headers repetidos
                    df_clean = df_clean[df_clean['Home'] != 'Home']
                    if not df_clean.empty:
                        return df_clean
    except Exception as e:
        print(f"Error scraping: {e}")
        return None
    return None

# ==========================================
# 3. UTILS Y MOTORES CIENTÍFICOS (V28)
# ==========================================
def encontrar_equipo_db(nombre_live, lista_db):
    matches = difflib.get_close_matches(nombre_live, lista_db, n=1, cutoff=0.5) # Cutoff bajado para ser más flexible
    return matches[0] if matches else None

def calcular_gap_rating(df, team):
    matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)].tail(10)
    if len(matches) < 5: return 0
    gap = 0
    for _, r in matches.iterrows():
        if r['HomeTeam'] == team: g=r['FTHG']; t=r['HST']; c=r['HC']
        else: g=r['FTAG']; t=r['AST']; c=r['AC']
        gap += (g * 1.0) + (t * 0.4) + (c * 0.2)
    return gap / len(matches)

def predecir_poisson(l_h, l_a):
    mh, ma = 6, 6
    ph = [poisson.pmf(i, l_h) for i in range(mh)]
    pa = [poisson.pmf(i, l_a) for i in range(ma)]
    pm = np.outer(ph, pa)
    return np.sum(np.tril(pm, -1)), np.sum(np.diag(pm)), np.sum(np.triu(pm, 1))

# ==========================================
# 4. INTERFAZ INTELIGENTE (AUTO-FALLBACK)
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")

# --- CARGA DE DATOS ---
with st.spinner("Cargando cerebro..."):
    df_db, ligas_db = cargar_db_historica()
    # Intentamos cargar el live, si falla será None
    df_live = cargar_partidos_hoy()

# --- ESTADO DE LA SESIÓN ---
if 'partido_seleccionado' not in st.session_state:
    st.session_state.partido_seleccionado = None

# --- LÓGICA DE VISUALIZACIÓN ---

# CASO 1: Tenemos datos en vivo -> Mostramos Browser
if df_live is not None and not df_live.empty and st.session_state.partido_seleccionado is None:
    st.sidebar.success("📡 Señal en Vivo: ACTIVA")
    st.markdown("## 📅 Partidos de Hoy")
    
    # Filtro de Ligas Top para limpiar la vista
    top_keywords = ['Premier', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'Champions']
    df_live['EsTop'] = df_live['Competition'].apply(lambda x: any(k in str(x) for k in top_keywords))
    
    comps = df_live.sort_values('EsTop', ascending=False)['Competition'].unique()
    
    for comp in comps:
        matches = df_live[df_live['Competition'] == comp]
        if matches.empty: continue
        
        # Icono según si es top o no
        icon = "🏆" if any(k in str(comp) for k in top_keywords) else "⚽"
        
        with st.expander(f"{icon} {comp}", expanded=("Premier" in str(comp) or "Liga" in str(comp))):
            for _, row in matches.iterrows():
                if st.button(f"🕒 {row['Time']} | {row['Home']} vs {row['Away']}", key=f"btn_{row['Home']}"):
                    st.session_state.partido_seleccionado = {'home': row['Home'], 'away': row['Away']}
                    st.rerun()
    
    st.markdown("---")
    if st.button("⚠️ No encuentro mi partido (Modo Manual)"):
        st.session_state.partido_seleccionado = "MANUAL_MODE"
        st.rerun()

# CASO 2: NO tenemos datos en vivo O el usuario eligió Manual -> Mostramos Selectores
elif df_live is None or df_live.empty or st.session_state.partido_seleccionado == "MANUAL_MODE":
