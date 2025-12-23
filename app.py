import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
from scipy.stats import poisson

# ==========================================
# CONFIGURACIÓN KOMERCIAL BET ELITE V15.1
# ==========================================
st.set_page_config(page_title="Komercial Bet Elite", page_icon="💎", layout="wide")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; font-family: 'Helvetica Neue', sans-serif; text-align: center; margin-bottom: 0px;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px; padding: 10px;}
    .card {padding: 20px; border-radius: 10px; background-color: #1a1c24; border: 1px solid #d4af37; margin-bottom: 15px;}
    .success-text {color: #00ff7f; font-weight: bold;}
    .gold-text {color: #d4af37; font-weight: bold;}
    .form-text {font-size: 18px; letter-spacing: 2px;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 1. MOTOR DE DATOS
# ==========================================
@st.cache_data
def cargar_datos():
    files = glob.glob("*.csv")
    if not files: return None, None, None
    dfs = []
    cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'HST', 'AST', 'HF', 'AF', 
            'HC', 'AC', 'HS', 'AS', 'HY', 'AY', 'HR', 'AR', 'HTHG', 'HTAG', 'Referee']
    for f in files:
        try:
            df_check = pd.read_csv(f, nrows=1)
            use_cols = [c for c in cols if c in df_check.columns]
            df = pd.read_csv(f, usecols=use_cols)
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
    return df, df['League'].unique()

# ==========================================
# 2. CÁLCULOS ESTADÍSTICOS (ALGORITMOS FIJOS)
# ==========================================
def calcular_metricas_completas(df, local, visitante):
    stats = {}
    for eq in [local, visitante]:
        # Tomamos los últimos 10 partidos para tendencia, pero exigimos mínimo 5
        matches = df[(df['HomeTeam'] == eq) | (df['AwayTeam'] == eq)].tail(10)
        if len(matches) < 5: return None
        
        f_l, c_l, card_l, g_l, ga_l, sot_f, sot_a, btts_l, u25_l, g2h_l, card_0_l = [],[],[],[],[],[],[],[],[],[],[]
        
        for _, r in matches.iterrows():
            is_h = r['HomeTeam'] == eq
            f_l.append(r['HF'] if is_h else r['AF'])
            c_l.append(r['HC'] if is_h else r['AC'])
            cards = (r['HY']+r['HR']) if is_h else (r['AY']+r['AR'])
            card_l.append(cards)
            card_0_l.append(1 if cards > 0 else 0)
            g = r['FTHG'] if is_h else r['FTAG']
            ga = r['FTAG'] if is_h else r['FTHG']
            g_l.append(g); ga_l.append(ga)
            sot_f.append(r['HST'] if is_h else r['AST'])
            sot_a.append(r['AST'] if is_h else r['HST'])
            g2h_l.append(g - (r['HTHG'] if is_h else r['HTAG']))
            btts_list = 1 if (g > 0 and ga > 0) else 0
            btts_l.append(btts_list)
            u25_l.append(1 if (g + ga) < 2.5 else 0)
            
        # Generar tira de forma (W/D/L)
        last_5 = matches.tail(5)
        forma = ""
        for _, r in last_5.iterrows():
            res = 'H' if r['FTHG']>r['FTAG'] else ('A' if r['FTAG']>r['FTHG'] else 'D')
            if (r['HomeTeam']==eq and res=='H') or (r['AwayTeam']==eq and res=='A'): forma += "✅"
            elif res=='D': forma += "➖"
            else: forma += "❌"

        stats[eq] = {
            'Forma': forma, 'Fouls': np.mean(f_l), 'Corn': np.mean(c_l), 'Cards': np.mean(card_l),
            'Goals': np.mean(g_l), 'G_Conc': np.mean(ga_l), 'SOT_F': np.mean(sot_f), 'SOT_A': np.mean(sot_a),
            'BTTS': np.mean(btts_l), 'U25': np.mean(u25_l), 'G_2H': np.mean(g2h_l), 'Prob_Card': np.mean(card_0_l)
        }
    return stats

def predict_poisson(l_avg, v_avg):
    probs = np.zeros((5, 5))
    for i in range(5):
        for j in range(5):
            probs[i][j] = poisson.pmf(i, l_avg) * poisson.pmf(j, v_avg)
    idx = np.unravel_index(np.argsort(probs, axis=None)[::-1], probs.shape)
    return [(f"{idx[0][k]}-{idx[1][k]}", probs[idx[0][k]][idx[1][k]]) for k in range(3)]

# ==========================================
# 3. INTERFAZ KOMERCIAL BET
# ==========================================
st.markdown("<h1>💎 KOMERCIAL BET <span style='color:grey; font-size:18px'>ELITE V15.1</span></h1>", unsafe_allow_html=True)

df_full, ligas = cargar_datos()

if df_full is not None:
    with st.sidebar:
        st.header("⚙️ Configuración")
        liga_sel = st.selectbox("Liga", sorted(ligas))
        df_liga = df_full[df_full['League'] == liga_sel]
        equipos = sorted(df_liga['HomeTeam'].unique())
        local = st.selectbox("Local", equipos)
        visitante = st.selectbox("Visitante", [x for x in equipos if x != local])
        
        # Gestión Árbitro
        ref_avg = 4.5
        if 'Referee' in df_liga.columns:
            df_liga['TC'] = df_liga['HY']+df_liga['AY']+df_liga['HR']+df_liga['AR']
            refs = df_liga.groupby('Referee')['TC'].mean().to_dict()
            r_sel = st.selectbox("Árbitro", ["Desconocido"] + sorted(list(refs.keys())))
            if r_sel != "Desconocido": ref_avg = refs[r_sel]
        else: ref_avg = st.number_input("Media Árbitro (Manual)", 0.0, 10.0, 4.5)
        
        bankroll = st.number_input("Banca (€)", 100, 100000, 1000)
        btn = st.button("🚀 ANALIZAR PARTIDO", type="primary", use_container_width=True)

    if btn:
        s = calcular_metricas_completas(df_full, local, visitante)
        if s:
            l, v = s[local], s[visitante]
            
            # Rachas y Marcadores
            st.markdown(f"<div style='display:flex; justify-content:space-around; align-items:center; margin-bottom:20px;'><div><h3 style='margin:0'>{local}</h3><p class='form-text'>{l['Forma']}</p></div><h2 style='color:#d4af37'>VS</h2><div><h3 style='margin:0'>{visitante}</h3><p class='form-text'>{v['Forma']}</p></div></div>", unsafe_allow_html=True)
            
            xg_h, xg_v = (l['Goals'] + v['G_Conc'])/2, (v['Goals'] + l['G_Conc'])/2
            scores = predict_poisson(xg_h, xg_v)
            cols = st.columns(3)
            for i, (score, prob) in enumerate(scores):
                cols[i].markdown(f"<div style='text-align:center; border:1px solid #d4af37; border-radius:10px; padding:10px;'><span style='font-size:22px; font-weight:bold;'>{score}</span><br><span style='color:grey;'>IA Prob: {prob*100:.1f}%</span></div>", unsafe_allow_html=True)
            
            st.markdown("---")
            
            # --- ALGORITMOS DE OPORTUNIDADES ---
            opciones = []
            
            # 1. TIROS A PUERTA (RESTAURADO Y FIJO)
            # Si el local hace >= 10 faltas y el visitante encaja poco, el visitante dispara.
            if l['Fouls'] >= 10.0 and v['G_Conc'] <= 1.4:
                opciones.append(("🎯 TIROS VISITANTE", "Visitante +2.5 Tiros a Puerta", 78, 1.55))
            
            # 2. TARJETAS (LOGICA TRIPLE)
            proj_cards = l['Cards'] + v['Cards'] + (ref_avg - 4.0)
            if l['Prob_Card'] >= 0.85 and v['Prob_Card'] >= 0.85:
                opciones.append(("🟨 AMBOS RECIBEN", "Sí (Ambos ven tarjeta)", 90, 1.45))
            if proj_cards >= 3.8:
                opciones.append(("🟥 LÍNEA DE TARJETAS", "Más de 3.5 Tarjetas", 85, 1.35))
            if proj_cards >= 5.2:
                opciones.append(("🔥 OVER TARJETAS", "Más de 4.5 Tarjetas (Partido Tenso)", 72, 1.90))

            # 3. PORTEROS (PARADAS)
            if l['SOT_F'] >= 5.2:
                opciones.append(("🧤 PARADAS", f"Portero Visitante +3.5 Paradas (Recibe {l['SOT_F']:.1f} tiros)", 80, 1.60))

            # 4. CÓRNERS
            t_corn = l['Corn'] + v['Corn']
            if t_corn >= 9.8:
                opciones.append(("🚩 CÓRNERS TOTALES", "Más de 8.5 Córners", 82, 1.40))
            if l['Corn'] >= 6.2:
                opciones.append(("🚩 CÓRNERS LOCAL", "Más de 5.5 Córners Local", 70, 1.85))

            # 5. GOLES (BTTS Y LATE GOAL)
            sum_2h = l['G_2H'] + v['G_2H']
            if sum_2h >= 1.4:
                opciones.append(("⏱️ GOL TARDÍO", "Habrá gol en la 2ª Parte", 80, 1.35))
            if l['BTTS'] >= 0.65 and v['BTTS'] >= 0.65:
                opciones.append(("⚽ AMBOS MARCAN", "Sí (Tendencia goleadora)", 75, 1.70))

            # RENDER DE OPORTUNIDADES
            st.subheader("💡 Oportunidades de Inversión")
            if opciones:
                for tit, desc, conf, cuota in opciones:
                    p = conf/100
                    b = cuota - 1
                    kelly = max(0, ((b*p)-(1-p))/b * 0.5) if b>0 else 0
                    stake = bankroll * kelly
                    
                    st.markdown(f"""
                    <div class="card">
                        <div style="display:flex; justify-content:space-between">
                            <span class="gold-text">{tit}</span>
                            <span class="success-text">{conf}% Fiabilidad</span>
                        </div>
                        <div style="font-size:18px; margin: 10px 0;">{desc}</div>
                        <div style="color:#aaa; font-size:14px;">Inversión Sugerida: <b>{stake:.1f}€</b> ({kelly*100:.1f}% del bank)</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No se detectan señales con suficiente ventaja estadística.")
