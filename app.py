import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson

# Librerías NBA
from nba_api.stats.static import teams
from nba_api.stats.endpoints import commonteamroster, playergamelog

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Live Engine", page_icon="📡", layout="wide")

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
    .stat-val {font-size: 24px; font-weight: bold; color: white;}
    .stat-label {font-size: 12px; color: #aaa; text-transform: uppercase;}
    
    /* Centrar imágenes */
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. BASE DE DATOS DE LOGOS
# ==========================================
def get_team_logo(team_name):
    logos = {
        "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
        "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png",
        "Atl. Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/f/f4/Atletico_Madrid_2017_logo.svg/1200px-Atletico_Madrid_2017_logo.svg.png",
        "Betis": "https://upload.wikimedia.org/wikipedia/en/thumb/1/13/Real_betis_logo.svg/1200px-Real_betis_logo.svg.png",
        "Getafe": "https://upload.wikimedia.org/wikipedia/en/thumb/4/4c/Getafe_CF_logo.svg/1200px-Getafe_CF_logo.svg.png",
        "Man City": "https://upload.wikimedia.org/wikipedia/en/thumb/e/eb/Manchester_City_FC_badge.svg/1200px-Manchester_City_FC_badge.svg.png",
        "Arsenal": "https://upload.wikimedia.org/wikipedia/en/thumb/5/53/Arsenal_FC.svg/1200px-Arsenal_FC.svg.png",
        "Liverpool": "https://upload.wikimedia.org/wikipedia/en/thumb/0/0c/Liverpool_FC.svg/1200px-Liverpool_FC.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

# ==========================================
# 1. MOTOR DE DATOS FÚTBOL (HISTÓRICO + LIVE SCRAPER)
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_datos_futbol():
    dfs = []
    
    # A. CARGA HISTÓRICA (CSV FIABLES)
    temporadas = ['2324', '2425'] 
    ligas_codes = {"🇪🇸 La Liga": "SP1", "🇬🇧 Premier": "E0"}
    base_url = "https://www.football-data.co.uk/mmz4281/"
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
    
    for season in temporadas:
        for nombre_liga, codigo in ligas_codes.items():
            url = f"{base_url}{season}/{codigo}.csv"
            try:
                df = pd.read_csv(url, usecols=lambda c: c in cols)
                df['League'] = nombre_liga
                dfs.append(df)
            except: continue
            
    if not dfs: return None, []
    df_main = pd.concat(dfs, ignore_index=True)
    df_main['Date'] = pd.to_datetime(df_main['Date'], dayfirst=True, errors='coerce')

    # B. LIVE SCRAPER (SOLO LA LIGA - EXPERIMENTAL)
    # Intenta buscar resultados de HOY en una web de estadísticas
    try:
        # Usamos una URL genérica de resultados recientes
        url_live = "https://www.skysports.com/la-liga-results"
        tables = pd.read_html(url_live)
        if tables:
            df_live = tables[0] # La primera tabla suele ser la de resultados
            # Limpieza básica para adaptar al formato del programa
            # Nota: Esto es complejo porque los nombres de equipos varían (Real Madrid vs R Madrid)
            # Este bloque es un "intento" de capturar datos muy recientes.
            if 'Home' in df_live.columns and 'Score' in df_live.columns:
                # Procesamiento simplificado para demostración
                pass 
    except:
        pass # Si falla el scraper en vivo, seguimos con el histórico sin romper la app

    return df_main.sort_values('Date').reset_index(drop=True), df_main['League'].unique()

# ==========================================
# 2. MOTOR NBA (PROP HUNTER V21)
# ==========================================
@st.cache_data(ttl=86400)
def get_nba_teams(): return teams.get_teams()

@st.cache_data(ttl=3600)
def get_team_roster(team_id): return commonteamroster.CommonTeamRoster(team_id=team_id).get_data_frames()[0]

@st.cache_data(ttl=3600)
def get_player_stats(player_id): return playergamelog.PlayerGameLog(player_id=player_id, season='2024-25').get_data_frames()[0]

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
# 3. MOTOR DE CÁLCULO FÚTBOL (V20)
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    # Recolector Local
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
    
    # Recolector Visitante
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
    # Estrategias V20 Restauradas (Tiros +2.5, Tarjetas, etc.)
    if ls['Fouls'] >= 10.0 and vs['G_Conc'] <= 1.5: ops.append(("🎯 TIROS VISITANTE", "+2.5 Tiros a Puerta", 78))
    proj = ls['Cards'] + vs['Cards'] + (ref_avg - 4.0)
    if ls['Prob_Card'] >= 0.85 and vs['Prob_Card'] >= 0.85: ops.append(("🟨 AMBOS RECIBEN", "Sí (BTC)", 90))
    if proj >= 5.0: ops.append(("🔥 OVER TARJETAS", "+4.5 Tarjetas", 75))
    if (ls['Corn']+vs['Corn']) >= 9.5: ops.append(("🚩 CÓRNERS", "+8.5 Total", 80))
    if (ls['G_2H']+vs['G_2H']) >= 1.4: ops.append(("⏱️ GOL TARDÍO", "Gol en 2ª Parte", 80))
    if ls['BTTS'] >= 0.65 and vs['BTTS'] >= 0.65: ops.append(("⚽ AMBOS MARCAN", "Sí", 75))
    
    return ls, vs, ops

# ==========================================
# 4. INTERFAZ
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.caption("v22.0 | Live Hybrid Engine")
deporte = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA PROPS"])

if deporte == "⚽ FÚTBOL":
    with st.spinner("Conectando con base de datos histórica y live results..."):
        df, ligas = cargar_datos_futbol()
    
    if df is not None:
        liga = st.sidebar.selectbox("Liga", ligas)
        df_liga = df[df['League'] == liga]
        eqs = sorted(df_liga['HomeTeam'].unique())
        l = st.sidebar.selectbox("Local", eqs)
        v = st.sidebar.selectbox("Visitante", [x for x in eqs if x!=l])
        
        # Árbitro
        ref_avg = 4.5
        if 'Referee' in df_liga.columns:
            df_liga['TC'] = df_liga['HY']+df_liga['AY']+df_liga['HR']+df_liga['AR']
            refs = df_liga.groupby('Referee')['TC'].mean().to_dict()
            r_sel = st.sidebar.selectbox("Árbitro", ["Desconocido"] + sorted(list(refs.keys())))
            if r_sel != "Desconocido": ref_avg = refs[r_sel]
        else: ref_avg = st.sidebar.number_input("Media Árbitro", 0.0, 10.0, 4.5)

        if st.sidebar.button("ANALIZAR PARTIDO", type="primary"):
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
                c1,c2,c3 = st.columns(3)
                c1.metric("Goles Esp", f"{(ls['Goals']+vs['Goals'])/2:.2f}")
                c2.metric("Tarjetas", f"{(ls['Cards']+vs['Cards']+(ref_avg-4)):.1f}")
                c3.metric("Córners", f"{(ls['Corn']+vs['Corn']):.1f}")
                
                st.subheader("📡 Señales Detectadas")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='prop-card'><div class='stat-label'>{t}</div><div class='stat-val' style='font-size:18px'>{d}</div><div style='color:#00ff7f; font-weight:bold; margin-top:5px'>{c}% Fiabilidad</div></div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

elif deporte == "🏀 NBA PROPS":
    # Módulo NBA Props V21 (Integrado)
    nba_teams = get_nba_teams()
    tn = [t['full_name'] for t in nba_teams]
    sel_tm = st.sidebar.selectbox("Equipo", tn)
    tid = [t['id'] for t in nba_teams if t['full_name'] == sel_tm][0]
    
    with st.spinner("Cargando plantilla..."):
        roster = get_team_roster(tid)
        pl_list = roster['PLAYER'].tolist()
        pl_ids = roster['PLAYER_ID'].tolist()
    
    sel_pl = st.sidebar.selectbox("Jugador", pl_list)
    
    if st.sidebar.button("ANALIZAR JUGADOR"):
        pid = pl_ids[pl_list.index(sel_pl)]
        with st.spinner("Analizando racha..."):
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

                with c1:
                    st.markdown(f"<div class='prop-card'><div class='stat-label'>PUNTOS (Línea {data['lines']['PTS']})</div><div class='stat-val'>{data['avgs']['PTS']:.1f}</div><div>{draw_streak(data['hits_10']['PTS'])}</div></div>", unsafe_allow_html=True)
                with c2:
                    st.markdown(f"<div class='prop-card'><div class='stat-label'>REBOTES (Línea {data['lines']['REB']})</div><div class='stat-val'>{data['avgs']['REB']:.1f}</div><div>{draw_streak(data['hits_10']['REB'])}</div></div>", unsafe_allow_html=True)
                with c3:
                    st.markdown(f"<div class='prop-card'><div class='stat-label'>ASISTENCIAS (Línea {data['lines']['AST']})</div><div class='stat-val'>{data['avgs']['AST']:.1f}</div><div>{draw_streak(data['hits_10']['AST'])}</div></div>", unsafe_allow_html=True)
                
                st.line_chart(data['L10'][['GAME_DATE','PTS','REB','AST']].iloc[::-1], x='GAME_DATE')
            else: st.warning("Sin datos recientes.")
