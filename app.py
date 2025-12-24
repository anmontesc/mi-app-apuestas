import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

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
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. MOTOR DE DATOS MULTI-TEMPORADA
# ==========================================
@st.cache_data(ttl=3600) 
def cargar_datos_web(deporte):
    dfs = []
    
    # Lista de temporadas a escanear (Pasado, Presente, Futuro)
    temporadas = ['2324', '2425', '2526'] 
    
    # Códigos de ligas en Football-Data
    ligas_codes = {
        "🇪🇸 La Liga": "SP1",
        "🇬🇧 Premier": "E0",
        "🇮🇹 Serie A": "I1",
        "🇩🇪 Bundesliga": "D1",
        "🇫🇷 Ligue 1": "F1"
    }

    if deporte == "⚽ FÚTBOL":
        base_url = "https://www.football-data.co.uk/mmz4281/"
        cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 
                'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
        
        for season in temporadas:
            for nombre_liga, codigo in ligas_codes.items():
                url = f"{base_url}{season}/{codigo}.csv"
                try:
                    # Intentamos descargar. Si la temporada 25/26 no existe aún, saltará al except
                    df = pd.read_csv(url, usecols=lambda c: c in cols)
                    df['League'] = nombre_liga
                    df['Season'] = season # Etiquetamos la temporada
                    dfs.append(df)
                except:
                    # Simplemente ignoramos si el archivo no existe (normal para 25/26 al principio)
                    continue
                
    elif deporte == "🏀 NBA":
        # NBA sigue siendo archivo local o URL única, ya que no hay repositorio histórico estándar fácil
        try:
            df = pd.read_csv("NBA.csv")
            if 'PTS' in df.columns: 
                 df = df.rename(columns={'Visitor/Neutral': 'AwayTeam', 'Home/Neutral': 'HomeTeam', 'PTS': 'FTAG', 'PTS.1': 'FTHG'})
            df['League'] = "🇺🇸 NBA"
            dfs.append(df)
        except:
            pass

    if not dfs: return None, []

    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    # Ordenamos por fecha para que el análisis .tail() coja siempre los MÁS RECIENTES
    df = df.sort_values('Date').reset_index(drop=True).dropna(subset=['Date'])
    
    return df, df['League'].unique()

# ==========================================
# 2. MOTOR DE CÁLCULO
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    # Cogemos los últimos 10 partidos GLOBALES (pueden ser de este año o del anterior)
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    # --- DATOS LOCAL ---
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
    
    # --- DATOS VISITANTE ---
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
    
    # --- GENERADOR DE SEÑALES ---
    ops = []
    
    # Tiros (Visitante)
    if ls['Fouls'] >= 10.0 and vs['G_Conc'] <= 1.5: 
        ops.append(("🎯 TIROS VISITANTE", "+2.5 Tiros a Puerta", 78))
    
    # Tarjetas
    proj = ls['Cards'] + vs['Cards'] + (ref_avg - 4.0)
    if ls['Prob_Card'] >= 0.85 and vs['Prob_Card'] >= 0.85: 
        ops.append(("🟨 AMBOS RECIBEN", "Sí (Probabilidad Alta)", 90))
    if proj >= 5.0: 
        ops.append(("🔥 OVER TARJETAS", "+4.5 Tarjetas (Partido Tenso)", 75))
    elif proj <= 3.5:
        ops.append(("🕊️ UNDER TARJETAS", "-4.5 Tarjetas (Partido Limpio)", 70))
        
    # Córners / Goles
    if (ls['Corn']+vs['Corn']) >= 9.5: 
        ops.append(("🚩 CÓRNERS", "+8.5 Total del Partido", 80))
    if (ls['G_2H']+vs['G_2H']) >= 1.4: 
        ops.append(("⏱️ GOL TARDÍO", "Gol en la 2ª Parte", 80))
    if ls['BTTS'] >= 0.65 and vs['BTTS'] >= 0.65:
        ops.append(("⚽ AMBOS MARCAN", "Sí (Tendencia BTTS)", 75))
    
    return ls, vs, ops

def analizar_nba(df, local, visitante):
    # Lógica NBA
    def get_stats(t):
        m = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(10)
        if len(m)<5: return None
        pts, pts_a, tot = [], [], []
        for _,r in m.iterrows():
            if r['HomeTeam']==t: p=r['FTHG']; pa=r['FTAG']
            else: p=r['FTAG']; pa=r['FTHG']
            pts.append(p); pts_a.append(pa); tot.append(p+pa)
        return {'PTS': np.mean(pts), 'DEF': np.mean(pts_a), 'TOT': np.mean(tot)}
    
    l, v = get_stats(local), get_stats(visitante)
    if not l or not v: return None, None, None
    
    ops = []
    pace = (l['TOT'] + v['TOT']) / 2
    if pace > 230: ops.append(("🏀 OVER PUNTOS", f"+{int(pace)-6} Puntos", 80))
    if l['DEF'] > 118: ops.append(("🎯 PUNTOS VISITA", "Over Puntos Equipo Visitante", 82))
    
    return l, v, ops

# ==========================================
# 3. INTERFAZ
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.caption("v18.0 | Multi-Season Engine")
deporte = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA"])

# Mensaje de carga
with st.spinner('Conectando con servidores de datos (23/24, 24/25, 25/26)...'):
    df, ligas = cargar_datos_web(deporte)

if df is None or df.empty:
    st.error(f"❌ No hay datos disponibles para {deporte}.")
    if deporte == "🏀 NBA": st.info("Recuerda subir 'NBA.csv' a GitHub.")
else:
    # --- FÚTBOL ---
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
                st.markdown(f"<h2 style='text-align:center'>{l} <span style='color:#666'>vs</span> {v}</h2>", unsafe_allow_html=True)
                
                # KPIs principales
                c1, c2, c3 = st.columns(3)
                c1.metric("Goles Esperados", f"{(ls['Goals']+vs['Goals'])/2:.2f}")
                c2.metric("Tarjetas Proy.", f"{(ls['Cards']+vs['Cards']+(ref_avg-4)):.1f}")
                c3.metric("Córners Proy.", f"{(ls['Corn']+vs['Corn']):.1f}")
                
                st.markdown("---")
                st.subheader("📡 Señales Detectadas")
                
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"""
                        <div class='card'>
                            <span class='signal-title'>{t}</span>
                            <span class='signal-conf'>{c}%</span>
                            <div style='color:#ccc; margin-top:5px;'>{d}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else: 
                    st.info("El algoritmo no detecta ineficiencias claras en este partido.")

    # --- NBA ---
    elif deporte == "🏀 NBA":
        eqs = sorted(df['HomeTeam'].unique())
        l = st.sidebar.selectbox("Home Team", eqs)
        v = st.sidebar.selectbox("Away Team", [x for x in eqs if x!=l])
        
        if st.sidebar.button("ANALIZAR NBA", type="primary"):
            ls, vs, ops = analizar_nba(df, l, v)
            if ls:
                c1, c2 = st.columns(2)
                c1.metric(l, f"{ls['PTS']:.1f} pts", f"Def: {ls['DEF']:.1f}")
                c2.metric(v, f"{vs['PTS']:.1f} pts", f"Def: {vs['DEF']:.1f}")
                
                st.markdown("---")
                st.subheader("📡 Señales NBA")
                if ops:
                    for t, d, c in ops:
                        st.markdown(f"""
                        <div class='card'>
                            <span class='signal-title'>{t}</span>
                            <span class='signal-conf'>{c}%</span>
                            <div style='color:#ccc; margin-top:5px;'>{d}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else: st.info("Sin señales claras.")
