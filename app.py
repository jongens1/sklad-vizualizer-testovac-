import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="SKLC3 Warehouse Layout")

st.title("🔄 SKLC3 - 3D Warehouse Map")

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

    # Logika pre poschodia
    if selected_main == "CELÝ LOOP (A-F)":
        zone_df = df_raw[df_raw['tmp_zone'].isin(['2A','2B','2C','2D','2E','2F'])].copy()
    else:
        zone_df = df_raw[df_raw['tmp_zone'] == selected_main].copy()

    levels = sorted(zone_df['ur_num'].unique().astype(int))
    selected_level = st.sidebar.selectbox("Vyber poschodie:", ["Všetky úrovne (Priemer)"] + [str(l) for l in levels])

    # --- AGREGÁCIA DÁT ---
    if selected_level == "Všetky úrovne (Priemer)":
        # Spriemerujeme hodnoty pre každý stĺpec regálu
        plot_df = zone_df.groupby(['tmp_zone', 'ul_num', 'poz_num']).agg({
            'util_num': 'mean', 'Počet produktov': 'mean', 'Množstvo produktov': 'sum'
        }).reset_index()
        plot_df['display_name'] = plot_df.apply(lambda r: f"{r['tmp_zone']}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d}", axis=1)
        plot_df['z_viz'] = 1 # Všetko v jednej rovine
    else:
        plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()
        plot_df['display_name'] = plot_df['Názov lokácie']
        plot_df['z_viz'] = plot_df['ur_num']

    # --- LOGIKA ROZLOŽENIA PODĽA NÁKRESU ---
    def get_layout_coords(row):
        z, u, p = row['tmp_zone'], row['ul_num'], row['poz_num']
        u_gap, p_gap = 2.5, 1.2
        
        if z == '2A': return (u * u_gap), 240 + (p * p_gap)
        if z == '2B': return (u * u_gap), 160 + (p * p_gap)
        if z == '2C': return (u * u_gap), 80 + (p * p_gap)
        if z == '2D': return (u * u_gap), 0 + (p * p_gap)
        if z == '2E': return -80 + (p * p_gap), (u * u_gap) + 80
        if z == '2F': return 250 + (p * p_gap), (u * u_gap) + 80
        return u * u_gap, p * p_gap

    coords = plot_df.apply(lambda r: pd.Series(get_layout_coords(r)), axis=1)
    plot_df['x_viz'], plot_df['y_viz'] = coords[0], coords[1]

    # VYKRESLENIE
    st.subheader(f"Zobrazenie: {selected_main} ({selected_level})")
    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()
    fig.add_trace(go.Scatter3d(
        x=plot_df['x_viz'], y=plot_df['y_viz'], z=plot_df['z_viz'],
        mode='markers',
        marker=dict(
            size=7 if selected_main == "CELÝ LOOP (A-F)" else 12,
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=0.5, color='black'),
            opacity=0.9,
            colorbar=dict(title=viz_mode, x=1.05)
        ),
        text=plot_df['display_name'],
        hovertemplate="<b>%{text}</b><br>Hodnota: %{marker.color:.1f}<extra></extra>"
    ))

    fig.update_layout(
        scene=dict(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            zaxis=dict(title='Poschodie', range=[0, 9] if selected_level != "Všetky úrovne (Priemer)" else [0, 2]),
            aspectmode='manual',
            aspectratio=dict(x=1.5, y=2, z=0.1 if selected_level == "Všetky úrovne (Priemer)" else 0.4)
        ),
        margin=dict(l=0, r=0, b=0, t=30), height=850
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 Tip: V režime 'Priemer' vidíš celkové zaťaženie regálového stĺpca v jednej rovine.")

else:
    st.info("👋 Nahraj Excel pre zobrazenie Loopu.")
