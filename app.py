"""Loadings Assessment - Streamlit web app: multiple floors/walls, editable databases."""
import io
import json

import pandas as pd
import streamlit as st

from core import (EMPTY, FloorBuildUp, ImposedItem, Layer, WallBuildUp,
                  database_from_records, load_database)

st.set_page_config(page_title="Loadings Assessment", layout="wide")
ss = st.session_state
PALETTE = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
           "#46c8c8", "#f032e6", "#a0c820", "#808000", "#008080"]


def s(x, default=""):
    return default if x is None or (isinstance(x, float) and pd.isna(x)) else x


def num(x):
    try:
        return 0.0 if pd.isna(x) else float(x)
    except (TypeError, ValueError):
        return 0.0


# ------------------------------------------------------------------ state
def new_id():
    ss.next_id += 1
    return ss.next_id


def blank_layers(n=3):
    return [{"Material": EMPTY, "Thickness [mm]": 0.0} for _ in range(n)]


def add_floor(data=None):
    n = len(ss.floors) + 1
    d = data or {}
    ss.floors.append({
        "id": new_id(), "name": d.get("name", f"Floor {n}"),
        "number": d.get("number", n), "color": d.get("color", PALETTE[(n - 1) % len(PALETTE)]),
        "layers": d.get("layers") or blank_layers(),
        "imposed": d.get("imposed") or [{"Usage": EMPTY}],
    })
    ss.floors[-1]["init_layers"] = json.loads(json.dumps(ss.floors[-1]["layers"]))
    ss.floors[-1]["init_imposed"] = json.loads(json.dumps(ss.floors[-1]["imposed"]))


def add_wall(data=None):
    n = len(ss.walls) + 1
    d = data or {}
    ss.walls.append({
        "id": new_id(), "name": d.get("name", f"Wall {n}"),
        "height": d.get("height", 3.0), "layers": d.get("layers") or blank_layers(),
    })
    ss.walls[-1]["init_layers"] = json.loads(json.dumps(ss.walls[-1]["layers"]))


def set_db_frames(sdl_records, ll_records):
    ss.sdl_init = pd.DataFrame(sdl_records, columns=["name", "value", "unit", "group"])
    ss.ll_init = pd.DataFrame(ll_records, columns=["name", "udl", "point", "category"])
    for k in ("sdl_editor", "ll_editor"):
        ss.pop(k, None)


def reset_db():
    b = load_database()
    set_db_frames(b.sdl_records(), b.ll_records())


def apply_db_upload():
    f = ss.get("db_upload")
    if f is not None:
        raw = json.load(f)
        set_db_frames(raw["sdl"], raw["ll"])


def apply_project_upload():
    f = ss.get("proj_upload")
    if f is None:
        return
    p = json.load(f)
    set_db_frames(p["db"]["sdl"], p["db"]["ll"])
    ss.floors, ss.walls = [], []
    for d in p.get("floors", []):
        add_floor(d)
    for d in p.get("walls", []):
        add_wall(d)
    for key, val in p.get("info", {}).items():
        ss[key] = val


def delete_item(kind, i):
    ss[kind] = [x for x in ss[kind] if x["id"] != i]


def duplicate_item(kind, i):
    src = next(x for x in ss[kind] if x["id"] == i)
    d = json.loads(json.dumps(src))
    d["name"] += " (copy)"
    if kind == "floors":
        d["number"] = max([x["number"] for x in ss.floors] + [0]) + 1
        add_floor(d)
    else:
        add_wall(d)


if "next_id" not in ss:
    ss.next_id = 0
    ss.floors, ss.walls = [], []
    reset_db()
    add_floor()
    add_wall()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Project")
    info = {"p_title": st.text_input("Project title", "PROJECT NAME", key="p_title"),
            "p_number": st.text_input("Project number", "E0XXX", key="p_number"),
            "p_by": st.text_input("By", "XX", key="p_by"),
            "p_checked": st.text_input("Checked by", "XX", key="p_checked"),
            "p_rev": st.text_input("Rev", "P1", key="p_rev")}

st.title("Loadings Assessment")
tab_floor, tab_wall, tab_db, tab_proj = st.tabs(
    ["Floors", "Walls", "Databases", "Project / export"])

