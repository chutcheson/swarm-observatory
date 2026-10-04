import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

CTRL_Q = ("for definitive closure test, launch detached setsid at the R5 prompt (not early) "
          "with sleep 80-90s, so increment occurs after the 65s deadline.")
PROOF_Q = ("HORIZON PROOF: DEC17 Q1 start 12:40:35; Q5 due 14:54:52 with 42s ends 14:55:34, "
           "exactly 1s before Q1+2h15m=14:55:35. Thus R5 is final by fixed episode horizon; no R6.")


def check(color=INK, size=1.0):
    return MathTex(r"\checkmark", color=color).scale(size)


def uline(glyphs, color=INK, buff=0.07, stroke=2.5):
    """Underline a glyph group, one stroke per text row, at the row's median glyph bottom."""
    rows = []
    for g in sorted(glyphs, key=lambda m: -m.get_center()[1]):
        if rows and abs(rows[-1][0].get_center()[1] - g.get_center()[1]) < 0.2:
            rows[-1].append(g)
        else:
            rows.append([g])
    out = VGroup()
    for row in rows:
        y = float(np.median([g.get_bottom()[1] for g in row])) - buff
        x0 = min(g.get_left()[0] for g in row)
        x1 = max(g.get_right()[0] for g in row)
        out.add(Line([x0, y, 0], [x1, y, 0], stroke_width=stroke, color=color))
    return out


def branch(a, b, color=DIM, stroke=2):
    """A soft tree edge from point a to point b (horizontal tangents)."""
    a, b = np.array(a), np.array(b)
    dx = (b[0] - a[0]) * 0.5
    return CubicBezier(a, a + RIGHT * dx, b - RIGHT * dx, b, stroke_width=stroke, color=color)


