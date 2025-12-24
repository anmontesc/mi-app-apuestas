import streamlit as st
import pandas as pd
import numpy as np
import datetime

# Librerías NBA
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguedashteamstats, commonteamroster, playergamelog

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Sharp Edition", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    
    .prop-card {
        background-color: #1e2130;
        padding: 15px;
        border-radius: 10px;
        border: 1px solid #2e3440;
        margin-bottom: 10px;
    }
    .game-card {
        background-color: #1a1c24;
        border-left: 5px solid #ff5722;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .stat-val {font-size: 20px; font-weight: bold; color: white;}
    .stat-label {font-size: 11px; color: #aaa; text-transform: uppercase;}
    
    /* Centrar imágenes */
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. LOGOS (Fútbol + NBA Genérico)
# ==========================================
def get_team_logo(team_name, sport="futbol"):
    if sport == "nba":
        # Mapeo simple de IDs o nombres a logos
        return f"https://cdn.nba.com/logos/nba/{team_name}/primary/L/logo.svg" # Truco: team_name debe ser el ID numérico a veces, pero usaremos genérico si falla
    
    logos = {
        "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
        "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png",
        "Man City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png",
        "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

# ==========================================
# 1. MOTOR DE DATOS FÚTBOL (Live Scraper V22)
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_datos_futbol():
    dfs = []
    temporadas = ['2324', '2425'] 
    ligas_codes = {"🇪🇸 La Liga": "SP1", "🇬🇧 Premier": "E0"}
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
# 2. MOTOR NBA (TEAMS & PROPS)
# ==========================================
@st.cache_data(ttl=86400)
def get_nba_teams(): return teams.get_teams()

@st.cache_data(ttl=3600)
def get_nba_advanced_stats():
    # CAMBIO IMPORTANTE: measure_type_nullable='Advanced'
    stats = leaguedashteamstats.LeagueDashTeamStats(
        season='2024-25', 
        measure_type_nullable='Advanced'
    ).get_data_frames()[0]
    return stats

@st.cache_data(ttl=3600)
def get_team_roster(team_id): return commonteamroster.CommonTeamRoster(team_id=team_id).get_data_frames()[0]

@st.cache_data(ttl=3600)
def get_player_stats(player_id): return playergamelog.PlayerGameLog(player_id=player_id, season='2024-25').get_data_frames()[0]

# --- LÓGICA DE PARTIDO NBA (ALGORITMO SHARP) ---
def analizar_partido_nba(home_name, away_name, df_stats):
    # Obtener stats de los equipos
    h_stats = df_stats[df_stats['TEAM_NAME'] == home_name].iloc[0]
    a_stats = df_stats[df_stats['TEAM_NAME'] == away_name].iloc[0]
    
    ops = []
    
    # 1. ALGORITMO DE PACE (RITMO) -> Para Over/Under
    # El Pace es estimación de posesiones por 48 min.
    game_pace = (h_stats['PACE'] + a_stats['PACE']) / 2
    if game_pace > 102.0:
        ops.append(("🏀 OVER PUNTOS", f"Pace Alto ({game_pace:.1f})", 80))
    elif game_pace < 96.0:
        ops.append(("🛡️ UNDER PUNTOS", f"Pace Lento ({game_pace:.1f})", 75))
        
    # 2. ALGORITMO NET RATING (EFICIENCIA) -> Para Ganador/Handicap
    # Net Rating = Puntos anotados - Puntos recibidos por 100 posesiones
    # Ajuste de cancha: +3.0 puntos de Net Rating al local suele ser estándar
    h_net = h_stats['E_NET_RATING'] + 3.0 
    a_net = a_stats['E_NET_RATING']
    diff_net = h_net - a_net
    
    if diff_net > 8.0:
        ops.append(("💪 VICTORIA LOCAL", f"{home_name} muy superior (+{diff_net:.1f} NetRtg)", 85))
    elif diff_net < -5.0:
        ops.append(("💪 VICTORIA VISITA", f"{away_name} superior pese a ser visita", 75))
    elif abs(diff_net) < 2.0:
        ops.append(("⚖️ PARTIDO CERRADO", "Final apretado (Clutch Time)", 65))

    # 3. ALGORITMO REBOTE (FOUR FACTORS)
    # Rebote ofensivo vs Rebote defensivo
    # Si Local rebotea mucho en ataque y Visita no cierra el rebote -> Ventaja Local
    if h_stats['OREB_PCT'] > 0.30 and a_stats['DREB_PCT'] < 0.70:
        ops.append(("🗑️ DOMINIO REBOTE", f"Ventaja {home_name} en pintura", 70))
        
    # 4. RACHAS (L10)
    # Si un equipo gana mucho y el otro pierde mucho
    if h_stats['W_PCT'] > 0.60 and a_stats['W_PCT'] < 0.40:
        ops.append(("🔥 FORMA LOCAL", f"{home_name} en buena dinámica", 80))

    return h_stats, a_stats, ops

# --- LÓGICA PROPS (V21) ---
def analizar_props(player_name, player_id):
    df = get_player_stats(player_id)
    if df.empty: return None
    df[['PTS','REB','AST']] = df[['PTS','REB','AST']].astype(int)
    last_10 = df.head(10).copy()
    avgs = {'PTS': df['PTS'].mean(), 'REB': df['REB'].mean(), 'AST': df['AST'].mean()}
    lines = {k: round(v) for k,v in avgs.items()}
    hits_10 = {
        'PTS': [1 if x >= lines['PTS'] else 0 for x in last_10['PTS']],
        'REB': [1 if x >= lines['REB'] else 0 for x in last_10['REB']],
        'AST': [1 if x >= lines['AST'] else 0 for x in last_10['AST']]
    }
    return {'name': player_name, 'L10': last_10, 'avgs': avgs, 'lines': lines, 'hits_10': hits_10}

# ==========================================
# 3. MOTOR FÚTBOL (V20)
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    l_stats = {'Fouls':[], 'Goals':[], 'SOT_F':[], 'Corn':[], 'Cards':[], 'Prob_Card':[], 'BTTS':[], 'G_2H':[]}
    for _, r in matches.iterrows():
        is_h = r['HomeTeam'] == local
        l_stats['Fouls'].append(r['HF'] if is_h else r['AF'])
        l_stats['Goals'].append(r['FTHG'] if is_h else r['FTAG'])
        l_stats['SOT_F'].append(r['HST'] if is_h else r['AST'])
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
st.sidebar.caption("v23.0 | Sharp Edition")
modo = st.sidebar.selectbox("Selecciona Modo", ["⚽ FÚTBOL", "🏀 NBA TEAMS (Game Analysis)", "🏀 NBA PROPS (Player Analysis)"])

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
                st.subheader("📡 Señales Detectadas")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='prop-card'><div class='stat-label'>{t}</div><div class='stat-val' style='font-size:18px'>{d}</div><div style='color:#00ff7f; font-weight:bold'>{c}% Confianza</div></div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

elif modo == "🏀 NBA TEAMS (Game Analysis)":
    # Cargar datos avanzados NBA
    with st.spinner("Descargando Advanced Stats NBA 2024-25..."):
        df_adv = get_nba_advanced_stats()
    
    # Selectores
    teams_list = sorted(df_adv['TEAM_NAME'].unique())
    l = st.sidebar.selectbox("Equipo Local (Home)", teams_list)
    v = st.sidebar.selectbox("Equipo Visitante (Away)", [x for x in teams_list if x!=l])
    
    if st.sidebar.button("ANALIZAR PARTIDO NBA", type="primary"):
        h_s, a_s, ops = analizar_partido_nba(l, v, df_adv)
        
        # --- TABLA COMPARATIVA (TALE OF THE TAPE) ---
        st.markdown(f"<h2 style='text-align:center'>{l} vs {v}</h2>", unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Net Rating", f"{h_s['E_NET_RATING']:.1f}", delta=f"{h_s['E_NET_RATING'] - a_s['E_NET_RATING']:.1f} vs Riv")
        c2.metric("Pace (Ritmo)", f"{h_s['PACE']:.1f}", f"Vs {a_s['PACE']:.1f}")
        c3.metric("Rebote %", f"{h_s['REB_PCT']:.1%}", f"Vs {a_s['REB_PCT']:.1%}")
        c4.metric("Victorias", f"{h_s['W_PCT']:.0%}", f"Vs {a_s['W_PCT']:.0%}")
        
        st.markdown("---")
        
        # --- SEÑALES ALGORÍTMICAS ---
        st.subheader("🧠 Análisis Algorítmico (Sharp Model)")
        if ops:
            for t, d, c in ops:
                st.markdown(f"""
                <div class='game-card'>
                    <div style='display:flex; justify-content:space-between'>
                        <span style='color:#ff5722; font-weight:bold; font-size:18px'>{t}</span>
                        <span style='color:white; font-weight:bold'>{c}%</span>
                    </div>
                    <div style='color:#ccc; margin-top:5px'>{d}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("El modelo indica que el partido está muy equilibrado (No Bet).")
            
        # Tabla detallada
        with st.expander("Ver Estadísticas Avanzadas Completas"):
            st.dataframe(pd.DataFrame([h_s, a_s]))

elif modo == "🏀 NBA PROPS (Player Analysis)":
    nba_teams = get_nba_teams()
    sel_tm = st.sidebar.selectbox("Equipo", [t['full_name'] for t in nba_teams])
    tid = [t['id'] for t in nba_teams if t['full_name'] == sel_tm][0]
    
    with st.spinner("Cargando plantilla..."):
        roster = get_team_roster(tid)
        pl_list = roster['PLAYER'].tolist()
        pl_ids = roster['PLAYER_ID'].tolist()
    
    sel_pl = st.sidebar.selectbox("Jugador", pl_list)
    
    if st.sidebar.button("ANALIZAR JUGADOR"):
        pid = pl_ids[pl_list.index(sel_pl)]
        data = analizar_props(sel_pl, pid)
        if data:
            st.markdown(f"## 🏀 {data['name']}")
            c1,c2,c3 = st.columns(3)
            def draw_streak(hits):
                html = ""
                for h in reversed(hits): 
                    color = "#00ff7f" if h == 1 else "#ff4b4b"
                    html += f"<div style='background-color:{color}; width:8px; height:25px; display:inline-block; margin-right:2px; border-radius:2px;'></div>"
                return html
            
            with c1: st.markdown(f"<div class='prop-card'><div class='stat-label'>PTS (L {data['lines']['PTS']})</div><div class='stat-val'>{data['avgs']['PTS']:.1f}</div><div>{draw_streak(data['hits_10']['PTS'])}</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='prop-card'><div class='stat-label'>REB (L {data['lines']['REB']})</div><div class='stat-val'>{data['avgs']['REB']:.1f}</div><div>{draw_streak(data['hits_10']['REB'])}</div></div>", unsafe_allow_html=True)
            with c3: st.markdown(f"<div class='prop-card'><div class='stat-label'>AST (L {data['lines']['AST']})</div><div class='stat-val'>{data['avgs']['AST']:.1f}</div><div>{draw_streak(data['hits_10']['AST'])}</div></div>", unsafe_allow_html=True)
            st.line_chart(data['L10'][['GAME_DATE','PTS','REB','AST']].iloc[::-1], x='GAME_DATE')
        else: st.warning("Sin datos recientes.")