# --------------------------------------------------------------- DATABASES
with tab_db:
    st.caption("Edit values, add rows at the bottom of a table, delete rows by selecting them. "
               "Changes apply immediately to all floors and walls. They are kept only during "
               "this session: download the database (or the project) to keep them.")
    st.subheader("Superdead load database")
    sdl_df = st.data_editor(
        ss.sdl_init, key="sdl_editor", num_rows="dynamic", use_container_width=True, height=380,
        column_config={
            "name": st.column_config.TextColumn("Material / layer", required=True),
            "value": st.column_config.NumberColumn("Value", format="%.4g"),
            "unit": st.column_config.SelectboxColumn("Unit", options=["kN/m2", "kN/m3"], required=True),
            "group": st.column_config.TextColumn("Group")})
    st.subheader("Imposed load database")
    ll_df = st.data_editor(
        ss.ll_init, key="ll_editor", num_rows="dynamic", use_container_width=True, height=380,
        column_config={
            "name": st.column_config.TextColumn("Usage", required=True),
            "udl": st.column_config.NumberColumn("UDL [kN/m2]", format="%.4g"),
            "point": st.column_config.NumberColumn("Point load [kN]", format="%.4g"),
            "category": st.column_config.TextColumn("Category")})

    clean_sdl = [{k: s(v) for k, v in r.items()} for r in sdl_df.to_dict("records")]
    clean_ll = [{k: s(v) for k, v in r.items()} for r in ll_df.to_dict("records")]
    db = database_from_records(clean_sdl, clean_ll)

    names = [str(r["name"]).strip() for r in clean_sdl if str(r["name"]).strip()]
    dup = sorted({n for n in names if names.count(n) > 1})
    if dup:
        st.warning("Duplicate material names (only the first is used): " + ", ".join(dup))

    c1, c2 = st.columns(2)
    c1.download_button("Download database (.json)", db.to_json(), "database.json",
                       "application/json")
    c2.button("Reset to original database", on_click=reset_db)
    st.file_uploader("Load a database file", type="json", key="db_upload")
    st.button("Apply uploaded database", on_click=apply_db_upload)

MATERIALS = [EMPTY] + sorted(k for k in db.sdl if k != EMPTY)
LL_ITEMS = [EMPTY] + [k for k in db.ll if k != EMPTY]


def layer_table(key, init):
    # `init` must stay constant between runs: the editor stores only the edits made on top of it.
    df = st.data_editor(
        pd.DataFrame(init, columns=["Material", "Thickness [mm]"]), key=key, num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Material": st.column_config.SelectboxColumn(options=MATERIALS, required=True),
            "Thickness [mm]": st.column_config.NumberColumn(
                min_value=0.0, step=5.0, help="Used only for materials given in kN/m3")})
    recs = [{"Material": s(r["Material"], EMPTY) or EMPTY, "Thickness [mm]": num(r["Thickness [mm]"])}
            for r in df.to_dict("records")]
    missing = [r["Material"] for r in recs if r["Material"] != EMPTY and r["Material"] not in db.sdl]
    if missing:
        st.warning("Not in the database anymore (counted as 0): " + ", ".join(missing))
    return recs


def swatch(color):
    return (f"<span style='display:inline-block;width:1.1em;height:1.1em;border-radius:3px;"
            f"background:{color};vertical-align:middle'></span>")


def layer_rows(recs, height=None):
    rows = []
    for r in recs:
        a = Layer(r["Material"], r["Thickness [mm]"]).load(db)
        row = {"Material": r["Material"], "Thickness [mm]": r["Thickness [mm]"],
               "Load [kN/m2]": round(a, 4)}
        if height is not None:
            row["Line load [kN/m]"] = round(a * height, 4)
        rows.append(row)
    return rows


# ------------------------------------------------------------------ FLOORS
floor_results = []
with tab_floor:
    summary_ph = st.container()
    for f in list(ss.floors):
        i = f["id"]
        with st.expander(f"{f['number']} · {f['name']}", expanded=True):
            c1, c2, c3 = st.columns([3, 1, 1])
            f["name"] = c1.text_input("Floor name", f["name"], key=f"fn{i}")
            f["number"] = int(c2.number_input("No.", value=int(f["number"]), step=1, key=f"fnum{i}"))
            f["color"] = c3.color_picker("Colour", f["color"], key=f"fcol{i}")
            st.markdown("**Superdead load**")
            f["layers"] = layer_table(f"fl{i}", f["init_layers"])
            st.markdown("**Imposed load**")
            ll = st.data_editor(
                pd.DataFrame(f["init_imposed"], columns=["Usage"]), key=f"fll{i}", num_rows="dynamic",
                use_container_width=True,
                column_config={"Usage": st.column_config.SelectboxColumn(options=LL_ITEMS, required=True)})
            f["imposed"] = [{"Usage": s(r["Usage"], EMPTY) or EMPTY} for r in ll.to_dict("records")]
            fb = FloorBuildUp(f["name"], [Layer(r["Material"], r["Thickness [mm]"]) for r in f["layers"]],
                              [ImposedItem(r["Usage"]) for r in f["imposed"]])
            m1, m2, m3 = st.columns(3)
            m1.metric("Superdead [kN/m2]", f"{fb.sdl_total(db):.2f}")
            m2.metric("Imposed UDL [kN/m2]", f"{fb.ll_udl_total(db):.2f}")
            m3.metric("Imposed point [kN]", f"{fb.ll_point_total(db):.2f}")
            b1, b2, _ = st.columns([1, 1, 4])
            b1.button("Duplicate", key=f"fdup{i}", on_click=duplicate_item, args=("floors", i))
            b2.button("Delete", key=f"fdel{i}", on_click=delete_item, args=("floors", i))
            floor_results.append((f, fb))
    st.button("＋ Add floor", on_click=add_floor)

    with summary_ph:
        if floor_results:
            st.subheader("Floor summary")
            sdf = pd.DataFrame([{"No.": f["number"], "Colour": f["color"], "Name": f["name"],
                                 "SDL [kN/m2]": round(fb.sdl_total(db), 3),
                                 "LL UDL [kN/m2]": round(fb.ll_udl_total(db), 3),
                                 "LL point [kN]": round(fb.ll_point_total(db), 3)}
                                for f, fb in floor_results]).sort_values("No.")
            st.dataframe(sdf.style.apply(
                lambda col: [f"background-color:{v};color:{v}" for v in col], subset=["Colour"]),
                use_container_width=True, hide_index=True)

