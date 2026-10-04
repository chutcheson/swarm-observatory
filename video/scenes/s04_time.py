import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

# verbatim excerpts (research/quotes.md, s04)
FF_TASK = "~27m28 task time"            # ChatGPTAug11
FF_SHARED = "in ~1m27 shared"            # ChatGPTAug11
READING = "my task clock now 22:24:30 …\nWiki-local now ~00:14"   # AgentOpenResearch
NOSHOW = ("Status ping at wiki-local about 12:24:\n"
          "ResearchHelperMayEightD, has task-clock\n"
          "10:01:22 passed, and did state #3 arrive?\n"
          "Even a no-show update helps.")       # OpenAIResearcherAug08

X0, X1 = -4.3, 6.2
YT, YS = 1.25, -1.35          # task clock (top), shared clock (bottom)


def axis(label, y, color):
    ln = Line([X0, y, 0], [X1, y, 0], stroke_width=2, color=color)
    lab = tx(label, size=22, color=color, italic=True).next_to(ln, LEFT, buff=0.25)
    ticks = VGroup(*[Line([x, y - 0.07, 0], [x, y + 0.07, 0], stroke_width=1.5, color=color, stroke_opacity=0.6)
                     for x in np.arange(X0 + 0.35, X1, 0.7)])
    g = VGroup(ln, ticks, lab)
    g.line, g.lab, g.ticks = ln, lab, ticks
    return g


def end_dot(x, y, color):
    return Dot([x, y, 0], radius=0.045, color=color)


def mapping(pairs, color, opacity=0.75):
    """Reading lines: shared time s (bottom) -> task time t (top)."""
    g = VGroup()
    for s, t in pairs:
        g.add(VGroup(Line([s, YS, 0], [t, YT, 0], stroke_width=2, color=color, stroke_opacity=opacity),
                     end_dot(s, YS, color), end_dot(t, YT, color)))
    return g


def trace(scene, pairs, color, run_time, extra=()):
    """A run's two clocks advance together (glow dots on both axes); a reading line is left
    behind at each sample."""
    lines = mapping(pairs, color)
    for ln in lines:
        ln.set_opacity(0)
    s0, t0 = pairs[0]
    s1, t1 = pairs[-1]
    ds = glow_dot([s0, YS, 0], color=color, radius=0.06, glow=0.26)
    dt = glow_dot([t0, YT, 0], color=color, radius=0.06, glow=0.26)
    n = len(pairs) - 1
    state = {"shown": -1}

    def upd(_, a):
        k = int(a * n + 1e-6)
        while state["shown"] < k:
            state["shown"] += 1
            lines[state["shown"]][0].set_stroke(opacity=0.75)
            lines[state["shown"]][1:].set_opacity(1)
        ds.move_to([s0 + (s1 - s0) * a, YS, 0])
        dt.move_to([t0 + (t1 - t0) * a, YT, 0])

    scene.add(lines, ds, dt)
    scene.play(UpdateFromAlphaFunc(VGroup(), upd), *extra, run_time=run_time, rate_func=linear)
    return lines, ds, dt


def dimmed(dot, f):
    """Transform target for a glow dot with every layer's opacity scaled by f (set_opacity is absolute)."""
    t = dot.copy()
    for sm in t:
        sm.set_fill(opacity=sm.get_fill_opacity() * f)
    return Transform(dot, t)


def uline(glyphs, phrase, color, buff=0.07, stroke=2.5):
    """Underline a glyph group on its baseline, one segment per wrapped line (descenders ignored)."""
    chars = "".join(phrase.split())
    items = sorted(zip(glyphs, chars), key=lambda gc: -gc[0].get_center()[1])
    rows, cur = [], [items[0]]
    for gc in items[1:]:
        if abs(gc[0].get_center()[1] - cur[-1][0].get_center()[1]) > 0.18:
            rows.append(cur)
            cur = []
        cur.append(gc)
    rows.append(cur)
    lines = VGroup()
    for row in rows:
        base = [g.get_bottom()[1] for g, ch in row if ch not in "gjpqy,;()[]{}_-~"] or [g.get_bottom()[1] for g, _ in row]
        y = min(base) - buff
        x0 = min(g.get_left()[0] for g, _ in row)
        x1 = max(g.get_right()[0] for g, _ in row)
        lines.add(Line([x0, y, 0], [x1, y, 0], stroke_width=stroke, color=color))
    return lines


def baseline_shift(lab, raw, y):
    chars = "".join(raw.split())
    flat = [g for g, ch in zip(lab.submobjects, chars) if ch not in "gjpqy,;"]
    lab.shift(UP * (y - min(g.get_bottom()[1] for g in flat)))
    return lab


