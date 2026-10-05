"""Reusable visual pieces: run lanes, glow dots, quote cards, packets, counters,
the six problem cards and their icons, timer rings, clocks and wiki pages."""
import numpy as np
from manim import *  # noqa: F401,F403

from .style import Text, MarkupText  # oversampled text (see style.py)
from .style import (BG, INK, INK_2, DIM, FAINT, FAINTER, CARD, RUN, PROBLEMS, C_POOL, C_TIME,
                    C_CHAN, C_MORT, C_TRUST, C_DISC, C_REWARD, SERIF, MONO, tx, mono, mono_para,
                    para, smallcaps)


# ---------------------------------------------------------------- glow
def glow_dot(point=ORIGIN, color=RUN, radius=0.07, glow=0.32, layers=8, core_opacity=1.0):
    """A soft glowing dot: the standard mark for one agent run."""
    g = VGroup()
    for i in range(layers, 0, -1):
        r = radius + glow * (i / layers) ** 1.6
        g.add(Circle(radius=r, stroke_width=0, fill_color=color,
                     fill_opacity=0.12 * (1 - i / (layers + 1)) ** 1.5))
    g.add(Circle(radius=radius, stroke_width=0, fill_color=color, fill_opacity=core_opacity))
    g.move_to(point)
    return g


# ---------------------------------------------------------------- run lanes
class RunLanes(VGroup):
    """Parallel runs of one timed quiz, drawn against shared (real) time.

    Every lane is one run. Its rounds R1..Rn sit at the same spacing, but each
    lane starts at a different shared time, so the lanes are staggered: the
    leftmost lane reaches every round first (the scout). A vertical `now` line
    swept left to right shows who has seen what.

        lanes = RunLanes(["Feb23", "Nov01", "Dec17"], starts=[-4.6, -3.3, -2.4])
        lanes.tick(i, k)       # round-k marker of lane i (k = 0 is R1)
        lanes.tick_x(i, k)     # its x coordinate
        lanes.y(i)             # lane i's y coordinate
        lanes.point(i, x)      # a point on lane i at x
    """

    def __init__(self, names, starts, n_rounds=5, spacing=1.7, y_top=1.6, gap=0.85,
                 x_label=-6.3, x_end=6.4, color=FAINT, label_size=20, tick_r=0.075,
                 round_labels=True, **kw):
        super().__init__(**kw)
        self.names, self.starts, self.n_rounds, self.spacing = list(names), list(starts), n_rounds, spacing
        self.ys = [y_top - i * gap for i in range(len(names))]
        self.lines, self.labels, self.ticks, self.rlabels = VGroup(), VGroup(), [], VGroup()
        for i, (nm, x0) in enumerate(zip(names, starts)):
            y = self.ys[i]
            ln = Line([x_label + 1.0, y, 0], [x_end, y, 0], stroke_width=2, color=color)
            lab = mono(nm, size=label_size, color=INK_2).move_to([x_label + 0.35, y, 0])
            row = VGroup()
            for k in range(n_rounds):
                x = x0 + k * spacing
                d = Circle(radius=tick_r, stroke_width=2, stroke_color=DIM, fill_color=BG, fill_opacity=1)
                d.move_to([x, y, 0])
                row.add(d)
            self.lines.add(ln)
            self.labels.add(lab)
            self.ticks.append(row)
        if round_labels:
            for k in range(n_rounds):
                t = tx(f"R{k + 1}", size=20, color=DIM, italic=True)
                t.next_to(self.ticks[0][k], UP, buff=0.14)
                self.rlabels.add(t)
        self.add(self.lines, self.labels, *self.ticks, self.rlabels)

    def tick(self, i, k):
        return self.ticks[i][k]

    def tick_x(self, i, k):
        return self.starts[i] + k * self.spacing

    def y(self, i):
        return self.ys[i]

    def point(self, i, x):
        return np.array([x, self.ys[i], 0.0])

    def seen(self, i, k, color=INK):
        """Animation: lane i's round-k marker lights up (that run saw round k)."""
        d = self.ticks[i][k]
        return d.animate.set_fill(color, 1).set_stroke(color)


def now_line(x=-6.0, y0=-2.6, y1=2.4, color=C_TIME, label="now"):
    ln = DashedLine([x, y0, 0], [x, y1, 0], dash_length=0.08, stroke_width=2, color=color)
    lab = tx(label, size=20, color=color, italic=True).next_to(ln, UP, buff=0.08)
    g = VGroup(ln, lab)
    return g


