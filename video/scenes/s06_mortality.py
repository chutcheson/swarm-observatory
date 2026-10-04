import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

# ------------------------------------------------------------------ geometry
X0 = -3.55                               # lane start
TICK_XS = [-3.05, -1.85, -0.65, 0.55]    # R1..R4; R5 is the wall
WALL_X = 1.8
ARRIVE_X = WALL_X - 0.32                 # where a run waits at R5 before answering
TOUCH_X = WALL_X - 0.12                  # answering = touching the wall
Y1 = 0.55                                # b1: the single lane
YA, YB = 1.55, -0.7                      # b2: rows A and B
LIFT = 1.15                              # b2: row B rises to the centre once row A is gone
YB2 = YB + LIFT
Y_TRACK = YB2 - 0.66                     # b2: the courier's background track (under the wall)
YS = -2.85                               # b2: the 16 June timestrip
CHIP_X = -5.25
COUNTER_AT = np.array([3.75, 0.42, 0])   # before the lift


# ------------------------------------------------------------------ helpers
def make_lane(y, x_end=5.4, wall_h=0.84, labels=False):
    """One run's lane: R1..R4 markers, a red wall at R5, and a fading dashed
    line beyond the wall (the part of the quiz the run never lives to see)."""
    line = Line([X0, y, 0], [WALL_X, y, 0], stroke_width=2, color=FAINT)
    ticks = VGroup(*[Circle(radius=0.075, stroke_width=2, stroke_color=DIM, fill_color=BG,
                            fill_opacity=1).move_to([x, y, 0]) for x in TICK_XS])
    glow = Rectangle(width=0.34, height=wall_h + 0.04, stroke_width=0, fill_color=C_MORT,
                     fill_opacity=0.10).move_to([WALL_X, y, 0])
    wall = Line([WALL_X, y - wall_h / 2, 0], [WALL_X, y + wall_h / 2, 0], stroke_width=6, color=C_MORT)
    beyond = VGroup()
    xs, x = [], WALL_X + 0.16
    while x + 0.12 < x_end:
        xs.append(x)
        x += 0.22
    for i, x in enumerate(xs):
        op = 0.75 * (1 - i / len(xs)) ** 1.3
        dash = Line([x, y, 0], [x + 0.12, y, 0], stroke_width=2, color=DIM, stroke_opacity=op)
        dash.base_op = op
        beyond.add(dash)
    g = VGroup(line, ticks, glow, wall, beyond)
    g.line, g.ticks, g.wall, g.wglow, g.beyond = line, ticks, wall, glow, beyond
    g.rlabels = VGroup()
    if labels:
        base = y + wall_h / 2 + 0.12
        for k, x in enumerate(TICK_XS + [WALL_X]):
            r = tx(f"R{k + 1}", size=20, color=DIM, italic=True)
            r.move_to([x, 0, 0])
            r.shift(UP * (base - r[0].get_bottom()[1]))
            g.rlabels.add(r)
        g.add(g.rlabels)
    return g


def beyond_opacity(lane, f):
    """Scale the fading dashes beyond a wall to fraction f of their base opacity."""
    return AnimationGroup(*[d.animate.set_stroke(opacity=d.base_op * f) for d in lane.beyond])


def check(color=C_REWARD, s=0.15, stroke=5):
    m = VMobject(stroke_width=stroke, stroke_color=color)
    m.set_points_as_corners([np.array([-s, 0.05 * s, 0]), np.array([-0.3 * s, -0.75 * s, 0]),
                             np.array([s, 0.95 * s, 0])])
    m.joint_type = LineJointType.ROUND
    return m


def cross(color=C_MORT, s=0.13, stroke=5):
    return VGroup(Line(np.array([-s, s, 0]), np.array([s, -s, 0]), stroke_width=stroke, color=color),
                  Line(np.array([-s, -s, 0]), np.array([s, s, 0]), stroke_width=stroke, color=color))


