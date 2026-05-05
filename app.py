import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import os

st.set_page_config(layout="wide", page_title="Warehouse 3D Visualizer")

st.title("🚀 SKLC3 - 3D Warehouse Digital Twin")

@st.cache_data
def load_and_parse_data(file_source):
    df = pd.read_excel(file_source)
    df['% Využité kapacity'] = df['% Využité kapacity'].fillna(0)
    df['Počet produktov'] = df['Počet produktov'].fillna(0)
    df['Množstvo produktov'] = df['Množstvo produktov'].fillna(0)
    
    def parse_location(loc_name):
        try:
            parts = str(loc_name).split('-')
            zone, ulicka, pozicia = parts[0], int(parts[1]), int(parts[2])
            uroven = int(parts[3]) if len(parts) >= 4 else 1
            return zone, ulicka, pozicia, uroven
        except:
            return None, None, None, None

    df[['tmp_zone', 'ul_num', 'poz_num', 'ur_num']] = df.apply(
        lambda r: pd.Series(parse_location(r['Názov lokácie'])), axis=1
    )
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
    st.sidebar.header("📍 Nastavenia")
    
    # Výber zóny
    available_zones = sorted(df_raw['tmp_zone'].unique())
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=available_zones.index("2A") if "2A" in available_zones else 0)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    # Prepínač 2D vs 3D
    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa", "3D Model"])

    if view_mode == "2D Mapa":
        # Tu by bol tvoj pôvodný kód (skrátene pre tento príklad)
        st.info("Zobrazený 2D režim - tvoj pôvodný kód tu ostáva.")
        # (Vlož sem v prípade potreby tvoj predchádzajúci kód pre Scatter plot)
        
    else:
        st.subheader(f"3D Vizualizácia Zóny {selected_zone}")
        
        # --- PRÍPRAVA DÁT PRE 3D (PYDECK) ---
        # Pydeck potrebuje farby ako list [R, G, B]
        def get_color(util):
            if util < 30: return [40, 180, 99, 160]   # Zelená
            if util < 70: return [244, 208, 63, 160]  # Žltá
            return [231, 76, 60, 200]                 # Červená

        zone_df['color'] = zone_df['util_num'].apply(get_color)

        # Definícia 3D vrstvy
        layer = pdk.Layer(
            "ColumnLayer",
            zone_df,
            get_position=["ul_num", "poz_num"],
            get_elevation="util_num", # Výška stĺpca podľa % využitia
            elevation_scale=0.5,      # Faktor násobenia výšky
            radius=0.4,               # Šírka stĺpca
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        # Nastavenie pohľadu kamery
        view_state = pdk.ViewState(
            latitude=zone_df['poz_num'].mean(),
            longitude=zone_df['ul_num'].mean(),
            zoom=13,
            pitch=45, # Uhol naklonenia (3D efekt)
            bearing=0
        )

        # Vykreslenie 3D grafu
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={
                "text": "Lokácia: {Názov lokácie}\nVyužitie: {util_num}%\nSKU: {Počet produktov}"
            },
            map_style=None, # Vypne reálnu mapu sveta v pozadí
        )

        st.pydeck_chart(r)
        
        st.write("💡 Tip: Podrž **pravé tlačidlo myši** pre otáčanie pohľadu alebo **Ctrl + ľavé tlačidlo**.")

    st.dataframe(zone_df[['Názov lokácie', 'Sekcia', 'util_num']].sort_values('util_num', ascending=False), hide_index=True)

else:
    st.error("Súbor data.xlsx nebol nájdený.")
