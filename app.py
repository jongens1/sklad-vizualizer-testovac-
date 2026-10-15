import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os


# CAD kotvy a mierka sú spoločné pre všetky filtre. Súradnice sú relatívne,
# nie zamerané metre. Zmeňte tieto hodnoty po overení skutočného CAD výkresu.
# Proporcie odčítané zo snímky DWG (1452 × 892 px), nie zamerané metre.
# X rastie doprava, Y nahor. Rozmery sú približne desatina pixelových rozmerov.
# Rozsah čísel lokácií sa mapuje do obálky zóny vždy z CELÉHO Excelu.
AISLE_STEP = 1.05
POSITION_STEP = 0.75
ZONE_GAP = 6.0
EXPANDED_GAP_FACTOR = 2.0
OUTLINE_PADDING = 0.5
AXIS_PADDING_RATIO = 0.04
MAX_SECTION_LABELS = 25
CAD_LAYOUT = {
    "2A": {"x0": 0, "y0": 105, "orientation": "horizontal"},
    "2B": {"x0": 0, "y0": 72, "orientation": "horizontal"},
    "2C": {"x0": 0, "y0": 39, "orientation": "horizontal"},
    "2D": {"x0": 0, "y0": 6, "orientation": "horizontal"},
    "2E": {"x0": -35, "y0": 39, "orientation": "vertical"},
    "2F": {"x0": 95, "y0": 39, "orientation": "vertical"},
    "2A": {"x0": 24.6, "y0": 65.8, "width": 99.8, "height": 15.4, "orientation": "horizontal"},
    "2B": {"x0": 19.0, "y0": 41.2, "width": 91.8, "height": 15.8, "orientation": "horizontal"},
    "2C": {"x0": 19.0, "y0": 24.0, "width": 91.8, "height": 14.4, "orientation": "horizontal"},
    "2D": {"x0": 3.0, "y0": 2.4, "width": 140.8, "height": 13.2, "orientation": "horizontal"},
    "2E": {"x0": 2.5, "y0": 20.5, "width": 13.0, "height": 54.5, "orientation": "vertical"},
    "2F": {"x0": 126.4, "y0": 20.6, "width": 12.9, "height": 51.0, "orientation": "vertical"},
}
# Voliteľné reverse_aisle/reverse_position v konfigurácii otočia číslovanie.
# Snímka neumožňuje spoľahlivo priradiť konkrétne čísla k jednotlivým regálom.
# Orientačné stanice v priechodoch; ich identita/poloha nie je overená DWG.
# Orientačné stanice. x/y sú súradnice v pôvodnom CAD_LAYOUT.
# x/y sú súradnice v pôvodnom CAD_LAYOUT.
# Voliteľná zone umožní stanici sledovať posun jej zóny a filter zóny.
# Bez zone je stanica pevná a zobrazí sa iba v celom loope.
STATIONS = [
    {"name": "Stanica 1", "x": 10, "y": 120, "type": "station", "zone": "2A"},
    {"name": "Stanica 2", "x": 50, "y": 120, "type": "station", "zone": "2A"},
    {"name": "Inbound", "x": -20, "y": 20, "type": "inbound"},
    {"name": "Outbound", "x": 105, "y": 20, "type": "outbound"},
    {"name": "Stanica 1", "x": 40, "y": 61, "type": "station", "zone": "2A"},
    {"name": "Stanica 2", "x": 90, "y": 61, "type": "station", "zone": "2A"},
    {"name": "Inbound", "x": 12, "y": 18, "type": "inbound"},
    {"name": "Outbound", "x": 133, "y": 18, "type": "outbound"},
]
STATION_STYLES = {
    "station": ("Stanica", "#2563eb", "diamond"),
    "inbound": ("Príjem", "#7c3aed", "circle"),
    "outbound": ("Expedícia", "#db2777", "square"),
}
REQUIRED_COLUMNS = [
    "Názov lokácie", "% Využité kapacity", "Počet produktov",
    "Množstvo produktov", "Sekcia",
]
LOOP = "CELÝ LOOP (A-F)"
ALL_LEVELS = "Všetky úrovne (Priemer)"
CAPACITY = "Využitie kapacity (%)"


