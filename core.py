"""Calculation logic for the Loadings Assessment sheet (no UI code here).

Rules reproduced from the Excel workbook:
  * Superdead layer: unit kN/m2 -> value used as is; unit kN/m3 -> value * thickness[mm] / 1000.
  * Floor SDL total = sum of layers [kN/m2].
  * Imposed load: UDL [kN/m2] and point load [kN] looked up by usage; totals are sums.
  * Wall line load [kN/m] = sum of (layer load [kN/m2] x wall height [m]).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DB_PATH = Path(__file__).with_name("database.json")
EMPTY = "-"


@dataclass(frozen=True)
class Database:
    sdl: dict   # name -> {"name","value","unit","group"}
    ll: dict    # name -> {"name","udl","point","category"}

    def sdl_records(self) -> list[dict]:
        return [dict(v) for v in self.sdl.values()]

    def ll_records(self) -> list[dict]:
        return [dict(v) for v in self.ll.values()]

    def to_json(self) -> str:
        return json.dumps({"sdl": self.sdl_records(), "ll": self.ll_records()},
                          indent=1, ensure_ascii=False)


def database_from_records(sdl: list[dict], ll: list[dict]) -> Database:
    """Build a Database from (possibly user-edited) records. First duplicate wins (as VLOOKUP)."""
    s, l = {}, {}
    for r in sdl:
        n = str(r.get("name", "")).strip()
        if n and n not in s:
            s[n] = {"name": n, "value": float(r.get("value") or 0),
                    "unit": r.get("unit") if r.get("unit") in ("kN/m2", "kN/m3") else "kN/m2",
                    "group": str(r.get("group") or "")}
    for r in ll:
        n = str(r.get("name", "")).strip()
        if n and n not in l:
            l[n] = {"name": n, "udl": float(r.get("udl") or 0),
                    "point": float(r.get("point") or 0), "category": str(r.get("category") or "")}
    s.setdefault(EMPTY, {"name": EMPTY, "value": 0.0, "unit": "kN/m2", "group": ""})
    l.setdefault(EMPTY, {"name": EMPTY, "udl": 0.0, "point": 0.0, "category": ""})
    return Database(s, l)


def load_database(path: str | None = None) -> Database:
    raw = json.loads(Path(path or DB_PATH).read_text(encoding="utf-8"))
    return database_from_records(raw["sdl"], raw["ll"])


def layer_load(db: Database, material: str, thickness_mm: float = 0.0) -> float:
    """Load of one layer in kN/m2. Unknown/empty material -> 0."""
    if not material or material == EMPTY or material not in db.sdl:
        return 0.0
    item = db.sdl[material]
    if item["unit"] == "kN/m2":
        return item["value"]
    return item["value"] * (thickness_mm or 0.0) / 1000.0


@dataclass
class Layer:
    material: str = EMPTY
    thickness_mm: float = 0.0

    def load(self, db: Database) -> float:
        return layer_load(db, self.material, self.thickness_mm)


@dataclass
class ImposedItem:
    name: str = EMPTY

    def values(self, db: Database) -> tuple[float, float]:
        item = db.ll.get(self.name)
        return (item["udl"], item["point"]) if item else (0.0, 0.0)


@dataclass
class FloorBuildUp:
    name: str = "Floor"
    layers: list[Layer] = field(default_factory=list)
    imposed: list[ImposedItem] = field(default_factory=list)

    def sdl_total(self, db: Database) -> float:
        return sum(l.load(db) for l in self.layers)

    def ll_udl_total(self, db: Database) -> float:
        return sum(i.values(db)[0] for i in self.imposed)

    def ll_point_total(self, db: Database) -> float:
        return sum(i.values(db)[1] for i in self.imposed)


@dataclass
class WallBuildUp:
    name: str = "Wall"
    height_m: float = 3.0
    layers: list[Layer] = field(default_factory=list)

    def area_load(self, db: Database) -> float:
        return sum(l.load(db) for l in self.layers)

    def line_load(self, db: Database) -> float:
        return sum(l.load(db) * self.height_m for l in self.layers)
