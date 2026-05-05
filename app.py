import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import numpy as np
import os

st.set_page_config(layout="wide", page_title="Warehouse 3D Digital Twin")

st.title("🏛️ SKLC3 - 3D Model Regálov")

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
    available_zones = sorted(df_raw['tmp_zone'].unique())
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=available_zones.index("2A") if "2A" in available_zones else 0)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa", "3D Regály"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    if view_mode == "2D Mapa":
        # Tvoj overený 2D kód
        levels = sorted(zone_df['ur_num'].unique().astype(int))
        sel_level = st.sidebar.selectbox("Vyber poschodie:", ["Všetky"] + [str(l) for l in levels])
        plot_df = zone_df if sel_level == "Všetky" else zone_df[zone_df['ur_num'] == int(sel_level)]
        
        fig = go.Figure(go.Scatter(
            x=plot_df['ul_num'], y=plot_df['poz_num'], mode='markers',
            marker=dict(size=12, symbol='square', color=plot_df['util_num'], colorscale='RdYlGn_r', cmin=0, cmax=100, showscale=True),
            text=plot_df['Názov lokácie']
        ))
        fig.update_layout(height=700, plot_bgcolor='white')
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- 3D RACK MODEL ---
        st.subheader(f"3D Model skladu - Zóna {selected_zone}")
        
        # Filter pre uličky (aby 3D nebolo príliš husté, môžeš si vybrať rozsah)
        min_u, max_u = int(zone_df['ul_num'].min()), int(zone_df['ul_num'].max())
        sel_u = st.sidebar.slider("Rozsah uličiek na zobrazenie:", min_u, max_u, (min_u, min_u + 5))
        
        plot_df = zone_df[(zone_df['ul_num'] >= sel_u[0]) & (zone_df['ul_num'] <= sel_u[1])].copy()

        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

        fig = go.Figure()

        # 1. PRIDANIE PODLAHY (Sivý obdĺžnik)
        fig.add_trace(go.Mesh3d(
            x=[plot_df['ul_num'].min()-1, plot_df['ul_num'].max()+1, plot_df['ul_num'].max()+1, plot_df['ul_num'].min()-1],
            y=[plot_df['poz_num'].min()-1, plot_df['poz_num'].min()-1, plot_df['poz_num'].max()+1, plot_df['poz_num'].max()+1],
            z=[0.5, 0.5, 0.5, 0.5],
            color='lightgrey', opacity=0.5, name='Podlaha'
        ))

        # 2. VYKRESLENIE LOKÁCIÍ AKO BLOKOV
        fig.add_trace(go.Scatter3d(
            x=plot_df['ul_num'],
            y=plot_df['poz_num'],
            z=plot_df['ur_num'],
            mode='markers',
            marker=dict(
                size=12, # Veľké kocky
                symbol='square',
                color=plot_df[c_col],
                colorscale=c_scale,
                cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
                line=dict(width=1, color='black'),
                opacity=0.9
            ),
            text=plot_df['Názov lokácie'],
            hovertemplate="<b>%{text}</b><br>Využitie: %{marker.color:.1f}%<extra></extra>"
        ))

        fig.update_layout(
            scene=dict(
                xaxis=dict(title='Ulička', backgroundcolor="rgb(200, 200, 230)", gridcolor="white", showbackground=True),
                yaxis=dict(title='Pozícia (Bay)', backgroundcolor="rgb(230, 200, 230)", gridcolor="white", showbackground=True),
                zaxis=dict(title='Poschodie', nticks=9, range=[0, 9], backgroundcolor="rgb(230, 230, 200)", gridcolor="white", showbackground=True),
                aspectmode='manual',
                aspectratio=dict(x=1, y=1.5, z=0.5) # Tu nastavujeme, aby regály vyzerali dlhé a vysoké
            ),
            margin=dict(l=0, r=0, b=0, t=0),
            height=800
        )

        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **Tip:** Každý štvorček je jedna bunka v regáli. Regál tvorí 3x8 buniek (ulička-pozícia-poschodie).")

    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num', 'ur_num']), use_container_width=True)

else:
    st.info("Nahraj Excel súbor.")
