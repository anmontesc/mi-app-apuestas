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
    
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. LOGOS
# ==========================================
def get_team_logo(team_name):
    logos = {
        "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
        "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png",
        "Atl. Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f4/Atletico_Madrid_2017_logo.svg/1200px-Atletico_Madrid_2017_logo.svg.png",
        "Betis": "https://upload.wikimedia.org/wikipedia/en/thumb/1/13/Real_betis_logo.svg/1200px-Real_betis_logo.svg.png",
        "Man City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png",
        "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png",
        "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/1200px-Liverpool_FC.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

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
# 2. MOTOR NBA ROBUSTO (ANTI-FALLOS)
# ==========================================
@st.cache_data(ttl=86400)
def get_nba_teams(): return teams.get_teams()

@st.cache_data(ttl=3600)
def get_nba_stats_robust():
    # Intento 1: Estadísticas Avanzadas (Lo ideal)
    try:
        stats = leaguedashteamstats.LeagueDashTeamStats(season='2024-25', measure_type_nullable='Advanced', timeout=10).get_data_frames()[0]
        stats['DATA_TYPE'] = 'Advanced' # Marcamos que son buenas
        return stats
    except:
        pass # Si falla, vamos al plan B
    
    # Intento 2: Estadísticas Base (Si la NBA nos bloquea las avanzadas)
    try:
        # Esperamos un poco para no saturar
        time.sleep(1) 
        stats = leaguedashteamstats.LeagueDashTeamStats(season='2024-25', measure_type_nullable='Base', timeout=10).get_data_frames()[0]
        stats['DATA_TYPE'] = 'Base' # Marcamos que son básicas
        return stats
    except:
        return None # Si todo falla, devolvemos None

@st.cache_data(ttl=3600)
def get_team_roster(team_id): return commonteamroster.CommonTeamRoster(team_id=team_id).get_data_frames()[0]

@st.cache_data(ttl=3600)
def get_player_stats(player_id): return playergamelog.PlayerGameLog(player_id=player_id, season='2024-25').get_data_frames()[0]

def analizar_partido_nba(home_name, away_name, df_stats):
    if df_stats is None: return None, None, []
    
    h_stats = df_stats[df_stats['TEAM_NAME'] == home_name].iloc[0]
    a_stats = df_stats[df_stats['TEAM_NAME'] == away_name].iloc[0]
    
    ops = []
    
    # --- CÁLCULOS INTELIGENTES (Plan A vs Plan B) ---
    
    # Si tenemos datos AVANZADOS (Plan A)
    if 'PACE' in h_stats:
        pace_h = h_stats['PACE']
        pace_a = a_stats['PACE']
        net_h = h_stats['E_NET_RATING']
        net_a = a_stats['E_NET_RATING']
        reb_h = h_stats['REB_PCT']
        reb_a = a_stats['REB_PCT']
    
    # Si solo tenemos datos BASE (Plan B - Cálculo Manual)
    else:
        # Estimamos PACE: (Puntos + Puntos Rival) / 2
        # GP = Partidos jugados
        pace_h = (h_stats['PTS'] + h_stats['OPP_PTS']) / 2
        pace_a = (a_stats['PTS'] + a_stats['OPP_PTS']) / 2
        
        # Estimamos NET RATING: Diferencia de puntos media
        net_h = h_stats['PLUS_MINUS']
        net_a = a_stats['PLUS_MINUS']
        
        # Rebotes brutos (no es porcentaje, pero sirve para comparar)
        reb_h = h_stats['REB']
        reb_a = a_stats['REB']

    # --- GENERACIÓN DE SEÑALES ---
    
    # 1. PACE (Ritmo)
    game_pace = (pace_h + pace_a) / 2
    # Ajustamos umbrales según si es PACE real (aprox 100) o Puntos Totales (aprox 220)
    umbral_over = 102.0 if 'PACE' in h_stats else 230.0
    umbral_under = 96.0 if 'PACE' in h_stats else 215.0
    
    if game_pace > umbral_over:
        ops.append(("🏀 OVER PUNTOS", f"Ritmo Alto (Est: {game_pace:.1f})", 80))
    elif game_pace < umbral_under:
        ops.append(("🛡️ UNDER PUNTOS", f"Ritmo Lento (Est: {game_pace:.1f})", 75))

    # 2. NET RATING (Ganador)
    diff_net = (net_h + 3.0) - net_a # +3 por factor cancha
    if diff_net > 7.0:
        ops.append(("💪 VICTORIA LOCAL", f"{home_name} superior (+{diff_net:.1f})", 85))
    elif diff_net < -5.0:
        ops.append(("💪 VICTORIA VISITA", f"{away_name} superior (+{abs(diff_net):.1f})", 75))
        
    # 3. REBOTE
    if reb_h > (reb_a * 1.05): # Si local rebotea 5% más
        ops.append(("🗑️ DOMINIO REBOTE", f"Ventaja {home_name}", 70))

    return h_stats, a_stats, ops

# --- LÓGICA PROPS ---
def analizar_props(player_name, player_id):
    try:
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
    except: return None

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
st.sidebar.caption("v23.2 | Anti-Block Engine")
modo = st.sidebar.selectbox("Modo", ["⚽ FÚTBOL", "🏀 NBA TEAMS", "🏀 NBA PROPS"])

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
                st.subheader("📡 Señales Detectadas")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='prop-card'><div class='stat-label'>{t}</div><div class='stat-val' style='font-size:18px'>{d}</div><div style='color:#00ff7f; font-weight:bold'>{c}% Confianza</div></div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

elif modo == "🏀 NBA TEAMS":
    with st.spinner("Descargando NBA Stats (Modo Seguro)..."):
        df_adv = get_nba_stats_robust()
    
    if df_adv is not None:
        teams_list = sorted(df_adv['TEAM_NAME'].unique())
        l = st.sidebar.selectbox("Local", teams_list)
        v = st.sidebar.selectbox("Visitante", [x for x in teams_list if x!=l])
        
        if st.sidebar.button("ANALIZAR PARTIDO NBA", type="primary"):
            h_s, a_s, ops = analizar_partido_nba(l, v, df_adv)
            
            st.markdown(f"<h2 style='text-align:center'>{l} vs {v}</h2>", unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns(3)
            # Mostramos métricas adaptadas (si son base o avanzadas)
            lbl_pace = "Pace" if 'PACE' in h_s else "Puntos Totales (Est)"
            val_pace_h = h_s['PACE'] if 'PACE' in h_s else (h_s['PTS']+h_s['OPP_PTS'])/2
            
            c1.metric(lbl_pace, f"{val_pace_h:.1f}")
            c2.metric("Victorias %", f"{h_s['W_PCT']:.1%}", f"Vs {a_s['W_PCT']:.1%}")
            
            st.markdown("---")
            st.subheader("🧠 Análisis Algorítmico")
            if ops:
                for t, d, c in ops:
                    st.markdown(f"<div class='game-card'><span style='color:#ff5722; font-weight:bold; font-size:18px'>{t}</span><br>{d}</div>", unsafe_allow_html=True)
            else: st.info("Partido muy equilibrado.")
    else:
        st.error("Error conectando con NBA Stats. Intenta de nuevo en unos segundos.")

elif modo == "🏀 NBA PROPS":
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
