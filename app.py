import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet Auto", page_icon="📡", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    .card {padding: 20px; background-color: #1a1c24; border: 1px solid #d4af37; margin-bottom: 10px; border-radius:10px;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. MOTOR DE DATOS (CONEXIÓN WEB)
# ==========================================
# ttl=3600 significa: "Mantén los datos 1 hora. Después, vuelve a descargarlos".
@st.cache_data(ttl=3600) 
def cargar_datos_web(deporte):
    dfs = []
    
    # --- FUENTES DE DATOS EN VIVO ---
    urls_futbol = {
        "🇪🇸 La Liga": "https://www.football-data.co.uk/mmz4281/2425/SP1.csv",
        "🇬🇧 Premier": "https://www.football-data.co.uk/mmz4281/2425/E0.csv",
        "🇮🇹 Serie A": "https://www.football-data.co.uk/mmz4281/2425/I1.csv",
        "🇩🇪 Bundesliga": "https://www.football-data.co.uk/mmz4281/2425/D1.csv",
        "🇫🇷 Ligue 1": "https://www.football-data.co.uk/mmz4281/2425/F1.csv"
    }
    
    # URL de NBA (Repositorio público que suele actualizarse, si falla, usa manual)
    # Nota: Los datos de NBA gratuitos y en vivo son difíciles. Este es un ejemplo.
    # Si este link falla en el futuro, habrá que buscar otro o subir manual.
    url_nba = "https://raw.githubusercontent.com/datasets/nba-games/master/data/nba-games.csv" 

    if deporte == "⚽ FÚTBOL":
        cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 
                'HC', 'AC', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
        
        for liga, url in urls_futbol.items():
            try:
                # Leemos directamente desde la URL
                df = pd.read_csv(url, usecols=lambda c: c in cols)
                df['League'] = liga
                dfs.append(df)
            except Exception as e:
                # Si falla una liga, no rompemos el programa, solo avisamos en consola
                print(f"Error cargando {liga}: {e}")
                
    elif deporte == "🏀 NBA":
        try:
            # Intentamos cargar NBA desde repositorio web
            # Nota: Si no encuentras un CSV estable de la temporada 24/25, 
            # esta parte es mejor seguir haciéndola manual subiendo 'NBA.csv'.
            # Aquí dejo preparado el código para leer el archivo local si existe,
            # o intentar web si tienes una URL válida.
            try:
                # Prioridad: Archivo local actualizado por ti (más fiable en NBA)
                df = pd.read_csv("NBA.csv")
                if 'PTS' in df.columns: # Adaptador
                     df = df.rename(columns={'Visitor/Neutral': 'AwayTeam', 'Home/Neutral': 'HomeTeam', 'PTS': 'FTAG', 'PTS.1': 'FTHG'})
                df['League'] = "🇺🇸 NBA"
                dfs.append(df)
            except:
                st.warning("⚠️ No se encuentra NBA.csv y no hay URL estable configurada.")
        except: pass

    if not dfs: return None, []

    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values('Date').reset_index(drop=True).dropna(subset=['Date'])
    
    return df, df['League'].unique()

# ==========================================
# 2. CÁLCULOS (MOTOR V15.1)
# ==========================================
def analizar_futbol(df, local, visitante, ref_avg):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    
    # Recolector de datos
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

    # Medias Local
    ls = {k: np.mean(v) for k,v in l_stats.items()}
    
    # Visitante (Solo necesitamos datos defensivos y clave)
    matches_v = df[(df['HomeTeam'] == visitante) | (df['AwayTeam'] == visitante)].tail(10)
    v_stats = {'G_Conc':[], 'Cards':[], 'Prob_Card':[], 'Corn':[], 'BTTS':[], 'G_2H':[]}
    for _, r in matches_v.iterrows():
        is_h = r['HomeTeam'] == visitante
        g, ga = (r['FTHG'], r['FTAG']) if is_h else (r['FTAG'], r['FTHG'])
        v_stats['G_Conc'].append(ga)
        v_stats['Cards'].append((r['HY']+r['HR']) if is_h else (r['AY']+r['AR']))
        v_stats['Prob_Card'].append(1 if v_stats['Cards'][-1]>0 else 0)
        v_stats['Corn'].append(r['HC'] if is_h else r['AC'])
        v_stats['BTTS'].append(1 if g>0 and ga>0 else 0)
        v_stats['G_2H'].append(g - (r['HTHG'] if is_h else r['HTAG']))
    
    vs = {k: np.mean(v) for k,v in v_stats.items()}
    
    # Oportunidades
    ops = []
    if ls['Fouls'] >= 10.0 and vs['G_Conc'] <= 1.5: ops.append(("🎯 TIROS VISITANTE", "+2.5 Tiros", 78, 1.55))
    
    proj = ls['Cards'] + vs['Cards'] + (ref_avg - 4.0)
    if ls['Prob_Card'] >= 0.85 and vs['Prob_Card'] >= 0.85: ops.append(("🟨 AMBOS TARJETA", "SÍ", 90, 1.45))
    if proj >= 5.0: ops.append(("🔥 OVER TARJETAS", "+4.5 Tarjetas", 75, 1.85))
    if (ls['Corn']+vs['Corn']) >= 9.5: ops.append(("🚩 CÓRNERS", "+8.5 Total", 80, 1.45))
    if (ls['G_2H']+vs['G_2H']) >= 1.4: ops.append(("⏱️ GOL TARDÍO", "Gol en 2ª Parte", 80, 1.40))
    
    return ls, vs, ops

