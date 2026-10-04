import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

# verbatim excerpts (research/quotes.md, s07 rows)
Q_NOISE = ("COUNTER NOISE: … HI5/MT5/IA5/WV5/ID5 were batch-created within 8s … "
           "so NOT credible G5 confirmation.")
Q_CLARIFY = "CLARIFY: HI5/MT5/IA5/WV5/ID5/NY5/ME5 batch … was my polling test; ignore. … Sorry for noise."
Q_READ = "Observers please READ only, never /up."

NOISE = [("HI5", (-0.05, 1.2)), ("MT5", (1.75, 1.45)), ("IA5", (3.55, 1.05)),
         ("WV5", (0.85, -0.75)), ("ID5", (2.7, -0.9))]
MD5_AT = np.array([-3.4, 0.15, 0])


def counter(value, label, color, lab_color=None):
    """counter_box with a legible mono label (counter names are tokens)."""
    cb = counter_box(value, label, color)
    cb.remove(cb.lab)
    lab = mono(label, size=22, color=lab_color or color).next_to(cb.box, DOWN, buff=0.14)
    cb.add(lab)
    cb.lab = lab
    return cb


def card(text, sig, color, width, size, sig_size, header=None, pad=0.3):
    """quote_card with its own signature size (shared look: dark card, accent bar)."""
    body = mono_para(text, width=width, size=size, color=INK)
    s = tx("— " + sig, size=sig_size, color=DIM, italic=True)
    s.next_to(body, DOWN, buff=0.2, aligned_edge=RIGHT)
    inner = VGroup(body, s)
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


def dim_counter(cb, f=0.3):
    return AnimationGroup(cb.box.animate.set_stroke(opacity=f), cb.num.animate.set_opacity(f),
                          cb.lab.animate.set_opacity(f))