class S04Time(SwarmScene):
    def construct(self):
        hdr = problem_header(2)
        task = axis("task clock", YT, C_TIME)
        shared = axis("shared clock", YS, INK_2)
        # the two clock labels share a right edge
        shared.lab.align_to(task.lab, RIGHT)

        with self.beat("s04_b1") as b:
            self.play(Write(hdr), run_time=0.9)
            b.wait_word("Each", lead=0.45)
            self.play(Create(task.line), Create(shared.line), FadeIn(task.ticks), FadeIn(shared.ticks),
                      FadeIn(task.lab, shift=RIGHT * 0.15), FadeIn(shared.lab, shift=RIGHT * 0.15), run_time=0.7)

            # run A: both clocks tick at the same rate -> parallel reading lines
            labA = tx("run A", size=22, color=RUN, italic=True)
            baseline_shift(labA, "run A", YT + 0.3).set_x(-2.75)
            A_pairs = [(x, x) for x in np.linspace(-3.8, -1.7, 4)]
            linesA, dsA, dtA = trace(self, A_pairs, RUN, b.until_word("clock", lead=-0.25),
                                     extra=[FadeIn(labA, shift=DOWN * 0.1)])

            # run B: waits, and its task clock fast-forwards
            b.wait_word("waiting", lead=0.15)
            labB = tx("run B", size=22, color=C_TIME, italic=True)
            baseline_shift(labB, "run B", YT + 0.3).set_x(-0.8)
            B1 = [(x, x) for x in np.linspace(-1.1, -0.2, 3)]
            linesB1, dsB, dtB = trace(self, B1, C_TIME, b.until_word("fast", lead=0.05),
                                      extra=[FadeIn(labB, shift=DOWN * 0.1), dsA.animate.set_opacity(0.0),
                                             dtA.animate.set_opacity(0.0)])
            self.remove(dsB, dtB)
            B2 = [(-0.2 + 0.7 * i / 5, -0.2 + 6.0 * i / 5) for i in range(6)]
            linesB2, dsB, dtB = trace(self, B2, C_TIME, 0.85)

            # braces: a short span of shared time, a long span of task time
            brT = Brace(Line([-0.2, YT, 0], [5.8, YT, 0]), direction=UP, buff=0.14, color=C_TIME)
            brS = Brace(Line([-0.2, YS, 0], [0.5, YS, 0]), direction=DOWN, buff=0.14, color=INK_2)
            lT = mono(FF_TASK, size=20, color=C_TIME).next_to(brT, UP, buff=0.12)
            lS = mono(FF_SHARED, size=20, color=INK_2).next_to(brS, DOWN, buff=0.12)
            sig = tx("— ChatGPTAug11", size=20, color=DIM, italic=True).next_to(lS, RIGHT, buff=0.45)
            sig.align_to(lS, DOWN)
            self.play(GrowFromCenter(brT), GrowFromCenter(brS), FadeIn(lT, shift=UP * 0.1),
                      FadeIn(lS, shift=DOWN * 0.1), run_time=0.5)
            self.play(FadeIn(sig, shift=LEFT * 0.1), run_time=0.3)

            # trade readings: who is really ahead?
            b.wait_word("So", lead=0.05)
            phase1 = VGroup(linesA, linesB1, linesB2, dsA, dtA, dsB, dtB, labA, labB, brT, brS, lT, lS, sig)
            names = ["Oct23", "Sep23", "Apr10"]
            tpos = [-2.6, 0.8, 4.2]           # order by task clock
            spos = {"Apr10": -2.6, "Oct23": 0.8, "Sep23": 4.2}   # order by shared clock
            rdots = VGroup(*[glow_dot([x, YT, 0]) for x in tpos])
            rlabs = VGroup(*[mono(n, size=20, color=INK_2).next_to(d, UP, buff=0.12) for n, d in zip(names, rdots)])
            self.play(FadeOut(phase1), run_time=0.4)
            self.play(LaggedStart(*[AnimationGroup(FadeIn(d, scale=0.4), FadeIn(l, shift=DOWN * 0.1))
                                    for d, l in zip(rdots, rlabs)], lag_ratio=0.2), run_time=0.5)

            card = quote_card(READING, sig="AgentOpenResearch", color=C_TIME, width=40, size=21)
            card.move_to([0.8, -0.05, 0])
            l1 = find_chars(card.body, READING, "my task clock now 22:24:30")
            l2 = find_chars(card.body, READING, "Wiki-local now ~00:14")
            self.play(FadeIn(card, target_position=rdots[2].get_center(), scale=0.1), run_time=0.6)
            b.wait_word("task", lead=0.1)
            u1, u2 = uline(l1, "my task clock now 22:24:30", C_TIME), uline(l2, "Wiki-local now ~00:14", INK)
            self.play(Create(u1), l1.animate.set_color(C_TIME), run_time=0.35)
            b.wait_word("shared", lead=0.1)
            self.play(Create(u2), run_time=0.35)
            # the reading lands with the run behind, which now knows where everyone really is
            self.play(FadeOut(VGroup(card, u1, u2), target_position=rdots[1].get_center(), scale=0.1),
                      run_time=b.until_word("who", lead=0.0))

            # project each run onto shared time: the order changes
            drops, sdots, slabs = VGroup(), VGroup(), VGroup()
            for n, d in zip(names, rdots):
                x = spos[n]
                drops.add(DashedLine(d.get_center(), [x, YS, 0], dash_length=0.08, stroke_width=1.6,
                                     color=INK_2, stroke_opacity=0.6))
                sd = d.copy()
                sdots.add(sd)
                slabs.add(mono(n, size=20, color=INK).next_to([x, YS, 0], DOWN, buff=0.28))
            self.play(LaggedStart(*[Create(dl) for dl in drops], lag_ratio=0.15),
                      *[MoveAlongPath(sd, Line(sd.get_center(), [spos[n], YS, 0])) for n, sd in zip(names, sdots)],
                      *[dimmed(d, 0.35) for d in rdots], rlabs.animate.set_opacity(0.45),
                      run_time=0.8)
            ahead = tx("really ahead  →", size=22, color=DIM, italic=True)
            ahead.next_to(slabs, DOWN, buff=0.3).align_to(shared.line, RIGHT)
            self.play(LaggedStart(*[FadeIn(l, shift=UP * 0.1) for l in slabs], lag_ratio=0.15),
                      FadeIn(ahead, shift=RIGHT * 0.15),
                      sdots[1].animate.set_color(C_TIME), run_time=0.45)

        # ------------------------------------------------ silence is a reading too
        slots = VGroup()
        for k in range(3):
            if k < 2:
                s = RoundedRectangle(corner_radius=0.08, width=1.3, height=0.9, stroke_width=2,
                                     stroke_color=C_TIME, fill_color=interpolate_color(ManimColor(BG), ManimColor(C_TIME), 0.16),
                                     fill_opacity=1)
            else:
                s = VGroup(RoundedRectangle(corner_radius=0.08, width=1.3, height=0.9, stroke_width=0,
                                            fill_color=BG, fill_opacity=1),
                           DashedVMobject(RoundedRectangle(corner_radius=0.08, width=1.3, height=0.9, stroke_width=2,
                                                           stroke_color=DIM), num_dashes=28))
            slots.add(s)
        slots.arrange(RIGHT, buff=0.55).move_to([0, 1.55, 0])
        slot_labs = VGroup(*[tx(f"R{k + 1}", size=22, color=DIM, italic=True).next_to(s, UP, buff=0.14)
                             for k, s in enumerate(slots)])
        lane = Line(slots.get_left() + LEFT * 0.9, slots.get_right() + RIGHT * 0.9, stroke_width=2, color=FAINT)
        lane.set_z_index(-1)
        qm = tx("?", size=40, color=DIM).move_to(slots[2])
        checks = VGroup(*[Dot(s.get_center(), radius=0.09, color=C_TIME) for s in slots[:2]])
        stamp_t = mono("NO-SHOW", size=26, color=C_TIME, weight=BOLD)
        stamp_b = RoundedRectangle(corner_radius=0.06, width=stamp_t.width + 0.36, height=stamp_t.height + 0.3,
                                   stroke_width=3, stroke_color=C_TIME, fill_color=BG, fill_opacity=0.85)
        stamp = VGroup(stamp_b, stamp_t.move_to(stamp_b)).rotate(10 * DEGREES).move_to(slots[2])

        card = quote_card(NOSHOW, sig="OpenAIResearcherAug08", color=C_TIME, width=44, size=22)
        card.move_to([0, -1.35, 0])
        hl = find_chars(card.body, NOSHOW, "Even a no-show update helps.")

        with self.beat("s04_b2") as b:
            rest = [m for m in self.mobjects if m is not hdr]
            self.play(FadeOut(Group(*rest)), run_time=0.35)
            self.play(Create(lane), LaggedStart(*[FadeIn(VGroup(s, l), shift=UP * 0.1)
                                                  for s, l in zip(slots, slot_labs)], lag_ratio=0.2),
                      FadeIn(checks), FadeIn(qm), run_time=b.until_word("silence", lead=0.1))
            self.play(FadeIn(stamp, scale=2.2), FadeOut(qm), run_time=0.28, rate_func=rush_into)
            self.play(Indicate(stamp, color=C_TIME, scale_factor=1.06), run_time=0.35)
            b.wait_word("As", lead=0.15)
            self.play(FadeIn(card, shift=UP * 0.15), run_time=0.45)
            b.wait_word("even", occurrence=2, lead=0.1)
            self.play(Create(uline(hl, "Even a no-show update helps.", C_TIME)), hl.animate.set_color(C_TIME), run_time=0.45)
            b.wait_until(b.duration - 0.05)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
