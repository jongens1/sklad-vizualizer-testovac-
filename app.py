import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="SKLC3 Warehouse Layout")

st.title("🔄 SKLC3 - Kompletný 3D Pôdorys")

@st.cache_data
def load_and_parse_data(file_source):
    df = pd.read_excel(file_source)
    df['% Využité kapacity'] = df['% Využité kapacity'].fillna(0)
    df['Počet produktov'] = df['Počet produktov'].fillna(0)
    df['Množstvo produktov'] = df['Množstvo produktov'].fillna(0)
    df['Sekcia'] = df['Sekcia'].fillna("Nezaradené")

    def parse_location(loc_name):
        try:
            parts = str(loc_name).split('-')
            zone, ulicka, pozicia = parts[0], int(parts[1]), int(parts[2])
            uroven = int(parts[3]) if len(parts) >= 4 else 1
            return zone, ulicka, pozicia, uroven
        except:
            return None, None, None, None

    coords_data = df.apply(lambda r: pd.Series(parse_location(r['Názov lokácie'])), axis=1)
    df[['tmp_zone', 'ul_num', 'poz_num', 'ur_num']] = coords_data
    df = df.dropna(subset=['tmp_zone', 'ul_num', 'poz_num', 'ur_num'])
    
    def clean_percent(val):
        if isinstance(val, str): val = val.replace('%', '').replace(',', '.')
        try: return float(val)
        except: return 0.0
    df['util_num'] = df['% Využité kapacity'].apply(clean_percent)
    return df

df_raw = None
if os.path.exists("data.xlsx"):
    df_raw = load_and_parse_data("data.xlsx")

if df_raw is not None:
    st.sidebar.header("📍 Nastavenia")
    main_options = ["CELÝ LOOP (A-F)"] + sorted(df_raw['tmp_zone'].unique())
    selected_main = st.sidebar.selectbox("Vyber zobrazenie:", main_options)
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    # --- LOGIKA ROZLOŽENIA PODĽA NÁKRESU ---
    def get_layout_coords(row):
        z = row['tmp_zone']
        u = row['ul_num']
        p = row['poz_num']
        
        # Koeficienty pre medzery
        u_gap = 2.5 # Medzera medzi uličkami
        p_gap = 1.2 # Medzera medzi pozíciami
        
        # 1. STREDOVÝ STĹPEC (A, B, C, D pod sebou)
        # X os = ulička, Y os = pozícia + posun zóny
        if z == '2A': return (u * u_gap), 240 + (p * p_gap)
        if z == '2B': return (u * u_gap), 160 + (p * p_gap)
        if z == '2C': return (u * u_gap), 80 + (p * p_gap)
        if z == '2D': return (u * u_gap), 0 + (p * p_gap)
        
        # 2. BOČNÉ ZÓNY (E vľavo, F vpravo - otočené vertikálne)
        # Prehodíme uličku a pozíciu, aby boli regály otočené o 90 stupňov
        if z == '2E': return -80 + (p * p_gap), (u * u_gap) + 80
        if z == '2F': return 250 + (p * p_gap), (u * u_gap) + 80
        
        return u * u_gap, p * p_gap

    if selected_main == "CELÝ LOOP (A-F)":
        plot_df = df_raw[df_raw['tmp_zone'].isin(['2A','2B','2C','2D','2E','2F'])].copy()
        is_loop = True
    else:
        plot_df = df_raw[df_raw['tmp_zone'] == selected_main].copy()
        is_loop = False

    # Aplikácia súradníc
    coords = plot_df.apply(lambda r: pd.Series(get_layout_coords(r)), axis=1)
    plot_df['x_viz'], plot_df['y_viz'] = coords[0], coords[1]

    # VYKRESLENIE
    st.subheader(f"Zobrazenie: {selected_main}")
    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()

    fig.add_trace(go.Scatter3d(
        x=plot_df['x_viz'],
        y=plot_df['y_viz'],
        z=plot_df['ur_num'],
        mode='markers',
        marker=dict(
            size=6 if is_loop else 10,
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=0.5, color='black'),
            opacity=0.9,
            colorbar=dict(title=viz_mode, x=1.05)
        ),
        text=plot_df['Názov lokácie'],
        hovertemplate="<b>%{text}</b><br>Využitie: %{marker.color:.1f}%<extra></extra>"
    ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            zaxis=dict(title='Poschodie', range=[0, 9]),
            aspectmode='manual',
            # Prispôsobenie celkového pohľadu (X je šírka, Y je dĺžka haly)
            aspectratio=dict(x=1.5, y=2, z=0.3)
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=850
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 Tip: V pohľade LOOP sú zóny E a F na bokoch a A-D v stĺpci nad sebou (zobrazené v 3D priereze).")

else:
    st.info("👋 Prosím, nahraj Excel.")
