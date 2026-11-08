"""
Design tokens: the single source of truth for every color, size and radius.

The same values feed three places so the chrome and the charts never drift:
  * CSS custom properties (css_variables) used by ui/theme.css
  * .streamlit/config.toml (run `python -m ui.tokens` after editing)
  * Plotly layouts (ui/charts.py)

Light and dark are both designed, not auto-inverted. In CSS each variable is a
light-dark() pair; Streamlit sets `color-scheme` on .stApp, so the browser picks
the right side whenever the user switches theme.
"""

from __future__ import annotations

from pathlib import Path

# ----------------------------------------------------------
# Neutrals, accent and status
# ----------------------------------------------------------

LIGHT = {
    "canvas": "#FAFAFA",
    "surface": "#FFFFFF",
    "surface_2": "#F4F4F6",
    "surface_hover": "#F0F0F3",
    "border": "#E4E4E9",
    "border_strong": "#D4D4DB",
    "text": "#18181B",
    "text_2": "#52525B",
    "text_3": "#71717A",
    "grid": "#EDEDF0",
    "accent": "#4F46E5",
    "accent_text": "#4338CA",
    "on_accent": "#FFFFFF",
    "accent_soft": "rgba(79, 70, 229, 0.08)",
    "good": "#15803D",
    "good_soft": "rgba(21, 128, 61, 0.09)",
    "warn": "#B45309",
    "warn_soft": "rgba(180, 83, 9, 0.09)",
    "bad": "#DC2626",
    "bad_soft": "rgba(220, 38, 38, 0.08)",
    "neutral_soft": "rgba(113, 113, 122, 0.10)",
    "shadow": "0 1px 2px rgba(16, 16, 24, 0.04), 0 1px 1px rgba(16, 16, 24, 0.02)",
    "sidebar": "#FFFFFF",
}

DARK = {
    "canvas": "#0B0B0F",
    "surface": "#141418",
    "surface_2": "#1B1B21",
    "surface_hover": "#202027",
    "border": "#26262C",
    "border_strong": "#33333B",
    "text": "#EDEDF0",
    "text_2": "#A1A1AA",
    "text_3": "#8B8B94",
    "grid": "#222228",
    "accent": "#818CF8",
    "accent_text": "#A5B4FC",
    "on_accent": "#0B0B0F",
    "accent_soft": "rgba(129, 140, 248, 0.12)",
    "good": "#4ADE80",
    "good_soft": "rgba(74, 222, 128, 0.10)",
    "warn": "#FBBF24",
    "warn_soft": "rgba(251, 191, 36, 0.10)",
    "bad": "#F87171",
    "bad_soft": "rgba(248, 113, 113, 0.10)",
    "neutral_soft": "rgba(161, 161, 170, 0.12)",
    "shadow": "0 1px 2px rgba(0, 0, 0, 0.40)",
    "sidebar": "#111115",
}

# ----------------------------------------------------------
# Data colors (validated with the dataviz palette validator:
# adjacent CVD dE >= 8.4, normal-vision dE >= 19.3 in both modes)
# Fixed order. Never cycled; past 8 series fold into "Other".
# ----------------------------------------------------------

SERIES = {
    "light": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "dark": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
}

OTHER_COLOR = {"light": "#A1A1AA", "dark": "#52525B"}

# Single-hue blue ramp for magnitude (heatmaps, choropleths), light -> dark.
SEQUENTIAL = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
              "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

# Diverging: orange (negative) <- gray -> blue (positive)
DIVERGING = {
    "light": ["#c2410c", "#eb6834", "#f4a582", "#e4e4e7", "#86b6ef", "#3987e5", "#1c5cab"],
    "dark": ["#ea580c", "#d95926", "#9a4a2c", "#3f3f46", "#2a5a96", "#3987e5", "#86b6ef"],
}

# ----------------------------------------------------------
# Type, spacing, shape
# ----------------------------------------------------------

FONT_FAMILY = "Inter, 'Source Sans', system-ui, sans-serif"
FONT_SIZES = {"xs": 12, "sm": 13, "md": 14, "lg": 16, "xl": 20, "2xl": 28, "3xl": 36}
RADIUS = {"card": 12, "control": 8, "pill": 999}
SPACE = [0, 4, 8, 12, 16, 24, 32, 48]


def tokens_for(mode: str) -> dict:
    """Token dict for 'light' or 'dark' (anything else falls back to light)."""
    return DARK if mode == "dark" else LIGHT


def css_variables() -> str:
    """CSS custom properties scoped to .stApp, each a light-dark() pair."""
    lines = []
    for name in LIGHT:
        light, dark = LIGHT[name], DARK[name]
        css_name = "--is-" + name.replace("_", "-")
        if name == "shadow":
            # light-dark() only accepts colors, so shadows switch via a nested rule.
            continue
        lines.append(f"  {css_name}: light-dark({light}, {dark});")
    for i, (light, dark) in enumerate(zip(SERIES["light"], SERIES["dark"]), start=1):
        lines.append(f"  --is-series-{i}: light-dark({light}, {dark});")
    lines.append(f"  --is-font: {FONT_FAMILY};")
    lines.append(f"  --is-radius-card: {RADIUS['card']}px;")
    lines.append(f"  --is-radius-control: {RADIUS['control']}px;")
    # One shadow for both modes: barely visible on light, invisible-but-harmless on dark.
    lines.append(f"  --is-shadow: {LIGHT['shadow']};")

    return ".stApp {\n" + "\n".join(lines) + "\n}\n"


# ----------------------------------------------------------
# config.toml generator
# ----------------------------------------------------------

def _toml_list(values) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


def config_toml() -> str:
    font = "Inter:https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    return f"""# Generated from ui/tokens.py — run `python -m ui.tokens` after changing tokens.

[server]
headless = true
runOnSave = false

[client]
toolbarMode = "minimal"

[theme]
font = "{font}"
headingFont = "{font}"
codeFont = "monospace"
baseFontSize = {FONT_SIZES['md']}
baseRadius = "{RADIUS['card'] - 2}px"
buttonRadius = "{RADIUS['control']}px"
showWidgetBorder = true
showSidebarBorder = true
headingFontWeights = [600, 600, 600, 600, 600, 600]
headingFontSizes = ["28px", "20px", "16px", "14px", "13px", "12px"]
chartCategoricalColors = {_toml_list(SERIES['light'])}
chartSequentialColors = {_toml_list(SEQUENTIAL[:10])}

[theme.light]
primaryColor = "{LIGHT['accent']}"
backgroundColor = "{LIGHT['canvas']}"
secondaryBackgroundColor = "{LIGHT['surface_2']}"
textColor = "{LIGHT['text']}"
borderColor = "{LIGHT['border']}"
linkColor = "{LIGHT['accent']}"

[theme.light.sidebar]
backgroundColor = "{LIGHT['sidebar']}"
secondaryBackgroundColor = "{LIGHT['surface_2']}"
borderColor = "{LIGHT['border']}"

[theme.dark]
primaryColor = "{DARK['accent']}"
backgroundColor = "{DARK['canvas']}"
secondaryBackgroundColor = "{DARK['surface_2']}"
textColor = "{DARK['text']}"
borderColor = "{DARK['border']}"
linkColor = "{DARK['accent_text']}"

[theme.dark.sidebar]
backgroundColor = "{DARK['sidebar']}"
secondaryBackgroundColor = "{DARK['surface_2']}"
borderColor = "{DARK['border']}"
"""


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / ".streamlit" / "config.toml"
    target.parent.mkdir(exist_ok=True)
    target.write_text(config_toml(), encoding="utf-8")
    print(f"Wrote {target}")
