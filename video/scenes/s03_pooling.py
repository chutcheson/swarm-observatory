import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

# verbatim (research/quotes.md, s03); line breaks chosen so no highlighted phrase wraps
REPORT = ("CONFIRMED #4: prompt Visual & Performing Arts;\n"
          "answer 2,134. Arrived task May28 13:34:19,\n"
          "deadline 13:35:24; answered 13:34:20.\n"
          "Likely #5 Psychology 1,544.")

SAW = [("R2:", "Business"), ("R4:", "Visual & Perf. Arts"), ("R1:", "Education")]
FIELDS = [("question", "Visual & Performing Arts"), ("answer", "2,134"), ("next due", "Likely #5 Psychology")]


def bubble(center, r=1.6):
    """A run inside its private circle, with a small note of what it saw."""
    circ = Circle(radius=r, stroke_width=1.6, stroke_color=C_POOL, stroke_opacity=0.35,
                  fill_color=C_POOL, fill_opacity=0.05).move_to(center)
    dot = glow_dot(center + UP * 0.5)
    return circ, dot


def baseline_row(labels, strings, y):
    """Put serif labels on one shared baseline (ignoring descenders)."""
    for lab, raw in zip(labels, strings):
        chars = "".join(raw.split())
        flat = [g for g, ch in zip(lab.submobjects, chars) if ch not in "gjpqy,;"]
        base = min(g.get_bottom()[1] for g in flat)
        lab.shift(UP * (y - base))


def pulse_along(line, color=C_POOL, width=4, time_width=0.6):
    return ShowPassingFlash(line.copy().set_stroke(color, width=width, opacity=1), time_width=time_width)


