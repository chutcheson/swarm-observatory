import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

WORDS = ["pooling", "common", "compression", "mortality", "trust", "discovery"]


def field_of_runs(n=46, seed=11, x_lim=6.3, y_lim=3.3, min_d=0.85):
    """Agent runs scattered over the frame, plus the message lines between near neighbours."""
    rng = np.random.default_rng(seed)
    pts = []
    tries = 0
    while len(pts) < n and tries < 5000:
        tries += 1
        p = np.array([rng.uniform(-x_lim, x_lim), rng.uniform(-y_lim, y_lim), 0.0])
        if all(np.linalg.norm(p - q) > min_d for q in pts):
            pts.append(p)
    dots = VGroup(*[glow_dot(p, radius=0.055, glow=0.24) for p in pts])
    hues = [c for (_, _, _, c) in PROBLEMS]
    lines = VGroup()
    for i, p in enumerate(pts):
        near = sorted(range(len(pts)), key=lambda j: np.linalg.norm(pts[j] - p))[1:3]
        for j in near:
            if j > i or i not in sorted(range(len(pts)), key=lambda k: np.linalg.norm(pts[k] - pts[j]))[1:3]:
                ln = Line(p, pts[j], stroke_width=1.2, color=hues[(i + j) % 6], stroke_opacity=0.35)
                lines.add(ln)
    return dots, lines


class S10Close(SwarmScene):
    def construct(self):
        cards = [problem_card(n) for n in range(1, 7)]
        grid = problem_grid(cards).move_to([0, -0.2, 0])
        title = tx("Six meta-problems", size=46, color=INK).move_to([0, 2.95, 0])
        sub = MarkupText(f'that any group <span foreground="{C_REWARD}">rewarded together</span> must solve',
                         font=SERIF, font_size=26, color=DIM, slant=ITALIC).next_to(title, DOWN, buff=0.2)

        cav_txt = ["proposed", "helpfulness is an alternative", "next: tell them apart"]
        cav1 = VGroup(tx("proposed", size=24, color=INK_2, italic=True),
                      MathTex(r"\neq", color=INK_2, font_size=34),
                      tx("used", size=24, color=INK_2, italic=True)).arrange(RIGHT, buff=0.14)
        cav2 = tx("helpfulness is an alternative", size=24, color=INK_2, italic=True)
        cav3 = tx("next: tell them apart", size=24, color=INK_2, italic=True)
        cavs = VGroup(cav1, cav2, cav3).arrange(RIGHT, buff=1.1).move_to([0, -2.8, 0])
        seps = VGroup(*[tx("·", size=28, color=DIM).move_to((cavs[i].get_right() + cavs[i + 1].get_left()) / 2)
                        for i in range(2)])

        dots, lines = field_of_runs()

        with self.beat("s10_b1") as b:
            for n, w in enumerate(WORDS):
                b.wait_word(w, lead=0.15)
                self.play(FadeIn(cards[n], shift=UP * 0.2, scale=0.96), run_time=0.4)
            b.wait_word("six", lead=0.1)
            self.play(Write(title), run_time=0.7)
            b.wait_word("that", lead=0.1)
            self.play(FadeIn(sub, shift=UP * 0.1), run_time=0.5)

        with self.beat("s10_b2") as b:
            b.wait_word("proposed", lead=0.2)
            self.play(FadeIn(cav1, shift=UP * 0.1), run_time=0.4)
            b.wait_word("helpfulness", lead=0.2)
            self.play(FadeIn(seps[0]), FadeIn(cav2, shift=UP * 0.1), run_time=0.4)
            b.wait_word("separating", lead=0.1)
            self.play(FadeIn(seps[1]), FadeIn(cav3, shift=UP * 0.1), run_time=0.4)
            # But the problems are real
            b.wait_word("real", lead=0.2)
            self.play(LaggedStart(*[ShowPassingFlash(c.bg.copy().set_fill(opacity=0).set_stroke(c.pcolor, width=4), time_width=0.6)
                                    for c in cards], lag_ratio=0.08), run_time=0.9)
            # and these agents kept solving them
            b.wait_word("agents", lead=0.1)
            self.play(grid.animate.set_opacity(0.12), FadeOut(VGroup(title, sub, cavs, seps)),
                      LaggedStart(*[FadeIn(d, scale=0.5) for d in dots], lag_ratio=0.02),
                      run_time=0.9)
            self.play(Create(lines, lag_ratio=0.02),
                      LaggedStart(*[ShowPassingFlash(l.copy().set_stroke(width=3, opacity=1), time_width=0.5)
                                    for l in lines], lag_ratio=0.03), run_time=max(0.4, b.remaining(pad=0.3)))

        # end card
        end_t = tx("Notes for the Ones Behind", size=56, color=INK)
        end_s = smallcaps("Swarm Observatory", size=22, color=C_REWARD, spacing=1600)
        end_c = tx("Data: Nightingale wiki archive, June 2026 · quotes verbatim, handles self-chosen",
                   size=20, color=DIM, italic=True)
        end = VGroup(end_t, end_s, end_c).arrange(DOWN, buff=0.35).move_to([0, 0.1, 0])
        end_c.shift(DOWN * 0.35)
        # clear the runs and lines behind the card; the rest stay as a dim field
        x0, x1 = end.get_left()[0] - 0.5, end.get_right()[0] + 0.5
        y0, y1 = end.get_bottom()[1] - 0.45, end.get_top()[1] + 0.45

        def inside(pt):
            return x0 < pt[0] < x1 and y0 < pt[1] < y1

        def crosses(ln):
            a_, b_ = ln.get_start(), ln.get_end()
            return any(inside(a_ + (b_ - a_) * t) for t in np.linspace(0, 1, 25))

        hide = VGroup(*[d for d in dots if inside(d.get_center())], *[l for l in lines if crosses(l)])
        keep_dots = VGroup(*[d for d in dots if not inside(d.get_center())])
        keep_lines = [l for l in lines if not crosses(l)]
        # end card: 0.6 s in, 2 s hold, 0.8 s to black (3.4 s after the last beat)
        self.play(FadeOut(grid), FadeOut(hide), keep_dots.animate.fade(0.6),
                  VGroup(*keep_lines).animate.set_stroke(opacity=0.12),
                  FadeIn(end_t, shift=UP * 0.1), FadeIn(end_s, shift=UP * 0.1), FadeIn(end_c, shift=UP * 0.1),
                  run_time=0.6)
        self.play(LaggedStart(*[ShowPassingFlash(l.copy().set_stroke(width=2.5, opacity=0.6), time_width=0.4)
                                for l in keep_lines], lag_ratio=0.05), run_time=2.0)
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.8)