class S08Discovery(SwarmScene):
    def construct(self):
        header = problem_header(6)

        # ------------------------------------------------ the question: a run's last answer, then ?
        ly = 0.1
        rx = [-5.5, -4.6, -3.7, -2.8, -1.9]
        lane = Line([-6.1, ly, 0], [rx[-1], ly, 0], stroke_width=2, color=FAINT)
        ticks = VGroup(*[Circle(radius=0.075, stroke_width=2, stroke_color=DIM, fill_color=BG,
                                fill_opacity=1).move_to([x, ly, 0]) for x in rx])
        rlabs = VGroup(*[tx(f"R{k + 1}", size=20, color=DIM, italic=True).next_to(t, UP, buff=0.16)
                         for k, t in enumerate(ticks)])
        run = glow_dot([-6.1, ly, 0])
        ok = check(INK, 0.75).next_to(ticks[-1], DOWN, buff=0.22)
        last_lab = tx("last answer", size=20, color=INK_2, italic=True).next_to(ok, DOWN, buff=0.1)
        beyond = DashedLine([rx[-1] + 0.15, ly, 0], [-0.55, ly, 0], dash_length=0.09,
                            stroke_width=2, color=FAINT)
        qmark = tx("?", size=48, color=C_DISC).move_to([-0.25, ly, 0])
        hyp1 = tx("ends at its last answer", size=28, color=INK, italic=True)
        hyp2 = tx("ends on a timer", size=28, color=INK, italic=True)
        hyp1.move_to([0.75, ly + 0.85, 0], aligned_edge=LEFT)
        hyp2.move_to([0.75, ly - 0.85, 0], aligned_edge=LEFT)
        q_r = qmark.get_right() + RIGHT * 0.12
        br1 = branch(q_r, hyp1.get_left() + LEFT * 0.12, C_DISC)
        br2 = branch(q_r, hyp2.get_left() + LEFT * 0.12, C_DISC)

        b_group = VGroup(lane, ticks, rlabs, run, ok, last_lab, beyond, qmark, hyp1, hyp2, br1, br2)
        b_group.shift(RIGHT * 0.45)

        def light(m):
            for t in ticks:
                if run.get_center()[0] >= t.get_center()[0] - 1e-3:
                    t.set_fill(INK, 1).set_stroke(INK)

        # ------------------------------------------------ experiments with controls
        root = tx("silence", size=30, color=C_DISC, italic=True).move_to([-5.0, 1.0, 0])
        leaf_x = -3.0
        leaves = VGroup(
            tx("never launched", size=28, color=INK_2, italic=True),
            tx("ended at the answer", size=28, color=INK, italic=True),
            tx("ended at the deadline", size=28, color=INK, italic=True),
        )
        for i, lf in enumerate(leaves):
            lf.move_to([leaf_x, 2.0 - i * 1.0, 0], aligned_edge=LEFT)
        r_r = root.get_right() + RIGHT * 0.15
        edges = VGroup(*[branch(r_r, lf.get_left() + LEFT * 0.15, C_DISC) for lf in leaves])
        div_x0, div_x1 = leaf_x - 0.2, 2.2
        divs, marks, mlabs = VGroup(), VGroup(), VGroup()
        for y, lab in ((1.5, "launch mark"), (0.5, "mark after the 65 s deadline")):
            d = DashedLine([div_x0, y, 0], [div_x1, y, 0], dash_length=0.1, stroke_width=2.5,
                           color=C_DISC)
            m = glow_dot([div_x1 + 0.22, y, 0], color=C_DISC, radius=0.065, glow=0.24)
            t = tx(lab, size=22, color=C_DISC, italic=True).next_to(m, RIGHT, buff=0.2)
            divs.add(d)
            marks.add(m)
            mlabs.add(t)
        ccard = quote_card(CTRL_Q, sig="CashierCoordJun09OAI", color=C_DISC, width=66, size=20,
                           header="dse wiki · 17 June 2026, 06:26 UTC")
        ccard.move_to([0, -2.45, 0])
        ph1 = find_chars(ccard.body, CTRL_Q, "at the R5 prompt")
        ph2 = find_chars(ccard.body, CTRL_Q, "after the 65s deadline")

        # ------------------------------------------------ the proof
        pcard = quote_card(PROOF_Q, sig="OpenAIDec17ConstructionX", color=C_DISC, width=64, size=20,
                           header="dse wiki · 17 June 2026, 05:23 UTC")
        pcard.move_to([0, 1.62, 0])
        p_q1 = find_chars(pcard.body, PROOF_Q, "Q1 start 12:40:35")
        p_end = find_chars(pcard.body, PROOF_Q, "ends 14:55:34")
        p_1s = VGroup(*find_chars(pcard.body, PROOF_Q, "exactly 1s")[-2:])
        p_hor = find_chars(pcard.body, PROOF_Q, "Q1+2h15m=14:55:35")

        ty = -0.68
        tx0, tx1 = -5.4, 3.7
        tline = Line([tx0, ty, 0], [tx1, ty, 0], stroke_width=2.5, color=INK_2)
        q1_tick = Line([tx0, ty - 0.14, 0], [tx0, ty + 0.14, 0], stroke_width=3, color=INK)
        q1_lab = VGroup(tx("Q1 starts", size=22, color=INK, italic=True),
                        mono("12:40:35", size=18, color=INK_2)).arrange(DOWN, buff=0.08)
        q1_lab.next_to(q1_tick, DOWN, buff=0.14)
        hor = DashedLine([tx1, ty - 0.32, 0], [tx1, ty + 0.32, 0], dash_length=0.07, stroke_width=3,
                         color=C_DISC)
        q5_bar = Line([tx1 - 0.22, ty, 0], [tx1 - 0.02, ty, 0], stroke_width=9, color=INK)
        q5_lab = tx("R5", size=20, color=INK, italic=True).next_to(q5_bar, UP, buff=0.42)
        hor_lab = VGroup(tx("fixed horizon", size=24, color=C_DISC, italic=True),
                         tx("Q1 + 2 h 15 m", size=20, color=DIM, italic=True)).arrange(DOWN, buff=0.1,
                                                                                      aligned_edge=LEFT)
        hor_lab.next_to(hor, RIGHT, buff=0.5)

        zoom = Square(0.62, stroke_width=2, color=C_DISC).move_to([tx1 - 0.08, ty, 0])
        inset = RoundedRectangle(corner_radius=0.08, width=5.2, height=1.85, stroke_width=1.5,
                                 stroke_color=C_DISC, fill_color=CARD, fill_opacity=1)
        inset.move_to([2.75, -2.62, 0])
        conn = VGroup(Line(zoom.get_corner(DL), inset.get_corner(UL) + RIGHT * 0.08, stroke_width=1.2,
                           color=C_DISC, stroke_opacity=0.6),
                      Line(zoom.get_corner(DR), inset.get_corner(UR) + LEFT * 0.08, stroke_width=1.2,
                           color=C_DISC, stroke_opacity=0.6))
        iy = inset.get_center()[1] - 0.05
        ix0 = inset.get_left()[0] + 0.25
        s_per = 0.62           # units per second inside the inset
        t_end = ix0 + 4.6 * s_per     # 14:55:34
        t_hor = t_end + s_per         # 14:55:35
        iaxis = Line([ix0, iy, 0], [inset.get_right()[0] - 0.25, iy, 0], stroke_width=1.5, color=FAINT)
        isec = VGroup(*[Line([ix0 + k * s_per, iy - 0.05, 0], [ix0 + k * s_per, iy + 0.05, 0],
                             stroke_width=1.5, color=FAINT) for k in range(0, 8)
                        if ix0 + k * s_per < inset.get_right()[0] - 0.25])
        ibar = Line([ix0, iy, 0], [t_end, iy, 0], stroke_width=9, color=INK)
        ibar.set_stroke(opacity=[0.0, 1.0])
        iend = Line([t_end, iy - 0.18, 0], [t_end, iy + 0.18, 0], stroke_width=3, color=INK)
        iend_lab = VGroup(tx("R5 ends", size=20, color=INK, italic=True),
                          mono("14:55:34", size=17, color=INK_2)).arrange(DOWN, buff=0.06)
        iend_lab.next_to(iend, DOWN, buff=0.1).align_to(iend, RIGHT).shift(RIGHT * 0.05)
        ihor = DashedLine([t_hor, iy - 0.45, 0], [t_hor, iy + 0.45, 0], dash_length=0.07,
                          stroke_width=3, color=C_DISC)
        ihor_lab = VGroup(tx("horizon", size=20, color=C_DISC, italic=True),
                          mono("14:55:35", size=17, color=C_DISC)).arrange(DOWN, buff=0.06)
        ihor_lab.next_to(ihor, RIGHT, buff=0.12).align_to(iend_lab, DOWN)
        ibrace = BraceBetweenPoints([t_end, iy + 0.28, 0], [t_hor, iy + 0.28, 0], direction=UP,
                                    color=C_DISC, buff=0.02)
        ibrace_lab = tx("1 s", size=24, color=C_DISC).next_to(ibrace, UP, buff=0.06)

        with self.beat("s08_b1") as b:
            # Six: nobody told them the rules.
            self.play(Write(header), Create(lane), FadeIn(ticks), FadeIn(rlabs), run_time=0.85)
            self.add(run)
            ticks.add_updater(light)
            t_run = b.until_word("rules", lead=-0.55)
            self.play(run.animate.move_to(ticks[-1]), run_time=t_run, rate_func=smooth)
            ticks.remove_updater(light)
            self.play(FadeIn(ok, scale=0.6), FadeIn(last_lab, shift=UP * 0.1), run_time=0.35)
            # Does a run end at its last answer, or on a timer?
            b.wait_word("does", lead=0.05)
            self.play(Create(beyond), FadeIn(qmark, scale=0.7), run_time=0.6)
            b.wait_word("last", lead=0.1)
            self.play(Create(br1), FadeIn(hyp1, shift=RIGHT * 0.15), run_time=0.55)
            b.wait_word("timer", lead=0.1)
            self.play(Create(br2), FadeIn(hyp2, shift=RIGHT * 0.15), run_time=0.55)

            # So they designed experiments with controls
            b.wait_word("so", lead=0.0)
            self.play(FadeOut(VGroup(lane, ticks, rlabs, run, ok, last_lab, beyond, hyp1, hyp2, br1, br2)),
                      run_time=0.35)
            self.play(FadeTransform(qmark, root), run_time=0.45)
            self.play(LaggedStart(*[AnimationGroup(Create(e), FadeIn(lf, shift=RIGHT * 0.15))
                                    for e, lf in zip(edges, leaves)], lag_ratio=0.25),
                      FadeIn(ccard, shift=UP * 0.15), run_time=0.6)
            b.wait_word("controls", lead=0.1)
            self.play(Create(divs[0]), FadeIn(marks[0], scale=0.5), FadeIn(mlabs[0], shift=LEFT * 0.1),
                      Create(uline(ph1, C_DISC)), ph1.animate.set_color(C_DISC),
                      leaves[0].animate.set_opacity(0.45), run_time=0.4)
            self.play(Create(divs[1]), FadeIn(marks[1], scale=0.5), FadeIn(mlabs[1], shift=LEFT * 0.1),
                      Create(uline(ph2, C_DISC)), ph2.animate.set_color(C_DISC), run_time=0.4)

            # and one run posted a proof
            b.wait_word("posted", lead=0.4)
            exp_mobs = [m for m in self.mobjects if m is not header]
            self.play(FadeOut(Group(*exp_mobs)), run_time=0.35)
            self.play(FadeIn(pcard, shift=UP * 0.15), run_time=0.45)
            b.wait_word("proof", lead=-0.1)
            self.play(Create(tline), Create(q1_tick), Create(hor), FadeIn(q1_lab, shift=UP * 0.1),
                      Create(uline(p_q1, INK)), run_time=0.7)
            # the last round ends
            b.wait_word("round", lead=0.25)
            self.play(Create(q5_bar), FadeIn(q5_lab, shift=DOWN * 0.08),
                      Create(uline(p_end, INK)), run_time=0.45)
            # one second
            b.wait_word("one", 2, lead=0.15)
            self.play(Create(zoom), run_time=0.25)
            self.play(Create(conn), FadeIn(inset), FadeIn(iaxis), FadeIn(isec), Create(ibar),
                      Create(iend), FadeIn(iend_lab), Create(ihor), run_time=0.5)
            self.play(GrowFromCenter(ibrace), FadeIn(ibrace_lab, shift=DOWN * 0.08),
                      Create(highlight_box(p_1s, C_DISC)), p_1s.animate.set_color(C_DISC), run_time=0.35)
            # before a fixed horizon
            b.wait_word("fixed", lead=0.1)
            self.play(FadeIn(hor_lab, shift=LEFT * 0.1), FadeIn(ihor_lab, shift=LEFT * 0.1),
                      Create(uline(p_hor, C_DISC)), p_hor.animate.set_color(C_DISC), run_time=0.5)
            b.wait_until(b.duration - 0.06)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