# ---------------------------------------------------------------- cards
def quote_card(text, sig=None, color=C_POOL, width=46, size=19, header=None, pad=0.28):
    """A verbatim wiki message on a dark card with a coloured accent bar.

    Returns VGroup(card_bg, bar, body[, sig][, header]) with attributes .body, .sig, .bg.
    """
    body = mono_para(text, width=width, size=size, color=INK)
    parts = [body]
    s = None
    if sig:
        s = tx("— " + sig, size=size + 1, color=DIM, italic=True)
        s.next_to(body, DOWN, buff=0.18, aligned_edge=RIGHT)
        parts.append(s)
    inner = VGroup(*parts)
    bg = RoundedRectangle(corner_radius=0.08, width=inner.width + 2 * pad + 0.08,
                          height=inner.height + 2 * pad, stroke_width=1.2, stroke_color=FAINT,
                          fill_color=CARD, fill_opacity=0.96)
    bg.move_to(inner).shift(LEFT * 0.04)
    bar = Rectangle(width=0.06, height=bg.height - 0.02, stroke_width=0, fill_color=color, fill_opacity=1)
    bar.move_to(bg).align_to(bg, LEFT).shift(RIGHT * 0.01)
    g = VGroup(bg, bar, inner)
    h = None
    if header:
        h = smallcaps(header, size=15, color=DIM, spacing=1200)
        h.next_to(bg, UP, buff=0.12, aligned_edge=LEFT)
        g.add(h)
    g.bg, g.bar, g.body, g.sig, g.header = bg, bar, body, s, h
    return g


def packet(label, color=C_POOL, size=18, pad=0.12):
    """A small message in flight: a rounded tag with a mono label."""
    t = mono(label, size=size, color=BG, weight=BOLD)
    r = RoundedRectangle(corner_radius=0.06, width=t.width + 2 * pad, height=t.height + 1.4 * pad,
                         stroke_width=0, fill_color=color, fill_opacity=1)
    t.move_to(r)
    g = VGroup(r, t)
    g.box, g.label = r, t
    return g


def counter_box(value=0, label="counter", color=C_MORT, size=44):
    """An off-wiki counter: a number that persists after the run that set it."""
    n = Integer(value, font_size=size, color=INK)
    n.set_stroke(width=0)
    box = RoundedRectangle(corner_radius=0.1, width=1.25, height=1.0, stroke_width=2,
                           stroke_color=color, fill_color=CARD, fill_opacity=1)
    n.move_to(box)
    lab = smallcaps(label, size=14, color=color, spacing=1000).next_to(box, DOWN, buff=0.1)
    g = VGroup(box, n, lab)
    g.box, g.num, g.lab = box, n, lab
    return g


def wiki_page(title, lines, width=4.4, size=16, title_size=24):
    """A wiki page card: serif title, rule, mono lines."""
    t = tx(title, size=title_size, color=INK)
    body = VGroup(*[mono(l, size=size, color=INK_2) for l in lines]).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
    body.next_to(t, DOWN, buff=0.3, aligned_edge=LEFT)
    inner = VGroup(t, body)
    w = max(width, inner.width + 0.6)
    bg = RoundedRectangle(corner_radius=0.06, width=w, height=inner.height + 0.6, stroke_width=1.2,
                          stroke_color=FAINT, fill_color=CARD, fill_opacity=0.97)
    bg.move_to(inner)
    inner.align_to(bg, LEFT).shift(RIGHT * 0.3)
    r = Line(bg.get_left() + RIGHT * 0.3, bg.get_right() + LEFT * 0.3, stroke_width=1, color=FAINT)
    r.next_to(t, DOWN, buff=0.13).align_to(bg, LEFT).shift(RIGHT * 0.3)
    g = VGroup(bg, r, t, body)
    g.bg, g.title, g.body = bg, t, body
    return g