def safe_text(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def parse_location(value):
    parts = str(value).strip().upper().split("-")
    if len(parts) not in (3, 4) or not parts[0].isalnum():
        return None, None, None, None
    if not all(part.isascii() and part.isdigit() for part in parts[1:]):
        return None, None, None, None
    return parts[0], int(parts[1]), int(parts[2]), int(parts[3]) if len(parts) == 4 else 1


@st.cache_data(show_spinner=False)
def load_and_parse_data(file_source, file_mtime_ns, file_size, fraction_capacity=False):
    # mtime a veľkosť sú súčasťou kľúča cache: výmena Excelu obnoví dáta.
    df = pd.read_excel(file_source)
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError("V Exceli chýbajú stĺpce: " + ", ".join(missing))
    quality = {"loaded": len(df)}
    coords = pd.DataFrame(
        [parse_location(value) for value in df["Názov lokácie"]],
        columns=["tmp_zone", "ul_num", "poz_num", "ur_num"], index=df.index,
    )
    df = pd.concat([df, coords], axis=1)
    df = df.dropna(subset=list(coords.columns)).copy()
    quality["parsed"] = len(df)
    quality["rejected"] = quality["loaded"] - quality["parsed"]
    df[["ul_num", "poz_num", "ur_num"]] = df[["ul_num", "poz_num", "ur_num"]].astype(int)
    df["Sekcia"] = df["Sekcia"].fillna("Nezaradené").astype(str).str.strip().replace("", "Nezaradené")
    quality["numeric_replaced"] = 0
    for column in ["% Využité kapacity", "Počet produktov", "Množstvo produktov"]:
        raw = df[column].astype("string").str.strip()
        has_percent = raw.str.contains("%", regex=False, na=False)
        cleaned = raw.str.replace(r"[\s%]", "", regex=True).str.replace(",", ".", regex=False)
        numbers = pd.to_numeric(cleaned, errors="coerce").astype(float)
        numbers = numbers.replace([float("inf"), -float("inf")], float("nan"))
        quality["numeric_replaced"] += int(numbers.isna().sum())
        numbers = numbers.fillna(0)
        if column == "% Využité kapacity":
            # Text '76 %' je už v percentách. Excel percentá môžu byť 0.76.
            if fraction_capacity:
                numbers = numbers.where(has_percent, numbers * 100)
            df["util_num"] = numbers
        else:
            df[column] = numbers
    quality["duplicates"] = int(df.duplicated(["tmp_zone", "ul_num", "poz_num", "ur_num"]).sum())
    quality["outside_capacity"] = int(((df["util_num"] < 0) | (df["util_num"] > 100)).sum())
    quality["negative_counts"] = int(((df["Počet produktov"] < 0) | (df["Množstvo produktov"] < 0)).sum())
    return df, quality


def get_cad_coords(row, layout=None):
    cfg = (CAD_LAYOUT if layout is None else layout).get(row["tmp_zone"])
    u, p = row["ul_num"], row["poz_num"]
    if cfg is None:
        return u, p
    if "aisle_range" in cfg:
        def relative(value, limits, reverse):
            low, high = limits
            fraction = (value - low) / (high - low) if high > low else 0.5
            return 1 - fraction if reverse else fraction
        aisle = relative(u, cfg["aisle_range"], cfg.get("reverse_aisle", False))
        position = relative(p, cfg["position_range"], cfg.get("reverse_position", False))
        x, y = (aisle, position) if cfg["orientation"] == "horizontal" else (position, aisle)
        return cfg["x0"] + x * cfg["width"], cfg["y0"] + y * cfg["height"]
    if cfg["orientation"] == "horizontal":
        return cfg["x0"] + u * AISLE_STEP, cfg["y0"] + p * POSITION_STEP
    return cfg["x0"] + p * POSITION_STEP, cfg["y0"] + u * AISLE_STEP


def add_coords(df, layout):
    result = df.copy()
    xy = [get_cad_coords(row, layout) for _, row in result.iterrows()]
    result["x_viz"] = [point[0] for point in xy]
    result["y_viz"] = [point[1] for point in xy]
    return result


def bounds(df):
    return (float(df["x_viz"].min()), float(df["x_viz"].max()),
            float(df["y_viz"].min()), float(df["y_viz"].max()))


def build_layout(df, compact=True):
    """Usporiadanie D–C–B–A a bočných krídel E/F z celého vstupu.
    """Pevné obálky podľa fotografie; filtre nemenia mierku ani polohu.

    Kompaktný režim zabalí bloky s jednotnou medzerou. Rozšírený zachová
    aspoň CAD odstupy a zväčší minimálnu medzeru. Nikdy nepresúva jednotlivé
    lokácie vnútri zóny ani nepočíta rozloženie z aktuálneho filtra úrovne.
    Na rozdiel od balenia obdĺžnikov zostáva D pod celou halou, A je širšia
    než B/C a pravé krídlo je odsadené od B/C. Chýbajúca zóna nezatvorí
    jej priestor. Medzery v číslovaní ostávajú medzerami aj na mape.
    """
    layout = {zone: dict(cfg) for zone, cfg in CAD_LAYOUT.items()}
    gap = ZONE_GAP * (1 if compact else EXPANDED_GAP_FACTOR) + 2 * OUTLINE_PADDING
    base = add_coords(df[df["tmp_zone"].isin(CAD_LAYOUT)], CAD_LAYOUT)
    boxes = {zone: bounds(group) for zone, group in base.groupby("tmp_zone")}
    previous_top = None
    for zone in ("2D", "2C", "2B", "2A"):
        if zone not in boxes:
            continue
        _, _, bottom, top = boxes[zone]
        target = bottom if previous_top is None else previous_top + gap
        if not compact:
            target = max(bottom, target)
        layout[zone]["y0"] += target - bottom
        previous_top = top + target - bottom
    centers = [boxes[z] for z in ("2A", "2B", "2C", "2D") if z in boxes]
    if centers:
        left, right = min(b[0] for b in centers), max(b[1] for b in centers)
        for zone in ("2E", "2F"):
            if zone not in boxes:
                continue
            x_min, x_max, _, _ = boxes[zone]
            shift = left - gap - x_max if zone == "2E" else right + gap - x_min
            if not compact:
                shift = min(0, shift) if zone == "2E" else max(0, shift)
            layout[zone]["x0"] += shift
            # Bočné krídla zostávajú zarovnané s kotvou zóny C.
            layout[zone]["y0"] += layout["2C"]["y0"] - CAD_LAYOUT["2C"]["y0"]
    elif "2E" in boxes and "2F" in boxes:
        layout["2F"]["x0"] += max(0, boxes["2E"][1] + gap - boxes["2F"][0])
    for zone, group in df.groupby("tmp_zone"):
        if zone in layout:
            layout[zone]["aisle_range"] = (float(group["ul_num"].min()), float(group["ul_num"].max()))
            layout[zone]["position_range"] = (float(group["poz_num"].min()), float(group["poz_num"].max()))
    if not compact:
        extra = ZONE_GAP * (EXPANDED_GAP_FACTOR - 1)
        for zone, multiplier in {"2D": 0, "2C": 1, "2B": 2, "2A": 3, "2E": 1, "2F": 1}.items():
            layout[zone]["y0"] += extra * multiplier
        layout["2E"]["x0"] -= extra
        layout["2F"]["x0"] += extra
    return layout


def join_sections(values):
    return ", ".join(sorted(set(values)))


def prepare_plot(zone_df, selected_level, layout):
    aggregated = selected_level == ALL_LEVELS
    source = zone_df if aggregated else zone_df[zone_df["ur_num"] == int(selected_level)]
    if aggregated:
        plot = source.groupby(["tmp_zone", "ul_num", "poz_num"], as_index=False).agg(
            util_num=("util_num", "mean"),
            **{"Počet produktov": ("Počet produktov", "mean"),
               "Množstvo produktov": ("Množstvo produktov", "sum"),
               "Sekcia": ("Sekcia", join_sections)},
        )
        plot["z_viz"] = 1
        plot["Názov lokácie"] = plot.apply(
            lambda r: f"{r['tmp_zone']}-{int(r['ul_num']):02d}-{int(r['poz_num']):02d} (všetky úrovne)", axis=1
        ) if not plot.empty else pd.Series(dtype=str)
    else:
        plot = source.copy()
        plot["z_viz"] = plot["ur_num"]
    plot = add_coords(plot, layout)
    def hover(row):
        return (
            f"<b>Lokácia: {safe_text(row['Názov lokácie'])}</b><br>"
            f"Zóna: {safe_text(row['tmp_zone'])}<br>Ulička: {int(row['ul_num'])}<br>"
            f"Pozícia: {int(row['poz_num'])}<br>"
            f"Úroveň: {'všetky' if aggregated else int(row['ur_num'])}<br>"
            f"Sekcia: {safe_text(row['Sekcia'])}<br>"
            f"Využitie{' (priemer)' if aggregated else ''}: {row['util_num']:.1f} %<br>"
            f"Počet produktov{' (priemer)' if aggregated else ''}: {row['Počet produktov']:g}<br>"
            f"Množstvo produktov{' (suma)' if aggregated else ''}: {row['Množstvo produktov']:g}"
        )
    plot["hover_text"] = [hover(row) for _, row in plot.iterrows()]
    return plot, source


def visible_stations(layout, selected_zone):
    stations = []
    for station in STATIONS:
        zone = station.get("zone")
        if selected_zone != LOOP and zone != selected_zone:
            continue
        item = dict(station)
        if zone in layout:
            item["x"] += layout[zone]["x0"] - CAD_LAYOUT[zone]["x0"]
            item["y"] += layout[zone]["y0"] - CAD_LAYOUT[zone]["y0"]
        stations.append(item)
    return stations


def axis_range(values):
    low, high = min(values), max(values)
    padding = max((high - low) * AXIS_PADDING_RATIO, 1.0)
    return [low - padding, high + padding]


def create_figure(plot, source, layout, *, is_2d, is_loop, capacity,
                  show_zones, show_sections, stations, debug):
    fig = go.Figure()
    def trace(x, y, z, **kwargs):
        if is_2d:
            fig.add_trace(go.Scatter(x=x, y=y, **kwargs))
        else:
            fig.add_trace(go.Scatter3d(x=x, y=y, z=z, **kwargs))
    c_col = "util_num" if capacity else "Počet produktov"
    max_value = plot[c_col].max()
    cmax = 100 if capacity else (float(max_value) if pd.notna(max_value) and max_value > 0 else 1)
    trace(plot["x_viz"], plot["y_viz"], plot["z_viz"], mode="markers", name="Lokácie", showlegend=False,
          text=plot["hover_text"], hovertemplate="%{text}<extra></extra>",
          marker=dict(size=(3 if is_loop else 7) + (1 if is_2d else 0), symbol="square",
                      color=plot[c_col], colorscale="RdYlGn_r" if capacity else "Viridis",
                      cmin=0, cmax=cmax, opacity=0.9,
                      colorbar=dict(title=dict(text="Využitie %" if capacity else "Počet produktov"), thickness=14)))
    xs, ys = plot["x_viz"].tolist(), plot["y_viz"].tolist()
    label_z = float(plot["z_viz"].max())
    if show_zones:
        for zone, group in plot.groupby("tmp_zone"):
            left, right, bottom, top = bounds(group)
            left, right = left - OUTLINE_PADDING, right + OUTLINE_PADDING
            bottom, top = bottom - OUTLINE_PADDING, top + OUTLINE_PADDING
            trace([left, right, right, left, left], [bottom, bottom, top, top, bottom], [0] * 5,
                  mode="lines", line=dict(color="#a8b8ca", width=2), hoverinfo="skip", showlegend=False)
            trace([(left + right) / 2], [(bottom + top) / 2], [label_z + 0.2], mode="text",
                  text=[safe_text(zone)], textfont=dict(size=21, color="#0f172a"),
                  hoverinfo="skip", showlegend=False)
            xs.extend([left, right]); ys.extend([bottom, top])
    if show_sections:
        # Používame pôvodné členstvo, nie spojené názvy sekcií z agregácie.
        sections = add_coords(source, layout)
        sections = sections[sections["Sekcia"] != "Nezaradené"].drop_duplicates(
            ["tmp_zone", "ul_num", "poz_num", "ur_num", "Sekcia"])
        centers = sections.groupby(["tmp_zone", "Sekcia"], as_index=False).agg(
            x_viz=("x_viz", "mean"), y_viz=("y_viz", "mean"), count=("Sekcia", "size"))
        centers = centers.sort_values(["count", "tmp_zone", "Sekcia"], ascending=[False, True, True]).head(MAX_SECTION_LABELS)
        trace(centers["x_viz"], centers["y_viz"], [label_z + 0.1] * len(centers), mode="text",
              text=[safe_text(s) for s in centers["Sekcia"]], textposition="bottom center",
              textfont=dict(size=11, color="#475569"), hoverinfo="skip", showlegend=False)
    for station_type in sorted({s["type"] for s in stations}):
        group = [s for s in stations if s["type"] == station_type]
        title, color, symbol = STATION_STYLES.get(station_type, (station_type, "#2563eb", "diamond"))
        x, y = [s["x"] for s in group], [s["y"] for s in group]
        trace(x, y, [0] * len(group), mode="markers+text", name=title,
              text=[safe_text(s["name"]) for s in group], textposition="top center",
              textfont=dict(size=12, color=color), marker=dict(size=12 if is_2d else 8, color=color, symbol=symbol),
              hovertemplate="%{text}<br>Typ: " + safe_text(title) + "<extra></extra>")
        xs.extend(x); ys.extend(y)
    xr, yr = axis_range(xs), axis_range(ys)
    axis = dict(visible=debug, showticklabels=debug, showgrid=debug, zeroline=False)
    fig.update_layout(template="plotly_white", height=760, margin=dict(l=10, r=20, b=10, t=40),
                      legend=dict(orientation="h", y=1.08, x=0),
                      uirevision=str((is_2d, is_loop, tuple(xr), tuple(yr), label_z)))
    if is_2d:
        fig.update_layout(xaxis=dict(axis, range=xr, title="X", constrain="domain"),
                          yaxis=dict(axis, range=yr, title="Y", scaleanchor="x", scaleratio=1), dragmode="pan")
    else:
        span = max(xr[1] - xr[0], yr[1] - yr[0])
        fig.update_layout(scene=dict(
            xaxis=dict(axis, range=xr, title="X"), yaxis=dict(axis, range=yr, title="Y"),
            zaxis=dict(title="Úroveň", range=[-0.3, max(label_z + 1, 2)], dtick=1),
            aspectmode="manual", aspectratio=dict(x=(xr[1] - xr[0]) / span,
                                                  y=(yr[1] - yr[0]) / span, z=0.22),
            camera=dict(eye=dict(x=1.2, y=-1.5, z=1.8), center=dict(x=0, y=0, z=0))))
    return fig


def main():
    st.set_page_config(layout="wide", page_title="SKLC3 | Pôdorys skladu")
    st.title("SKLC3 · Pôdorys skladu")
    st.caption("Vyberte zónu a úroveň. Detail lokácie sa zobrazí po prejdení myšou.")
    st.caption("Rozloženie zón podľa snímky DWG. Polohy lokácií v zónach sú pomerné podľa číslovania; nejde o zamerané CAD súradnice.")
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.xlsx")
    if not os.path.isfile(file_path):
        st.error("Súbor data.xlsx nebol nájdený. Uložte ho do rovnakého priečinka ako app.py.")
        return
    with st.sidebar.expander("Formát vstupných dát"):
        fractions = st.checkbox("Kapacita v Exceli je číslo 0–1", value=False,
                                help="Zapnite pre Excel percentá: 0,765 znamená 76,5 %. Texty s % sa nemenia.")
    try:
        file_stat = os.stat(file_path)
        df, quality = load_and_parse_data(file_path, file_stat.st_mtime_ns, file_stat.st_size, fractions)
    except Exception as exc:
        st.error(f"Dáta sa nepodarilo načítať: {exc}")
        return
    st.sidebar.caption(f"Načítané: {quality['loaded']:,} · Naparsované: {quality['parsed']:,} · Vyradené: {quality['rejected']:,}")
    if quality["rejected"]:
        st.warning(f"{quality['rejected']} lokácií sa nepodarilo naparsovať a boli vynechané.")
    if quality["numeric_replaced"]:
        st.warning(f"{quality['numeric_replaced']} prázdnych alebo neplatných číselných hodnôt bolo nahradených nulou.")
    if quality["duplicates"]:
        st.warning(f"V dátach je {quality['duplicates']} opakovaných lokácií. Riadky sú zachované; súčty ich zahŕňajú.")
    if quality["outside_capacity"] or quality["negative_counts"]:
        st.warning(f"Skontrolujte dáta: {quality['outside_capacity']} využití mimo 0–100 % a {quality['negative_counts']} riadkov so zápornými počtami. Hodnoty zostávajú zachované.")
    if df.empty:
        st.info("Excel neobsahuje žiadne platné lokácie.")
        return
    st.sidebar.header("Výber zobrazenia")
    selected_zone = st.sidebar.selectbox("Vyber zobrazenie:", [LOOP] + sorted(df["tmp_zone"].unique()))
    is_loop = selected_zone == LOOP
    zone_df = df[df["tmp_zone"].isin(CAD_LAYOUT)] if is_loop else df[df["tmp_zone"] == selected_zone]
    levels = sorted(zone_df["ur_num"].unique())
    selected_level = st.sidebar.selectbox("Vyber úroveň:", [ALL_LEVELS] + [str(level) for level in levels])
    st.sidebar.header("Vizualizácia")
    view = st.sidebar.radio("Pohľad:", ["2D pôdorys", "3D pôdorys"])
    color = st.sidebar.radio("Farba podľa:", [CAPACITY, "Počet produktov"])
    compact = st.sidebar.checkbox("Kompaktný režim", value=True)
    st.sidebar.header("Orientácia")
    show_zones = st.sidebar.checkbox("Zobraziť zóny", value=True)
    show_sections = st.sidebar.checkbox("Zobraziť skupiny / sekcie", value=True)
    show_stations = st.sidebar.checkbox("Zobraziť stanice", value=True)
    st.sidebar.header("Debug")
    debug = st.sidebar.checkbox("Zobraziť orientačné osi", value=False)
    if zone_df.empty:
        st.info("Pre tento výber nie sú dostupné lokácie.")
        return
    if not is_loop and selected_zone not in CAD_LAYOUT:
        st.info("Táto zóna nemá CAD konfiguráciu. X predstavuje uličku a Y pozíciu.")
    layout = build_layout(df, compact)
    plot, source = prepare_plot(zone_df, selected_level, layout)
    if plot.empty:
        st.info("Pre vybranú úroveň nie sú dostupné lokácie.")
        return
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Zobrazené pozície" if selected_level == ALL_LEVELS else "Zobrazené lokácie", f"{len(plot):,}")
    c2.metric("Priemerné využitie", f"{source['util_num'].mean():.1f} %")
    c3.metric("Počet produktov (súčet)", f"{source['Počet produktov'].sum():,.0f}")
    c4.metric("Množstvo produktov (súčet)", f"{source['Množstvo produktov'].sum():,.0f}")
    st.caption(f"Zóna: {selected_zone} · Úroveň: {selected_level} · Zdrojových lokácií/riadkov: {len(source):,}")
    st.caption("Sumár je vypočítaný zo zdrojových riadkov výberu. Počet produktov je súčet za lokácie, nie počet unikátnych produktov v sklade.")
    if selected_level == ALL_LEVELS:
        st.caption("Každý bod spája úrovne jednej pozície: využitie a počet produktov sú priemery, množstvo je súčet. V 3D sú tieto body v spoločnej rovine.")
    if show_sections:
        section_count = source[source["Sekcia"] != "Nezaradené"][["tmp_zone", "Sekcia"]].drop_duplicates().shape[0]
        if section_count > MAX_SECTION_LABELS:
            st.caption(f"Zobrazuje sa {MAX_SECTION_LABELS} najväčších skupín z {section_count} (sekcia v rámci zóny).")
    stations = visible_stations(layout, selected_zone) if show_stations else []
    fig = create_figure(plot, source, layout, is_2d=view == "2D pôdorys", is_loop=is_loop,
                        capacity=color == CAPACITY, show_zones=show_zones, show_sections=show_sections,
                        stations=stations, debug=debug)
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": True})
    if show_stations:
        st.caption("Stanice majú orientačné polohy. V detaile zóny sa zobrazujú iba stanice priradené k tejto zóne.")
    if debug:
        st.dataframe(plot, use_container_width=True)


if __name__ == "__main__":
    main()
