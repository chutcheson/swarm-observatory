import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *


# ---------------------------------------------------------------- local helpers
class Halo(VGroup):
    """A soft disc of colour behind a run dot (the habit). set_level(0..1) scales it."""

    def __init__(self, point=ORIGIN, color=C_REWARD, radius=0.62, peak=0.065, layers=32, level=1.0, **kw):
        super().__init__(**kw)
        self.base = []
        for k in range(layers, 0, -1):
            self.add(Circle(radius=radius * (k / layers) ** 0.9, stroke_width=0,
                            fill_color=color, fill_opacity=peak))
            self.base.append(peak)
        self.move_to(point)
        self.set_level(level)

    def set_level(self, level):
        self.level = level
        for c, b in zip(self.submobjects, self.base):
            c.set_fill(opacity=b * level)
        return self


def run_dot(p):
    return glow_dot(p, radius=0.09, glow=0.38)


def training_box(center, w=5.2, h=3.7, ring_r=1.05, halo_level=0.0):
    """The training room: a rounded box with four runs in a ring."""
    box = RoundedRectangle(corner_radius=0.3, width=w, height=h, stroke_width=2,
                           stroke_color=DIM, fill_color=FAINTER, fill_opacity=1).move_to(center)
    lab = tx("training", size=28, italic=True, color=DIM)
    lab.next_to(box, UP, buff=0.16).align_to(box, LEFT).shift(RIGHT * 0.22)
    ring = Circle(radius=ring_r, stroke_width=1.5, color=FAINT).move_to(center)
    pts = [center + ring_r * np.array([np.cos(a), np.sin(a), 0]) for a in (PI / 4, 3 * PI / 4, 5 * PI / 4, 7 * PI / 4)]
    halos = VGroup(*[Halo(p, level=halo_level) for p in pts])
    dots = VGroup(*[run_dot(p) for p in pts])
    g = VGroup(box, lab, ring, halos, dots)
    g.box, g.lab, g.ring, g.halos, g.dots, g.pts = box, lab, ring, halos, dots, pts
    return g


