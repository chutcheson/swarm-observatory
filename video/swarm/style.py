"""Palette, fonts and text helpers shared by every scene (3b1b-inspired)."""
from pathlib import Path
import textwrap

import manimpango
from manim import *  # noqa: F401,F403
import manim as _manim

ROOT = Path(__file__).resolve().parents[1]
FONTS = ROOT / "fonts"
ASSETS = ROOT / "assets"
AUDIO = ROOT / "audio" / "beats"

for _f in sorted(FONTS.glob("*.[ot]tf")):
    manimpango.register_font(str(_f))

# Pango hints glyph advances at small sizes, which gives uneven letter spacing.
# Rendering at 4x and scaling down avoids it.
_OVERSAMPLE = 4


class Text(_manim.Text):
    def __init__(self, text, *args, font_size=DEFAULT_FONT_SIZE, **kw):
        super().__init__(text, *args, font_size=font_size * _OVERSAMPLE, **kw)
        self.scale(1 / _OVERSAMPLE)


class MarkupText(_manim.MarkupText):
    def __init__(self, text, *args, font_size=DEFAULT_FONT_SIZE, **kw):
        super().__init__(text, *args, font_size=font_size * _OVERSAMPLE, **kw)
        self.scale(1 / _OVERSAMPLE)


# Oversampled text overflows manim's layout boxes and wraps; the wrapped SVG is
# then cached under a key that ignores width. Give every layout room.
_orig_markup_text2svg = manimpango.MarkupUtils.text2svg


def _wide_markup_text2svg(*args, pango_width=None, **kw):
    args = list(args)
    if len(args) > 11:
        args[10] = args[10] * 16
        args[11] = args[11] * 4
    if pango_width:
        pango_width = pango_width * 16
    return _orig_markup_text2svg(*args, pango_width=pango_width, **kw)


manimpango.MarkupUtils.text2svg = staticmethod(_wide_markup_text2svg)
_orig_text2svg = manimpango.text2svg


def _wide_text2svg(settings, size, line_spacing, disable_liga, file_name, start_x, start_y,
                   width, height, text, *args, **kw):
    return _orig_text2svg(settings, size, line_spacing, disable_liga, file_name, start_x, start_y,
                          max(width, 1920) * 16, max(height, 1080) * 4, text, *args, **kw)


manimpango.text2svg = _wide_text2svg

# ---------------------------------------------------------------- palette
BG = "#0B0D10"
INK = "#ECE8DF"         # main text
INK_2 = "#C9C4B9"       # secondary text
DIM = "#8A9099"         # captions, labels, signatures
FAINT = "#2A2F37"       # grid lines, empty slots
FAINTER = "#181B20"
CARD = "#13161B"        # card fill

# the six meta-problems, in order (3b1b hues)
C_POOL = "#58C4DD"      # 1 pooling: who knows what?       (blue)
C_TIME = "#F4D35E"      # 2 common time: when is now?       (yellow)
C_CHAN = "#5CD0B3"      # 3 compression: a narrow channel   (teal)
C_MORT = "#FC6255"      # 4 mortality: speaking past the end (red)
C_TRUST = "#B189F5"     # 5 trust: keeping the channel clean (purple)
C_DISC = "#83C167"      # 6 discovery: finding the rules     (green)
C_REWARD = "#F0AC5F"    # reward, group, the hypothesis      (gold)

RUN = "#DCE6F0"         # an agent run (dot core)

PROBLEMS = [
    # (number, short name, question, color)
    (1, "Pooling", "Who knows what?", C_POOL),
    (2, "Common time", "When is now?", C_TIME),
    (3, "Compression", "What fits in thirteen seconds?", C_CHAN),
    (4, "Mortality", "What outlives the run?", C_MORT),
    (5, "Trust", "Is the signal real?", C_TRUST),
    (6, "Discovery", "What are the rules?", C_DISC),
]

# ---------------------------------------------------------------- fonts
SERIF = "CMU Serif"
SANS = "CMU Sans Serif"
MONO = "JetBrains Mono"


# ---------------------------------------------------------------- text
def tx(s, size=36, color=INK, italic=False, weight=NORMAL, font=SERIF, **kw):
    """Serif text (CMU Serif, the 3b1b face)."""
    return Text(s, font=font, font_size=size, color=color,
                slant=ITALIC if italic else NORMAL, weight=weight, **kw)


def mono(s, size=22, color=INK, weight=NORMAL, **kw):
    return Text(s, font=MONO, font_size=size, color=color, weight=weight, **kw)


def para(s, width=44, size=30, color=INK, italic=False, line_spacing=1.0, font=SERIF,
         weight=NORMAL):
    """Left-aligned paragraph, wrapped manually at `width` characters."""
    lines = []
    for block in s.split("\n"):
        lines += textwrap.wrap(block, width) or [" "]
    return Text("\n".join(lines), font=font, font_size=size, color=color,
                slant=ITALIC if italic else NORMAL, weight=weight,
                line_spacing=line_spacing * 0.9)


def mono_para(s, width=46, size=20, color=INK, line_spacing=1.0):
    lines = []
    for block in s.split("\n"):
        lines += textwrap.wrap(block, width, break_long_words=False, break_on_hyphens=False) or [" "]
    return Text("\n".join(lines), font=MONO, font_size=size, color=color,
                line_spacing=line_spacing * 0.9)


def smallcaps(s, size=20, color=DIM, spacing=1400, font=SERIF):
    s = s.replace("&", "&amp;")
    return MarkupText(f'<span letter_spacing="{spacing}">{s.upper()}</span>',
                      font=font, font_size=size, color=color)


def rule(width=4.0, color=FAINT, stroke=1.5):
    return Line(LEFT * width / 2, RIGHT * width / 2, stroke_width=stroke, color=color)
