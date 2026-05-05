import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import os

# Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Test")

st.title("🚀 SKLC3 - 3D Digital Twin (Map-free)")

# --- 1. FUNKCIA NA NAČÍTANIE DÁT ---
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
    # --- 2. SIDEBAR FILTRE ---
    st.sidebar.header("📍 Nastavenia")
    available_zones = sorted(df_raw['tmp_zone'].unique())
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=available_zones.index("2A") if "2A" in available_zones else 0)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    # Filtrovanie sekcií
    available_sections = sorted(zone_df['Sekcia'].unique())
    def set_all(val):
        for s in available_sections: st.session_state[f"cb_{s}"] = val
    
    col_a, col_b = st.sidebar.columns(2)
    col_a.button("Všetky", on_click=set_all, args=(True,))
    col_b.button("Žiadna", on_click=set_all, args=(False,))

    selected_sects = []
    with st.sidebar.expander("🏢 Filtrovať Sekcie", expanded=True):
        for sect in available_sections:
            if f"cb_{sect}" not in st.session_state: st.session_state[f"cb_{sect}"] = True
            if st.checkbox(sect, key=f"cb_{sect}"): selected_sects.append(sect)

    st.sidebar.markdown("---")
    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa", "3D Model"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    # --- 3. LOGIKA FILTROVANIA PRE GRAF ---
    levels = sorted(zone_df['ur_num'].unique().astype(int))
    selected_level = st.sidebar.selectbox("Vyber poschodie:", ["Všetky úrovne (Priemer)"] + [str(l) for l in levels])
    
    if selected_level == "Všetky úrovne (Priemer)":
        plot_df = zone_df.groupby(['ul_num', 'poz_num', 'Sekcia']).agg({'util_num': 'mean', 'Počet produktov': 'mean', 'Množstvo produktov': 'sum'}).reset_index()
        plot_df['display_name'] = plot_df.apply(lambda r: f"{selected_zone}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d}", axis=1)
    else:
        plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()
        plot_df['display_name'] = plot_df['Názov lokácie']

    active_df = plot_df[plot_df['Sekcia'].isin(selected_sects)].copy()
    inactive_df = plot_df[~plot_df['Sekcia'].isin(selected_sects)].copy()

    if view_mode == "2D Mapa":
        # --- PLOTLY 2D ---
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=inactive_df['ul_num'], y=inactive_df['poz_num'],
            mode='markers', marker=dict(size=14, symbol='square', color='#F0F0F0', line=dict(width=0.4, color='#CCCCCC')),
            text=inactive_df['display_name'], name="Neaktívne", hoverinfo='text'
        ))
        if not active_df.empty:
            c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')
            fig.add_trace(go.Scatter(
                x=active_df['ul_num'], y=active_df['poz_num'],
                mode='markers',
                marker=dict(size=16, symbol='square', color=active_df[c_col], colorscale=c_scale, showscale=True, line=dict(width=0.5, color='black')),
                text=active_df['display_name'],
                customdata=active_df[['util_num', 'Počet produktov', 'Sekcia']],
                hovertemplate="<b>%{text}</b><br>Sekcia: %{customdata[2]}<br>Využitie: %{customdata[0]:.1f}%<extra></extra>"
            ))
        fig.update_layout(height=700, plot_bgcolor='white', xaxis=dict(title="Ulička", dtick=5), yaxis=dict(title="Pozícia", dtick=5))
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- 4. 3D PYDECK BEZ MAPY SVETA ---
        st.subheader(f"3D Model: Zóna {selected_zone}")

        # Definujeme prázdny čierny štýl, aby sme nevideli mapu sveta
        EMPTY_MAP_STYLE = {
            "version": 8,
            "sources": {},
            "layers": [
                {
                    "id": "background",
                    "type": "background",
                    "paint": {"background-color": "#111111"} # Tmavošedé pozadie
                }
            ],
        }

        # Farby pre 3D stĺpce
        def get_color(row):
            val = row['util_num'] if viz_mode == "Využitie kapacity (%)" else (row['Počet produktov'] * 10)
            if val < 20: return [46, 204, 113, 200]   # Zelená
            if val < 80: return [241, 196, 15, 200]   # Žltá
            return [231, 76, 60, 200]                 # Červená

        active_df['color'] = active_df.apply(get_color, axis=1)

        # 3D Vrstva stĺpcov
        layer = pdk.Layer(
            "ColumnLayer",
            active_df,
            get_position=["ul_num", "poz_num"],
            get_elevation="util_num",
            elevation_scale=0.1, # Výška stĺpcov
            radius=0.4,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        # Nastavenie kamery priamo na súradnice skladu
        view_state = pdk.ViewState(
            latitude=active_df['poz_num'].mean() if not active_df.empty else 0,
            longitude=active_df['ul_num'].mean() if not active_df.empty else 0,
            zoom=15, # Väčší zoom, aby sme boli blízko
            pitch=45,
            bearing=0
        )

        # Samotný 3D graf s prázdnym štýlom
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=EMPTY_MAP_STYLE, # TOTO JE KĽÚČOVÉ - nahradí mapu sveta čiernou plochou
            tooltip={"text": "Lokácia: {display_name}\nVyužitie: {util_num:.1f}%"}
        )

        st.pydeck_chart(r)
        st.info("💡 **Tip pre 3D**: Pravé tlačidlo myši = Otáčanie | Ctrl + Myš = Nakláňanie | Koliesko = Zoom")

    st.dataframe(active_df.sort_values(['ul_num', 'poz_num']), use_container_width=True)
else:
    st.error("Súbor data.xlsx nebol nájdený.")
