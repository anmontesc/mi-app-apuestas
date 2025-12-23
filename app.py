import streamlit as st
import pandas as pd
import numpy as np
import glob
import os

# CONFIGURACIÓN
st.set_page_config(page_title="Betting IA Pro", page_icon="⚽", layout="centered")

# ==========================================
# 1. MOTOR DE CARGA (CON DIAGNÓSTICO)
# ==========================================
@st.cache_data
def cargar_datos():
    # Buscamos CSVs
    files = glob.glob("*.csv")
    
    # --- BLOQUE DE DIAGNÓSTICO ---
    if not files:
        st.error("❌ ERROR CRÍTICO: No encuentro los archivos .csv")
        st.warning(f"📂 Estoy buscando en la carpeta: {os.getcwd()}")
        st.info(f"📄 Archivos que SÍ veo aquí: {os.listdir()}")
        return None, None
    # -----------------------------
    
    dfs = []
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 
            'HC', 'AC', 'HS', 'AS', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
    
    contador = 0
    for f in files:
        try:
            df_check = pd.read_csv(f, nrows=1)
            use_cols = [c for c in cols if c in df_check.columns]
            df = pd.read_csv(f, usecols=use_cols)
            dfs.append(df)
            contador += 1
        except Exception as e:
            st.warning(f"⚠️ No pude leer {f}: {e}")

    if not dfs: return None, None

    df = pd.concat(dfs, ignore_index=True)
    df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
    df = df.sort_values('Date').reset_index(drop=True).dropna(subset=['Date'])
    
    if 'Referee' not in df.columns: df['Referee'] = 'Desconocido'
    
    return df, sorted(df['HomeTeam'].unique().tolist())

# ==========================================
# 2. CÁLCULO
# ==========================================
def calcular_metricas(df):
    stats_map = {team: [] for team in df['HomeTeam'].unique()}
    
    if 'Referee' in df.columns:
        df['TotalCards'] = df['HY'] + df['AY'] + df['HR'] + df['AR']
        ref_stats = df.groupby('Referee')['TotalCards'].mean().to_dict()
    else:
        ref_stats = {}

    estado_actual = {} 
    PARTIDOS_MEDIA = 10

    for idx, row in df.iterrows():
        h, a = row['HomeTeam'], row['AwayTeam']
        
        # Cálculos seguros (con .get para evitar errores si falta columna)
        saves_h = row.get('AST', 0) - row.get('FTHG', 0)
        saves_h = max(0, saves_h) # Evitar negativos
        
        saves_a = row.get('HST', 0) - row.get('FTAG', 0)
        saves_a = max(0, saves_a)

        cards_h = row.get('HY', 0) + row.get('HR', 0)
        cards_a = row.get('AY', 0) + row.get('AR', 0)
        
        btts = 1 if (row.get('FTHG', 0) > 0 and row.get('FTAG', 0) > 0) else 0
        total_goals = row.get('FTHG', 0) + row.get('FTAG', 0)
        over25 = 1 if total_goals > 2.5 else 0
        under25 = 1 if total_goals < 2.5 else 0
        
        g_2h_h = row.get('FTHG', 0) - row.get('HTHG', 0)
        g_2h_a = row.get('FTAG', 0) - row.get('HTAG', 0)

        stats_map[h].append({'F': row.get('HF',0), 'SOT_F': row.get('HST',0), 'C_F': row.get('HC',0), 'G_F': row.get('FTHG',0), 'G_A': row.get('FTAG',0), 'Cards': cards_h, 'Saves': saves_h, 'BTTS': btts, 'O25': over25, 'U25': under25, 'G2H': g_2h_h, 'SOT_A': row.get('AST',0), 'C_A': row.get('AC',0)})
        stats_map[a].append({'F': row.get('AF',0), 'SOT_F': row.get('AST',0), 'C_F': row.get('AC',0), 'G_F': row.get('FTAG',0), 'G_A': row.get('FTHG',0), 'Cards': cards_a, 'Saves': saves_a, 'BTTS': btts, 'O25': over25, 'U25': under25, 'G2H': g_2h_a, 'SOT_A': row.get('HST',0), 'C_A': row.get('HC',0)})

    for eq, hist in stats_map.items():
        if len(hist) >= 5:
            ult = hist[-PARTIDOS_MEDIA:]
            n = len(ult)
            estado_actual[eq] = {
                'Fouls': sum(x['F'] for x in ult)/n,
                'SOT_F': sum(x['SOT_F'] for x in ult)/n,
                'SOT_A': sum(x['SOT_A'] for x in ult)/n,
                'Corn_F': sum(x['C_F'] for x in ult)/n,
                'Corn_A': sum(x['C_A'] for x in ult)/n,
                'Gols_F': sum(x['G_F'] for x in ult)/n,
                'Gols_A': sum(x['G_A'] for x in ult)/n,
                'Gols_2H': sum(x['G2H'] for x in ult)/n,
                'Cards': sum(x['Cards'] for x in ult)/n,
                'Saves': sum(x['Saves'] for x in ult)/n,
                'P_BTTS': sum(x['BTTS'] for x in ult)/n,
                'P_O25': sum(x['O25'] for x in ult)/n,
                'P_U25': sum(x['U25'] for x in ult)/n,
                'P_Card': sum(1 for x in ult if x['Cards']>0)/n
            }
            
    return estado_actual, ref_stats