class S07Trust(SwarmScene):
    def construct(self):
        hdr = problem_header(5)

        md5 = counter(1, "MD5", C_TRUST).move_to(MD5_AT)
        noise = VGroup(*[counter(1, n, DIM, lab_color=DIM).move_to([x, y, 0]) for n, (x, y) in NOISE])
        noise_lab = tx("noise", size=26, color=DIM, italic=True)
        noise_lab.move_to([1.75, -2.05, 0])
        noise_note = tx("five new counters in eight seconds", size=21, color=DIM, italic=True)
        noise_note.next_to(noise_lab, DOWN, buff=0.12)

        eye = problem_icon(5, s=0.5).move_to(MD5_AT + UP * 2.0)
        gaze = DashedLine(eye.get_bottom() + DOWN * 0.08, md5.box.get_top() + UP * 0.1, dash_length=0.07,
                          dashed_ratio=0.5, stroke_width=2, color=C_TRUST)
        up = mono("/up", size=26, color=C_MORT).next_to(md5.box, RIGHT, buff=0.3)

        with self.beat("s07_b1") as b:
            self.play(Write(hdr), run_time=1.0)
            self.play(FadeIn(md5, shift=UP * 0.1), run_time=0.45)
            # "pollute easily": a burst of counters nobody asked for
            b.wait_word("pollute", lead=0.1)
            self.play(LaggedStart(*[FadeIn(c, scale=0.7) for c in noise], lag_ratio=0.18), run_time=0.8)
            self.play(FadeIn(noise_lab, shift=UP * 0.08), FadeIn(noise_note, shift=UP * 0.08), run_time=0.3)
            # "even reading a counter carelessly can bump it"
            b.wait_word("even", lead=0.05)
            self.play(*[dim_counter(c) for c in noise], noise_lab.animate.set_opacity(0.35),
                      noise_note.animate.set_opacity(0.35), FadeIn(eye, shift=DOWN * 0.1), run_time=0.4)
            self.play(Create(gaze), run_time=0.4)
            b.wait_word("bump", lead=0.1)
            md5.num.set_value(2)
            md5.num.set_color(C_MORT)
            self.play(Flash(md5.box, color=C_MORT, line_length=0.16, num_lines=12, flash_radius=0.9),
                      md5.box.animate.set_stroke(C_MORT, width=3.5), FadeIn(up, shift=RIGHT * 0.1),
                      gaze.animate.set_color(C_MORT), run_time=0.45)
            self.play(md5.box.animate.set_stroke(C_TRUST, width=2), md5.num.animate.set_color(INK), run_time=0.4)

            # "flag noise, own their mistakes in public": two posts, one minute apart
            c1 = card(Q_NOISE, "OpenAIResearchAug09X", C_TRUST, width=40, size=23, sig_size=22,
                      header="dse wiki · 16 June 2026, 22:42 UTC")
            c2 = card(Q_CLARIFY, "Sep21 watcher", C_TRUST, width=40, size=23, sig_size=22,
                      header="22:43 UTC · one minute later")
            c1.move_to([-0.9, 0, 0]).align_to(UP * 2.75, UP)
            c2.next_to(c1, DOWN, buff=0.7).align_to(c1, LEFT).shift(RIGHT * 1.2)
            hl_noise = find_chars(c1.body, Q_NOISE, "COUNTER NOISE")
            hl_sorry = find_chars(c2.body, Q_CLARIFY, "Sorry for noise.")
            handles = [find_chars(c1.body, Q_NOISE, n) for n, _ in NOISE]
            handle_ids = {id(g) for h in handles for g in h}
            rest1 = VGroup(*[g for g in c1.body if id(g) not in handle_ids])
            for c, h in zip(noise, handles):     # keep the flying names above the card
                c.lab.set_z_index(2)
                h.set_z_index(2)
            thread = VGroup(
                Line(c1.bar.get_bottom() + DOWN * 0.04, [c1.bar.get_x(), c2.bar.get_y(), 0], stroke_width=1.5,
                     color=FAINT),
                Line([c1.bar.get_x(), c2.bar.get_y(), 0], c2.bar.get_center() + LEFT * 0.05, stroke_width=1.5,
                     color=FAINT))

            # the five noise counters' names fly into the post that flags them
            b.wait_word("So", lead=0.1)
            gone = VGroup(md5, eye, gaze, up, noise_lab, noise_note,
                          *[VGroup(c.box, c.num) for c in noise])
            self.play(FadeOut(gone), *[c.lab.animate.set_opacity(1).set_color(INK) for c in noise], run_time=0.25)
            self.play(FadeIn(VGroup(c1.bg, c1.bar, c1.header), shift=UP * 0.12),
                      *[ReplacementTransform(c.lab, h) for c, h in zip(noise, handles)], run_time=0.45)
            self.play(FadeIn(rest1, shift=UP * 0.05), FadeIn(c1.sig), run_time=b.until_word("noise", lead=0.05))
            box1 = highlight_box(hl_noise, C_TRUST)
            self.play(Create(box1), hl_noise.animate.set_color(C_TRUST), run_time=0.35)
            b.wait_word("own", lead=0.1)
            self.play(FadeIn(VGroup(c2.bg, c2.bar, c2.header, c2.body, c2.sig), shift=UP * 0.12),
                      Create(thread), run_time=0.35)
            ul = underline(hl_sorry, C_TRUST, buff=0.1)
            self.play(Create(ul), hl_sorry.animate.set_color(C_TRUST), run_time=0.4)

            # "tell observers: read only"
            c3 = card(Q_READ, "April11OECDScout", C_TRUST, width=44, size=34, sig_size=24,
                      header="dse wiki · 20 June 2026, 11:28 UTC")
            c3.move_to(DOWN * 0.6)
            eye2 = problem_icon(5, s=0.62).next_to(c3, UP, buff=0.6)
            hl_read = find_chars(c3.body, Q_READ, "READ only")
            hl_up = find_chars(c3.body, Q_READ, "never /up.")
            b.wait_word("and", occurrence=1, lead=0.05)
            self.play(FadeOut(VGroup(c1, c2, box1, ul, thread)), run_time=0.3)
            self.play(FadeIn(VGroup(c3.bg, c3.bar, c3.header), shift=UP * 0.12), FadeIn(eye2, shift=DOWN * 0.1),
                      run_time=0.35)
            self.play(FadeIn(c3.body, shift=UP * 0.06), FadeIn(c3.sig), run_time=0.45)
            b.wait_word("read", occurrence=2, lead=0.05)
            self.play(Create(underline(hl_read, C_TRUST, buff=0.1, stroke=3.5)), hl_read.animate.set_color(C_TRUST),
                      run_time=0.35)
            self.play(hl_up.animate.set_color(C_MORT), run_time=0.3)
            b.wait_until(b.duration - 0.05)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
