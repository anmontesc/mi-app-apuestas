import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Pro Local", page_icon="📂", layout="wide")

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
# 0. LOGOS (URLS Fijas)
# ==========================================
def get_team_logo(team_name):
    # Diccionario ampliado de logos
    logos = {
        "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
        "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png",
        "Atl. Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f4/Atletico_Madrid_2017_logo.svg/1200px-Atletico_Madrid_2017_logo.svg.png",
        "Betis": "https://upload.wikimedia.org/wikipedia/en/thumb/1/13/Real_betis_logo.svg/1200px-Real_betis_logo.svg.png",
        "Man City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png",
        "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png",
        "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/1200px-Liverpool_FC.svg.png",
        "Boston Celtics": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8f/Boston_Celtics.svg/1200px-Boston_Celtics.svg.png",
        "Los Angeles Lakers": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Los_Angeles_Lakers_logo.svg/1200px-Los_Angeles_Lakers_logo.svg.png",
        "Golden State Warriors": "https://upload.wikimedia.org/wikipedia/en/thumb/0/01/Golden_State_Warriors_logo.svg/1200px-Golden_State_Warriors_logo.svg.png",
        "Miami Heat": "https://upload.wikimedia.org/wikipedia/en/thumb/f/fb/Miami_Heat_logo.svg/1200px-Miami_Heat_logo.svg.png",
        "Chicago Bulls": "https://upload.wikimedia.org/wikipedia/en/thumb/6/67/Chicago_Bulls_logo.svg/1200px-Chicago_Bulls_logo.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

# ==========================================
# 1. MOTOR DE DATOS FÚTBOL (Web CSVs)
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
                # Lectura directa de URL
                df = pd.read_csv(f"{base_url}{season}/{codigo}.csv", usecols=lambda c: c in cols)
                df['League'] = nombre_liga
                dfs.append(df)
            except: continue
            
    if not dfs: return None, []
    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    return df.sort_values('Date').reset_index(drop=True), df['League'].unique()

# ==========================================
# 2. MOTOR DE DATOS NBA (CSV Local)
# ==========================================
@st.cache_data
def cargar_datos_nba_local():
    try:
        # Cargamos el archivo que has subido: nba_stats.csv
        df = pd.read_csv("nba_stats.csv")
        
        # Limpieza básica por si acaso
        if 'Team' in df.columns:
            # Eliminamos filas vacías o de separadores
            df = df.dropna(subset=['Team'])
            # Filtramos solo equipos reales (eliminando filas de 'League Average' si las hay)
            df = df[df['Team'] != 'League Average']
            return df
        else:
            return None
    except:
        return None

def analizar_partido_nba(home_name, away_name, df_nba):
    # Buscamos las filas de los equipos
    try:
        h_stats = df_nba[df_nba['Team'] == home_name].iloc[0]
        a_stats = df_nba[df_nba['Team'] == away_name].iloc[0]
    except:
        return None, None, []

    ops = []
    
    # --- MÉTRICAS DE EFICIENCIA (SHARP) ---
    # ORtg: Puntos anotados por 100 posesiones (Ataque)
    # DRtg: Puntos recibidos por 100 posesiones (Defensa)
    # NRtg: Diferencia neta (Lo bueno que es el equipo en general)
    
    h_ortg = float(h_stats['ORtg'])
    h_drtg = float(h_stats['DRtg'])
    h_nrtg = float(h_stats['NRtg'])
    
    a_ortg = float(a_stats['ORtg'])
    a_drtg = float(a_stats['DRtg'])
    a_nrtg = float(a_stats['NRtg'])
    
    # 1. GANADOR (NET RATING)
    # Ajuste de campo: Se suele dar +3.0 puntos de ventaja al local en el Net Rating
    diff_net = (h_nrtg + 3.0) - a_nrtg
    
    if diff_net > 8.0:
        ops.append(("💪 VICTORIA LOCAL", f"{home_name} es muy superior (+{diff_net:.1f} NetRtg)", 85))
    elif diff_net < -5.0:
        ops.append(("💪 VICTORIA VISITA", f"{away_name} es superior (+{abs(diff_net):.1f} NetRtg)", 80))
    elif abs(diff_net) < 2.0:
        ops.append(("⚖️ PARTIDO CERRADO", "Final apretado (Clutch Time)", 60))

    # 2. ESPECTÁCULO (OFENSIVA vs DEFENSA)
    # Si el Ataque Local es mucho mejor que la Defensa Visitante -> Puntos Local
    if h_ortg > (a_drtg + 5.0):
        ops.append(("🔥 ATAQUE LOCAL", f"{home_name} anotará con facilidad", 75))
    
    if a_ortg > (h_drtg + 5.0):
        ops.append(("🔥 ATAQUE VISITA", f"{away_name} anotará con facilidad", 75))

    # 3. OVER / UNDER (ESTIMACIÓN POR EFICIENCIA)
    # Si ambos tienen ataques eficientes (ORtg > 116) y defensas flojas (DRtg > 115)
    if h_ortg > 116 and a_ortg > 116:
        ops.append(("🏀 ALTA PUNTUACIÓN", "Duelo de ataques eficientes", 75))
    elif h_drtg < 110 and a_drtg < 110:
        ops.append(("🛡️ BAJA PUNTUACIÓN", "Duelo defensivo (Roca)", 70))

    return h_stats, a_stats, ops

# ==========================================
# 3. MOTOR FÚTBOL (Lógica V20)
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    # Recolector Stats
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
st.sidebar.caption("v25.0 | Local Data Engine")
modo = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA TEAMS"])

if modo == "⚽ FÚTBOL":
    with st.spinner("Cargando datos históricos..."):
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
                col_l, col_vs, col_v = st.columns([1, 0.5, 1])
                with col_l:
                    st.image(get_team_logo(l), width=100)
                    st.metric(l, f"{ls['Goals']:.2f} Goles")
                with col_vs:
                    st.markdown("<br><h1 style='text-align:center; color:#d4af37'>VS</h1>", unsafe_allow_html=True)
                with col_v:
                    st.image(get_team_logo(v), width=100)
                    st.metric(v, f"{vs['Goals']:.2f} Goles")
                st.markdown("---")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='game-card'><span style='color:#00ff7f; font-weight:bold'>{t}</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

elif modo == "🏀 NBA TEAMS":
    df_nba = cargar_datos_nba_local()
    
    if df_nba is not None:
        st.success("✅ Base de datos NBA cargada (Local)")
        teams_list = sorted(df_nba['Team'].unique())
        l = st.sidebar.selectbox("Local", teams_list)
        v = st.sidebar.selectbox("Visitante", [x for x in teams_list if x!=l])
        
        if st.sidebar.button("ANALIZAR NBA", type="primary"):
            h_s, a_s, ops = analizar_partido_nba(l, v, df_nba)
            
            if h_s is not None:
                st.markdown(f"<h2 style='text-align:center'>{l} vs {v}</h2>", unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Net Rating", f"{h_s['NRtg']}", delta=f"{h_s['NRtg'] - a_s['NRtg']:.1f}")
                c2.metric("Ofensiva (ORtg)", f"{h_s['ORtg']}", f"Vs {a_s['ORtg']}")
                c3.metric("Victorias %", f"{h_s['W/L%']}", f"Vs {a_s['W/L%']}")
                
                st.markdown("---")
                st.subheader("🧠 Análisis Algorítmico (Sharp)")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='game-card'><span style='color:#ff5722; font-weight:bold'>{t}</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Partido muy equilibrado.")
            else:
                st.error("Error leyendo datos del equipo.")
    else:
        st.error("❌ No se encuentra 'nba_stats.csv' en la carpeta.")
        st.info("Asegúrate de subir el archivo CSV a GitHub con ese nombre exacto.")
