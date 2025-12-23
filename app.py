import streamlit as st
import pandas as pd
import numpy as np
import glob
import os

# ==========================================
# CONFIGURACIÓN DE PÁGINA (ESTILO PREMIUM)
# ==========================================
st.set_page_config(
    page_title="Komercial Bet",
    page_icon="💎",
    layout="wide", # Usar todo el ancho de la pantalla
    initial_sidebar_state="expanded"
)

# Estilos CSS para dar look "Dark/Gold"
st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; text-align: center; font-family: 'Helvetica Neue', sans-serif;}
    h2, h3 {color: #e0e0e0;}
    .stMetric {background-color: #1f2937; padding: 10px; border-radius: 5px; border: 1px solid #374151;}
    .css-1d391kg {padding-top: 1rem;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. MOTOR DE CARGA INTELIGENTE (POR LIGAS)
# ==========================================
@st.cache_data
def cargar_datos():
    files = glob.glob("*.csv")
    if not files: return None, None, None
    
    dfs = []
    # Columnas necesarias
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 
            'HC', 'AC', 'HS', 'AS', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
    
    for f in files:
        try:
            df_check = pd.read_csv(f, nrows=1)
            use_cols = [c for c in cols if c in df_check.columns]
            df = pd.read_csv(f, usecols=use_cols)
            
            # ETIQUETADO DE LIGAS
            if "SP1" in f: df['League'] = "🇪🇸 La Liga"
            elif "E0" in f: df['League'] = "🇬🇧 Premier League"
            elif "I1" in f: df['League'] = "🇮🇹 Serie A"
            else: df['League'] = "🌍 Otra"
            
            dfs.append(df)
        except: pass

    if not dfs: return None, None, None

    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values('Date').reset_index(drop=True).dropna(subset=['Date'])
    
    if 'Referee' not in df.columns: df['Referee'] = 'Desconocido'

    # Estructura de equipos por liga
    ligas_disponibles = sorted(df['League'].unique())
    equipos_por_liga = {}
    for liga in ligas_disponibles:
        equipos = sorted(df[df['League'] == liga]['HomeTeam'].unique())
        equipos_por_liga[liga] = equipos
        
    return df, equipos_por_liga, ligas_disponibles

# ==========================================
# 2. PROCESAMIENTO MATEMÁTICO (V12)
# ==========================================
def calcular_metricas(df):
    # (El mismo motor potente de la V12, optimizado)
    stats_map = {team: [] for team in df['HomeTeam'].unique()}
    
    if 'Referee' in df.columns:
        df['TotalCards'] = df['HY'] + df['AY'] + df['HR'] + df['AR']
        ref_stats = df.groupby('Referee')['TotalCards'].mean().to_dict()
    else:
        ref_stats = {}

    estado = {} 
    PARTIDOS_MEDIA = 10

    for idx, row in df.iterrows():
        h, a = row['HomeTeam'], row['AwayTeam']
        # Cálculos seguros
        saves_h = max(0, row.get('AST', 0) - row.get('FTHG', 0))
        saves_a = max(0, row.get('HST', 0) - row.get('FTAG', 0))
        cards_h = row.get('HY', 0) + row.get('HR', 0)
        cards_a = row.get('AY', 0) + row.get('AR', 0)
        btts = 1 if (row.get('FTHG', 0) > 0 and row.get('FTAG', 0) > 0) else 0
        total_goals = row.get('FTHG', 0) + row.get('FTAG', 0)
        over25 = 1 if total_goals > 2.5 else 0
        under25 = 1 if total_goals < 2.5 else 0
        g_2h_h = row.get('FTHG', 0) - row.get('HTHG', 0)
        g_2h_a = row.get('FTAG', 0) - row.get('HTAG', 0)

        data_h = {'F': row.get('HF',0), 'SOT_F': row.get('HST',0), 'C_F': row.get('HC',0), 'G_F': row.get('FTHG',0), 'Cards': cards_h, 'Saves': saves_h, 'BTTS': btts, 'O25': over25, 'U25': under25, 'G2H': g_2h_h, 'SOT_A': row.get('AST',0)}
        data_a = {'F': row.get('AF',0), 'SOT_F': row.get('AST',0), 'C_F': row.get('AC',0), 'G_F': row.get('FTAG',0), 'Cards': cards_a, 'Saves': saves_a, 'BTTS': btts, 'O25': over25, 'U25': under25, 'G2H': g_2h_a, 'SOT_A': row.get('HST',0)}
        
        stats_map[h].append(data_h)
        stats_map[a].append(data_a)

    for eq, hist in stats_map.items():
        if len(hist) >= 5:
            ult = hist[-PARTIDOS_MEDIA:]
            n = len(ult)
            estado[eq] = {
                'Fouls': sum(x['F'] for x in ult)/n,
                'SOT_F': sum(x['SOT_F'] for x in ult)/n,
                'SOT_A': sum(x['SOT_A'] for x in ult)/n,
                'Corn_F': sum(x['C_F'] for x in ult)/n,
                'Gols_F': sum(x['G_F'] for x in ult)/n,
                'Gols_2H': sum(x['G2H'] for x in ult)/n,
                'Cards': sum(x['Cards'] for x in ult)/n,
                'Saves': sum(x['Saves'] for x in ult)/n,
                'P_BTTS': sum(x['BTTS'] for x in ult)/n,
                'P_O25': sum(x['O25'] for x in ult)/n,
                'P_U25': sum(x['U25'] for x in ult)/n,
                'P_Card': sum(1 for x in ult if x['Cards']>0)/n
            }
    return estado, ref_stats

# ==========================================
# 3. INTERFAZ GRÁFICA (FRONTEND)
# ==========================================

# CABECERA
st.markdown("<h1>💎 KOMERCIAL BET <span style='font-size:15px; color:grey'>V13</span></h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center;'>Inteligencia Artificial aplicada a mercados deportivos</p>", unsafe_allow_html=True)

df, equipos_dict, ligas = cargar_datos()

if df is None:
    st.error("❌ Error: No se detectan archivos CSV en el repositorio.")
    st.info("Asegúrate de subir SP1.csv, E0.csv, I1.csv a GitHub.")
else:
    # --- BARRA LATERAL (CONTROLES) ---
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # 1. Selector de Liga
        liga_sel = st.selectbox("Seleccionar Liga", ligas)
        
        # 2. Equipos (Filtrados)
        equipos_liga = equipos_dict[liga_sel]
        local = st.selectbox("Equipo Local", equipos_liga)
        
        # 3. Visitante (Eliminando al Local de la lista)
        vis_options = [x for x in equipos_liga if x != local]
        visitante = st.selectbox("Equipo Visitante", vis_options)
        
        # 4. Árbitro
        estado, ref_stats = calcular_metricas(df)
        lista_refs = sorted(list(ref_stats.keys()))
        referee = st.selectbox("Árbitro (Opcional)", ["Desconocido"] + lista_refs)
        
        st.markdown("---")
        analyze_btn = st.button("🚀 ANALIZAR MERCADOS", type="primary", use_container_width=True)
        st.caption("Powered by Komercial Bet AI")

    # --- PANEL CENTRAL (RESULTADOS) ---
    if analyze_btn:
        if local not in estado or visitante not in estado:
            st.error("⚠️ Datos insuficientes para generar predicción (Muestra < 5 partidos).")
        else:
            l = estado[local]
            v = estado[visitante]
            
            # --- SECCIÓN 1: HEAD TO HEAD (COMPARADOR) ---
            st.subheader("📊 Comparativa de Rendimiento (Medias 10p)")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Goles A Favor", f"{l['Gols_F']:.1f}", delta=f"{l['Gols_F']-v['Gols_F']:.1f}")
            col2.metric("Córners", f"{l['Corn_F']:.1f}", delta=f"{l['Corn_F']-v['Corn_F']:.1f}")
            col3.metric("Tarjetas", f"{l['Cards']:.1f}", delta=f"{l['Cards']-v['Cards']:.1f}", delta_color="inverse")
            col4.metric("Goles 2ª Parte", f"{l['Gols_2H']:.1f}", f"Vs {v['Gols_2H']:.1f} Vis")
            
            # --- SECCIÓN 2: MOTOR DE OPORTUNIDADES ---
            st.markdown("---")
            st.subheader("🔥 Oportunidades Detectadas")
            
            opciones = []
            
            # LÓGICA V12
            # Goles
            sum_g2h = l['Gols_2H'] + v['Gols_2H']
            if sum_g2h >= 1.5: opciones.append(("⏱️ GOL TARDÍO", f"Gol en 2ª Parte", f"Media combinada: {sum_g2h:.1f}", 80))
            if l['P_U25'] >= 0.60 and v['P_U25'] >= 0.60: opciones.append(("🛡️ UNDER 2.5", "Menos de 2.5 Goles", "Equipos cerrados", 70))
            if l['P_BTTS'] >= 0.65 and v['P_BTTS'] >= 0.65: opciones.append(("⚽ AMBOS MARCAN", "Sí (BTTS)", f"Prob: {l['P_BTTS']:.0%} / {v['P_BTTS']:.0%}", 75))
            
            # Porteros
            if v['SOT_F'] >= 5.0 and l['Saves'] >= 3.0: opciones.append(("🧤 PORTERO LOCAL", "+3.5 Paradas", f"Recibe {v['SOT_F']:.1f} tiros/p", 85))
            if l['SOT_F'] >= 5.0 and v['Saves'] >= 3.0: opciones.append(("🧤 PORTERO VISITA", "+3.5 Paradas", f"Recibe {l['SOT_F']:.1f} tiros/p", 85))
            
            # Córners
            tc = l['Corn_F'] + v['Corn_F']
            if tc >= 10.5: opciones.append(("🚩 CÓRNERS", "Más de 9.5", f"Proyección: {tc:.1f}", 75))
            if l['Corn_F'] >= 6.5: opciones.append(("🚩 CÓRNERS LOCAL", "Más de 5.5", f"Media: {l['Corn_F']:.1f}", 70))
            
            # Tarjetas
            t_cards = l['Cards'] + v['Cards']
            ref_txt = ""
            if referee != "Desconocido":
                r_avg = ref_stats[referee]
                t_cards += (r_avg - 4.0)
                ref_txt = f"(Ajuste: {r_avg:.1f})"
            
            if t_cards >= 5.5: opciones.append(("🟥 TARJETAS", "Más de 4.5", f"Proy: {t_cards:.1f} {ref_txt}", 80))
            if l['P_Card'] >= 0.85 and v['P_Card'] >= 0.85: opciones.append(("🟨 BTC", "Ambos Reciben Tarjeta", "Alta probabilidad", 90))

            # Tiros
            if l['Fouls'] >= 11: opciones.append(("🎯 TIROS", "Visitante +3.5 Tiros", "Local agresivo deja espacios", 65))

            # RENDERIZADO DE CARTAS
            if opciones:
                for titulo, apuesta, razon, confianza in opciones:
                    # Color según confianza
                    color = "green" if confianza > 80 else "orange"
                    
                    with st.container():
                        c1, c2 = st.columns([3, 1])
                        with c1:
                            st.markdown(f"**{titulo}**")
                            st.write(f"👉 {apuesta}")
                            st.caption(f"ℹ️ {razon}")
                        with c2:
                            st.progress(confianza, text=f"{confianza}% Fiabilidad")
                        st.markdown("---")
            else:
                st.info("💤 El algoritmo no detecta valor claro en los mercados principales para este partido.")

    else:
        # PANTALLA DE BIENVENIDA
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h3>Bienvenido al panel de control</h3>
            <p>Selecciona una liga y los equipos en la barra lateral para comenzar el análisis.</p>
        </div>
        """, unsafe_allow_html=True)
