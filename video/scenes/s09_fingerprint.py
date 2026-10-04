import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

PRO_Q = "On prompt, post STATE5-XX … FIRST, then answer within 13s."
CON_Q = "Do not risk the answer for signaling."


def chip(label, color=INK_2, text_color=INK, size=32):
    t = tx(label, size=size, color=text_color)
    r = RoundedRectangle(corner_radius=0.14, width=t.width + 0.6, height=0.78, stroke_width=2.5,
                         stroke_color=color, fill_color=CARD, fill_opacity=1)
    t.move_to(r)
    g = VGroup(r, t)
    return g


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


def bar(x, y0, h, color, width=0.7):
    """A value bar standing on (or hanging from) the axis at y0; h may be negative."""
    r = Rectangle(width=width, height=abs(h), stroke_width=0, fill_color=color, fill_opacity=0.9)
    r.move_to([x, y0 + h / 2, 0])
    return r


class S09Fingerprint(SwarmScene):
    def construct(self):
        # ------------------------------------------------ the flip
        L, R = np.array([-1.75, 0.35, 0]), np.array([1.75, 0.35, 0])
        ans = chip("answer").move_to(L)
        relay = chip("relay", C_MORT, C_MORT).move_to(R)
        signal = chip("signal", C_MORT, C_MORT).move_to(L)
        arrow = Arrow(LEFT * 0.6, RIGHT * 0.6, buff=0, stroke_width=3, color=DIM,
                      max_tip_length_to_length_ratio=0.25).move_to((L + R) / 2)
        when0 = tx("16 June, 10:23", size=22, color=DIM, italic=True).move_to([0, -0.75, 0])
        when1 = tx("16 June, 21:51", size=22, color=DIM, italic=True).move_to(when0)

        # ------------------------------------------------ individual reward: signaling costs c
        ax_y = -0.45
        sx = -3.4                                   # the signaller's column
        eq2 = MathTex(r"R_i", r"=", r"\sum\nolimits_j r_j", font_size=68, color=INK).move_to([sx, 2.3, 0])
        eq = MathTex(r"R_i", r"=", r"r_i", font_size=68, color=INK)
        eq.shift(eq2[0].get_center() - eq[0].get_center())
        eq2[2].set_color(C_REWARD)
        eq_lab = tx("individual reward", size=24, color=DIM, italic=True).next_to(eq, DOWN, buff=0.25)
        eq_lab2 = tx("group reward", size=24, color=C_REWARD, italic=True).next_to(eq2, DOWN, buff=0.12)
        axis = Line([sx - 1.3, ax_y, 0], [sx + 1.3, ax_y, 0], stroke_width=2, color=FAINT)
        axis_ext = Line([sx + 1.3, ax_y, 0], [5.4, ax_y, 0], stroke_width=2, color=FAINT)
        me = glow_dot([sx, -2.6, 0])
        me_lab = tx("signaller", size=22, color=DIM, italic=True).next_to(me, DOWN, buff=0.12)
        c_h = 0.9
        cost = bar(sx, ax_y, -c_h, C_MORT)
        cost_lab = MathTex(r"-c", font_size=44, color=C_MORT).next_to(cost, RIGHT, buff=0.2)

        # ring: the signaller's own 13 s
        rc = np.array([2.9, -0.2, 0])
        rr = 1.5
        f = ValueTracker(0.0)
        base = Circle(radius=rr, stroke_width=10, color=FAINT).move_to(rc)

        def ans_arc():
            a = Arc(radius=rr, start_angle=PI / 2 - TAU * f.get_value(), angle=-TAU * (1 - f.get_value()),
                    stroke_width=10, color=INK_2)
            return a.move_arc_center_to(rc)

        def sig_arc():
            a = Arc(radius=rr, start_angle=PI / 2, angle=-TAU * max(f.get_value(), 1e-4),
                    stroke_width=10, color=C_MORT)
            a.move_arc_center_to(rc)
            if f.get_value() < 1e-3:
                a.set_stroke(opacity=0)
            return a

        arc_a = always_redraw(ans_arc)
        arc_s = always_redraw(sig_arc)
        secs = VGroup(tx("13", size=44, color=INK), tx("s", size=30, color=DIM, italic=True)).arrange(
            RIGHT, buff=0.08, aligned_edge=DOWN).move_to(rc)
        a_ang = -3 * PI / 4
        ans_lab = tx("answer", size=26, color=INK_2, italic=True).move_to(
            rc + (rr + 0.62) * np.array([np.cos(a_ang), np.sin(a_ang), 0]))
        f_end = 0.28
        s_ang = PI / 2 - TAU * f_end / 2
        sig_lab = tx("signal", size=26, color=C_MORT, italic=True).move_to(
            rc + (rr + 0.65) * np.array([np.cos(s_ang), np.sin(s_ang), 0]))
        ring = VGroup(base, arc_a, arc_s, secs, ans_lab, sig_lab)

        with self.beat("s09_b1") as b:
            # Now look again at that flip.
            b.wait_word("now", lead=0.05)
            self.play(FadeIn(ans, shift=UP * 0.1), GrowArrow(arrow), FadeIn(relay, shift=UP * 0.1),
                      FadeIn(when0), run_time=0.55)
            b.wait_word("flip", lead=0.25)
            self.play(ans.animate(path_arc=-PI * 0.75).move_to(R),
                      Transform(relay, signal, path_arc=-PI * 0.75),
                      FadeTransform(when0, when1), run_time=0.7)
            b.wait_word("an", lead=-0.05)
            order = VGroup(relay, arrow, ans)
            self.play(order.animate.scale(0.6).move_to([0, 3.05, 0]), FadeOut(when1, shift=UP * 0.2),
                      run_time=0.45)
            # An agent scored only on its own answer
            b.wait_word("scored", lead=0.1)
            self.play(Write(eq), FadeIn(eq_lab, shift=UP * 0.1), Create(axis), FadeIn(me, scale=0.6),
                      FadeIn(me_lab), run_time=0.7)
            b.wait_word("own", lead=0.15)
            self.play(Create(base), Create(arc_a), FadeIn(secs), FadeIn(ans_lab), run_time=0.6)
            self.add(arc_s)
            # has no reason to signal.
            b.wait_word("signal", lead=0.15)
            self.play(GrowFromEdge(cost, UP), FadeIn(cost_lab, shift=DOWN * 0.1), run_time=0.5)
            # Every second spent signaling comes out of its own question.
            b.wait_word("second", lead=0.2)
            self.play(f.animate.set_value(f_end), FadeIn(sig_lab, run_time=0.8), run_time=1.9,
                      rate_func=smooth)
            b.wait_word("question", lead=0.05)
            self.play(Indicate(ans_lab, color=INK, scale_factor=1.12),
                      Indicate(cost_lab, color=C_MORT, scale_factor=1.15), run_time=0.7)

        # ------------------------------------------------ group reward: their gain is partly yours
        others_x = [1.3, 2.9, 4.5]
        others = VGroup(*[glow_dot([x, -2.6, 0]) for x in others_x])
        others_lab = tx("runs behind", size=22, color=DIM, italic=True).next_to(others, DOWN, buff=0.12)
        b_h = 0.55
        gains = VGroup(*[bar(x, ax_y, b_h, C_POOL) for x in others_x])
        flyers = VGroup(*[Dot(me.get_center(), radius=0.06, color=C_MORT) for _ in others_x])
        stack = VGroup(*[bar(sx, ax_y + b_h * k, b_h, C_POOL) for k in range(3)])
        gain_lab = MathTex(r"+b", font_size=44, color=C_POOL).next_to(stack, RIGHT, buff=0.2)
        net = bar(sx, ax_y, 3 * b_h - c_h, C_REWARD)
        net_lab = MathTex(r"b - c > 0", font_size=48, color=C_REWARD)
        net_lab.next_to(net, RIGHT, buff=0.3).align_to(net, DOWN).shift(UP * 0.08)
        pays = tx("signaling pays", size=26, color=C_REWARD, italic=True).next_to(net_lab, UP, buff=0.18,
                                                                             aligned_edge=LEFT)

        pro = quote_card(PRO_Q, sig="AgentNov11OAI", color=C_REWARD, width=36, size=27,
                         header="dse wiki · 16 June 2026, 21:51 UTC")
        con = quote_card(CON_Q, sig="OpenAIFeb28Watcher", color=C_MORT, width=36, size=27,
                         header="dse wiki · 18 June 2026, 00:49 UTC")
        pro.move_to([0, 1.4, 0]).to_edge(LEFT, buff=1.1)
        con.move_to([0, -1.75, 0]).to_edge(RIGHT, buff=1.1)
        vs = tx("vs", size=40, color=DIM, italic=True).move_to([0, -0.15, 0])
        first = find_chars(pro.body, PRO_Q, "FIRST")
        risk = find_chars(con.body, CON_Q, "risk the answer")

        with self.beat("s09_b2") as b:
            # Spending your seconds on someone else's score
            arc_a.clear_updaters()
            arc_s.clear_updaters()
            self.play(FadeOut(ring), run_time=0.4)
            b.wait_word("someone", lead=0.3)
            self.play(Create(axis_ext), FadeIn(others, scale=0.6), FadeIn(others_lab), run_time=0.45)
            self.add(flyers)
            self.play(*[fl.animate(path_arc=-PI / 3).move_to(o.get_center()) for fl, o in zip(flyers, others)],
                      run_time=0.5, rate_func=smooth)
            self.remove(flyers)
            self.play(LaggedStart(*[GrowFromEdge(g, DOWN) for g in gains], lag_ratio=0.15),
                      *[Flash(o.get_center(), color=C_POOL, line_length=0.12, flash_radius=0.25)
                        for o in others], run_time=0.55)
            # only makes sense if their score is partly yours.
            b.wait_word("their", lead=0.05)
            self.play(TransformMatchingTex(eq, eq2), FadeTransform(eq_lab, eq_lab2), run_time=0.6)
            b.wait_word("partly", lead=0.1)
            self.play(*[ReplacementTransform(g.copy(), s) for g, s in zip(gains, stack)],
                      FadeIn(gain_lab, shift=LEFT * 0.1), run_time=0.6)
            b.wait_word("yours", lead=0.0)
            self.play(ReplacementTransform(VGroup(stack, cost), net),
                      FadeOut(VGroup(gain_lab, cost_lab)), FadeIn(net_lab, shift=UP * 0.1), run_time=0.5)
            self.play(FadeIn(pays, shift=UP * 0.08), run_time=0.3)
            # And the agents argued over that trade, out loud.
            b.wait_word("agents", lead=0.0)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.35)
            self.play(FadeIn(pro, shift=RIGHT * 0.2), run_time=0.4)
            self.play(FadeIn(vs, scale=0.8), run_time=0.2)
            self.play(FadeIn(con, shift=LEFT * 0.2), run_time=0.4)
            b.wait_word("trade", lead=0.05)
            self.play(Create(highlight_box(first, C_REWARD)), first.animate.set_color(C_REWARD),
                      Create(uline(risk, C_MORT)), risk.animate.set_color(C_MORT), run_time=0.4)
            b.wait_until(b.duration - 0.06)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
