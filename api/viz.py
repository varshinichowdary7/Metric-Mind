"""
Chart selection from a semantic-layer annotation.

The semantic layer already tells us the *shape* of every result: which members
are dimensions, which are time dimensions (and at what granularity), and which
are measures (with a type — currency / percent / number). That annotation is
enough to pick the right chart deterministically, the same way a BI tool does,
without the LLM guessing or the UI hand-coding a chart per question.

`recommend_chart` is a pure function of (annotation, data): identical input ->
identical chart spec, so it is unit-testable alongside the rest of the
determinism suite. The spec it returns is renderer-agnostic (the web UI maps it
onto ECharts), and it only ever *names* members the annotation already exposes —
it never invents fields.

Chart vocabulary returned in `chart`:
  * "line"  — a trend over a time grouping.
  * "bar"   — a comparison across one categorical breakdown.
  * "pie"   — a part-to-whole composition (small, non-negative, additive).
  * "kpi"   — a single aggregate value; show the headline number, not a chart.
  * "none"  — no clean chart for this shape; fall back to the data table.
"""

from __future__ import annotations

# A pie only reads well for a handful of slices; beyond this, use a bar.
PIE_MAX_SLICES = 6
# Additive measures can compose a whole; a percentage cannot be summed into one.
ADDITIVE_TYPES = {"currency", "number"}


def recommend_chart(annotation: dict | None, data: list | None) -> dict:
    """Pick a chart for a governed query result. Pure and deterministic."""
    annotation = annotation or {}
    rows = data or []

    measures = list(annotation.get("measures", {}).keys())
    dims = list(annotation.get("dimensions", {}).keys())
    time_dims = annotation.get("timeDimensions", {})
    # Only a time dimension with a granularity becomes a grouping column; one
    # without is filter-only (its dateRange narrows the WHERE), so it is not an axis.
    time_cols = [name for name, spec in time_dims.items() if spec.get("granularity")]

    if not measures:
        return {"chart": "none", "reason": "no measures to plot"}

    n_cat = len(dims) + len(time_cols)

    # A single aggregate row with no breakdown is a headline number, not a chart.
    if n_cat == 0:
        return {"chart": "kpi", "series": measures, "reason": "single aggregate value"}

    # Trend over time.
    if time_cols:
        x = time_cols[0]
        if len(dims) == 0:
            return {
                "chart": "line",
                "x": x,
                "xType": "time",
                "series": measures,
                "reason": "time series of " + ", ".join(measures),
            }
        # Time split by one categorical breakdown and one measure -> multi-series line.
        if len(dims) == 1 and len(measures) == 1:
            return {
                "chart": "line",
                "x": x,
                "xType": "time",
                "seriesBy": dims[0],
                "measure": measures[0],
                "reason": f"time series of {measures[0]} split by {dims[0]}",
            }
        return {"chart": "none", "reason": "too many dimensions to chart over time"}

    # One categorical breakdown, no time.
    if len(dims) == 1:
        x = dims[0]
        measure = measures[0]
        mtype = annotation["measures"][measure].get("type")
        numeric = [r.get(measure) for r in rows if isinstance(r.get(measure), (int, float))]
        composition = (
            len(measures) == 1
            and mtype in ADDITIVE_TYPES
            and 2 <= len(rows) <= PIE_MAX_SLICES
            and all(v >= 0 for v in numeric)  # a negative slice has no meaning in a pie
        )
        if composition:
            return {
                "chart": "pie",
                "x": x,
                "measure": measure,
                "reason": f"composition of {measure} across {x}",
            }
        return {
            "chart": "bar",
            "x": x,
            "xType": "category",
            "series": measures,
            "reason": f"comparison across {x}",
        }

    return {"chart": "none", "reason": "no clean chart for this shape"}