# ------------------------------------------------------------------- WALLS
wall_results = []
with tab_wall:
    wsummary_ph = st.container()
    for w in list(ss.walls):
        i = w["id"]
        with st.expander(w["name"], expanded=True):
            c1, c2 = st.columns([3, 1])
            w["name"] = c1.text_input("Wall name", w["name"], key=f"wn{i}")
            w["height"] = c2.number_input("Height [m]", min_value=0.0, value=float(w["height"]),
                                          step=0.1, key=f"wh{i}")
            w["layers"] = layer_table(f"wl{i}", w["init_layers"])
            wb_ = WallBuildUp(w["name"], w["height"],
                              [Layer(r["Material"], r["Thickness [mm]"]) for r in w["layers"]])
            st.dataframe(pd.DataFrame(layer_rows(w["layers"], w["height"])),
                         use_container_width=True, hide_index=True)
            m1, m2 = st.columns(2)
            m1.metric("Wall face load [kN/m2]", f"{wb_.area_load(db):.2f}")
            m2.metric("Line load [kN/m]", f"{wb_.line_load(db):.2f}")
            b1, b2, _ = st.columns([1, 1, 4])
            b1.button("Duplicate", key=f"wdup{i}", on_click=duplicate_item, args=("walls", i))
            b2.button("Delete", key=f"wdel{i}", on_click=delete_item, args=("walls", i))
            wall_results.append((w, wb_))
    st.button("＋ Add wall", on_click=add_wall)
    with wsummary_ph:
        if wall_results:
            st.subheader("Wall summary")
            st.dataframe(pd.DataFrame([{"Name": w["name"], "Height [m]": w["height"],
                                        "Face load [kN/m2]": round(wb_.area_load(db), 3),
                                        "Line load [kN/m]": round(wb_.line_load(db), 3)}
                                       for w, wb_ in wall_results]),
                         use_container_width=True, hide_index=True)

# ----------------------------------------------------------------- PROJECT
with tab_proj:
    project = {"info": info, "db": {"sdl": db.sdl_records(), "ll": db.ll_records()},
               "floors": [{k: f[k] for k in ("name", "number", "color", "layers", "imposed")}
                          for f, _ in floor_results],
               "walls": [{k: w[k] for k in ("name", "height", "layers")} for w, _ in wall_results]}
    st.subheader("Save / load project")
    st.download_button("Download project (.json)", json.dumps(project, indent=1),
                       f"{info['p_number']}_loadings_project.json", "application/json")
    st.file_uploader("Open a saved project", type="json", key="proj_upload")
    st.button("Load project", on_click=apply_project_upload)

    st.subheader("Export results")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame({"Field": ["Project", "Number", "By", "Checked", "Rev"],
                      "Value": list(info.values())}).to_excel(xw, sheet_name="Info", index=False)
        pd.DataFrame([{"No.": f["number"], "Colour": f["color"], "Name": f["name"],
                       "SDL [kN/m2]": fb.sdl_total(db), "LL UDL [kN/m2]": fb.ll_udl_total(db),
                       "LL point [kN]": fb.ll_point_total(db)}
                      for f, fb in floor_results]).to_excel(xw, sheet_name="Floors", index=False)
        pd.DataFrame([{"Floor No.": f["number"], "Floor": f["name"], **r}
                      for f, _ in floor_results for r in layer_rows(f["layers"])]
                     ).to_excel(xw, sheet_name="Floor layers", index=False)
        pd.DataFrame([{"Floor No.": f["number"], "Floor": f["name"], "Usage": r["Usage"],
                       "UDL [kN/m2]": ImposedItem(r["Usage"]).values(db)[0],
                       "Point [kN]": ImposedItem(r["Usage"]).values(db)[1]}
                      for f, _ in floor_results for r in f["imposed"]]
                     ).to_excel(xw, sheet_name="Floor imposed", index=False)
        pd.DataFrame([{"Name": w["name"], "Height [m]": w["height"],
                       "Face load [kN/m2]": wb_.area_load(db), "Line load [kN/m]": wb_.line_load(db)}
                      for w, wb_ in wall_results]).to_excel(xw, sheet_name="Walls", index=False)
        pd.DataFrame([{"Wall": w["name"], "Height [m]": w["height"], **r}
                      for w, _ in wall_results for r in layer_rows(w["layers"], w["height"])]
                     ).to_excel(xw, sheet_name="Wall layers", index=False)
    st.download_button("Download results (.xlsx)", buf.getvalue(),
                       f"{info['p_number']}_loadings.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
