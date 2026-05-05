import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Digital Twin")

st.title("🚀 SKLC3 - Warehouse 3D Digital Twin")

# --- 2. FUNKCIA NA NAČÍTANIE DÁT ---
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

# Načítanie dát
df_raw = None
if os.path.exists("data.xlsx"):
    df_raw = load_and_parse_data("data.xlsx")

if df_raw is not None:
    # 3. SIDEBAR
    st.sidebar.header("📍 Nastavenia")
    available_zones = sorted(df_raw['tmp_zone'].unique())
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=available_zones.index("2A") if "2A" in available_zones else 0)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa", "3D Model"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    levels = sorted(zone_df['ur_num'].unique().astype(int))
    selected_level = st.sidebar.selectbox("Vyber poschodie:", ["Všetky úrovne (Priemer)"] + [str(l) for l in levels])
    
    if selected_level == "Všetky úrovne (Priemer)":
        plot_df = zone_df.groupby(['ul_num', 'poz_num', 'Sekcia']).agg({
            'util_num': 'mean', 'Počet produktov': 'mean', 'Množstvo produktov': 'sum'
        }).reset_index()
        plot_df['display_name'] = plot_df.apply(lambda r: f"{selected_zone}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d}", axis=1)
    else:
        plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()
        plot_df['display_name'] = plot_df['Názov lokácie']

    # --- 4. VYKRESLENIE ---
    
    if view_mode == "2D Mapa":
        fig = go.Figure()
        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')
        
        fig.add_trace(go.Scatter(
            x=plot_df['ul_num'], y=plot_df['poz_num'],
            mode='markers',
            marker=dict(size=15, symbol='square', color=plot_df[c_col], colorscale=c_scale, showscale=True, line=dict(width=0.5, color='black')),
            text=plot_df['display_name'],
            hovertemplate="<b>%{text}</b><br>Hodnota: %{marker.color:.1f}<extra></extra>"
        ))
        fig.update_layout(height=700, plot_bgcolor='white', xaxis=dict(title="Ulička"), yaxis=dict(title="Pozícia"))
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- NOVÝ 3D MODEL CEZ PLOTLY (BEZ MAPY SVETA) ---
        st.subheader(f"3D Vizualizácia: Zóna {selected_zone}")

        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

        fig = go.Figure(data=[go.Scatter3d(
            x=plot_df['ul_num'],
            y=plot_df['poz_num'],
            z=plot_df['util_num'], # Výška bodu v 3D priestore
            mode='markers',
            marker=dict(
                size=8,
                color=plot_df[c_col],                # Farba podľa využitia/SKU
                colorscale=c_scale,
                opacity=0.8,
                symbol='square',                     # Štvorcové stĺpce
                colorbar=dict(title=viz_mode)
            ),
            text=plot_df['display_name'],
            hovertemplate="<b>%{text}</b><br>Využitie: %{z:.1f}%<extra></extra>"
        )])

        fig.update_layout(
            scene=dict(
                xaxis_title='Ulička',
                yaxis_title='Pozícia',
                zaxis_title='Využitie %',
                aspectmode='manual',
                aspectratio=dict(x=1, y=1, z=0.5) # Sploštenie výšky pre lepší prehľad
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            height=800
        )

        st.plotly_chart(fig, use_container_width=True)
        st.info("🖱️ **Ľavé tlačidlo**: Otáčanie | **Pravé tlačidlo**: Posun | **Koliesko**: Zoom")

    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num']), use_container_width=True)

else:
    st.info("👋 Prosím, nahraj Excel alebo pridaj 'data.xlsx' na GitHub.")