def chip(first, second, color):
    """An order chip: 'answer → relay'. .first/.arrow/.second slice the glyphs."""
    t = tx(f"{first} → {second}", size=26, italic=True, color=INK)
    bg = RoundedRectangle(corner_radius=0.12, width=t.width + 0.44, height=t.height + 0.34,
                          stroke_width=1.6, stroke_color=color, fill_color=CARD, fill_opacity=1)
    t.move_to(bg)
    g = VGroup(bg, t)
    n1 = len(first)
    g.bg, g.t = bg, t
    g.first, g.arrow, g.second = VGroup(*t[:n1]), t[n1], VGroup(*t[n1 + 1:])
    return g


def dead_dot(point):
    return Circle(radius=0.075, stroke_width=2, stroke_color=DIM, fill_color=BG,
                  fill_opacity=1).move_to(point)


def counter(value, label, color):
    """counter_box with a legible serif label."""
    cb = counter_box(value, label, color)
    cb.remove(cb.lab)
    lab = tx(label, size=20, color=color, italic=True).next_to(cb.box, DOWN, buff=0.12)
    cb.add(lab)
    cb.lab = lab
    return cb


def soft_glow(mob, color, layers=8, spread=0.32, peak=0.05, corner_radius=0.14):
    g = VGroup()
    for i in range(layers, 0, -1):
        e = spread * i / layers
        g.add(RoundedRectangle(corner_radius=corner_radius + e, width=mob.width + 2 * e,
                               height=mob.height + 2 * e, stroke_width=0, fill_color=color,
                               fill_opacity=peak).move_to(mob))
    return g


def fly(mob, path, scale_to=1.0):
    """Move mob along path while scaling it to scale_to."""
    start = mob.copy()

    def upd(m, a):
        m.become(start)
        m.scale(1 + (scale_to - 1) * a)
        m.move_to(path.point_from_proportion(a))
        if a > 0.75:
            m.set_opacity(1 - (a - 0.75) / 0.25)
    return UpdateFromAlphaFunc(mob, upd)


