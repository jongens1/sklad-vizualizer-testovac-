import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

# 1. Nastavenie stránky
st.set_page_config(layout="wide", page_title="Warehouse 3D Loop")

st.title("🔄 SKLC3 - 3D Celkový Pohľad (Loop)")

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
    
    # NOVÉ: Možnosť vybrať buď konkrétnu zónu alebo celý LOOP
    available_zones = sorted(df_raw['tmp_zone'].unique())
    main_selection = st.sidebar.selectbox("Vyber zobrazenie:", ["CELÝ LOOP (A-F)"] + available_zones)

    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    # Logika pre globálne súradnice kociek
    def get_global_coords(row):
        z = row['tmp_zone']
        u = row['ul_num']
        p = row['poz_num']
        
        # Štandardný rozostup medzi uličkami
        u_space = u * 4.0
        
        # OFFSETY PRE JEDNOTLIVÉ ZÓNY (KOCKY)
        # Každá kocka je posunutá o 400 jednotiek na osi X
        offsets = {
            '2E': 0,
            '2A': 400,
            '2B': 800,
            '2C': 1200,
            '2D': 1600,
            '2F': 2000
        }
        
        base_x = offsets.get(z, 0) if main_selection == "CELÝ LOOP (A-F)" else 0
        return base_x + u_space, p

    if main_selection == "CELÝ LOOP (A-F)":
        plot_df = df_raw[df_raw['tmp_zone'].isin(['2A','2B','2C','2D','2E','2F'])].copy()
        is_loop = True
    else:
        plot_df = df_raw[df_raw['tmp_zone'] == main_selection].copy()
        is_loop = False

    # Aplikácia globálnych súradníc
    coords = plot_df.apply(lambda r: pd.Series(get_global_coords(r)), axis=1)
    plot_df['x_glob'], plot_df['y_glob'] = coords[0], coords[1]

    # VYKRESLENIE
    st.subheader(f"3D Model: {main_selection}")
    
    c_col, c_scale = ('util_num', 'RdYlGn_r') if viz_mode == "Využitie kapacity (%)" else ('Počet produktov', 'Viridis_r')

    fig = go.Figure()

    # 1. VYKRESLENIE KONŠTRUKCIE (Len ak nie sme v loope, kvôli výkonu)
    if not is_loop:
        for u_orig in plot_df['ul_num'].unique():
            u_viz = u_orig * 4.0
            fig.add_trace(go.Scatter3d(
                x=[u_viz, u_viz], y=[plot_df['poz_num'].min(), plot_df['poz_num'].max()], z=[0.5, 0.5],
                mode='lines', line=dict(color='gray', width=2), showlegend=False, hoverinfo='none'
            ))

    # 2. VYKRESLENIE LOKÁCIÍ (KOCKY)
    fig.add_trace(go.Scatter3d(
        x=plot_df['x_glob'],
        y=plot_df['y_glob'],
        z=plot_df['ur_num'],
        mode='markers',
        marker=dict(
            size=6 if is_loop else 12, # Menšie body pre celý loop
            symbol='square',
            color=plot_df[c_col],
            colorscale=c_scale,
            cmin=0, cmax=100 if viz_mode == "Využitie kapacity (%)" else plot_df[c_col].max(),
            line=dict(width=0.5, color='black'),
            opacity=0.9,
            colorbar=dict(title=viz_mode, x=1.05)
        ),
        text=plot_df['Názov lokácie'],
        hovertemplate="<b>%{text}</b><br>Hodnota: %{marker.color:.1f}<extra></extra>"
    ))

    # 3. NASTAVENIE POHĽADU
    fig.update_layout(
        scene=dict(
            xaxis=dict(title='Uličky (Globálne)', showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(title='Pozícia (Bay)', showgrid=False, zeroline=False, showticklabels=False),
            zaxis=dict(title='Poschodie', dtick=1, range=[0, 9]),
            aspectmode='manual',
            # Ak je to Loop, natiahneme X os poriadne doprava
            aspectratio=dict(x=4 if is_loop else 1, y=1, z=0.3)
        ),
        margin=dict(l=0, r=0, b=0, t=30),
        height=850
    )

    st.plotly_chart(fig, use_container_width=True)
    
    st.write("### Detailný zoznam lokálií (Top 100)")
    st.dataframe(plot_df.sort_values([c_col], ascending=False).head(100), use_container_width=True)

else:
    st.info("👋 Prosím, nahraj Excel alebo pridaj 'data.xlsx' na GitHub.")
