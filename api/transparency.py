"""
Transparency: a human-readable preview of the governed SQL (Phase 10).

The semantic layer compiles every agent query into parameterized SQL and returns
it as `{sql, params}` — the executable, injection-safe form, with `?`
placeholders bound separately. That is the source of truth, but `?` placeholders
are hard to read in a UI, so this module renders a *copy-pasteable preview* with
each bound value inlined as a properly-quoted literal.

The preview is display-only: it never runs. The agent still executes the
parameterized form; this just lets a human see exactly what the governed query
compiled to (the "View SQL" panel), reinforcing that nothing below the semantic
boundary is hidden.

Safe because `semantic.model.build_sql` only ever emits `?` as a bound-parameter
placeholder — it never puts a literal `?` inside the generated SQL — so counting
placeholders left-to-right matches `params` exactly.
"""

from __future__ import annotations

from datetime import date, datetime


def _literal(value) -> str:
    """Render one bound value as a SQL literal for display."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (date, datetime)):
        return "'" + value.isoformat() + "'"
    # Strings (and anything else) are single-quoted with quotes escaped.
    return "'" + str(value).replace("'", "''") + "'"


def inline_sql(sql: str, params=None) -> str:
    """Return `sql` with each `?` replaced by the next bound value as a literal.

    Extra placeholders (more `?` than params) are left as `?`; extra params are
    ignored. Purely for readable display — use the parameterized form to execute.
    """
    params = list(params or [])
    parts = (sql or "").split("?")
    out = [parts[0]]
    for i, part in enumerate(parts[1:]):
        out.append(_literal(params[i]) if i < len(params) else "?")
        out.append(part)
    return "".join(out)