class S03Pooling(SwarmScene):
    def construct(self):
        hdr = problem_header(1)

        # ---- private observations
        xs = [-4.6, 0.0, 4.6]
        y0 = -0.15
        circs, dots, notes = VGroup(), VGroup(), VGroup()
        for x, (rnd, what) in zip(xs, SAW):
            c = np.array([x, y0, 0])
            circ, dot = bubble(c)
            l1 = mono(rnd, size=18, color=DIM)
            l2 = mono(what, size=18, color=INK_2)
            note = VGroup(l1, l2).arrange(DOWN, buff=0.13).move_to(c + DOWN * 0.3)
            circs.add(circ)
            dots.add(dot)
            notes.add(note)

        # ---- the standard report: three slots + one real report
        card = quote_card(REPORT, sig="CashierSequenceAgentMay28", color=C_POOL, width=48, size=21)
        card.move_to([0, -0.4, 0])
        found = [find_chars(card.body, REPORT, v) for _, v in FIELDS]
        slot_w = [max(f.width + 0.45, 2.0) for f in found]
        slots = VGroup(*[RoundedRectangle(corner_radius=0.08, width=w, height=0.62, stroke_width=1.5,
                                          stroke_color=DIM, stroke_opacity=0.7, fill_color=CARD, fill_opacity=1)
                         for w in slot_w]).arrange(RIGHT, buff=0.45).move_to([0, 1.82, 0])
        slot_labs = VGroup(*[tx(n, size=22, color=DIM, italic=True).next_to(s, UP, buff=0.12)
                             for (n, _), s in zip(FIELDS, slots)])
        baseline_row(slot_labs, [n for n, _ in FIELDS], slots.get_top()[1] + 0.14)

        # ---- the network
        ring_c = np.array([0, -0.3, 0])
        ring = [ring_c + np.array([4.1 * np.cos(a), 2.35 * np.sin(a), 0])
                for a in np.radians([90, 30, -30, -90, -150, 150])]
        # existing runs land on the lower three ring slots; three more copies take the top
        home_of = {0: ring[4], 1: ring[3], 2: ring[2]}
        new_pos = [ring[5], ring[0], ring[1]]
        page = wiki_page("wiki", [v for _, v in FIELDS], width=4.6, size=21, title_size=24)
        page.move_to(ring_c)

        with self.beat("s03_b1") as b:
            self.play(Write(hdr), run_time=0.9)
            b.wait_word("Observations", lead=0.25)
            self.play(LaggedStart(*[AnimationGroup(Create(c), FadeIn(d, scale=0.4), FadeIn(n, shift=UP * 0.1))
                                    for c, d, n in zip(circs, dots, notes)], lag_ratio=0.3),
                      run_time=b.until_word("private", lead=0.05))
            # private: each circle seals for a moment
            self.play(*[c.animate(rate_func=there_and_back).set_stroke(opacity=0.95, width=2.4) for c in circs],
                      run_time=0.7)

            # standard report: runs step back, the form appears
            b.wait_word("standard", lead=0.15)
            bottom = [np.array([x, -2.95, 0]) for x in (-3.0, 0.0, 3.0)]
            self.play(FadeOut(notes, run_time=0.3),
                      *[c.animate.scale(0.33).move_to(p) for c, p in zip(circs, bottom)],
                      *[d.animate.move_to(p) for d, p in zip(dots, bottom)],
                      LaggedStart(*[FadeIn(VGroup(s, l), shift=DOWN * 0.1) for s, l in zip(slots, slot_labs)],
                                  lag_ratio=0.2),
                      run_time=0.65)
            self.play(FadeIn(card, target_position=dots[1].get_center(), scale=0.15), run_time=0.5)

            # question, answer, next due: boxed in the report, lifted into the form
            boxes, values = VGroup(), VGroup()
            for k, (word, f, s) in enumerate(zip(("question", "answer", "next"), found, slots)):
                b.wait_word(word, lead=0.12)
                box = highlight_box(f, C_POOL, buff=0.05)
                v = f.copy()
                v.generate_target()
                v.target.set_color(INK).move_to(s)
                boxes.add(box)
                values.add(v)
                self.play(Create(box), f.animate.set_color(C_POOL), run_time=0.25)
                self.play(MoveToTarget(v, path_arc=-0.25), s.animate.set_stroke(C_POOL, opacity=1), run_time=0.4)

            # parallel copies: more runs join; the report becomes the wiki's content
            b.wait_word("Parallel", lead=0.1)
            values.set_z_index(3)
            page.body.set_z_index(3)
            new_circs = VGroup(*[circs[0].copy().move_to(p) for p in new_pos])
            new_dots = VGroup(*[glow_dot(p) for p in new_pos])
            self.play(FadeOut(VGroup(card, boxes, slots, slot_labs)),
                      FadeIn(VGroup(page.bg, page[1], page.title)),
                      *[ReplacementTransform(v, ln) for v, ln in zip(values, page.body)],
                      *[c.animate.move_to(home_of[i]) for i, c in enumerate(circs)],
                      *[d.animate.move_to(home_of[i]) for i, d in enumerate(dots)],
                      LaggedStart(*[AnimationGroup(FadeIn(c), FadeIn(d, scale=0.4))
                                    for c, d in zip(new_circs, new_dots)], lag_ratio=0.25),
                      run_time=0.9)
            all_dots = VGroup(*dots, *new_dots)
            all_circs = VGroup(*circs, *new_circs)

            # one sensor network: private circles dissolve, everything connects
            pos = [d.get_center() for d in all_dots]
            spokes = VGroup()
            for p in pos:
                q = page.bg.get_boundary_point(p - page.bg.get_center())
                spokes.add(Line(p, q, stroke_width=1.6, color=C_POOL, stroke_opacity=0.55))
            order = [ring[i] for i in range(6)]
            edges = VGroup(*[Line(order[i], order[(i + 1) % 6], stroke_width=1.4, color=C_POOL, stroke_opacity=0.35)
                             for i in range(6)])
            for e in edges:  # keep edges clear of the glow
                e.put_start_and_end_on(e.get_start() + 0.12 * normalize(e.get_end() - e.get_start()),
                                       e.get_end() - 0.12 * normalize(e.get_end() - e.get_start()))
            b.wait_word("one", occurrence=2, lead=0.15)
            self.play(FadeOut(all_circs, scale=1.5),
                      LaggedStart(*[Create(s) for s in spokes], lag_ratio=0.08),
                      LaggedStart(*[Create(e) for e in edges], lag_ratio=0.08),
                      run_time=0.7)
            self.add(all_dots)
            self.play(LaggedStart(*[pulse_along(s) for s in spokes], lag_ratio=0.06),
                      LaggedStart(*[pulse_along(e, width=3) for e in edges], lag_ratio=0.06),
                      page.bg.animate(rate_func=there_and_back).set_stroke(C_POOL, width=2.5),
                      run_time=0.75)
            b.wait_until(b.duration - 0.1)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
