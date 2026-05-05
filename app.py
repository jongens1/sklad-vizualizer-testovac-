import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="SKLC3 CAD Warehouse Layout")

st.title("🏛️ SKLC3 - 3D Warehouse Digital Twin (CAD Match)")

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

    if selected_main == "CELÝ LOOP (A-F)":
        zone_df = df_raw[df_raw['tmp_zone'].isin(['2A','2B','2C','2D','2E','2F'])].copy()
    else:
        zone_df = df_raw[df_raw['tmp_zone'] == selected_main].copy()

    levels = sorted(zone_df['ur_num'].unique().astype(int))
    selected_level = st.sidebar.selectbox("Vyber poschodie:", ["Všetky úrovne (Priemer)"] + [str(l) for l in levels])

    # --- LOGIKA MAPY PODĽA CAD VÝKRESU ---
    def get_cad_coords(row):
        z, u, p = row['tmp_zone'], row['ul_num'], row['poz_num']
        
        # 1. Zóny A, B, C, D (Stredový blok - vertikálne regály)
        # Rozmiestnime ich vedľa seba na osi X
        zone_offsets_x = {'2A': 40, '2B': 90, '2C': 140, '2D': 190}
        
        if z in zone_offsets_x:
            x = zone_offsets_x[z] + (u * 1.5)
            # Pridáme medzeru v strede uličky pre koridor (ak p > 15, posunieme hore)
            y = p if p <= 15 else p + 10
            return x, y
        
        # 2. Zóna 2E (Ľavé krídlo - horizontálne regály)
        if z == '2E':
            # P je dĺžka regálu (X), U je číslo radu (Y)
            return p * 0.8, 40 + (u * 2.5)
        
        # 3. Zóna 2F (Pravé krídlo - horizontálne regály)
        if z == '2F':
            return 250 + (p * 0.8), 40 + (u * 2.5)
        
        return u, p

    # --- PRÍPRAVA DÁT ---
    if selected_level == "Všetky úrovne (Priemer)":
        plot_df = zone_df.groupby(['tmp_zone', 'ul_num', 'poz_num']).agg({
            'util_num': 'mean', 'Počet produktov': 'mean', 'Množstvo produktov': 'sum'
        }).reset_index()
        plot_df['display_name'] = plot_df.apply(lambda r: f"{r['tmp_zone']}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d}", axis=1)
        plot_df['z_viz'] = 1
    else:
        plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()
        plot_df['display_name'] = plot_df['Názov lokácie']
        plot_df['z_viz'] = plot_df['ur_num']

    # Aplikácia CAD súradníc
    coords = plot_df.apply(lambda r: pd.Series(get_cad_coords(r)), axis=1)
    plot_df['x_viz'], plot_df['y_viz'] = coords[0], coords[1]

    # --- VYKRESLENIE ---
    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()

    # Hlavná vrstva regálov
    fig.add_trace(go.Scatter3d(
        x=plot_df['x_viz'], y=plot_df['y_viz'], z=plot_df['z_viz'],
        mode='markers',
        marker=dict(
            size=6 if selected_main == "CELÝ LOOP (A-F)" else 10,
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=0.2, color='black'),
            opacity=0.9
        ),
        text=plot_df['display_name'],
        hovertemplate="<b>%{text}</b><br>Využitie: %{marker.color:.1f}%<extra></extra>"
    ))

    # Nastavenie scény tak, aby pripomínala pôdorys haly
    fig.update_layout(
        title=f"3D Pôdorys skladu: {selected_main} ({selected_level})",
        scene=dict(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, title=""),
            zaxis=dict(title='Poschodie', range=[0, 9] if selected_level != "Všetky úrovne (Priemer)" else [0, 2]),
            aspectmode='manual',
            # X je šírka haly, Y je dĺžka haly
            aspectratio=dict(x=2, y=1.5, z=0.1 if selected_level == "Všetky úrovne (Priemer)" else 0.4)
        ),
        margin=dict(l=0, r=0, b=0, t=40), height=850
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 Toto zobrazenie kopíruje CAD layout: E (vľavo), A-D (stred), F (vpravo).")

else:
    st.info("Nahraj Excel súbor.")