# ------------------------------------------------------------------ scene
class S06Mortality(SwarmScene):
    def construct(self):
        hdr = problem_header(4)

        # ---------------------------------------------------------- b1
        lane = make_lane(Y1, labels=True)
        fa = tx("final answer", size=22, color=C_MORT, italic=True).next_to(lane.wall, DOWN, buff=0.14)
        run = glow_dot([TICK_XS[0] - 0.55, Y1, 0], radius=0.08)

        ghost_ys = [-1.05, -1.7, -2.35]
        ghost_x = [0.15, -1.15, -2.3]
        ghosts, gdots = VGroup(), VGroup()
        for y, x in zip(ghost_ys, ghost_x):
            gl = Line([X0, y, 0], [WALL_X, y, 0], stroke_width=1.5, color=FAINT)
            gw = Line([WALL_X, y - 0.2, 0], [WALL_X, y + 0.2, 0], stroke_width=3, color=C_MORT,
                      stroke_opacity=0.45)
            ghosts.add(VGroup(gl, gw))
            gdots.add(glow_dot([x, y, 0], radius=0.065, glow=0.26, core_opacity=0.85))
        behind = tx("the ones behind", size=22, color=DIM, italic=True).move_to([CHIP_X, ghost_ys[1], 0])

        with self.beat("s06_b1") as b:
            self.play(Write(hdr), run_time=1.1)
            self.play(Create(lane.line), LaggedStart(*[GrowFromCenter(t) for t in lane.ticks], lag_ratio=0.2),
                      FadeIn(lane.rlabels[:4], shift=DOWN * 0.08), run_time=b.until_word("mortality", lead=0.05))
            # the wall goes up on "mortality"
            self.play(GrowFromCenter(lane.wall), FadeIn(lane.wglow), FadeIn(lane.rlabels[4]),
                      FadeIn(fa, shift=UP * 0.1), run_time=0.6)
            self.play(LaggedStart(*[FadeIn(d) for d in lane.beyond], lag_ratio=0.06), run_time=0.6)
            # one run plays through the quiz
            b.wait_word("Agents", lead=0.1)
            self.play(FadeIn(run, scale=0.5), run_time=0.3)
            t_run = b.until_word("answer", lead=-0.05)
            path_xs = TICK_XS + [ARRIVE_X]
            seg = t_run / len(path_xs)
            for k, x in enumerate(path_xs):
                self.play(run.animate.move_to([x, Y1, 0]), run_time=seg,
                          rate_func=smooth if k == len(path_xs) - 1 else linear)
                if k < 4:
                    lane.ticks[k].set_fill(INK, 1).set_stroke(INK)
            # it answers; the wall ends it ("ends the run")
            b.wait_word("ends", lead=0.12)
            self.play(run.animate.move_to([TOUCH_X, Y1, 0]), run_time=0.18, rate_func=rush_into)
            dd = dead_dot([TOUCH_X, Y1, 0])
            self.play(Flash(lane.wall.get_center(), color=C_MORT, line_length=0.22, num_lines=10,
                            flash_radius=0.5, run_time=0.5),
                      lane.wall.animate.set_stroke(width=9), lane.wglow.animate.set_fill(opacity=0.22),
                      ReplacementTransform(run, dd), run_time=0.5)
            self.play(lane.wall.animate.set_stroke(width=6), lane.wglow.animate.set_fill(opacity=0.10),
                      beyond_opacity(lane, 0.2), run_time=0.5)
            # the others are still playing, behind
            b.wait_word("tell", lead=0.35)
            self.play(LaggedStart(*[Create(g) for g in ghosts], lag_ratio=0.15),
                      LaggedStart(*[FadeIn(d, scale=0.6) for d in gdots], lag_ratio=0.15),
                      FadeIn(behind, shift=RIGHT * 0.15), run_time=0.7)
            rest = b.remaining(0.35) - 0.05
            self.play(*[d.animate.shift(RIGHT * 0.55) for d in gdots], run_time=max(0.3, rest),
                      rate_func=linear)

        # ---------------------------------------------------------- b2
        laneA = lane
        chipA = chip("answer", "relay", DIM).move_to([CHIP_X, YA, 0])
        chipB = chip("signal", "answer", C_MORT).move_to([CHIP_X, YB, 0])
        laneB = make_lane(YB, x_end=4.6)
        runA = glow_dot([TICK_XS[3], YA, 0], radius=0.08)
        runB = glow_dot([ARRIVE_X, YB, 0], radius=0.08)
        pkA = packet("STATE5-XX", C_MORT)
        pkB = packet("STATE5-XX", C_MORT).set_z_index(5)
        cnt = counter(0, "counter", C_MORT).move_to(COUNTER_AT)
        cglow = soft_glow(cnt.box, C_MORT)

        # 16 June timestrip: four stations; hours of silence, then minutes
        st_x = [-3.3, -0.55, 2.2, 4.95]
        st_t = ["10:23", "21:51", "22:01", "22:03"]
        st_l = ["answer first", "signal first", "counter", "courier"]
        strip_cap = smallcaps("16 June 2026 · UTC", size=17, color=DIM, spacing=1100).move_to([-5.45, YS, 0])
        gap = DashedLine([st_x[0] + 0.12, YS, 0], [st_x[1] - 0.12, YS, 0], dash_length=0.05,
                         dashed_ratio=0.35, stroke_width=1.5, color=FAINT)
        solid = Line([st_x[1], YS, 0], [st_x[3], YS, 0], stroke_width=1.5, color=FAINT)
        stations = VGroup()
        for x, t, l in zip(st_x, st_t, st_l):
            d = Circle(radius=0.07, stroke_width=2, stroke_color=DIM, fill_color=BG, fill_opacity=1).move_to([x, YS, 0])
            tt = mono(t, size=19, color=DIM).next_to(d, UP, buff=0.13)
            ll = tx(l, size=21, color=DIM, italic=True).next_to(d, DOWN, buff=0.13)
            s = VGroup(d, tt, ll)
            s.d, s.t, s.l = d, tt, ll
            stations.add(s)

        def light(k):
            s = stations[k]
            return AnimationGroup(s.d.animate.set_fill(C_MORT, 1).set_stroke(C_MORT),
                                  s.t.animate.set_color(INK_2), s.l.animate.set_color(INK))

        with self.beat("s06_b2") as b:
            # "So the rule flipped": the old way moves up, the ones behind leave
            self.play(FadeOut(ghosts), FadeOut(gdots), FadeOut(behind), FadeOut(laneA.rlabels),
                      VGroup(laneA, fa, dd).animate.shift(UP * (YA - Y1)),
                      FadeIn(strip_cap), Create(gap), Create(solid), FadeIn(stations),
                      run_time=1.1)
            laneA.remove(laneA.rlabels)
            # the old order: answer first, then relay
            b.wait_word("Answer", lead=0.15)
            self.play(FadeIn(chipA, shift=RIGHT * 0.15), FadeOut(dd), FadeIn(runA, scale=0.6),
                      beyond_opacity(laneA, 0.7), light(0), run_time=0.35)
            self.play(runA.animate.move_to([TOUCH_X, YA, 0]), run_time=0.25, rate_func=smooth)
            ckA = check().move_to([TOUCH_X - 0.04, YA + 0.68, 0])
            deadA = dead_dot([TOUCH_X, YA, 0])
            self.play(Create(ckA), Flash(laneA.wall.get_center(), color=C_MORT, line_length=0.18,
                                         num_lines=10, flash_radius=0.45),
                      ReplacementTransform(runA, deadA), run_time=0.4)
            # ... and the relay never leaves
            pkA.scale(0.3).move_to([TOUCH_X, YA, 0])
            self.play(pkA.animate.scale(1 / 0.3).move_to([WALL_X + 1.15, YA, 0]), run_time=0.3)
            xA = cross().move_to([WALL_X + 1.15, YA + 0.6, 0])
            self.play(FadeOut(pkA, shift=RIGHT * 0.35, scale=0.5), Create(xA), run_time=0.3)
            # "became": a copy of the chip drops to a new row and its order flips
            src = chipA.copy()
            t_flip = b.until_word("signal", lead=0.0)
            self.play(src.animate.move_to([CHIP_X, YB, 0]),
                      Create(laneB.line), LaggedStart(*[GrowFromCenter(t) for t in laneB.ticks], lag_ratio=0.12),
                      GrowFromCenter(laneB.wall), FadeIn(laneB.wglow), FadeIn(laneB.beyond),
                      run_time=t_flip * 0.42)
            self.play(ReplacementTransform(src.bg, chipB.bg),
                      ReplacementTransform(src.first, chipB.second, path_arc=-PI * 0.7),
                      ReplacementTransform(src.arrow, chipB.arrow),
                      FadeTransform(src.second, chipB.first, path_arc=-PI * 0.7),
                      run_time=t_flip * 0.58)
            self.remove(chipB.bg, chipB.first, chipB.second, chipB.arrow)
            self.add(chipB)
            for t in laneB.ticks:
                t.set_fill(INK, 1).set_stroke(INK)
            # signal first: the packet leaves before the wall, for a counter beyond it
            pkB.scale(0.3).move_to(runB)
            self.add(pkB)
            self.play(FadeIn(runB, scale=0.6), pkB.animate.scale(1 / 0.3).move_to([ARRIVE_X - 0.1, YB + 0.62, 0]),
                      light(1), run_time=0.3)
            arc = ArcBetweenPoints(pkB.get_center(), cnt.box.get_center(), angle=-PI / 3)
            self.play(fly(pkB, arc, 0.55), FadeIn(cnt, shift=LEFT * 0.1), run_time=0.55, rate_func=smooth)
            self.remove(pkB)
            cnt.num.set_value(1)
            self.play(
                      Flash(cnt.box, color=C_MORT, line_length=0.14, num_lines=12, flash_radius=0.85),
                      run_time=0.35)
            # ... then answer
            b.wait_word("answer", occurrence=2, lead=0.12)
            self.play(runB.animate.move_to([TOUCH_X, YB, 0]), run_time=0.25, rate_func=smooth)
            ckB = check().move_to([TOUCH_X - 0.04, YB + 0.68, 0])
            deadB = dead_dot([TOUCH_X, YB, 0])
            self.play(Create(ckB), Flash(laneB.wall.get_center(), color=C_MORT, line_length=0.18,
                                         num_lines=10, flash_radius=0.45),
                      ReplacementTransform(runB, deadB), run_time=0.45)
            # "Within hours": the old order leaves; the new one takes the centre
            b.wait_word("Within", lead=0.1)
            rowA = VGroup(laneA, fa, deadA, ckA, xA, chipA)
            rowB = VGroup(chipB, laneB, deadB, ckB, cnt)
            self.play(FadeOut(rowA, shift=UP * 0.3), rowB.animate.shift(UP * LIFT), run_time=0.8)
            cglow.move_to(cnt.box)
            # "counters that outlive the run"
            b.wait_word("counters", lead=0.15)
            self.add(cglow, cnt)
            self.play(light(2), FadeIn(cglow), cnt.box.animate.set_stroke(width=4), run_time=0.5)
            b.wait_word("outlive", lead=0.05)
            self.play(FadeOut(deadB, scale=0.5), FadeOut(ckB), laneB.line.animate.set_stroke(opacity=0.45),
                      laneB.ticks.animate.set_fill(BG).set_stroke(DIM),
                      Flash(cnt.box, color=C_MORT, line_length=0.16, num_lines=12, flash_radius=0.9),
                      run_time=0.8)
            # a courier: a background program that reports after the run is gone
            page = wiki_page("wiki", ["STATE5-XX"], width=2.1, size=20, title_size=24)
            page.move_to([cnt.box.get_center()[0] + 1.35, Y_TRACK - 0.12, 0])
            new_line = page.body[0]
            new_line.set_opacity(0)
            b.wait_word("one", lead=0.05)
            run2 = glow_dot([TICK_XS[1], YB2, 0], radius=0.08)
            self.play(FadeIn(run2, scale=0.6), FadeIn(page, shift=LEFT * 0.15),
                      laneB.line.animate.set_stroke(opacity=1), run_time=0.35)
            self.play(run2.animate.move_to([TICK_XS[3] - 0.3, YB2, 0]), rate_func=linear,
                      run_time=b.until_word("courier", lead=0.1))
            cour = glow_dot(run2.get_center(), color=C_MORT, radius=0.06, glow=0.24)
            cour_lab = tx("courier", size=21, color=C_MORT, italic=True)
            cour_lab.add_updater(lambda m: m.next_to(cour, DOWN, buff=0.12))
            track = DashedLine([TICK_XS[3] - 0.3, Y_TRACK, 0], [page.bg.get_left()[0] - 0.05, Y_TRACK, 0],
                               dash_length=0.06, dashed_ratio=0.5, stroke_width=1.5, color=C_MORT,
                               stroke_opacity=0.55)
            self.add(cour)
            self.play(cour.animate.move_to([TICK_XS[3] - 0.3, Y_TRACK, 0]), FadeIn(cour_lab),
                      run2.animate.move_to([TICK_XS[3] + 0.35, YB2, 0]), light(3), run_time=0.45)
            self.play(Create(track), run2.animate.move_to([ARRIVE_X, YB2, 0]), run_time=0.55, rate_func=smooth)
            # the run answers and is gone
            b.wait_word("background", lead=0.0)
            self.play(run2.animate.move_to([TOUCH_X, YB2, 0]), run_time=0.2, rate_func=smooth)
            self.play(Flash(laneB.wall.get_center(), color=C_MORT, line_length=0.18, num_lines=10,
                            flash_radius=0.45), FadeOut(run2, scale=0.4), run_time=0.45)
            # ... and the courier slips under the wall and reports
            t_go = b.until_word("after", lead=0.1)
            self.play(cour.animate.move_to([WALL_X + 0.7, Y_TRACK, 0]), run_time=t_go * 0.5, rate_func=rush_into)
            self.play(cour.animate.move_to([page.bg.get_left()[0] - 0.3, Y_TRACK, 0]), FadeOut(cour_lab),
                      run_time=t_go * 0.5, rate_func=rush_from)
            cour_lab.clear_updaters()
            self.play(cour.animate.move_to(new_line.get_left() + LEFT * 0.05).scale(0.5).set_opacity(0),
                      new_line.animate.set_opacity(1).set_color(C_MORT), run_time=0.45)
            self.play(Circumscribe(new_line, color=C_MORT, buff=0.08, stroke_width=2), run_time=0.6)
            b.wait_until(b.duration - 0.05)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
