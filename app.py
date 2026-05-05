import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Rack Model")

st.title("🚀 SKLC3 - 3D Digitálne dvojča skladu")

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

    view_mode = st.sidebar.radio("Režim zobrazenia:", ["2D Mapa (Plocha)", "3D Model (Regály)"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    levels = sorted(zone_df['ur_num'].unique().astype(int))
    # Pridaná možnosť vidieť celý regál
    selected_level = st.sidebar.selectbox("Vyber zobrazenie:", ["Celý regál (všetky úrovne)"] + [str(l) for l in levels])
    
    if selected_level == "Celý regál (všetky úrovne)":
        # NEAGREGUJEME - chceme vidieť každú lokáciu zvlášť
        plot_df = zone_df.copy()
    else:
        plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()

    # --- 4. VYKRESLENIE ---
    
    if view_mode == "2D Mapa (Plocha)":
        if selected_level == "Celý regál (všetky úrovne)":
            st.warning("V 2D režime pri zobrazení všetkých úrovní sa body prekrývajú. Odporúčam vybrať konkrétne poschodie.")
        
        fig = go.Figure()
        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')
        
        fig.add_trace(go.Scatter(
            x=plot_df['ul_num'], y=plot_df['poz_num'],
            mode='markers',
            marker=dict(
                size=12, symbol='square', color=plot_df[c_col], 
                colorscale=c_scale, cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
                showscale=True, line=dict(width=0.5, color='black')
            ),
            text=plot_df['Názov lokácie'],
            hovertemplate="<b>%{text}</b><br>Využitie: %{marker.color:.1f}%<extra></extra>"
        ))
        fig.update_layout(height=700, plot_bgcolor='white', xaxis=dict(title="Ulička"), yaxis=dict(title="Pozícia"))
        st.plotly_chart(fig, use_container_width=True)

    else:
        # --- 3D MODEL (RACK VIEW) ---
        st.subheader(f"3D Pohľad na regály: Zóna {selected_zone}")

        c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

        fig = go.Figure(data=[go.Scatter3d(
            x=plot_df['ul_num'],
            y=plot_df['poz_num'],
            z=plot_df['ur_num'], # OS Z JE TERAZ ÚROVEŇ (1-8)
            mode='markers',
            marker=dict(
                size=5,
                color=plot_df[c_col],
                colorscale=c_scale,
                cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
                opacity=0.9,
                symbol='square',
                colorbar=dict(title=viz_mode, x=1.1)
            ),
            text=plot_df['Názov lokácie'],
            customdata=plot_df[['util_num', 'ur_num']],
            hovertemplate=(
                "<b>Lokácia: %{text}</b><br>" +
                "Poschodie: %{customdata[1]}<br>" +
                "Využitie: %{customdata[0]:.1f}%<extra></extra>"
            )
        )])

        fig.update_layout(
            scene=dict(
                xaxis_title='Ulička',
                yaxis_title='Pozícia',
                zaxis_title='Poschodie (Úroveň)',
                zaxis=dict(dtick=1), # Zobrazujeme poschodia po jednom (1, 2, 3...)
                aspectmode='manual',
                aspectratio=dict(x=1, y=1, z=0.5) # Výška regálu
            ),
            margin=dict(l=0, r=0, b=0, t=30),
            height=850
        )

        st.plotly_chart(fig, use_container_width=True)
        st.info("💡 **Tip**: Body nad sebou predstavujú skutočné poschodia regálu. Farba indikuje ich zaplnenosť.")

    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num', 'ur_num']), use_container_width=True)

else:
    st.info("👋 Prosím, nahraj Excel alebo pridaj 'data.xlsx' na GitHub.")
