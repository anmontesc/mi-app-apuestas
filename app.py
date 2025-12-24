import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import datetime

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet Pro", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    .card {
        padding: 15px; 
        background-color: #1a1c24; 
        border-left: 5px solid #d4af37; 
        margin-bottom: 10px; 
        border-radius: 5px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .signal-title {color: #d4af37; font-weight: bold; font-size: 18px;}
    .signal-conf {float: right; color: #00ff7f; font-weight: bold;}
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. LOGOS
# ==========================================
def get_team_logo(team_name):
    # Mapeo básico de nombres de Basketball-Reference a URLs
    logos = {
        "Boston Celtics": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8f/Boston_Celtics.svg/1200px-Boston_Celtics.svg.png",
        "Los Angeles Lakers": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Los_Angeles_Lakers_logo.svg/1200px-Los_Angeles_Lakers_logo.svg.png",
        "Golden State Warriors": "https://upload.wikimedia.org/wikipedia/en/thumb/0/01/Golden_State_Warriors_logo.svg/1200px-Golden_State_Warriors_logo.svg.png",
        "Miami Heat": "https://upload.wikimedia.org/wikipedia/en/thumb/f/fb/Miami_Heat_logo.svg/1200px-Miami_Heat_logo.svg.png",
        "Chicago Bulls": "https://upload.wikimedia.org/wikipedia/en/thumb/6/67/Chicago_Bulls_logo.svg/1200px-Chicago_Bulls_logo.svg.png",
        "Dallas Mavericks": "https://upload.wikimedia.org/wikipedia/en/thumb/9/97/Dallas_Mavericks_logo18.svg/1200px-Dallas_Mavericks_logo18.svg.png",
        "Real Madrid": "https://upload.wikimedia.org/wikipedia/en/thumb/5/56/Real_Madrid_CF.svg/1200px-Real_Madrid_CF.svg.png",
        "Barcelona": "https://upload.wikimedia.org/wikipedia/en/thumb/4/47/FC_Barcelona_%28crest%29.svg/1200px-FC_Barcelona_%28crest%29.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

# ==========================================
# 1. MOTOR DE DATOS (SCRAPER INCLUIDO)
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_datos_web(deporte):
    dfs = []
    
    if deporte == "⚽ FÚTBOL":
        temporadas = ['2324', '2425', '2526'] 
        ligas_codes = {"🇪🇸 La Liga": "SP1", "🇬🇧 Premier": "E0", "🇮🇹 Serie A": "I1", "🇩🇪 Bundesliga": "D1", "🇫🇷 Ligue 1": "F1"}
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

    elif deporte == "🏀 NBA":
        # --- NBA SCRAPER BASKETBALL-REFERENCE ---
        # Año actual para la URL (Si estamos en dic 2024, la temporada es 2025)
        year = 2025
        months = ['october', 'november', 'december', 'january', 'february', 'march', 'april']
        
        for m in months:
            url = f"https://www.basketball-reference.com/leagues/NBA_{year}_games-{m}.html"
            try:
                # Pandas lee las tablas HTML automáticamente
                tables = pd.read_html(url)
                if tables:
                    df_m = tables[0]
                    # Limpieza básica
                    # Renombrar columnas para que coincidan con nuestro sistema
                    # Visitor/Neutral -> AwayTeam, Home/Neutral -> HomeTeam, PTS -> FTAG/FTHG
                    rename_map = {
                        'Visitor/Neutral': 'AwayTeam',
                        'Home/Neutral': 'HomeTeam',
                        'PTS': 'FTAG',
                        'PTS.1': 'FTHG',
                        'Date': 'Date'
                    }
                    df_m = df_m.rename(columns=rename_map)
                    
                    # Filtramos solo columnas útiles y filas válidas (partidos jugados)
                    if 'FTHG' in df_m.columns and 'FTAG' in df_m.columns:
                        df_m = df_m.dropna(subset=['FTHG', 'FTAG']) # Solo partidos terminados
                        df_m = df_m[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']]
                        df_m['League'] = "🇺🇸 NBA"
                        dfs.append(df_m)
            except Exception as e:
                # Si el mes aún no existe o falla la conexión, continuamos
                continue

    if not dfs: return None, []

    df = pd.concat(dfs, ignore_index=True)
    
    # Limpieza de fechas
    if deporte == "🏀 NBA":
        # Formato Basketball-Ref: "Tue, Oct 24, 2023"
        df['Date'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
    else:
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
    df = df.sort_values('Date').reset_index(drop=True).dropna(subset=['Date'])
    
    return df, df['League'].unique()

# ==========================================
# 2. MOTOR DE CÁLCULO
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    # Recolectores
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
    if ls['Prob_Card'] >= 0.85 and vs['Prob_Card'] >= 0.85: ops.append(("🟨 AMBOS RECIBEN", "Sí (Probabilidad Alta)", 90))
    if proj >= 5.0: ops.append(("🔥 OVER TARJETAS", "+4.5 Tarjetas (Tenso)", 75))
    elif proj <= 3.5: ops.append(("🕊️ UNDER TARJETAS", "-4.5 Tarjetas (Limpio)", 70))
    if (ls['Corn']+vs['Corn']) >= 9.5: ops.append(("🚩 CÓRNERS", "+8.5 Total", 80))
    if (ls['G_2H']+vs['G_2H']) >= 1.4: ops.append(("⏱️ GOL TARDÍO", "Gol en la 2ª Parte", 80))
    if ls['BTTS'] >= 0.65 and vs['BTTS'] >= 0.65: ops.append(("⚽ AMBOS MARCAN", "Sí (BTTS)", 75))
    
    return ls, vs, ops

def analizar_nba(df, local, visitante):
    def get_stats(t):
        m = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(10)
        if len(m)<5: return None
        pts, pts_a, tot = [], [], []
        for _,r in m.iterrows():
            if r['HomeTeam']==t: p=r['FTHG']; pa=r['FTAG']
            else: p=r['FTAG']; pa=r['FTHG']
            pts.append(p); pts_a.append(pa); tot.append(p+pa)
        # Forma simple (Puntos anotados - recibidos en los ultimos 5)
        last_5 = m.tail(5)
        diff = []
        for _,r in last_5.iterrows():
            if r['HomeTeam']==t: diff.append(r['FTHG'] - r['FTAG'])
            else: diff.append(r['FTAG'] - r['FTHG'])
            
        return {'PTS': np.mean(pts), 'DEF': np.mean(pts_a), 'TOT': np.mean(tot), 'FORMA': np.mean(diff)}
    
    l, v = get_stats(local), get_stats(visitante)
    if not l or not v: return None, None, None
    
    ops = []
    pace = (l['TOT'] + v['TOT']) / 2
    
    # 1. Over/Under Puntos
    if pace > 235: ops.append(("🏀 OVER PUNTOS", f"+{int(pace)-5} (Ritmo Frenético)", 80))
    elif pace < 210: ops.append(("🛡️ UNDER PUNTOS", f"-{int(pace)+5} (Ritmo Lento)", 75))
    
    # 2. Hándicap (Spread) - Aproximación
    diff = l['FORMA'] - v['FORMA'] + 3 # +3 por factor cancha
    if diff > 7: ops.append(("💪 LOCAL CUBRE", f"{local} gana fácil", 75))
    elif diff < -5: ops.append(("💪 VISITANTE CUBRE", f"{visitante} compite/gana", 75))
    
    # 3. Props
    if l['DEF'] > 120: ops.append(("🎯 PUNTOS VISITA", f"{visitante} Over Puntos Equipo", 85))
    if v['DEF'] > 120: ops.append(("🎯 PUNTOS LOCAL", f"{local} Over Puntos Equipo", 85))
    
    return l, v, ops

# ==========================================
# 3. INTERFAZ
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.caption("v20.0 | Live Scraper")
deporte = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA"])

with st.spinner(f'Analizando mercados en vivo ({deporte})...'):
    df, ligas = cargar_datos_web(deporte)

if df is None or df.empty:
    st.error(f"❌ No se han encontrado datos para {deporte}.")
    if deporte == "🏀 NBA": st.info("Intenta subir un archivo 'NBA.csv' manual si el scraper falla.")
else:
    if deporte == "⚽ FÚTBOL":
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
        else:
            ref_avg = st.sidebar.number_input("Media Árbitro (Manual)", 0.0, 10.0, 4.5)

        if st.sidebar.button("ANALIZAR", type="primary"):
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
                
                # KPIs
                c1, c2, c3 = st.columns(3)
                c1.metric("Goles Esperados", f"{(ls['Goals']+vs['Goals'])/2:.2f}")
                c2.metric("Tarjetas Proy.", f"{(ls['Cards']+vs['Cards']+(ref_avg-4)):.1f}")
                c3.metric("Córners Proy.", f"{(ls['Corn']+vs['Corn']):.1f}")
                
                st.subheader("📡 Señales Detectadas")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='card'><span class='signal-title'>{t}</span><span class='signal-conf'>{c}%</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

    elif deporte == "🏀 NBA":
        eqs = sorted(df['HomeTeam'].unique())
        l = st.sidebar.selectbox("Home", eqs)
        v = st.sidebar.selectbox("Away", [x for x in eqs if x!=l])
        
        if st.sidebar.button("ANALIZAR NBA", type="primary"):
            ls, vs, ops = analizar_nba(df, l, v)
            if ls:
                col_l, col_vs, col_v = st.columns([1, 0.5, 1])
                with col_l:
                    st.image(get_team_logo(l), width=100)
                    st.metric(l, f"{ls['PTS']:.1f} PTS")
                with col_vs:
                    st.markdown("<br><h1 style='text-align:center; color:#ff5722'>VS</h1>", unsafe_allow_html=True)
                with col_v:
                    st.image(get_team_logo(v), width=100)
                    st.metric(v, f"{vs['PTS']:.1f} PTS")
                
                st.markdown("---")
                st.subheader("📡 Señales NBA")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"<div class='card'><span class='signal-title'>{t}</span><span class='signal-conf'>{c}%</span><br>{d}</div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")