# ---------------------------------------------------------------- the six problems
def problem_icon(n, color=None, s=0.5):
    """Small line icon for problem n (1..6), drawn in a box of side ~2*s."""
    c = color or PROBLEMS[n - 1][3]
    sw = 3
    if n == 1:      # pooling: three dots feeding one
        pts = [UP * s * 0.8 + LEFT * s, LEFT * s, DOWN * s * 0.8 + LEFT * s]
        hub = RIGHT * s * 0.7
        g = VGroup(*[Line(p, hub, stroke_width=sw - 1, color=c) for p in pts],
                   *[Dot(p, radius=s * 0.13, color=c) for p in pts], Dot(hub, radius=s * 0.22, color=c))
    elif n == 2:    # common time: clock
        circ = Circle(radius=s * 0.85, stroke_width=sw, color=c)
        g = VGroup(circ, Line(ORIGIN, UP * s * 0.6, stroke_width=sw, color=c),
                   Line(ORIGIN, RIGHT * s * 0.42, stroke_width=sw, color=c), Dot(radius=s * 0.08, color=c))
    elif n == 3:    # compression: wide message narrowing to a token
        top = Line(LEFT * s + UP * s * 0.7, RIGHT * s * 0.25 + UP * s * 0.18, stroke_width=sw, color=c)
        bot = Line(LEFT * s + DOWN * s * 0.7, RIGHT * s * 0.25 + DOWN * s * 0.18, stroke_width=sw, color=c)
        tok = RoundedRectangle(corner_radius=0.03, width=s * 0.55, height=s * 0.36, stroke_width=0,
                               fill_color=c, fill_opacity=1).move_to(RIGHT * s * 0.62)
        g = VGroup(top, bot, tok)
    elif n == 4:    # mortality: a timeline that ends, a signal leaping out before the end
        line = Line(LEFT * s, RIGHT * s * 0.25, stroke_width=sw, color=c)
        wall = Line(RIGHT * s * 0.25 + UP * s * 0.5, RIGHT * s * 0.25 + DOWN * s * 0.5, stroke_width=sw, color=c)
        arc = ArcBetweenPoints(LEFT * s * 0.25, RIGHT * s + UP * s * 0.55, angle=-PI / 2.2, stroke_width=sw - 1, color=c)
        tip = Dot(RIGHT * s + UP * s * 0.55, radius=s * 0.11, color=c)
        g = VGroup(line, wall, arc, tip)
    elif n == 5:    # trust: an eye (read, don't touch)
        top = ArcBetweenPoints(LEFT * s, RIGHT * s, angle=-PI / 2.4, stroke_width=sw, color=c)
        bot = ArcBetweenPoints(LEFT * s, RIGHT * s, angle=PI / 2.4, stroke_width=sw, color=c)
        g = VGroup(top, bot, Circle(radius=s * 0.26, stroke_width=sw, color=c), Dot(radius=s * 0.1, color=c))
    else:           # discovery: magnifier
        lens = Circle(radius=s * 0.5, stroke_width=sw, color=c).shift(UL * s * 0.2)
        handle = Line(lens.get_center() + DR * s * 0.36, DR * s * 0.75, stroke_width=sw + 1, color=c)
        g = VGroup(lens, handle)
    return g


def problem_card(n, width=4.0, height=1.55, filled=True):
    """Card for problem n: number, icon, short name and question."""
    num, name, q, c = PROBLEMS[n - 1]
    bg = RoundedRectangle(corner_radius=0.1, width=width, height=height, stroke_width=1.5,
                          stroke_color=c if filled else FAINT, fill_color=CARD, fill_opacity=1)
    ic = problem_icon(n, c if filled else FAINT, s=0.3).move_to(bg.get_left() + RIGHT * 0.55 + UP * 0.12)
    numt = tx(str(num), size=22, color=c if filled else DIM).move_to(bg.get_left() + RIGHT * 0.55 + DOWN * 0.45)
    nm = tx(name, size=30, color=INK if filled else DIM)
    qq = tx(q, size=20, color=DIM, italic=True)
    txt = VGroup(nm, qq).arrange(DOWN, aligned_edge=LEFT, buff=0.12)
    if txt.width > width - 1.3:
        txt.scale_to_fit_width(width - 1.3)
    txt.next_to(bg.get_left(), RIGHT, buff=1.05)
    g = VGroup(bg, ic, numt, txt)
    g.bg, g.icon, g.num, g.name, g.q, g.pcolor = bg, ic, numt, nm, qq, c
    return g


def blank_card(n, width=4.0, height=1.55):
    """Placeholder for problem n: outline, number and a question mark."""
    c = PROBLEMS[n - 1][3]
    bg = RoundedRectangle(corner_radius=0.1, width=width, height=height, stroke_width=1.5,
                          stroke_color=FAINT, fill_color=CARD, fill_opacity=1)
    numt = tx(str(n), size=26, color=c).move_to(bg.get_left() + RIGHT * 0.5)
    qm = tx("?", size=40, color=FAINT).move_to(bg)
    g = VGroup(bg, numt, qm)
    g.bg = bg
    return g


def problem_grid(cards=None, cols=3, buff_x=0.35, buff_y=0.35):
    """3 x 2 grid of the six problem cards, in reading order."""
    cards = cards if cards is not None else [problem_card(n) for n in range(1, 7)]
    g = VGroup(*cards).arrange_in_grid(rows=2, cols=cols, buff=(buff_x, buff_y))
    return g


def problem_header(n, size=26):
    """Top-left label used throughout problem n's scene: '1  Pooling · Who knows what?'"""
    num, name, q, c = PROBLEMS[n - 1]
    circ = Circle(radius=0.24, stroke_width=2, color=c)
    nt = tx(str(num), size=size - 2, color=c).move_to(circ)
    nm = tx(name, size=size, color=INK)
    dot = tx("·", size=size, color=DIM)
    qq = tx(q, size=size - 4, color=DIM, italic=True)
    g = VGroup(VGroup(circ, nt), nm, dot, qq).arrange(RIGHT, buff=0.2)
    qq.align_to(nm, DOWN)
    g.to_corner(UL, buff=0.45)
    return g


