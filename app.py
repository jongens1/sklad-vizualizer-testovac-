import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Digital Twin")

st.title("🏛️ SKLC3 - 3D Priemyselný Model Skladu")

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

    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    # --- 3D RACK MODEL LOGIKA ---
    # Logika pre rozostupy uličiek
    spacing_factor = 4.0 # Šírka uličky (čím väčšie, tým širšia ulička)
    zone_df['x_viz'] = zone_df['ul_num'] * spacing_factor
    
    # Filter uličiek (aby to nebolo príliš ťažké na výkon, defaultne 10 uličiek)
    min_u, max_u = int(zone_df['ul_num'].min()), int(zone_df['ul_num'].max())
    sel_u = st.sidebar.slider("Zobraziť rozsah uličiek:", min_u, max_u, (min_u, min_u + 10))
    
    plot_df = zone_df[(zone_df['ul_num'] >= sel_u[0]) & (zone_df['ul_num'] <= sel_u[1])].copy()

    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()

    # 1. KRESLENIE KONŠTRUKCIE (POLICE A STĹPY)
    # Pre každú vybranú uličku nakreslíme "rám"
    for u_orig in plot_df['ul_num'].unique():
        u = u_orig * spacing_factor
        
        # Horizontálne nosníky (Police) - kreslíme len podlahu a vrch pre výkon, alebo všetky
        for z in range(1, int(plot_df['ur_num'].max()) + 2):
            fig.add_trace(go.Scatter3d(
                x=[u, u], y=[plot_df['poz_num'].min()-0.5, plot_df['poz_num'].max()+0.5], z=[z-0.5, z-0.5],
                mode='lines', line=dict(color='#444', width=2), showlegend=False, hoverinfo='none'
            ))

        # Vertikálne stojky (každé 3 Bay-e)
        positions = list(range(int(plot_df['poz_num'].min()), int(plot_df['poz_num'].max()) + 2))
        for p in positions:
            if (p-1) % 3 == 0 or p == max(positions):
                fig.add_trace(go.Scatter3d(
                    x=[u, u], y=[p-0.5, p-0.5], z=[0.5, plot_df['ur_num'].max() + 0.5],
                    mode='lines', line=dict(color='gray', width=3), showlegend=False, hoverinfo='none'
                ))

    # 2. VYKRESLENIE TOVARU (KOCKY)
    fig.add_trace(go.Scatter3d(
        x=plot_df['x_viz'],
        y=plot_df['poz_num'],
        z=plot_df['ur_num'],
        mode='markers',
        marker=dict(
            size=10, 
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=1, color='black'),
            opacity=0.9,
            colorbar=dict(title=viz_mode, x=1.05)
        ),
        text=plot_df['Názov lokácie'],
        hovertemplate="<b>%{text}</b><br>Hodnota: %{marker.color:.1f}<extra></extra>"
    ))

    # 3. NASTAVENIE POHĽADU (Perspektíva)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Uličky (Rady)', showbackground=True, backgroundcolor="#f0f0f0"),
            yaxis=dict(title='Pozícia v rade (Bay)', showbackground=True, backgroundcolor="#e5e5e5"),
            zaxis=dict(title='Poschodie', dtick=1, range=[0, 9], showbackground=True, backgroundcolor="#d5d5d5"),
            aspectmode='manual',
            # Pomer strán: X (šírka skladu), Y (dĺžka regálov), Z (výška)
            aspectratio=dict(x=2, y=2, z=0.5) 
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=850,
        title=f"3D Priemyselný model: Zóna {selected_zone}"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 Medzi radmi sú teraz voľné uličky. Pre lepšiu prehľadnosť použi slider uličiek vľavo.")
    
    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num', 'ur_num']), use_container_width=True)

else:
    st.info("👋 Prosím, nahraj Excel.")
