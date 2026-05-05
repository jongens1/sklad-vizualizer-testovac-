import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

st.set_page_config(layout="wide", page_title="Warehouse 3D Digital Twin")

st.title("🏗️ SKLC3 - Realistický 3D Model Regálov")

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

    # --- 3D RACK MODEL ---
    # Filter pre uličky (pre prehľadnosť v 3D zobrazíme naraz len malú časť)
    min_u, max_u = int(zone_df['ul_num'].min()), int(zone_df['ul_num'].max())
    sel_u = st.sidebar.slider("Rozsah uličiek na zobrazenie:", min_u, max_u, (min_u, min_u + 3))
    
    plot_df = zone_df[(zone_df['ul_num'] >= sel_u[0]) & (zone_df['ul_num'] <= sel_u[1])].copy()

    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()

    # 1. KONŠTRUKCIA REGÁLU (Oceľové nosníky)
    # Vykreslíme horizontálne čiary (police) pre každú uličku
    for u in plot_df['ul_num'].unique():
        for z in range(1, int(plot_df['ur_num'].max()) + 2):
            fig.add_trace(go.Scatter3d(
                x=[u, u], y=[plot_df['poz_num'].min()-0.5, plot_df['poz_num'].max()+0.5], z=[z-0.5, z-0.5],
                mode='lines', line=dict(color='black', width=4), showlegend=False, hoverinfo='none'
            ))

    # Vykreslíme vertikálne čiary (stĺpy) - každé 3 pozície jeden rám
    for u in plot_df['ul_num'].unique():
        # Stĺpy na začiatku, konca a každé 3 pozície
        positions = list(range(int(plot_df['poz_num'].min()), int(plot_df['poz_num'].max()) + 2))
        for p in positions:
            if (p-1) % 3 == 0 or p == max(positions):
                fig.add_trace(go.Scatter3d(
                    x=[u, u], y=[p-0.5, p-0.5], z=[0.5, plot_df['ur_num'].max() + 0.5],
                    mode='lines', line=dict(color='gray', width=6), showlegend=False, hoverinfo='none'
                ))

    # 2. VYKRESLENIE BUNKIEK (Tovar v regáli)
    fig.add_trace(go.Scatter3d(
        x=plot_df['ul_num'],
        y=plot_df['poz_num'],
        z=plot_df['ur_num'],
        mode='markers',
        marker=dict(
            size=20, # Ešte väčšie kocky aby vyplnili rám
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=1, color='black'),
            opacity=0.9,
            colorbar=dict(title=viz_mode, x=1.1)
        ),
        text=plot_df['Názov lokácie'],
        hovertemplate="<b>%{text}</b><br>Využitie: %{marker.color:.1f}%<extra></extra>"
    ))

    # 3. NASTAVENIE PROPORCIÍ (Crucial for "Rack" look)
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Ulička (Rady)', gridcolor='white', showbackground=True, backgroundcolor="#f0f0f0"),
            yaxis=dict(title='Pozícia (Bay)', gridcolor='white', showbackground=True, backgroundcolor="#e5e5e5"),
            zaxis=dict(title='Poschodie', dtick=1, range=[0, 9], gridcolor='white', showbackground=True, backgroundcolor="#d5d5d5"),
            aspectmode='manual',
            # Tu nastavíme: šírka uličiek(x), dĺžka regálu(y), výška(z)
            # Y je 4x dlhšie ako X, aby to vyzeralo ako dlhý rad
            aspectratio=dict(x=1, y=3, z=1) 
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=850,
        title=f"Realistický 3D pohľad: Zóna {selected_zone}"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.info("💡 **Legenda:** Čierne čiary sú police, sivé stĺpy sú rámy regálov. Každá ulička je jeden rad.")
    
    st.write("### Dáta zobrazených regálov")
    st.dataframe(plot_df.sort_values(['ul_num', 'poz_num', 'ur_num']), use_container_width=True)

else:
    st.info("Nahraj Excel súbor.")
