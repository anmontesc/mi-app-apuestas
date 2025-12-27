import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import poisson
import difflib # Para encontrar nombres de equipos parecidos

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Live Center", page_icon="📲", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    
    /* Estilo Botón Partido */
    .stButton button {
        width: 100%;
        background-color: #1e2130;
        border: 1px solid #444;
        color: white;
        text-align: left;
        padding: 15px;
        margin-bottom: 5px;
    }
    .stButton button:hover {
        border-color: #d4af37;
        color: #d4af37;
    }
    
    .scientific-card {
        background-color: #1e2130;
        border-left: 5px solid #00b4d8;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 5px;
    }
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
# 2. MOTOR DE PARTIDOS DE HOY (Live Scraper)
# ==========================================
@st.cache_data(ttl=1800) # Se actualiza cada 30 mins
def cargar_partidos_hoy():
    try:
        # Usamos FBref para sacar los partidos del día (Es muy fiable)
        url = "https://fbref.com/en/matches/"
        tables = pd.read_html(url)
        
        # FBref suele poner todos los partidos en la primera tabla
        df_hoy = tables[0]
        
        # Limpieza básica
        # Filtramos columnas necesarias: Hora, Local, Visitante, Competición
        if 'Home' in df_hoy.columns and 'Away' in df_hoy.columns:
            df_hoy = df_hoy[['Time', 'Home', 'Away', 'Competition', 'Round']]
            df_hoy = df_hoy.dropna(subset=['Home', 'Away'])
            return df_hoy
    except:
        return None

# ==========================================
# 3. TRADUCTOR DE EQUIPOS (Fuzzy Logic)
# ==========================================
def encontrar_equipo_db(nombre_live, lista_db):
    # Busca el nombre más parecido en nuestra base de datos histórica
    # Ej: "Nott'm Forest" (Live) -> "Nottm Forest" (DB)
    matches = difflib.get_close_matches(nombre_live, lista_db, n=1, cutoff=0.6)
    if matches:
        return matches[0]
    return None

# ==========================================
# 4. MOTORES CIENTÍFICOS (V28)
# ==========================================
def calcular_gap_rating(df, team):
    matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)].tail(10)
    if len(matches) < 5: return 0
    gap = 0
    for _, r in matches.iterrows():
        if r['HomeTeam'] == team: g=r['FTHG']; t=r['HST']; c=r['HC']
        else: g=r['FTAG']; t=r['AST']; c=r['AC']
        gap += (g * 1.0) + (t * 0.4) + (c * 0.2)
    return gap / len(matches)

def analizar_arbitro(df_liga, referee_name):
    total = (df_liga['HY'] + df_liga['AY'] + df_liga['HR'] + df_liga['AR'])
    avg_league = total.mean()
    if referee_name:
        df_ref = df_liga[df_liga['Referee'] == referee_name]
        if len(df_ref) > 2:
            avg_ref = (df_ref['HY'] + df_ref['AY'] + df_ref['HR'] + df_ref['AR']).mean()
            return (avg_ref / avg_league) if avg_league > 0 else 1.0, avg_ref
    return 1.0, 4.0 # Default

def predecir_poisson(l_h, l_a):
    mh, ma = 6, 6
    ph = [poisson.pmf(i, l_h) for i in range(mh)]
    pa = [poisson.pmf(i, l_a) for i in range(ma)]
    pm = np.outer(ph, pa)
    return np.sum(np.tril(pm, -1)), np.sum(np.diag(pm)), np.sum(np.triu(pm, 1))

# ==========================================
# 5. INTERFAZ TIPO "APP MÓVIL"
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.info("Modo: Live Match Browser")

# A. CARGA DE DATOS
with st.spinner("Conectando con satélites de fútbol..."):
    df_db, ligas_db = cargar_db_historica()
    df_live = cargar_partidos_hoy()

# B. NAVEGADOR DE PARTIDOS (PÁGINA PRINCIPAL)
if 'partido_seleccionado' not in st.session_state:
    st.session_state.partido_seleccionado = None

