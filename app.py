import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

st.set_page_config(layout="wide", page_title="Warehouse Map Pro")

st.title("📊 SKLC3 - Stav lokácií")

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
            zone = parts[0]
            ulicka = int(parts[1])
            pozicia = int(parts[2])
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

uploaded_file = st.sidebar.file_uploader("Nahraj vlastný Excel (.xlsx)", type=["xlsx"])

df_raw = None
if uploaded_file:
    df_raw = load_and_parse_data(uploaded_file)
elif os.path.exists("data.xlsx"):
    df_raw = load_and_parse_data("data.xlsx")

if df_raw is not None:
    st.sidebar.header("📍 1. Základný výber")
    
    available_zones = sorted(df_raw['tmp_zone'].unique())
    default_zone_index = 0
    if "2A" in available_zones:
        default_zone_index = available_zones.index("2A")
    
    selected_zone = st.sidebar.selectbox("Vyber Zónu:", available_zones, index=default_zone_index)
    zone_df = df_raw[df_raw['tmp_zone'] == selected_zone].copy()

    st.sidebar.header("🏢 2. Filtrovať Sekcie")
    available_sections = sorted(zone_df['Sekcia'].unique())

    def set_all(val):
        for s in available_sections:
            st.session_state[f"cb_{s}"] = val

    col_a, col_b = st.sidebar.columns(2)
    col_a.button("Všetky", on_click=set_all, args=(True,))
    col_b.button("Žiadna", on_click=set_all, args=(False,))

    selected_sects = []
    with st.sidebar.expander("Zoznam sekcií v zóne", expanded=True):
        for sect in available_sections:
            if f"cb_{sect}" not in st.session_state:
                st.session_state[f"cb_{sect}"] = True
            if st.checkbox(sect, key=f"cb_{sect}"):
                selected_sects.append(sect)

    st.sidebar.markdown("---")
    view_type = st.sidebar.radio("Typ zobrazenia:", ["Pohľad na celú plochu (Pôdorys)", "Detail jednej uličky (Profil)"])
    viz_mode = st.sidebar.radio("Farba podľa:", ["Využitie kapacity (%)", "Počet produktov"])

    if view_type == "Pohľad na celú plochu (Pôdorys)":
        levels = sorted(zone_df['ur_num'].unique().astype(int))
        level_options = ["Všetky úrovne (Priemer)"] + [str(l) for l in levels]
        selected_level = st.sidebar.selectbox("Vyber poschodie:", level_options)
        if selected_level == "Všetky úrovne (Priemer)":
            plot_df = zone_df.groupby(['ul_num', 'poz_num', 'Sekcia']).agg({
                'util_num': 'mean', 'Počet produktov': 'mean', 'Množstvo produktov': 'sum'
            }).reset_index()
            plot_df['display_name'] = plot_df.apply(lambda r: f"{selected_zone}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d}", axis=1)
        else:
            plot_df = zone_df[zone_df['ur_num'] == int(selected_level)].copy()
            plot_df['display_name'] = plot_df['Názov lokácie']
        x_col, y_col = 'ul_num', 'poz_num'
    else:
        available_aisles = sorted(zone_df['ul_num'].unique().astype(int))
        selected_aisle = st.sidebar.selectbox("Vyber uličku:", available_aisles)
        plot_df = zone_df[zone_df['ul_num'] == selected_aisle].copy()
        plot_df['display_name'] = plot_df['Názov lokácie']
        x_col, y_col = 'poz_num', 'ur_num'

    active_mask = plot_df['Sekcia'].isin(selected_sects)
    active_df = plot_df[active_mask].copy()
    inactive_df = plot_df[~active_mask].copy()

    max_dim = max(plot_df[x_col].max() - plot_df[x_col].min(), plot_df[y_col].max() - plot_df[y_col].min()) if not plot_df.empty else 0
    auto_size = 45 if max_dim < 15 else (28 if max_dim < 40 else (18 if max_dim < 80 else 14))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=inactive_df[x_col], y=inactive_df[y_col],
        mode='markers',
        marker=dict(size=auto_size, symbol='square', color='#F0F0F0', line=dict(width=0.4, color='#CCCCCC')),
        text=inactive_df['display_name'],
        name="Neaktívne",
        hovertemplate="<b>%{text}</b><br>Sekcia: %{customdata}<br><i>(Vypnutá sekcia)</i><extra></extra>",
        customdata=inactive_df['Sekcia']
    ))

    if not active_df.empty:
        if viz_mode == "Využitie kapacity (%)":
            c_col, c_scale, c_min, c_max = 'util_num', 'RdYlGn_r', 0, 100
        else:
            c_col, c_scale, c_min, c_max = 'Počet produktov', 'Viridis_r', 0, active_df['Počet produktov'].max()
        fig.add_trace(go.Scatter(
            x=active_df[x_col], y=active_df[y_col],
            mode='markers',
            marker=dict(size=auto_size, symbol='square', color=active_df[c_col], colorscale=c_scale, cmin=c_min, cmax=c_max, showscale=True, line=dict(width=0.5, color='black')),
            text=active_df['display_name'],
            name="Aktívne",
            customdata=active_df[['ul_num', 'poz_num', 'util_num', 'Počet produktov', 'Sekcia']],
            hovertemplate="<b>%{text}</b><br>Sekcia: %{customdata[4]}<br>Využitie: %{customdata[2]:.1f}%<br>SKU: %{customdata[3]:.1f}<extra></extra>"
        ))

    fig.update_layout(
        xaxis=dict(title="Ulička", tickmode='linear', dtick=5, gridcolor='#f8f8f8', range=[plot_df[x_col].min()-1, plot_df[x_col].max()+1]),
        yaxis=dict(title="Pozícia", tickmode='linear', dtick=5, gridcolor='#f8f8f8', range=[plot_df[y_col].min()-1, plot_df[y_col].max()+1]),
        height=780, plot_bgcolor='white', showlegend=False, margin=dict(l=10, r=10, t=30, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- ÚPRAVA TABUĽKY (Premenovanie a formátovanie) ---
    st.write("### Detail aktívnych sekcií")
    
    if not active_df.empty:
        # 1. Výber a zoradenie dát
        report_df = active_df.sort_values(['ul_num', 'poz_num']).copy()
        
        # 2. Výber len dôležitých stĺpcov pre používateľa
        report_df = report_df[['display_name', 'Sekcia', 'util_num', 'Počet produktov', 'Množstvo produktov']]
        
        # 3. Premenovanie stĺpcov
        report_df.columns = ['Lokácia', 'Sekcia', '% Využitia', 'Počet SKU', 'Celkom kusov']
        
        # 4. Zaokrúhlenie pre krajší vzhľad
        report_df['% Využitia'] = report_df['% Využitia'].round(2)
        report_df['Počet SKU'] = report_df['Počet SKU'].round(1)
        
        # 5. Zobrazenie s vypnutým indexom
        st.dataframe(report_df, use_container_width=True, hide_index=True)
    else:
        st.write("Žiadne aktívne sekcie na zobrazenie.")

else:
    st.info("👋 Prosím, nahraj Excel alebo pridaj 'data.xlsx' na GitHub.")
