"""
Cube.dev parity (Phase 11).

The README promises the Cube model under cube/ is a *drop-in swap* for the local
Python semantic layer: the same member names, so the agent's governed queries run
unchanged against Cube Cloud in production. This test enforces that promise —
every measure, dimension, and time dimension the Python layer exposes to the
agent must exist, by the same `cube.member` name, in the Cube YAML (and a time
dimension must be typed `time` on both sides).

Without this, the two definitions could silently drift and the "swap" claim would
quietly become false.
"""

import glob
import os

import yaml

from semantic.model import DIMENSIONS, MEASURES, TIME_DIMENSIONS

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUBE_GLOB = os.path.join(REPO, "cube", "model", "cubes", "*.yml")


def _load_cube_model() -> dict:
    """cube name -> {'measures': set[str], 'dimensions': {name: type}}."""
    model: dict = {}
    for path in glob.glob(CUBE_GLOB):
        with open(path, encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)
        for cube in doc.get("cubes", []):
            model[cube["name"]] = {
                "measures": {m["name"] for m in cube.get("measures", [])},
                "dimensions": {d["name"]: d.get("type") for d in cube.get("dimensions", [])},
            }
    return model


CUBE = _load_cube_model()


def _split(member: str) -> tuple[str, str]:
    cube, _, name = member.partition(".")
    return cube, name


def test_cube_model_loaded():
    # Guard: if the glob or YAML parsing breaks, fail loudly instead of silently
    # asserting nothing in the parity tests below.
    assert {"sales", "order_costs", "date", "geography", "product"} <= set(CUBE)


def test_every_python_measure_exists_in_cube():
    for member in MEASURES:
        cube, name = _split(member)
        assert cube in CUBE, f"{member}: cube {cube!r} missing from the Cube model"
        assert name in CUBE[cube]["measures"], f"{member} is not defined as a Cube measure"


def test_every_python_dimension_exists_in_cube():
    for member in DIMENSIONS:
        cube, name = _split(member)
        assert cube in CUBE, f"{member}: cube {cube!r} missing from the Cube model"
        assert name in CUBE[cube]["dimensions"], f"{member} is not defined as a Cube dimension"


def test_every_python_time_dimension_is_a_cube_time_dimension():
    for member in TIME_DIMENSIONS:
        cube, name = _split(member)
        assert cube in CUBE, f"{member}: cube {cube!r} missing from the Cube model"
        assert CUBE[cube]["dimensions"].get(name) == "time", (
            f"{member} must be a `type: time` dimension in the Cube model"
        )