if st.session_state.partido_seleccionado is None:
    st.markdown("## 📅 Partidos de Hoy")
    
    if df_live is not None and not df_live.empty:
        # Agrupar por Liga
        competitions = df_live['Competition'].unique()
        
        # Filtro: Solo mostrar ligas "Top" para no saturar (Opcional)
        # Puedes quitar esto para ver todo
        top_leagues = [c for c in competitions if any(x in str(c) for x in ['Premier', 'Liga', 'Serie A', 'Bundesliga', 'Ligue 1'])]
        others = [c for c in competitions if c not in top_leagues]
        
        # Mostrar Ligas Top Primero
        for comp in top_leagues + others:
            matches_in_comp = df_live[df_live['Competition'] == comp]
            if matches_in_comp.empty: continue
            
            with st.expander(f"🏆 {comp}", expanded=True if comp in top_leagues else False):
                for _, row in matches_in_comp.iterrows():
                    match_label = f"🕒 {row['Time']} | **{row['Home']}** vs **{row['Away']}**"
                    if st.button(match_label, key=f"{row['Home']}-{row['Away']}"):
                        st.session_state.partido_seleccionado = {
                            'home': row['Home'],
                            'away': row['Away'],
                            'league_live': comp
                        }
                        st.rerun()
    else:
        st.warning("No se han encontrado partidos importantes hoy o la fuente está descansando.")
        st.info("Prueba a refrescar la página en unos minutos.")

# C. PANTALLA DE ANÁLISIS (DETALLE)
else:
    # Botón Volver
    if st.button("⬅️ VOLVER A LA LISTA"):
        st.session_state.partido_seleccionado = None
        st.rerun()

    sel = st.session_state.partido_seleccionado
    home_live = sel['home']
    away_live = sel['away']
    
    st.markdown(f"<h1 style='text-align:center'>{home_live} <span style='color:#666'>vs</span> {away_live}</h1>", unsafe_allow_html=True)
    
    # 1. TRADUCCIÓN DE NOMBRES (Live -> DB)
    equipos_db = df_db['HomeTeam'].unique()
    h_db = encontrar_equipo_db(home_live, equipos_db)
    a_db = encontrar_equipo_db(away_live, equipos_db)
    
    if h_db and a_db:
        # Encontramos los equipos en la base de datos histórica
        # Buscamos la liga en la DB (usando el equipo local)
        fila_equipo = df_db[df_db['HomeTeam'] == h_db].iloc[0]
        liga_db = fila_equipo['League']
        df_liga = df_db[df_db['League'] == liga_db]
        
        # EJECUTAR MOTOR CIENTÍFICO (V28)
        gap_h = calcular_gap_rating(df_db, h_db)
        gap_a = calcular_gap_rating(df_db, a_db)
        
        # Poisson
        l_h = gap_h * 0.45
        l_a = gap_a * 0.35
        p_w, p_d, p_l = predecir_poisson(l_h, l_a)
        
        # MOSTRAR RESULTADOS
        c1, c2 = st.columns(2)
        c1.metric(f"GAP {h_db}", f"{gap_h:.2f}")
        c2.metric(f"GAP {a_db}", f"{gap_a:.2f}")
        
        st.markdown("---")
        st.subheader("🧪 Proyecciones del Modelo")
        
        # Tarjetas Científicas
        col_sci1, col_sci2 = st.columns(2)
        
        with col_sci1:
            st.markdown(f"""
            <div class='scientific-card'>
                <div class='math-title'>PROBABILIDAD VICTORIA</div>
                <div class='math-val'>{p_w*100:.1f}% vs {p_l*100:.1f}%</div>
                <div class='math-desc'>Empate estimado: {p_d*100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_sci2:
            gap_diff = gap_h - gap_a
            if gap_diff > 1.5: msg = f"Dominio claro de {h_db}"
            elif gap_diff < -1.5: msg = f"Dominio claro de {a_db}"
            else: msg = "Partido muy ajustado"
            
            st.markdown(f"""
            <div class='scientific-card'>
                <div class='math-title'>DIAGNÓSTICO GAP</div>
                <div class='math-val'>{msg}</div>
                <div class='math-desc'>Basado en volumen ofensivo reciente</div>
            </div>
            """, unsafe_allow_html=True)

        # KELLY
        st.markdown("### 💰 Calculadora Kelly")
        cuota = st.number_input("Cuota que paga la casa por el Favorito", 1.0, 10.0, 2.0)
        prob_fav = max(p_w, p_l)
        b = cuota - 1
        q = 1 - prob_fav
        f = (b * prob_fav - q) / b
        stake = max(0, f * 0.3)
        
        if stake > 0:
            st.success(f"📈 APUESTA SUGERIDA: **{stake*100:.1f}%** del Bankroll")
        else:
            st.warning("📉 NO HAY VALOR: La cuota es demasiado baja para el riesgo real.")

    else:
        st.error(f"⚠️ No pude encontrar datos históricos suficientes para **{home_live}** o **{away_live}**.")
        st.info(f"Posiblemente sean equipos de una liga menor que no está en nuestra base de datos Premium (Big 5).")
        st.write(f"Nombre intentado buscar en DB: {h_db} vs {a_db}")
