"""Small deterministic, dependency-free SVG charts for report artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from html import escape
from math import isfinite
from typing import Literal

from fathomark_reporting.model import ReportModel

Theme = Literal["light", "dark", "print"]

_THEMES: dict[Theme, dict[str, str]] = {
    "light": {
        "background": "#ffffff",
        "foreground": "#17212b",
        "muted": "#d9e2ec",
        "accent": "#2f6f73",
        "positive": "#2f855a",
        "negative": "#c05621",
    },
    "dark": {
        "background": "#17212b",
        "foreground": "#f4f7f9",
        "muted": "#52616b",
        "accent": "#80cbc4",
        "positive": "#68d391",
        "negative": "#f6ad55",
    },
    "print": {
        "background": "#ffffff",
        "foreground": "#000000",
        "muted": "#b0b0b0",
        "accent": "#333333",
        "positive": "#000000",
        "negative": "#555555",
    },
}


def _colors(theme: Theme) -> dict[str, str]:
    try:
        return _THEMES[theme]
    except KeyError as exc:
        raise ValueError(f"unknown chart theme: {theme}") from exc


def _svg_open(*, width: int, height: int, title: str, theme: Theme) -> list[str]:
    colors = _colors(theme)
    safe_title = escape(title, quote=True)
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{safe_title}">',
        f"<title>{safe_title}</title>",
        f'<rect width="100%" height="100%" fill="{colors["background"]}"/>',
    ]


def _svg_close(lines: list[str]) -> str:
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _text(value: object) -> str:
    return escape(str(value), quote=True)


def _number(value: float | None) -> str:
    if value is None:
        return "NR"
    if not isfinite(value):
        raise ValueError("chart values must be finite")
    return f"{value:g}"


def render_factor_chart(report: ReportModel, *, theme: Theme = "light") -> str:
    """Render factor scores on the 0–10 framework scale."""
    report.verify_integrity()
    colors = _colors(theme)
    factors = tuple(sorted(report.factors, key=lambda factor: factor.factor))
    width = 800
    height = max(100, 64 + len(factors) * 32)
    lines = _svg_open(
        width=width,
        height=height,
        title=f"{report.scope.symbol} factor scores",
        theme=theme,
    )
    for index, factor in enumerate(factors):
        y = 42 + index * 32
        bar_width = max(0.0, min(10.0, factor.proposed_score)) * 42
        lines.extend(
            [
                f'<text x="16" y="{y + 5}" fill="{colors["foreground"]}" font-size="14">{_text(factor.factor)}</text>',
                f'<rect x="230" y="{y - 10}" width="420" height="18" rx="3" fill="{colors["muted"]}"/>',
                f'<rect x="230" y="{y - 10}" width="{bar_width:g}" height="18" rx="3" fill="{colors["accent"]}"/>',
                f'<text x="670" y="{y + 5}" fill="{colors["foreground"]}" font-size="14">{_text(_number(factor.proposed_score))}/10</text>',
            ]
        )
    return _svg_close(lines)


def render_valuation_sensitivity(
    *,
    rows: Sequence[str],
    columns: Sequence[str],
    values: Sequence[Sequence[float | None]],
    theme: Theme = "light",
) -> str:
    """Render a rectangular valuation sensitivity matrix."""
    if len(rows) != len(values):
        raise ValueError("row count does not match values")
    if not rows or not columns:
        raise ValueError("sensitivity matrix requires rows and columns")
    if any(len(row) != len(columns) for row in values):
        raise ValueError("column count does not match values")
    colors = _colors(theme)
    width = 220 + len(columns) * 100
    height = 64 + len(rows) * 36
    lines = _svg_open(
        width=width,
        height=height,
        title="valuation sensitivity matrix",
        theme=theme,
    )
    for col_index, column in enumerate(columns):
        x = 220 + col_index * 100
        lines.append(
            f'<text x="{x + 50}" y="28" text-anchor="middle" fill="{colors["foreground"]}" font-size="13">{_text(column)}</text>'
        )
    for row_index, row_label in enumerate(rows):
        y = 46 + row_index * 36
        lines.append(
            f'<text x="16" y="{y + 22}" fill="{colors["foreground"]}" font-size="13">{_text(row_label)}</text>'
        )
        for col_index, value in enumerate(values[row_index]):
            x = 220 + col_index * 100
            lines.extend(
                [
                    f'<rect x="{x}" y="{y}" width="96" height="30" rx="3" fill="{colors["muted"]}"/>',
                    f'<text x="{x + 48}" y="{y + 20}" text-anchor="middle" fill="{colors["foreground"]}" font-size="13">{_text(_number(value))}</text>',
                ]
            )
    return _svg_close(lines)


def render_score_change(
    before: Mapping[str, float | None],
    after: Mapping[str, float | None],
    *,
    theme: Theme = "light",
) -> str:
    """Render deterministic score deltas, including added or missing factors."""
    colors = _colors(theme)
    factors = sorted(set(before) | set(after))
    width = 800
    height = max(100, 64 + len(factors) * 32)
    lines = _svg_open(
        width=width,
        height=height,
        title="factor score changes",
        theme=theme,
    )
    for index, factor in enumerate(factors):
        y = 42 + index * 32
        old = before.get(factor)
        new = after.get(factor)
        delta = None if old is None or new is None else new - old
        delta_label = "NR" if delta is None else f"{delta:+.1f}"
        color = colors["accent"] if delta is None or delta >= 0 else colors["negative"]
        lines.extend(
            [
                f'<text x="16" y="{y + 5}" fill="{colors["foreground"]}" font-size="14">{_text(factor)}</text>',
                f'<text x="300" y="{y + 5}" fill="{colors["foreground"]}" font-size="13">{_text(_number(old))} → {_text(_number(new))}</text>',
                f'<rect x="440" y="{y - 10}" width="{min(250, abs(delta or 0) * 25):g}" height="18" rx="3" fill="{color}"/>',
                f'<text x="710" y="{y + 5}" fill="{color}" font-size="14">{_text(delta_label)}</text>',
            ]
        )
    return _svg_close(lines)