# ==========================================
# 3. INTERFAZ
# ==========================================
st.title("⚽ IA Betting Panel V12")

df, lista_equipos = cargar_datos()

if df is not None:
    st.success(f"✅ Base de datos cargada: {len(df)} partidos.")
    estado, ref_stats = calcular_metricas(df)

    # --- SELECCIÓN ---
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        local = st.selectbox("Equipo Local", lista_equipos, index=None)
    with col2:
        visitante = st.selectbox("Equipo Visitante", lista_equipos, index=None)
    
    lista_refs = sorted(list(ref_stats.keys()))
    referee = st.selectbox("Árbitro (Opcional)", ["Desconocido"] + lista_refs)

    if st.button("🔍 ANALIZAR", type="primary"):
        if not local or not visitante:
            st.warning("⚠️ Selecciona equipos.")
        elif local not in estado or visitante not in estado:
            st.error("⚠️ Faltan datos históricos.")
        else:
            l = estado[local]
            v = estado[visitante]
            opciones = []

            # LÓGICA
            sum_g2h = l['Gols_2H'] + v['Gols_2H']
            if sum_g2h >= 1.5: opciones.append(("⏱️ GOL TARDÍO", f"Gol en 2ª Parte (Media: {sum_g2h:.1f})"))
            if l['P_U25'] >= 0.60 and v['P_U25'] >= 0.60: opciones.append(("🛡️ UNDER 2.5", "Menos de 2.5 Goles"))
            if l['P_BTTS'] >= 0.65 and v['P_BTTS'] >= 0.65: opciones.append(("⚽ AMBOS MARCAN", f"SÍ (Prob: {l['P_BTTS']:.2f}/{v['P_BTTS']:.2f})"))
            if v['SOT_F'] >= 5.0 and l['Saves'] >= 3.0: opciones.append(("🧤 PORTERO LOCAL", f"+3.5 Paradas"))
            if l['SOT_F'] >= 5.0 and v['Saves'] >= 3.0: opciones.append(("🧤 PORTERO VISITA", f"+3.5 Paradas"))
            tc = l['Corn_F'] + v['Corn_F']
            if tc >= 10.5: opciones.append(("🚩 CÓRNERS", f"Más de 9.5 (Proy: {tc:.1f})"))
            if l['Corn_F'] >= 6.5: opciones.append(("🚩 CÓRNERS LOCAL", f"Más de 5.5"))
            
            t_cards = l['Cards'] + v['Cards']
            ref_txt = ""
            if referee != "Desconocido":
                r_avg = ref_stats[referee]
                t_cards += (r_avg - 4.0)
                ref_txt = f"(Ajuste Árbitro)"
            
            if t_cards >= 5.5: opciones.append(("🟥 TARJETAS", f"Más de 4.5 {ref_txt}"))
            if l['P_Card'] >= 0.85 and v['P_Card'] >= 0.85: opciones.append(("🟨 AMBOS RECIBEN", "SÍ"))
            if l['Fouls'] >= 11 and v['Gols_A'] <= 1.2: opciones.append(("🎯 TIROS VISITANTE", "+3.5 Tiros"))

            # MOSTRAR
            c1, c2 = st.columns(2)
            c1.info(f"**{local}**\nG: {l['Gols_F']:.1f} | C: {l['Corn_F']:.1f}")
            c2.info(f"**{visitante}**\nG: {v['Gols_F']:.1f} | C: {v['Corn_F']:.1f}")

            if opciones:
                for t, d in opciones:
                    st.success(f"**{t}** | {d}")
            else:
                st.warning("💤 Sin señales claras.")
