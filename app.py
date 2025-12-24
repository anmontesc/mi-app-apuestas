import streamlit as st
import pandas as pd
import numpy as np

# ==========================================
# CONFIGURACIÓN VISUAL
# ==========================================
st.set_page_config(page_title="Komercial Bet: Pattern Hunter", page_icon="🕵️", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    
    .pattern-box {
        background-color: #1e2130;
        border-left: 5px solid #d4af37;
        padding: 15px;
        margin-bottom: 10px;
        border-radius: 5px;
    }
    .pattern-title {color: #d4af37; font-weight: bold; font-size: 18px;}
    .pattern-desc {color: #ccc; font-size: 14px;}
    
    div[data-testid="stImage"] > img {display: block; margin-left: auto; margin-right: auto;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 0. LOGOS
# ==========================================
def get_team_logo(team_name):
    # Logos básicos (Puedes ampliar la lista)
    logos = {
        "Boston Celtics": "https://upload.wikimedia.org/wikipedia/en/thumb/8/8f/Boston_Celtics.svg/1200px-Boston_Celtics.svg.png",
        "Denver Nuggets": "https://upload.wikimedia.org/wikipedia/en/thumb/7/76/Denver_Nuggets.svg/100px-Denver_Nuggets.svg.png",
        "Los Angeles Lakers": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Los_Angeles_Lakers_logo.svg/1200px-Los_Angeles_Lakers_logo.svg.png",
        "Golden State Warriors": "https://upload.wikimedia.org/wikipedia/en/thumb/0/01/Golden_State_Warriors_logo.svg/1200px-Golden_State_Warriors_logo.svg.png"
    }
    return logos.get(team_name, "https://cdn-icons-png.flaticon.com/512/1665/1665926.png")

# ==========================================
# 1. MOTOR NBA (CARGA CSV)
# ==========================================
@st.cache_data
def cargar_datos_nba():
    try:
        df = pd.read_csv("nba_stats.csv")
        # Limpieza y Conversión
        df = df[df['Rk'] != 'Rk'] # Quitar cabeceras repetidas
        cols_num = ['W', 'L', 'ORtg', 'DRtg', 'NRtg', 'MOV']
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
        return df
    except: return None

# ==========================================
# 2. MOTOR DE PATRONES (Lógica Condicional)
# ==========================================
def buscar_patrones_nba(h, a):
    patrones = []
    
    # DATOS NORMALIZADOS
    # Usamos .get() por si alguna columna falla, con valor default seguro
    h_ortg = h.get('ORtg', 110); h_drtg = h.get('DRtg', 110)
    a_ortg = a.get('ORtg', 110); a_drtg = a.get('DRtg', 110)
    h_mov = h.get('MOV', 0); a_mov = a.get('MOV', 0)
    h_win = h.get('W', 0) / (h.get('W', 1) + h.get('L', 1)) # Win %
    
    # --- PATRÓN 1: EL CAÑÓN DE CRISTAL (Glass Cannon) ---
    # Lógica: Ataque Élite vs Defensa Coladero = Lluvia de puntos
    if h_ortg >= 118.0 and a_drtg >= 116.0:
        patrones.append({
            "titulo": "🔥 CAÑÓN DE CRISTAL (Local)",
            "condicion": f"Local ORtg ({h_ortg}) es Élite y Visita DRtg ({a_drtg}) es Pésimo.",
            "evento": f"El Local superará su línea de puntos (+118 pts).",
            "confianza": 85
        })
        
    if a_ortg >= 118.0 and h_drtg >= 116.0:
        patrones.append({
            "titulo": "🔥 CAÑÓN DE CRISTAL (Visitante)",
            "condicion": f"Visita ORtg ({a_ortg}) es Élite y Local DRtg ({h_drtg}) es Pésimo.",
            "evento": f"El Visitante superará su línea de puntos (+115 pts).",
            "confianza": 85
        })

    # --- PATRÓN 2: EL FALSO FAVORITO (Paper Tiger) ---
    # Lógica: Local gana mucho (W%) pero por poco margen (MOV). Está sobrevalorado.
    if h_win > 0.60 and h_mov < 2.5 and a_mov > -1.0:
        patrones.append({
            "titulo": "🐯 FALSO FAVORITO (Paper Tiger)",
            "condicion": f"Local gana mucho ({h_win:.0%}) pero con poco margen (+{h_mov}).",
            "evento": "El Visitante cubrirá el Hándicap (Spread). Partido trampa.",
            "confianza": 75
        })

    # --- PATRÓN 3: LA MURALLA (The Grind) ---
    # Lógica: Dos equipos que defienden bien y atacan regular.
    if h_drtg < 112.0 and a_drtg < 112.0 and h_ortg < 115.0:
        patrones.append({
            "titulo": "🧱 LA MURALLA (Defensive Grind)",
            "condicion": "Ambos equipos permiten < 112 pts por 100 posesiones.",
            "evento": "UNDER de Puntos Total. Partido lento y físico.",
            "confianza": 80
        })

    # --- PATRÓN 4: DESAJUSTE TOTAL (Mismatch) ---
    # Lógica: Uno es muy bueno en NetRating y el otro muy malo.
    net_diff = h.get('NRtg', 0) - a.get('NRtg', 0)
    if net_diff > 9.0:
        patrones.append({
            "titulo": "🚜 APLASTADORA (Blowout)",
            "condicion": f"Diferencia de NetRating abismal (+{net_diff}).",
            "evento": "Victoria cómoda del Local por +10 puntos.",
            "confianza": 90
        })

    return patrones

# ==========================================
# 3. MOTOR FÚTBOL (Tus patrones originales)
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

def analizar_futbol(df, local, visitante):
    matches = df[(df['HomeTeam'] == local) | (df['AwayTeam'] == local)].tail(10)
    if len(matches) < 5: return None
    # Medias Simples
    l_fouls = np.mean([r['HF'] if r['HomeTeam']==local else r['AF'] for _,r in matches.iterrows()])
    matches_v = df[(df['HomeTeam'] == visitante) | (df['AwayTeam'] == visitante)].tail(10)
    v_conc = np.mean([r['FTAG'] if r['HomeTeam']==visitante else r['FTHG'] for _,r in matches_v.iterrows()])
    
    patrones = []
    # PATRÓN FÚTBOL (Tuyo)
    if l_fouls >= 10.0 and v_conc <= 1.5:
        patrones.append(("🎯 TIROS VISITANTE", f"Local agresivo ({l_fouls:.1f} faltas) vs Visita rocoso.", 78))
        
    return patrones

# ==========================================
# 4. INTERFAZ
# ==========================================
st.sidebar.title("💎 KOMERCIAL BET")
st.sidebar.caption("v27.0 | Pattern Hunter")
modo = st.sidebar.selectbox("Deporte", ["⚽ FÚTBOL", "🏀 NBA PATTERNS"])

if modo == "⚽ FÚTBOL":
    # (Código Fútbol Simplificado para dar prioridad a NBA aquí)
    df, ligas = cargar_datos_futbol()
    if df is not None:
        liga = st.sidebar.selectbox("Liga", ligas)
        df_liga = df[df['League'] == liga]
        eqs = sorted(df_liga['HomeTeam'].unique())
        l = st.sidebar.selectbox("Local", eqs)
        v = st.sidebar.selectbox("Visitante", [x for x in eqs if x!=l])
        if st.sidebar.button("BUSCAR PATRONES"):
            pats = analizar_futbol(df, l, v)
            if pats:
                for t, d, c in pats:
                     st.markdown(f"<div class='pattern-box'><div class='pattern-title'>{t}</div><div>{d}</div></div>", unsafe_allow_html=True)
            else: st.info("Ningún patrón estadístico coincide hoy.")

elif modo == "🏀 NBA PATTERNS":
    df_nba = cargar_datos_nba()
    
    if df_nba is not None:
        teams_list = sorted(df_nba['Team'].unique())
        l = st.sidebar.selectbox("Local", teams_list)
        v = st.sidebar.selectbox("Visitante", [x for x in teams_list if x!=l])
        
        if st.sidebar.button("ANALIZAR EMPAREJAMIENTO", type="primary"):
            # Obtener datos fila
            h_stats = df_nba[df_nba['Team'] == l].iloc[0]
            a_stats = df_nba[df_nba['Team'] == v].iloc[0]
            
            # Cabecera
            st.markdown(f"<h2 style='text-align:center'>{l} vs {v}</h2>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.metric("Ataque (ORtg)", f"{h_stats['ORtg']}", f"Vs {a_stats['ORtg']}")
            c2.metric("Defensa (DRtg)", f"{h_stats['DRtg']}", f"Vs {a_stats['DRtg']}")
            st.markdown("---")
            
            # BUSCADOR DE PATRONES
            st.subheader("🕵️ PATRONES DETECTADOS")
            
            patrones = buscar_patrones_nba(h_stats, a_stats)
            
            if patrones:
                for p in patrones:
                    st.markdown(f"""
                    <div class='pattern-box'>
                        <div style='display:flex; justify-content:space-between'>
                            <span class='pattern-title'>{p['titulo']}</span>
                            <span style='color:#00ff7f; font-weight:bold'>{p['confianza']}%</span>
                        </div>
                        <div style='margin-top:5px; font-style:italic; color:#aaa'>Condición: {p['condicion']}</div>
                        <div style='margin-top:5px; font-weight:bold; color:white'>👉 {p['evento']}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("El sistema ha estudiado el partido pero NO ha encontrado patrones claros de alta probabilidad.")
                st.markdown("*Significa que el partido está equilibrado y no hay ineficiencias estadísticas que explotar.*")
    else:
        st.error("Sube 'nba_stats.csv' para activar el motor.")
