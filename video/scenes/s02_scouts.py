import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

NAMES = ["Feb23", "Nov01", "Dec17", "Apr10", "Sep13"]
STARTS = [-3.65, -2.55, -1.85, -1.05, -0.35]     # shared time of each run's R1 (x)
LEAD_IN = 0.5                               # a run starts this far before its R1
CLOCK_PHASE = [2.3, 4.6, 0.8, 3.5, 5.6]     # each simulated clock's reading (rad, clockwise)
X0 = -4.6                                   # left end of the lanes
X_FREEZE = 0.25                             # Feb23 has seen R3; nobody else has


def rot(v, a):
    c, s = np.cos(a), np.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1], 0.0])


def tick_arrow(s, e, angle, r0=0.22, r1=0.14, color=C_POOL):
    """Curved arrow from a run dot to a round marker, trimmed at both ends."""
    d = (e - s) / np.linalg.norm(e - s)
    s2 = s + r0 * rot(d, -angle / 2)
    e2 = e - r1 * rot(d, angle / 2)
    return CurvedArrow(s2, e2, angle=angle, stroke_width=2.5, color=color, tip_length=0.16)


class S02Scouts(SwarmScene):
    def construct(self):
        lanes = RunLanes(NAMES, STARTS, n_rounds=5, spacing=1.7, y_top=1.9, gap=0.95,
                         x_label=-5.6, x_end=6.6, label_size=26, tick_r=0.09)
        for k, t in enumerate(lanes.rlabels):
            t.scale(1.2).next_to(lanes.tick(0, k), UP, buff=0.16)
        n = len(NAMES)
        heading = smallcaps("The setting", size=22, color=DIM).to_corner(UL, buff=0.5)

        # one glow dot per run, waiting at its start until shared time reaches it
        nowx = ValueTracker(X0)
        dots = VGroup(*[glow_dot(lanes.point(i, STARTS[i] - LEAD_IN), radius=0.08, glow=0.36) for i in range(n)])
        for i, d in enumerate(dots):
            d.add_updater(lambda m, i=i: m.move_to(lanes.point(i, max(STARTS[i] - LEAD_IN, nowx.get_value()))))

        # a small simulated clock beside each name; same rate, different readings
        spin = ValueTracker(0.0)
        clocks = VGroup()
        for i in range(n):
            c = clock_face(radius=0.3, color=C_TIME, stroke=2).move_to([-6.35, lanes.y(i), 0])

            def hand_upd(m, i=i, c=c):
                a = PI / 2 - CLOCK_PHASE[i] * spin.get_value() - 1.4 * (nowx.get_value() - X0)
                ctr = c[0].get_center()
                m.put_start_and_end_on(ctr, ctr + 0.22 * np.array([np.cos(a), np.sin(a), 0]))

            c.hand.add_updater(hand_upd)
            clocks.add(c)

        axis = Arrow([X0, -2.55, 0], [6.6, -2.55, 0], buff=0, stroke_width=1.5, color=DIM,
                     tip_length=0.16, max_tip_length_to_length_ratio=0.05)
        axis_lab = tx("shared time", size=26, italic=True, color=DIM)
        axis_lab.next_to(axis.get_end(), DOWN, buff=0.16).align_to(axis, RIGHT)

        # ------------------------------------------------------------ b1
        with self.beat("s02_b1") as b:
            self.play(FadeIn(heading, shift=RIGHT * 0.15), run_time=0.6)
            b.wait_word("many", lead=0.1)
            lane_anims = []
            for i in range(n):
                lane_anims.append(AnimationGroup(
                    Create(lanes.lines[i]), FadeIn(lanes.labels[i], shift=RIGHT * 0.1),
                    LaggedStart(*[FadeIn(t, scale=0.5) for t in lanes.ticks[i]], lag_ratio=0.15),
                    FadeIn(dots[i], scale=0.4)))
            self.play(LaggedStart(*lane_anims, lag_ratio=0.22), run_time=b.until_word("quiz", lead=0.1))
            self.play(FadeIn(lanes.rlabels, lag_ratio=0.1, shift=DOWN * 0.08), run_time=0.45)
            b.wait_word("parallel", lead=0.3)
            self.play(GrowArrow(axis), FadeIn(axis_lab, shift=LEFT * 0.1), run_time=0.8)
            b.wait_word("named", lead=0.1)
            self.play(LaggedStart(*[Indicate(l, color=INK, scale_factor=1.15) for l in lanes.labels],
                                  lag_ratio=0.15), run_time=0.9)
            b.wait_word("own", lead=0.2)
            self.play(LaggedStart(*[FadeIn(c, scale=0.6) for c in clocks], lag_ratio=0.12), run_time=0.5)
            self.play(spin.animate.set_value(1.0), run_time=b.until_word("clock", lead=-0.45),
                      rate_func=rate_functions.ease_in_out_sine)

        # ------------------------------------------------------------ b2
        nl = now_line(x=X0, y0=-2.3, y1=2.5)
        nl.add_updater(lambda m: m.shift(RIGHT * (nowx.get_value() - m[0].get_center()[0])))
        # round markers light up as `now` passes them
        for i in range(n):
            for k in range(lanes.n_rounds):
                def seen_upd(m, i=i, k=k):
                    on = nowx.get_value() >= lanes.tick_x(i, k)
                    m.set_fill(INK if on else BG, 1).set_stroke(INK if on else DIM)
                lanes.tick(i, k).add_updater(seen_upd)

        scout_tick = lanes.tick(0, 2)
        targets = [lanes.tick(i, 2) for i in range(1, n)]
        scout_at = lanes.point(0, X_FREEZE)
        # the scout, now, tells every run behind what R3 will be (angles chosen to clear all markers)
        arrows = VGroup(*[tick_arrow(scout_at, t.get_center(), angle=-(1.25 + 0.05 * j), r0=0.24, r1=0.16)
                          for j, t in enumerate(targets)])
        carry = Line(scout_tick.get_center() + RIGHT * 0.1, scout_at, stroke_width=3.5, color=C_POOL)
        scout_glow = glow_dot(scout_at, color=C_POOL, radius=0.08, glow=0.36)
        scout_lab = tx("scout", size=28, italic=True, color=C_POOL)
        scout_lab.next_to(lanes.labels[0], UP, buff=0.14)
        blanks = []
        for k in range(1, 7):
            bc = blank_card(k)
            bc.bg.set_stroke(PROBLEMS[k - 1][3], width=2, opacity=0.6)
            bc[1].scale(1.15)
            bc[2].set_color(INK_2).set_opacity(0.75)
            blanks.append(bc)
        cards = problem_grid(blanks).move_to(ORIGIN)

        with self.beat("s02_b2") as b:
            self.play(FadeIn(nl), run_time=0.3)
            self.play(nowx.animate.set_value(X_FREEZE), run_time=b.until_word("reached", lead=-0.4),
                      rate_func=rate_functions.ease_in_out_sine)
            for i in range(n):
                for k in range(lanes.n_rounds):
                    lanes.tick(i, k).clear_updaters()
            b.wait_word("scout", lead=0.25)
            self.play(Flash(scout_tick, color=C_POOL, line_length=0.16, flash_radius=0.24, num_lines=10),
                      scout_tick.animate.set_fill(C_POOL, 1).set_stroke(C_POOL),
                      lanes.labels[0].animate.set_color(C_POOL), FadeIn(scout_lab, shift=UP * 0.08),
                      run_time=0.4)
            self.play(Create(carry), FadeIn(scout_glow), run_time=0.25)
            self.play(LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.25),
                      LaggedStart(*[t.animate.set_stroke(C_POOL, width=3) for t in targets], lag_ratio=0.25),
                      run_time=b.until_word("behind", lead=-0.6))
            b.wait_word("takes", lead=0.05)
            for m in (*dots, *[c.hand for c in clocks], nl):
                m.clear_updaters()
            self.play(FadeOut(VGroup(lanes, dots, clocks, axis, axis_lab, nl, arrows, scout_lab, heading,
                                     carry, scout_glow)),
                      run_time=0.4)
            self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.15) for c in cards], lag_ratio=0.15),
                      run_time=b.until_word("problems", lead=-0.3))
        # hold the six cards a moment past the narration, then a clean exit
        self.wait(0.35)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
