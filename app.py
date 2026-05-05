import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Test")

st.title("🚀 SKLC3 - 3D Warehouse Digital Twin")

# --- 2. FUNKCIA NA NAČÍTANIE DÁT S CACHINGOM ---
@st.cache_data
def load_and_parse_data(file_source):
    """Načíta Excel a pripraví dáta."""
    df = pd.read_excel(file_source)
    
    # Ošetrenie prázdnych hodnôt
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

# --- 3. LOGIKA ZDROJA DÁT ---
uploaded_file = st.sidebar.file_uploader("Nahraj vlastný Excel (.xlsx)", type=["xlsx"])

df_raw = None
if uploaded_file:
    df_raw = load_and_parse_data(uploaded_file)
elif os.path.exists("data.xlsx"):
    df_raw = load_and_parse_data("data.xlsx")

if df_raw is not None:
    # 4. SIDEBAR FILTRE
    st.sidebar.header("📍 Nastavenia")
    
    available_zones = sorted(df_raw['tmp_zone'].unique())
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=available_zones.index("2A") if "2A" in available_zones else 0)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    # Režim a Metrika
    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa", "3D Model"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    # Výber poschodia
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

    # --- 5. VYKRESLENIE ---
    
    if view_mode == "2D Mapa":
        # PÔVODNÝ 2D PLOTLY KÓD
        fig = go.Figure()
        
        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')
        
        fig.add_trace(go.Scatter(
            x=plot_df['ul_num'], y=plot_df['poz_num'],
            mode='markers',
            marker=dict(
                size=15, symbol='square', color=plot_df[c_col],
                colorscale=c_scale, showscale=True, line=dict(width=0.5, color='black')
            ),
            text=plot_df['display_name'],
            customdata=plot_df[['util_num', 'Počet produktov', 'Sekcia']],
            hovertemplate="<b>%{text}</b><br>Využitie: %{customdata[0]:.1f}%<extra></extra>"
        ))

        fig.update_layout(height=700, plot_bgcolor='white', xaxis=dict(title="Ulička"), yaxis=dict(title="Pozícia"))
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- OPRAVENÝ 3D PYDECK ---
        st.subheader(f"3D Model: Zóna {selected_zone}")

        # Definícia farieb pre stĺpce
        def get_color(row):
            val = row['util_num'] if viz_mode == "Využitie kapacity (%)" else (row['Počet produktov'] * 10)
            if val < 20: return [46, 204, 113, 200]
            if val < 80: return [241, 196, 15, 200]
            return [231, 76, 60, 200]

        plot_df['color'] = plot_df.apply(get_color, axis=1)

        layer = pdk.Layer(
            "ColumnLayer",
            plot_df,
            get_position=["ul_num", "poz_num"],
            get_elevation="util_num",
            elevation_scale=0.2,
            radius=0.4,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        view_state = pdk.ViewState(
            latitude=plot_df['poz_num'].mean() if not plot_df.empty else 0,
            longitude=plot_df['ul_num'].mean() if not plot_df.empty else 0,
            zoom=14, pitch=45, bearing=0
        )

        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="dark", # Bezpečný štýl pre Streamlit Cloud
            tooltip={"text": "Lokácia: {display_name}\nVyužitie: {util_num:.1f}%"}
        )

        st.pydeck_chart(r)
        st.info("🖱️ **Pravé tlačidlo**: Otáčanie | **Ctrl + Myš**: Nakláňanie")

    # Tabuľka na spodku
    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num']), use_container_width=True)

else:
    st.info("👋 Prosím, nahraj Excel alebo pridaj 'data.xlsx' na GitHub.")
