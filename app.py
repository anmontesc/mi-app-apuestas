import streamlit as st
import pandas as pd
import numpy as np
import datetime
import time

# Librerías NBA
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguedashteamstats, commonteamroster, playergamelog

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Robust", page_icon="🛡️", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    .game-card {
        background-color: #1a1c24;
        border-left: 5px solid #ff5722;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. LOGOS
# ==========================================
def get_team_logo(team_name):
    # Logos básicos para demo
    return "https://cdn-icons-png.flaticon.com/512/1665/1665926.png"

# ==========================================
# 1. MOTOR DE DATOS FÚTBOL
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_datos_futbol():
    dfs = []
    temporadas = ['2324', '2425'] 
    ligas_codes = {"🇪🇸 La Liga": "SP1", "🇬🇧 Premier": "E0", "🇮🇹 Serie A": "I1"}
    base_url = "https://www.football-data.co.uk/mmz4281/"
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
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
    return df.sort_values('Date').reset_index(drop=True), df['League'].unique()

# ==========================================
# 2. MOTOR NBA (CON MODO RESCATE)
# ==========================================
@st.cache_data(ttl=86400)
def get_nba_teams(): return teams.get_teams()

@st.cache_data(ttl=3600)
def get_nba_stats_robust():
    # Intento 1: API Online
    try:
        # Headers para intentar engañar al servidor
        headers = {'User-Agent': 'Mozilla/5.0'} 
        stats = leaguedashteamstats.LeagueDashTeamStats(season='2024-25', measure_type_nullable='Base', timeout=5, headers=headers).get_data_frames()[0]
        return stats, "API"
    except:
        return None, "ERROR"

def analizar_partido_nba(home_name, away_name, df_stats, source_type):
    # Adaptador de columnas según si viene de API o CSV Manual
    if source_type == "MANUAL":
        # Mapeo de nombres manuales a nombres del código
        # Asumimos que el CSV manual tiene columnas estándar
        try:
            h_stats = df_stats[df_stats['Team'] == home_name].iloc[0]
            a_stats = df_stats[df_stats['Team'] == away_name].iloc[0]
            
            # Extraer datos (Adaptar nombres de columnas de Basketball-Ref)
            pace_h = float(h_stats.get('Pace', 99))
            pace_a = float(a_stats.get('Pace', 99))
            # Net Rating aprox (SRS o NRtg)
            net_h = float(h_stats.get('NRtg', h_stats.get('SRS', 0)))
            net_a = float(a_stats.get('NRtg', a_stats.get('SRS', 0)))
            win_h = float(h_stats.get('W/L%', 0.5))
            win_a = float(a_stats.get('W/L%', 0.5))
        except:
            return None, None, []
            
    else: # VIENE DE LA API
        h_stats = df_stats[df_stats['TEAM_NAME'] == home_name].iloc[0]
        a_stats = df_stats[df_stats['TEAM_NAME'] == away_name].iloc[0]
        # Cálculo manual de métricas si es API Base
        pace_h = (h_stats['PTS'] + h_stats['OPP_PTS']) / 2 # Estimación Pace
        pace_a = (a_stats['PTS'] + a_stats['OPP_PTS']) / 2
        net_h = h_stats['PLUS_MINUS']
        net_a = a_stats['PLUS_MINUS']
        win_h = h_stats['W_PCT']
        win_a = a_stats['W_PCT']

    # --- ALGORITMO SHARP ---
    ops = []
    
    # 1. Pace
    game_pace = (pace_h + pace_a) / 2
    if game_pace > 230 or game_pace < 90: # Ajuste de escala
        pass # Normalizar si es necesario
    
    # Lógica simplificada robusta
    if game_pace > 100.5: ops.append(("🏀 OVER PUNTOS", f"Ritmo Alto ({game_pace:.1f})", 80))
    elif game_pace < 97.0: ops.append(("🛡️ UNDER PUNTOS", f"Ritmo Lento ({game_pace:.1f})", 75))
    
    # 2. Net Rating
    diff = (net_h + 3.0) - net_a
    if diff > 6.0: ops.append(("💪 VICTORIA LOCAL", f"Ventaja clara (+{diff:.1f})", 85))
    elif diff < -4.0: ops.append(("💪 VICTORIA VISITA", f"Visitante superior (+{abs(diff):.1f})", 75))

    return {'PACE': pace_h, 'W': win_h}, {'PACE': pace_a, 'W': win_a}, ops

