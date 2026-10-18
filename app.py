"""Loadings Assessment - Streamlit web app (floors and walls)."""
import io
import pandas as pd
import streamlit as st

from core import load_database, Layer, ImposedItem, FloorBuildUp, WallBuildUp

st.set_page_config(page_title="Loadings Assessment", layout="wide")
db = load_database()
MATERIALS = ["-"] + sorted(k for k in db.sdl if k != "-")
LL_ITEMS = ["-"] + [k for k in db.ll if k != "-"]

st.title("Loadings Assessment")
with st.sidebar:
    st.header("Project")
    project = st.text_input("Project title", "PROJECT NAME")
    number = st.text_input("Project number", "E0XXX")
    by = st.text_input("By", "XX")
    checked = st.text_input("Checked by", "XX")
    rev = st.text_input("Rev", "P1")

tab_floor, tab_wall = st.tabs(["Floor loadings", "Wall loadings"])


def layers_editor(key, default):
    df = st.data_editor(
        pd.DataFrame(default, columns=["Material", "Thickness [mm]"]),
        key=key, num_rows="dynamic", use_container_width=True,
        column_config={
            "Material": st.column_config.SelectboxColumn(options=MATERIALS, required=True),
            "Thickness [mm]": st.column_config.NumberColumn(min_value=0.0, step=5.0,
                help="Used only for materials given in kN/m3"),
        })
    layers = [Layer(r["Material"] or "-", float(r["Thickness [mm]"] or 0))
              for _, r in df.iterrows()]
    return layers


def with_loads(layers, height=None):
    rows = []
    for l in layers:
        v, u = (0.0, "") if l.material == "-" else db.sdl_value(l.material)
        a = l.load(db)
        row = {"Material": l.material, "Database value": v, "Unit": u,
               "Thickness [mm]": l.thickness_mm, "Load [kN/m2]": round(a, 4)}
        if height is not None:
            row["Line load [kN/m]"] = round(a * height, 4)
        rows.append(row)
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ FLOOR
with tab_floor:
    st.subheader("Superdead load")
    f_title = st.selectbox("Floor type", db.area_types, index=2)
    f_layers = layers_editor("floor_layers", [["-", 0.0]] * 3)
    f_sdl = with_loads(f_layers)
    st.dataframe(f_sdl, use_container_width=True, hide_index=True)

    st.subheader("Imposed load")
    ll_df = st.data_editor(
        pd.DataFrame({"Category / usage": ["-", "-"]}), key="floor_ll", num_rows="dynamic",
        use_container_width=True,
        column_config={"Category / usage": st.column_config.SelectboxColumn(
            options=LL_ITEMS, required=True)})
    floor = FloorBuildUp(f_title, f_layers, [ImposedItem(n or "-") for n in ll_df.iloc[:, 0]])
    ll_rows = pd.DataFrame(
        [{"Usage": i.name, "UDL [kN/m2]": i.values(db)[0], "Point load [kN]": i.values(db)[1]}
         for i in floor.imposed])
    st.dataframe(ll_rows, use_container_width=True, hide_index=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total superdead [kN/m2]", f"{floor.sdl_total(db):.2f}")
    c2.metric("Total imposed UDL [kN/m2]", f"{floor.ll_udl_total(db):.2f}")
    c3.metric("Total imposed point [kN]", f"{floor.ll_point_total(db):.2f}")

# ------------------------------------------------------------------- WALL
with tab_wall:
    w_title = st.selectbox("Wall type", db.wall_types, index=0)
    height = st.number_input("Wall height [m]", min_value=0.0, value=3.0, step=0.1)
    w_layers = layers_editor("wall_layers", [["-", 0.0]] * 3)
    wall = WallBuildUp(w_title, height, w_layers)
    st.dataframe(with_loads(w_layers, height), use_container_width=True, hide_index=True)
    c1, c2 = st.columns(2)
    c1.metric("Wall face load [kN/m2]", f"{wall.area_load(db):.2f}")
    c2.metric("Line load [kN/m]", f"{wall.line_load(db):.2f}")

# ----------------------------------------------------------------- EXPORT
st.divider()
buf = io.BytesIO()
with pd.ExcelWriter(buf, engine="openpyxl") as xw:
    pd.DataFrame({"Field": ["Project", "Number", "By", "Checked", "Rev"],
                  "Value": [project, number, by, checked, rev]}).to_excel(xw, "Info", index=False)
    f_sdl.to_excel(xw, "Floor SDL", index=False)
    ll_rows.to_excel(xw, "Floor LL", index=False)
    with_loads(w_layers, height).to_excel(xw, "Wall", index=False)
st.download_button("Download results (.xlsx)", buf.getvalue(),
                   file_name=f"{number}_loadings.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