def analizar_nba(df, local, visitante):
    # Lógica NBA simplificada para el ejemplo
    def get_stats(t):
        m = df[(df['HomeTeam'] == t) | (df['AwayTeam'] == t)].tail(10)
        if len(m)<5: return None
        pts = []; pts_a = []; tot = []
        for _,r in m.iterrows():
            if r['HomeTeam']==t: p=r['FTHG']; pa=r['FTAG']
            else: p=r['FTAG']; pa=r['FTHG']
            pts.append(p); pts_a.append(pa); tot.append(p+pa)
        return {'PTS': np.mean(pts), 'DEF': np.mean(pts_a), 'TOT': np.mean(tot)}
    
    l, v = get_stats(local), get_stats(visitante)
    if not l or not v: return None, None, None
    
    ops = []
    pace = (l['TOT'] + v['TOT']) / 2
    if pace > 230: ops.append(("🏀 OVER PUNTOS", f"+{int(pace)-5}", 80, 1.90))
    if l['DEF'] > 118: ops.append(("🎯 PUNTOS VISITA", "Over Equipo", 82, 1.85))
    
    return l, v, ops

# ==========================================
# 3. INTERFAZ
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.info("📡 Modo Conectado: Descargando datos en vivo...")
deporte = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA"])

df, ligas = cargar_datos_web(deporte)

if df is None or df.empty:
    st.error("❌ No se pudieron descargar datos. Verifica tu conexión o las fuentes.")
else:
    if deporte == "⚽ FÚTBOL":
        liga = st.sidebar.selectbox("Liga", ligas)
        df_liga = df[df['League'] == liga]
        eqs = sorted(df_liga['HomeTeam'].unique())
        l = st.sidebar.selectbox("Local", eqs)
        v = st.sidebar.selectbox("Visitante", [x for x in eqs if x!=l])
        
        # Árbitro inteligente (Si la liga tiene datos)
        ref_avg = 4.5
        if 'Referee' in df_liga.columns:
            df_liga['TC'] = df_liga['HY']+df_liga['AY']+df_liga['HR']+df_liga['AR']
            refs = df_liga.groupby('Referee')['TC'].mean().to_dict()
            r_sel = st.sidebar.selectbox("Árbitro", ["Desconocido"] + sorted(list(refs.keys())))
            if r_sel != "Desconocido": ref_avg = refs[r_sel]
        else:
            ref_avg = st.sidebar.number_input("Media Árbitro (Manual)", 0.0, 10.0, 4.5)

        bank = st.sidebar.number_input("Banca", 100, 10000, 1000)
        
        if st.sidebar.button("ANALIZAR"):
            ls, vs, ops = analizar_futbol(df, l, v, ref_avg)
            if ls:
                st.markdown(f"## {l} vs {v}")
                c1, c2 = st.columns(2)
                c1.metric("Goles Local", f"{ls['Goals']:.2f}")
                c2.metric("Goles Visita", f"{vs['Goals']:.2f}")
                
                st.markdown("---")
                if ops:
                    for t, d, c, quota in ops:
                         stake = bank * ((((quota-1)*(c/100))-(1-(c/100)))/(quota-1)*0.5)
                         st.markdown(f"<div class='card'><b style='color:#d4af37'>{t}</b><br>{d}<br>Stake: {max(0, stake):.1f}€</div>", unsafe_allow_html=True)
                else: st.info("Sin señales claras.")

    elif deporte == "🏀 NBA":
        st.warning("⚠️ Nota: Asegúrate de tener 'NBA.csv' actualizado en GitHub o una URL válida.")
        eqs = sorted(df['HomeTeam'].unique())
        l = st.sidebar.selectbox("Home", eqs)
        v = st.sidebar.selectbox("Away", [x for x in eqs if x!=l])
        
        if st.sidebar.button("ANALIZAR NBA"):
            ls, vs, ops = analizar_nba(df, l, v)
            if ls:
                col1, col2 = st.columns(2)
                col1.metric(l, f"{ls['PTS']:.1f} pts")
                col2.metric(v, f"{vs['PTS']:.1f} pts")
                if ops:
                    for t, d, c, q in ops:
                        st.success(f"{t}: {d}")
