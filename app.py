    else:
        # --- OPRAVENÝ 3D PYDECK (Bezpečný pre Streamlit Cloud) ---
        st.subheader(f"3D Model: Zóna {selected_zone}")

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
            elevation_scale=0.5, # Zvýšil som mierku, aby boli stĺpce vyššie
            radius=0.4,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        # Nastavenie kamery
        view_state = pdk.ViewState(
            latitude=active_df['poz_num'].mean() if not active_df.empty else 0,
            longitude=active_df['ul_num'].mean() if not active_df.empty else 0,
            zoom=14,
            pitch=45,
            bearing=0
        )

        # Použijeme štandardný štýl "dark" - na súradniciach 1-100 bude aj tak vidieť len tmu/oceán
        r = pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style="dark", # Zmena z EMPTY_MAP_STYLE na "dark"
            tooltip={"text": "Lokácia: {display_name}\nVyužitie: {util_num:.1f}%"}
        )

        st.pydeck_chart(r)
        st.info("💡 **Tip pre 3D**: Pravé tlačidlo myši = Otáčanie | Ctrl + Myš = Nakláňanie")
