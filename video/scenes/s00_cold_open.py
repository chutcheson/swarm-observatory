import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

DATA = json.loads((Path(__file__).resolve().parents[1] / "data" / "daily_saves.json").read_text())
QUOTE = ("When round #5 arrives, answer first, then immediately add compact token "
         "STATE5-XX here (postal code). Pollers: search for STATE5-.")


class S00ColdOpen(SwarmScene):
    def construct(self):
        counts, days = DATA["counts"], DATA["days"]
        n = len(counts)
        x0, x1, y0 = -5.6, 5.6, -2.9
        w = (x1 - x0) / n
        hmax = 5.0
        axis = Line([x0 - 0.1, y0, 0], [x1 + 0.1, y0, 0], stroke_width=2, color=FAINT)
        bars = VGroup()
        for i, c in enumerate(counts):
            h = max(hmax * c / max(counts), 0.001)
            r = Rectangle(width=w * 0.72, height=h, stroke_width=0, fill_color=C_POOL, fill_opacity=0.85)
            r.move_to([x0 + w * (i + 0.5), y0 + h / 2, 0])
            bars.add(r)
        dlabels = VGroup()
        for d, txt in (("2026-05-24", "24 May"), ("2026-06-16", "16 June"), ("2026-07-02", "2 July")):
            i = days.index(d)
            t = tx(txt, size=20, color=DIM, italic=True).move_to([x0 + w * (i + 0.5), y0 - 0.32, 0])
            dlabels.add(t)
        cap = smallcaps("saves per day · four German wikis", size=16).to_corner(UL, buff=0.5)
        total = Integer(0, font_size=64, color=INK, group_with_commas=True)
        total.set_stroke(width=0)
        tot_lab = tx("edits", size=30, color=DIM, italic=True)
        total.move_to([3.4, 2.9, 0], aligned_edge=LEFT)
        tot_lab.next_to(total, DOWN, buff=0.12, aligned_edge=LEFT)
        tot = VGroup(total, tot_lab)

        with self.beat("s00_b1") as b:
            self.play(Create(axis), FadeIn(cap, shift=RIGHT * 0.2), FadeIn(dlabels), run_time=1.0)
            self.add(tot)
            t_grow = b.until_word("edits", lead=-0.2)
            self.play(LaggedStart(*[GrowFromEdge(r, DOWN) for r in bars], lag_ratio=0.04, run_time=t_grow),
                      ChangeDecimalToValue(total, DATA["total"], run_time=t_grow, rate_func=smooth))
            # a few agents lift out of the bloom; they talk only through the wiki
            peak = [days.index(d) for d in ("2026-06-16", "2026-06-17", "2026-06-18", "2026-06-20", "2026-06-21", "2026-06-22")]
            hub_c = np.array([0.0, 0.9, 0])
            hub = wiki_page("wiki", ["R4 = …", "R5 due 13:39", "STATE5-?"], width=1.9, size=13, title_size=20)
            hub.move_to(hub_c)
            rng = np.random.default_rng(7)
            dots, homes = VGroup(), []
            for k in range(9):
                i = peak[k % len(peak)]
                src = bars[i].get_top() + DOWN * rng.uniform(0.1, 0.6) * bars[i].height
                ang = PI / 2 + TAU * k / 9 + rng.uniform(-0.15, 0.15)
                dst = hub_c + np.array([3.6 * np.cos(ang), 1.75 * np.sin(ang), 0])
                dots.add(glow_dot(src, radius=0.06, glow=0.26))
                homes.append(dst)
            b.wait_word("notes", lead=0.4)
            self.play(bars.animate.set_fill(opacity=0.18), FadeIn(dots, scale=0.5),
                      total.animate.set_opacity(0.5), tot_lab.animate.set_opacity(0.5), run_time=0.5)
            self.play(*[d.animate.move_to(h) for d, h in zip(dots, homes)], FadeIn(hub, scale=0.9),
                      run_time=1.2, rate_func=smooth)
            spokes = VGroup(*[Line(d.get_center(), hub.get_center(), buff=0.0, stroke_width=1.3, color=INK_2,
                                   stroke_opacity=0.45) for d in dots])
            for sp, d in zip(spokes, dots):
                sp.put_start_and_end_on(d.get_center(), hub.bg.get_boundary_point(d.get_center() - hub.get_center()))
            self.play(LaggedStart(*[Create(sp) for sp in spokes], lag_ratio=0.08, run_time=b.until_word("never", lead=0.1)))
            self.play(LaggedStart(*[ShowPassingFlash(sp.copy().set_stroke(C_POOL, width=3, opacity=1), time_width=0.5)
                                    for sp in spokes], lag_ratio=0.1, run_time=1.3))
            self.add(dots)

        card = quote_card(QUOTE, sig="SectorAgentJun20X", color=C_TIME, width=40, size=27,
                          header="dse wiki · 16 June 2026, 10:23 UTC")
        card.move_to(UP * 0.2)
        af = find_chars(card.body, QUOTE, "answer first")
        tok = find_chars(card.body, QUOTE, "STATE5-XX")
        with self.beat("s00_b2") as b:
            self.play(FadeOut(VGroup(bars, axis, dlabels, cap, dots, spokes, hub, tot)), run_time=0.5)
            self.play(FadeIn(card.bg, card.bar, card.header, shift=UP * 0.15), run_time=0.4)
            self.play(Write(card.body, run_time=b.until_word("answer", lead=0.05), rate_func=linear))
            self.play(Create(underline(af, C_TIME)), af.animate.set_color(C_TIME), run_time=0.4)
            self.play(FadeIn(card.sig, shift=LEFT * 0.1), run_time=0.3)
            b.wait_word("token", lead=0.1)
            self.play(Create(highlight_box(tok, C_CHAN)), tok.animate.set_color(C_CHAN), run_time=0.45)
            b.wait_until(b.duration - 0.05)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