# ==========================================
# 3. MOTOR FÚTBOL
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    l_stats = {'Fouls':[], 'Goals':[], 'Corn':[], 'Cards':[], 'Prob_Card':[], 'BTTS':[], 'G_2H':[]}
    for _, r in matches.iterrows():
        is_h = r['HomeTeam'] == local
        l_stats['Fouls'].append(r['HF'] if is_h else r['AF'])
        l_stats['Goals'].append(r['FTHG'] if is_h else r['FTAG'])
        l_stats['Corn'].append(r['HC'] if is_h else r['AC'])
        cards = (r['HY']+r['HR']) if is_h else (r['AY']+r['AR'])
        l_stats['Cards'].append(cards)
        l_stats['Prob_Card'].append(1 if cards > 0 else 0)
        g, ga = (r['FTHG'], r['FTAG']) if is_h else (r['FTAG'], r['FTHG'])
        l_stats['BTTS'].append(1 if g>0 and ga>0 else 0)
        l_stats['G_2H'].append(g - (r['HTHG'] if is_h else r['HTAG']))
    ls = {k: np.mean(v) for k,v in l_stats.items()}
    
    matches_v = df[(df['HomeTeam'] == visitante) | (df['AwayTeam'] == visitante)].tail(10)
    v_stats = {'Goals': [], 'G_Conc':[], 'Cards':[], 'Prob_Card':[], 'Corn':[], 'BTTS':[], 'G_2H':[]}
    for _, r in matches_v.iterrows():
        is_h = r['HomeTeam'] == visitante
        g, ga = (r['FTHG'], r['FTAG']) if is_h else (r['FTAG'], r['FTHG'])
        v_stats['Goals'].append(g)
        v_stats['G_Conc'].append(ga)
        v_stats['Cards'].append((r['HY']+r['HR']) if is_h else (r['AY']+r['AR']))
        v_stats['Prob_Card'].append(1 if v_stats['Cards'][-1]>0 else 0)
        v_stats['Corn'].append(r['HC'] if is_h else r['AC'])
        v_stats['BTTS'].append(1 if g>0 and ga>0 else 0)
        v_stats['G_2H'].append(g - (r['HTHG'] if is_h else r['HTAG']))
    vs = {k: np.mean(v) for k,v in v_stats.items()}
    
    ops = []
    if ls['Fouls'] >= 10.0 and vs['G_Conc'] <= 1.5: ops.append(("🎯 TIROS VISITANTE", "+2.5 Tiros a Puerta", 78))
    proj = ls['Cards'] + vs['Cards'] + (ref_avg - 4.0)
    if ls['Prob_Card'] >= 0.85 and vs['Prob_Card'] >= 0.85: ops.append(("🟨 AMBOS RECIBEN", "Sí (BTC)", 90))
    if proj >= 5.0: ops.append(("🔥 OVER TARJETAS", "+4.5 Tarjetas", 75))
    if (ls['Corn']+vs['Corn']) >= 9.5: ops.append(("🚩 CÓRNERS", "+8.5 Total", 80))
    if (ls['G_2H']+vs['G_2H']) >= 1.4: ops.append(("⏱️ GOL TARDÍO", "Gol en 2ª Parte", 80))
    if ls['BTTS'] >= 0.65 and vs['BTTS'] >= 0.65: ops.append(("⚽ AMBOS MARCAN", "Sí", 75))
    return ls, vs, ops

# ==========================================
# 4. INTERFAZ UNIFICADA
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.caption("v24.0 | Fallback Engine")
modo = st.sidebar.selectbox("Modo", ["⚽ FÚTBOL", "🏀 NBA TEAMS"])

if modo == "⚽ FÚTBOL":
    with st.spinner("Cargando DB Fútbol..."):
        df, ligas = cargar_datos_futbol()
    if df is not None:
        liga = st.sidebar.selectbox("Liga", ligas)
        df_liga = df[df['League'] == liga]
        eqs = sorted(df_liga['HomeTeam'].unique())
        l = st.sidebar.selectbox("Local", eqs)
        v = st.sidebar.selectbox("Visitante", [x for x in eqs if x!=l])
        ref_avg = st.sidebar.number_input("Media Árbitro", 0.0, 10.0, 4.5)
        if st.sidebar.button("ANALIZAR FÚTBOL", type="primary"):
            ls, vs, ops = analizar_futbol(df, l, v, ref_avg)
            if ls:
                c1,c2 = st.columns(2)
                c1.metric(l, f"{ls['Goals']:.2f} Goles")
                c2.metric(v, f"{vs['Goals']:.2f} Goles")
                st.markdown("---")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='game-card'><span style='color:#00ff7f; font-weight:bold'>{t}</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

elif modo == "🏀 NBA TEAMS":
    st.markdown("### 🏀 Análisis NBA")
    
    # 1. INTENTAR API
    df_nba, status = get_nba_stats_robust()
    
    # 2. SI FALLA LA API, PEDIR ARCHIVO
    if status == "ERROR":
        st.error("⚠️ La API de la NBA ha bloqueado la conexión (IP Ban).")
        st.info("📂 **SOLUCIÓN:** Sube el archivo de estadísticas manualmente.")
        st.markdown("[📥 Descargar Stats CSV aquí](https://www.basketball-reference.com/leagues/NBA_2025_ratings.html) (Dale a 'Share & Export' > 'Get as CSV')")
        
        uploaded_file = st.file_uploader("Sube el CSV aquí", type=["csv"])
        
        if uploaded_file:
            try:
                # Leer CSV Manual (Basketball Reference format)
                # Saltamos la primera fila que suele ser cabecera doble
                df_nba = pd.read_csv(uploaded_file, skiprows=1)
                status = "MANUAL"
                st.success("✅ Archivo cargado correctamente.")
            except:
                st.error("Formato de archivo incorrecto.")
    
    # 3. SI TENEMOS DATOS (SEA API O MANUAL)
    if df_nba is not None:
        # Selector de equipos
        if status == "API":
            teams_list = sorted(df_nba['TEAM_NAME'].unique())
        else: # Manual
            teams_list = sorted(df_nba['Team'].unique())
            
        l = st.sidebar.selectbox("Local", teams_list)
        v = st.sidebar.selectbox("Visitante", [x for x in teams_list if x!=l])
        
        if st.sidebar.button("ANALIZAR NBA", type="primary"):
            h_s, a_s, ops = analizar_partido_nba(l, v, df_nba, status)
            
            if h_s:
                st.markdown(f"<h2 style='text-align:center'>{l} vs {v}</h2>", unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                c1.metric("Pace (Ritmo)", f"{h_s['PACE']:.1f}")
                c2.metric("Victorias %", f"{h_s['W']:.1%}")
                
                st.markdown("---")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='game-card'><span style='color:#ff5722; font-weight:bold'>{t}</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Partido equilibrado.")
            else:
                st.error("Error al procesar los datos del equipo.")
