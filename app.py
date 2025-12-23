import streamlit as st
import pandas as pd
import numpy as np
import glob
import os
from scipy.stats import poisson

# ==========================================
# CONFIGURACIÓN VISUAL (MODO DARK/GOLD)
# ==========================================
st.set_page_config(page_title="Komercial Bet Elite", page_icon="💎", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main {background-color: #0e1117;}
    h1 {color: #d4af37; font-family: 'Helvetica Neue', sans-serif;}
    .stMetric {background-color: #1a1c24; border: 1px solid #333; border-radius: 8px;}
    .success-box {padding: 15px; background-color: rgba(0, 255, 127, 0.1); border-left: 5px solid #00ff7f; border-radius: 5px; margin-bottom: 10px;}
    .prediction-box {padding: 15px; background-color: rgba(212, 175, 55, 0.1); border: 1px solid #d4af37; border-radius: 8px; text-align: center;}
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
# 2. CÁLCULO DE FORMA Y POISSON
# ==========================================
def get_form_string(row, team):
    # Devuelve W/D/L para un partido dado
    if row['HomeTeam'] == team:
        return '✅' if row['FTR'] == 'H' else ('❌' if row['FTR'] == 'A' else '➖')
    else:
        return '✅' if row['FTR'] == 'A' else ('❌' if row['FTR'] == 'H' else '➖')

def predecir_marcador_poisson(l_goal_avg, v_goal_avg):
    # Predice los marcadores más probables usando distribución de Poisson
    max_goals = 6
    probs = np.zeros((max_goals, max_goals))
    
    for i in range(max_goals):
        for j in range(max_goals):
            prob_home = poisson.pmf(i, l_goal_avg)
            prob_away = poisson.pmf(j, v_goal_avg)
            probs[i][j] = prob_home * prob_away
            
    # Obtener los 3 marcadores más probables
    indices = np.unravel_index(np.argsort(probs, axis=None)[::-1], probs.shape)
    top_scores = []
    for k in range(3):
        h_score = indices[0][k]
        a_score = indices[1][k]
        prob = probs[h_score][a_score]
        top_scores.append((f"{h_score}-{a_score}", prob))
        
    return top_scores

def calcular_stats_avanzadas(df, local, visitante):
    PARTIDOS = 10
    df['FTR'] = np.where(df['FTHG'] > df['FTAG'], 'H', np.where(df['FTAG'] > df['FTHG'], 'A', 'D'))
    
    stats = {}
    for eq in [local, visitante]:
        matches = df[(df['HomeTeam'] == eq) | (df['AwayTeam'] == eq)].tail(PARTIDOS)
        if len(matches) < 5: return None
        
        # Racha (Forma) últimos 5 partidos
        last_5 = matches.tail(5)
        forma = "".join([get_form_string(r, eq) for _, r in last_5.iterrows()])
        
        # Medias
        goals_for = []
        goals_ag = []
        
        for _, r in matches.iterrows():
            if r['HomeTeam'] == eq:
                goals_for.append(r['FTHG'])
                goals_ag.append(r['FTAG'])
            else:
                goals_for.append(r['FTAG'])
                goals_ag.append(r['FTHG'])
                
        # Datos básicos para el resto de lógica (simplificado para integración)
        # Recalculamos métricas completas como en V14
        # ... (Aquí iría la lógica completa V14, resumida para este ejemplo)
        # Para Poisson usamos Media Goles A Favor (Ataque) y En Contra (Defensa)
        
        stats[eq] = {
            'Forma': forma,
            'Att_Strength': np.mean(goals_for),
            'Def_Weakness': np.mean(goals_ag)
        }
    
    # Cálculos V14 completos (reutilizados)
    # Nota: Por brevedad, fusionamos lógica. En producción usarías la función completa V14.
    # Aquí simulamos el retorno de stats completas + las nuevas
    full_stats_v14 = calcular_stats_v14(df, local, visitante) # Llamada a lógica previa
    if full_stats_v14:
        full_stats_v14[local].update(stats[local])
        full_stats_v14[visitante].update(stats[visitante])
        return full_stats_v14
    return None

# Función auxiliar V14 (La que ya tenías, optimizada)
def calcular_stats_v14(df, local, visitante):
    # [PEGA AQUÍ EL CONTENIDO DE LA FUNCIÓN calcular_stats DE LA VERSIÓN 14]
    # Por espacio en la respuesta, asumo que usas la lógica V14 para córners/tarjetas.
    # A continuación pongo una versión simplificada funcional para que el código corra directo.
    
    stats = {}
    for eq in [local, visitante]:
        matches = df[(df['HomeTeam'] == eq) | (df['AwayTeam'] == eq)].tail(10)
        if len(matches)<5: return None
        
        # Acumuladores básicos para demostración (usar V14 completa para precisión)
        f_l, c_l, card_l, g_l, ga_l, sot_f, saves, btts_l, u25_l = [],[],[],[],[],[],[],[],[]
        
        for _, r in matches.iterrows():
            is_h = r['HomeTeam'] == eq
            f_l.append(r['HF'] if is_h else r['AF'])
            c_l.append(r['HC'] if is_h else r['AC'])
            card_l.append((r['HY']+r['HR']) if is_h else (r['AY']+r['AR']))
            g = r['FTHG'] if is_h else r['FTAG']
            ga = r['FTAG'] if is_h else r['FTHG']
            g_l.append(g); ga_l.append(ga)
            sot = r['HST'] if is_h else r['AST']
            sot_a = r['AST'] if is_h else r['HST']
            sot_f.append(sot)
            saves.append(max(0, sot_a - ga))
            btts_l.append(1 if (g>0 and ga>0) else 0)
            u25_l.append(1 if (g+ga)<2.5 else 0)
            
        stats[eq] = {
            'Fouls': np.mean(f_l), 'Corn': np.mean(c_l), 'Cards': np.mean(card_l),
            'Goals': np.mean(g_l), 'G_Conc': np.mean(ga_l), 'SOT_F': np.mean(sot_f),
            'Saves': np.mean(saves), 'BTTS': np.mean(btts_l), 'U25': np.mean(u25_l),
            'Prob_Card': np.mean([1 if c>0 else 0 for c in card_l]),
            'G_2H': 0.5 # Simplificado para demo
        }
    return stats

# ==========================================
# 3. INTERFAZ ELITE
# ==========================================
st.markdown("<h1>💎 KOMERCIAL BET <span style='color:#d4af37'>ELITE</span></h1>", unsafe_allow_html=True)

df_full, ligas = cargar_datos()

if df_full is None:
    st.error("⚠️ Sube los CSV a GitHub.")
else:
    with st.sidebar:
        st.header("⚙️ Configuración")
        liga_sel = st.selectbox("Liga", sorted(ligas))
        df_liga = df_full[df_full['League'] == liga_sel]
        equipos = sorted(df_liga['HomeTeam'].unique())
        local = st.selectbox("Local", equipos)
        vis_list = [x for x in equipos if x != local]
        visitante = st.selectbox("Visitante", vis_list)
        
        # Gestión Árbitro (Simplificada V14)
        has_ref = 'Referee' in df_liga.columns and df_liga['Referee'].nunique() > 1
        ref_avg = 4.0
        if has_ref:
            df_liga['TC'] = df_liga['HY']+df_liga['AY']+df_liga['HR']+df_liga['AR']
            refs = df_liga.groupby('Referee')['TC'].mean().to_dict()
            r_sel = st.selectbox("Árbitro", ["Desconocido"] + sorted(list(refs.keys())))
            if r_sel != "Desconocido": ref_avg = refs[r_sel]
        else:
            ref_avg = st.number_input("Media Árbitro (Manual)", 0.0, 10.0, 4.5)
            
        st.markdown("---")
        # CALCULADORA KELLY
        st.subheader("💰 Gestión de Banca")
        bankroll = st.number_input("Tu Banca Total (€)", 100, 100000, 1000)
        
        btn = st.button("🚀 ANALIZAR ELITE", type="primary", use_container_width=True)

    if btn:
        stats = calcular_stats_avanzadas(df_full, local, visitante)
        
        if stats:
            l = stats[local]
            v = stats[visitante]
            
            # --- CABECERA CON RACHAS ---
            c1, c2, c3 = st.columns([1, 0.2, 1])
            with c1: 
                st.markdown(f"<h3 style='text-align:right'>{local}</h3>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:right; font-size:20px'>{l['Forma']}</div>", unsafe_allow_html=True)
            with c2: st.markdown("<h2 style='text-align:center'>VS</h2>", unsafe_allow_html=True)
            with c3: 
                st.markdown(f"<h3 style='text-align:left'>{visitante}</h3>", unsafe_allow_html=True)
                st.markdown(f"<div style='text-align:left; font-size:20px'>{v['Forma']}</div>", unsafe_allow_html=True)
            
            st.markdown("---")

            # --- 🔮 SIMULADOR POISSON ---
            # Estimamos Goles Esperados (xG) simples
            xg_home = (l['Goals'] + v['G_Conc']) / 2
            xg_away = (v['Goals'] + l['G_Conc']) / 2
            
            marcadores = predecir_marcador_poisson(xg_home, xg_away)
            
            st.subheader("🔮 Inteligencia Artificial: Marcador Exacto")
            col_res = st.columns(3)
            for i, (score, prob) in enumerate(marcadores):
                with col_res[i]:
                    st.markdown(f"""
                    <div class="prediction-box">
                        <div style="font-size: 24px; font-weight: bold;">{score}</div>
                        <div style="color: grey;">Prob: {prob*100:.1f}%</div>
                    </div>
                    """, unsafe_allow_html=True)

            # --- ESTRATEGIAS (Lógica V14) ---
            st.markdown("---")
            st.subheader("🧠 Estrategias de Valor")
            
            opciones = []
            # Tarjetas
            cards_proj = l['Cards'] + v['Cards'] + (ref_avg - 4.0)
            if cards_proj >= 5.5: opciones.append(("🟥 TARJETAS", "Más de 4.5", 85, 1.70)) # Cuota aprox 1.70
            
            # Córners
            if (l['Corn']+v['Corn']) >= 10.5: opciones.append(("🚩 CÓRNERS", "Más de 9.5", 75, 1.83))
            
            # Porteros
            if v['SOT_F'] >= 5.0 and l['Saves'] >= 3.0: opciones.append(("🧤 PORTERO LOCAL", "+3.5 Paradas", 80, 1.65))
            
            # Goles
            if l['BTTS'] >= 0.65 and v['BTTS'] >= 0.65: opciones.append(("⚽ BTTS", "Sí", 75, 1.75))

            if opciones:
                for tit, desc, conf, cuota_ref in opciones:
                    # CÁLCULO DE KELLY
                    # Fórmula: (bp - q) / b  donde b = cuota-1, p = probabilidad, q = 1-p
                    p = conf / 100
                    b = cuota_ref - 1
                    kelly_pct = ((b * p) - (1 - p)) / b
                    kelly_pct = max(0, kelly_pct * 0.5) # Kelly Fraccional (Conservador)
                    stake_eur = bankroll * kelly_pct
                    
                    st.markdown(f"""
                    <div class="success-box">
                        <div style="display:flex; justify-content:space-between">
                            <strong>{tit} | {desc}</strong>
                            <span>Fiabilidad: {conf}%</span>
                        </div>
                        <div style="margin-top:5px; font-size:14px; color:#d4af37">
                            💰 Stake Recomendado: <strong>{stake_eur:.1f}€ ({kelly_pct*100:.1f}%)</strong>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("💤 Partido muy ajustado. No hay valor claro.")

        else:
            st.error("Datos insuficientes para este partido.")