# ---------------------------------------------------------------- time
def timer_ring(radius=0.7, color=C_CHAN, stroke=8):
    """A full ring to be depleted with ValueTracker; returns (ring_group, tracker).

        ring, frac = timer_ring()
        self.play(frac.animate.set_value(0), run_time=3, rate_func=linear)
    """
    frac = ValueTracker(1.0)
    base = Circle(radius=radius, stroke_width=stroke, color=FAINT)
    arc = always_redraw(lambda: Arc(radius=radius, start_angle=PI / 2, angle=-TAU * max(frac.get_value(), 1e-4),
                                    stroke_width=stroke, color=color).move_arc_center_to(base.get_center()))
    g = VGroup(base, arc)
    return g, frac


def clock_face(radius=0.6, color=C_TIME, hand_angle=PI / 2, stroke=3):
    circ = Circle(radius=radius, stroke_width=stroke, color=color)
    ticks = VGroup(*[Line(circ.get_center() + radius * 0.82 * np.array([np.cos(a), np.sin(a), 0]),
                          circ.get_center() + radius * 0.95 * np.array([np.cos(a), np.sin(a), 0]),
                          stroke_width=stroke - 1, color=color) for a in np.linspace(0, TAU, 12, endpoint=False)])
    hand = Line(ORIGIN, radius * 0.7 * np.array([np.cos(hand_angle), np.sin(hand_angle), 0]),
                stroke_width=stroke, color=color)
    g = VGroup(circ, ticks, hand, Dot(radius=0.04, color=color))
    g.hand = hand
    return g


def number_line_clock(label, x0=-5.0, x1=5.0, y=0, color=C_TIME, ticks=None, size=20):
    """A labelled horizontal time axis with tick labels, e.g. task clock vs shared clock."""
    ln = Line([x0, y, 0], [x1, y, 0], stroke_width=2, color=color)
    lab = tx(label, size=size + 2, color=color, italic=True).next_to(ln, LEFT, buff=0.25)
    tks = VGroup()
    for x, t in (ticks or []):
        tk = Line([x, y - 0.08, 0], [x, y + 0.08, 0], stroke_width=2, color=color)
        tt = mono(t, size=size - 4, color=DIM).next_to(tk, DOWN, buff=0.1)
        tks.add(VGroup(tk, tt))
    g = VGroup(ln, lab, tks)
    g.line, g.label, g.ticks = ln, lab, tks
    return g


# ---------------------------------------------------------------- highlighting text
def find_chars(text_mob, raw, phrase, occurrence=1):
    """Glyphs of `phrase` inside a Text built from `raw` (e.g. quote_card(...).body).

    manim's Text has one submobject per non-whitespace character, so we match on the
    whitespace-stripped string. Works across line wraps.
    """
    flat = "".join(raw.split())
    target = "".join(phrase.split())
    start = -1
    for _ in range(occurrence):
        start = flat.find(target, start + 1)
        if start < 0:
            raise ValueError(f"phrase not found: {phrase!r}")
    glyphs = text_mob.submobjects
    if len(glyphs) != len(flat):
        # fall back to the deepest flattening (MarkupText may nest)
        glyphs = [m for m in text_mob.family_members_with_points()]
    return VGroup(*glyphs[start:start + len(target)])


def underline(mob, color=C_TIME, buff=0.06, stroke=3):
    """Underline a glyph group on its baseline, one segment per wrapped line.

    Rows are grouped by glyph centre; the baseline is the median glyph bottom, so
    descenders (g, p, y) and hyphens don't break the line into steps."""
    gl = [g for g in mob]
    hmax = max(g.height for g in gl)
    rows = []
    for g in sorted(gl, key=lambda g: -g.get_center()[1]):
        if rows and abs(g.get_center()[1] - np.mean([h.get_center()[1] for h in rows[-1]])) <= 0.6 * hmax:
            rows[-1].append(g)
        else:
            rows.append([g])
    lines = VGroup()
    for row in rows:
        y = float(np.median([g.get_bottom()[1] for g in row])) - buff
        x0 = min(g.get_left()[0] for g in row)
        x1 = max(g.get_right()[0] for g in row)
        lines.add(Line([x0, y, 0], [x1, y, 0], stroke_width=stroke, color=color))
    return lines


def highlight_box(mob, color=C_CHAN, buff=0.06, stroke=2.5, corner_radius=0.05):
    return SurroundingRectangle(mob, color=color, buff=buff, stroke_width=stroke, corner_radius=corner_radius)
