"""Calculation logic for the Loadings Assessment sheet (no UI code here).

Rules reproduced from the Excel workbook:
  * Superdead layer: if the database unit is kN/m2 the value is used as is,
    if it is kN/m3 it is multiplied by the thickness [mm] / 1000.
  * Floor SDL total = sum of layers [kN/m2].
  * Imposed load: UDL [kN/m2] and point load [kN] looked up by category item;
    totals are the sums of the selected items.
  * Wall: each layer [kN/m2] x wall height [m] -> line load [kN/m];
    wall total = sum of line loads.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DB_PATH = Path(__file__).with_name("database.json")
EMPTY = "-"


@dataclass(frozen=True)
class Database:
    sdl: dict          # name -> {"value", "unit", "group"}
    ll: dict           # name -> {"udl", "point", "category"}
    wall_types: list
    area_types: list

    def sdl_value(self, name: str) -> tuple[float, str]:
        item = self.sdl[name]
        return item["value"], item["unit"]

    def ll_values(self, name: str) -> tuple[float, float]:
        item = self.ll[name]
        return item["udl"], item["point"]


@lru_cache(maxsize=1)
def load_database(path: str | None = None) -> Database:
    raw = json.loads(Path(path or DB_PATH).read_text(encoding="utf-8"))
    return Database(
        sdl={x["name"]: x for x in raw["sdl"]},
        ll={x["name"]: x for x in raw["ll"]},
        wall_types=raw["labels"]["wall_types"],
        area_types=raw["labels"]["area_types"],
    )


def layer_load(db: Database, material: str, thickness_mm: float = 0.0) -> float:
    """Load of one layer in kN/m2 (same IF/VLOOKUP logic as the sheet)."""
    if not material or material == EMPTY:
        return 0.0
    value, unit = db.sdl_value(material)
    if unit == "kN/m2":
        return value
    return value * (thickness_mm or 0.0) / 1000.0


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
        if not self.name or self.name == EMPTY:
            return 0.0, 0.0
        return db.ll_values(self.name)


@dataclass
class FloorBuildUp:
    title: str = "Typical Upper Floor"
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
    title: str = "Typical Cavity Wall"
    height_m: float = 3.0
    layers: list[Layer] = field(default_factory=list)

    def area_load(self, db: Database) -> float:
        """Sum of layers, kN/m2 of wall face."""
        return sum(l.load(db) for l in self.layers)

    def line_load(self, db: Database) -> float:
        """Line load at the base of the wall, kN/m."""
        return sum(l.load(db) * self.height_m for l in self.layers)