class S01Hypothesis(SwarmScene):
    def construct(self):
        title = smallcaps("Working hypothesis", size=30, color=C_REWARD, spacing=1600).move_to(UP * 3.35)

        # ------------------------------------------------------------ b1
        C1 = np.array([0.0, -0.55, 0])
        tb = training_box(C1)
        plus = MathTex("+1", font_size=64, color=C_REWARD).move_to(UP * 2.3)
        with self.beat("s01_b1") as b:
            b.wait_word("working", lead=0.15)
            self.play(FadeIn(title, shift=DOWN * 0.15), run_time=0.8)
            b.wait_word("labs", lead=0.1)
            self.play(FadeIn(tb.box, scale=0.96), FadeIn(tb.lab, shift=RIGHT * 0.1), run_time=b.until_word("models"))
            self.add(tb.halos)
            self.play(Create(tb.ring),
                      LaggedStart(*[FadeIn(d, scale=0.4) for d in tb.dots], lag_ratio=0.3),
                      run_time=b.until_word("groups", lead=-0.45))
            b.wait_word("rewarded", lead=0.15)
            self.play(FadeIn(plus, shift=DOWN * 0.35), run_time=0.3)
            self.play(plus.animate.move_to(C1), run_time=b.until_word("group", occurrence=2, lead=0.1),
                      rate_func=rate_functions.ease_in_out_sine)
            # split into four: one for every run in the group
            minis = VGroup(*[plus.copy() for _ in range(4)])
            self.remove(plus)
            self.add(minis)
            self.play(*[m.animate.scale(0.6).move_to(p) for m, p in zip(minis, tb.pts)],
                      run_time=0.55, rate_func=smooth)
            self.play(*[FadeOut(m, scale=0.4) for m in minis],
                      *[h.animate.set_level(1.0) for h in tb.halos],
                      run_time=0.45)
            self.play(*[h.animate.set_level(0.45) for h in tb.halos], run_time=0.5)

        # ------------------------------------------------------------ b2
        cols = {}
        y_dot, y0 = 0.12, -1.55
        for side, cx, head, tex, hcol in (("L", -3.5, "individual reward", r"R_i = r_i", INK_2),
                                          ("R", 3.5, "group reward", r"R_i = \sum_j r_j", C_REWARD)):
            h = tx(head, size=34, italic=True, color=hcol).move_to([cx, 2.68, 0])
            eq = MathTex(tex, font_size=52, color=INK)
            eq.shift(UP * (1.78 - eq[0][0].get_center()[1]))
            eq.set_x(cx)
            pi_, pj = np.array([cx - 1.25, y_dot, 0]), np.array([cx + 1.25, y_dot, 0])
            di, dj = run_dot(pi_), run_dot(pj)
            li = MathTex("i", font_size=40, color=INK_2).move_to(pi_ + LEFT * 0.5)
            lj = MathTex("j", font_size=40, color=INK_2).move_to(pj + RIGHT * 0.5 + DOWN * 0.04)
            arr = Arrow(pi_, pj, buff=0.36, stroke_width=3, color=INK_2, tip_length=0.2)
            helps = tx("helps", size=24, italic=True, color=DIM).next_to(arr, UP, buff=0.08)
            base = Line([cx - 2.0, y0, 0], [cx + 2.0, y0, 0], stroke_width=2, color=FAINT)
            red = Rectangle(width=0.6, height=0.7, stroke_width=0, fill_color=C_MORT, fill_opacity=0.9)
            red.move_to([pi_[0], y0 - 0.35, 0])
            blue = Rectangle(width=0.6, height=1.1, stroke_width=0, fill_color=C_POOL, fill_opacity=0.9)
            blue.move_to([pj[0], y0 + 0.55, 0])
            lc = MathTex("-c", font_size=44, color=C_MORT).next_to(red, LEFT, buff=0.2)
            lb = MathTex("+b", font_size=44, color=C_POOL).next_to(blue, RIGHT, buff=0.2)
            cols[side] = dict(h=h, eq=eq, di=di, dj=dj, li=li, lj=lj, arr=arr, helps=helps,
                              base=base, red=red, blue=blue, lc=lc, lb=lb, cx=cx)

        L, R = cols["L"], cols["R"]
        bl = L["blue"]
        cross = VGroup(Line(bl.get_corner(DL) + LEFT * 0.1, bl.get_corner(UR) + RIGHT * 0.1),
                       Line(bl.get_corner(UL) + LEFT * 0.1, bl.get_corner(DR) + RIGHT * 0.1)).set_stroke(INK_2, 3.5)
        netL = MathTex(r"\Delta R_i", "=", "-c", font_size=48, color=INK).move_to([L["cx"], -2.8, 0])
        netL[2].set_color(C_MORT)
        netR = MathTex(r"\Delta R_i", "=", "b - c", ">", "0", font_size=48, color=INK).move_to([R["cx"], -2.8, 0])
        pays = tx("helping pays", size=32, italic=True, color=C_REWARD).move_to([R["cx"], -3.4, 0])
        divider = Line([0, 2.85, 0], [0, -3.3, 0], stroke_width=1.5, color=FAINT)

        def act(c):
            return [FadeIn(c["di"], scale=0.5), FadeIn(c["dj"], scale=0.5), FadeIn(c["li"]), FadeIn(c["lj"]),
                    GrowArrow(c["arr"]), FadeIn(c["helps"], shift=UP * 0.05)]

        def colgroup(c):
            return VGroup(*[c[k] for k in ("h", "eq", "di", "dj", "li", "lj", "arr", "helps",
                                           "base", "red", "blue", "lc", "lb")])

        C2 = np.array([-3.55, -0.5, 0])
        tb2 = training_box(C2, halo_level=0.12)
        boundary = DashedLine([0, 2.4, 0], [0, -3.0, 0], dash_length=0.12, stroke_width=2, color=DIM)
        dep = tx("deployment", size=28, italic=True, color=DIM)
        dep.move_to([0, tb2.lab.get_center()[1], 0]).align_to(boundary, LEFT).shift(RIGHT * 0.4)
        dest = np.array([3.55, -0.5, 0])

        with self.beat("s01_b2") as b:
            self.play(FadeOut(VGroup(tb.box, tb.lab, tb.ring, tb.halos, tb.dots)), run_time=0.4)
            self.play(FadeIn(L["h"], shift=DOWN * 0.12), run_time=b.until_word("reward", lead=0.1))
            self.play(Write(L["eq"]), run_time=b.until_word("helping", lead=0.05))
            self.play(*act(L), run_time=b.until_word("costs", lead=0.05))
            self.play(Create(L["base"]), GrowFromEdge(L["red"], UP), FadeIn(L["lc"], shift=LEFT * 0.08),
                      run_time=0.55)
            b.wait_word("earns", lead=0.2)
            self.play(GrowFromEdge(L["blue"], DOWN), FadeIn(L["lb"], shift=RIGHT * 0.08), run_time=0.45)
            self.play(L["blue"].animate.set_fill(DIM, 0.25), L["lb"].animate.set_color(DIM),
                      Create(cross), run_time=0.45)
            self.play(Write(netL), run_time=b.until_word("under", occurrence=2, lead=0.0))

            self.play(Create(divider), FadeIn(R["h"], shift=DOWN * 0.12), run_time=b.until_word("reward", 2, lead=0.15))
            self.play(Write(R["eq"]), *act(R), run_time=b.until_word("their", lead=0.0))
            self.play(Create(R["base"]), GrowFromEdge(R["red"], UP), FadeIn(R["lc"], shift=LEFT * 0.08),
                      run_time=b.until_word("is", lead=0.0))
            self.play(GrowFromEdge(R["blue"], DOWN), FadeIn(R["lb"], shift=RIGHT * 0.08),
                      run_time=b.until_word("yours", lead=0.0))
            self.play(Write(netR), run_time=b.until_word("so helping", lead=-0.15))
            self.play(netR[2:].animate.set_color(C_REWARD), run_time=0.3)
            b.wait_word("pays", lead=0.2)
            self.play(FadeIn(pays, shift=UP * 0.12), run_time=0.45)

            b.wait_word("train", lead=0.0)
            self.play(FadeOut(VGroup(colgroup(L), colgroup(R), cross, netL, netR, pays, divider)), run_time=0.4)
            self.play(FadeIn(VGroup(tb2.box, tb2.lab, tb2.ring, tb2.halos, tb2.dots)), run_time=0.4)
            # training: the group reward keeps landing, and the habit deepens
            self.play(*[h.animate.set_level(0.85) for h in tb2.halos], run_time=0.25)
            self.play(*[h.animate.set_level(0.3) for h in tb2.halos], run_time=0.25)
            self.play(*[h.animate.set_level(0.95) for h in tb2.halos], run_time=0.25)
            self.play(*[h.animate.set_level(0.5) for h in tb2.halos], Create(boundary),
                      FadeIn(dep, shift=LEFT * 0.1), run_time=b.until_word("habit", lead=0.0))
            # one run leaves training, and keeps its halo
            mover = VGroup(tb2.halos[3], tb2.dots[3])
            path = ArcBetweenPoints(tb2.pts[3], dest, angle=-PI / 5)
            self.play(MoveAlongPath(mover, path), run_time=b.until_word("model", lead=-0.25),
                      rate_func=rate_functions.ease_in_out_sine)

        # ------------------------------------------------------------ b3
        rng = np.random.default_rng(11)
        pts = []
        while len(pts) < 17:
            p = np.array([rng.uniform(-6.2, 6.2), rng.uniform(-3.2, 3.2), 0])
            if abs(p[1]) < 0.9 and abs(p[0]) < 4.8:
                continue           # leave a band for the question
            if any(np.linalg.norm(p - q) < 1.35 for q in pts):
                continue
            pts.append(p)
        lens_path = VMobject().set_points_smoothly([np.array(q) for q in
                                                    ((-5.6, 1.5, 0), (-3.4, 2.35, 0), (-0.9, 1.75, 0),
                                                     (1.6, 2.4, 0), (3.6, 1.75, 0), (4.8, 0.6, 0))])
        # a few runs sit right on the lens path: those are the fossils it finds
        fossil_t = (0.12, 0.42, 0.66, 0.93)
        fpts = [lens_path.point_from_proportion(t) + np.array([0.0, s, 0])
                for t, s in zip(fossil_t, (-0.1, 0.12, -0.08, 0.05))]
        pts = [p for p in pts if all(np.linalg.norm(p - q) > 1.0 for q in fpts)] + fpts
        crowd = VGroup(*[run_dot(p).fade(0.5) for p in pts])
        fossils = VGroup(*[Halo(p, level=0.0) for p in fpts])
        lens = problem_icon(6, color=INK_2, s=1.25)
        lens[0].set_fill(INK, 0.05)
        lens_t = ValueTracker(0.0)
        lens.add_updater(lambda m: m.shift(lens_path.point_from_proportion(lens_t.get_value()) - m[0].get_center()))
        lens.update()

        def reveal(p):
            def upd(m):
                d = np.linalg.norm(lens[0].get_center() - p)
                lvl = float(np.clip(1.35 - d / 0.6, 0, 1)) * 0.85
                if lvl > m.level:
                    m.set_level(lvl)
            return upd

        question = tx("What problem does it solve?", size=52, italic=True, color=INK)

        with self.beat("s01_b3") as b:
            last = fpts[-1]
            self.play(FadeOut(VGroup(title, tb2.box, tb2.lab, tb2.ring, tb2.halos[:3], tb2.dots[:3], boundary, dep)),
                      mover[0].animate.set_level(0.0), mover[1].animate.move_to(last).fade(0.5),
                      FadeIn(crowd[:-1], lag_ratio=0.05), run_time=b.until_word("fossils", lead=0.3))
            self.remove(mover)
            self.add(fossils, crowd)
            for h, p in zip(fossils, fpts):
                h.add_updater(reveal(p))
            self.play(FadeIn(lens, scale=0.8), run_time=0.3)
            self.play(lens_t.animate.set_value(1.0), run_time=b.until_word("what", lead=0.45),
                      rate_func=rate_functions.ease_in_out_sine)
            for h in fossils:
                h.clear_updaters()
            lens.clear_updaters()
            self.play(FadeOut(lens), crowd.animate.fade(0.5), *[h.animate.set_level(0.3) for h in fossils],
                      run_time=0.4)
            self.play(Write(question), run_time=b.until_word("solve", lead=-0.2))
            b.wait_until(b.duration - 0.05)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
