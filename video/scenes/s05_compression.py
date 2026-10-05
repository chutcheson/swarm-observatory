import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from swarm import *

# verbatim (research/quotes.md): a full report (s03), then the shrunken forms (s05)
REPORT = ("CONFIRMED #4: prompt Visual & Performing Arts;\n"
          "answer 2,134. Arrived task May28 13:34:19,\n"
          "deadline 13:35:24; answered 13:34:20.\n"
          "Likely #5 Psychology 1,544.")
FIRST = "COUNTRY FIRST"          # (Aug16 watcher)
LATER = "then values."           # same message
TOKEN = "STATE5-NH"              # SectorAgentJun15
TOKEN_Q = "a compact token STATE5-NH … is easiest"
CODE_Q = "CODE = 2+2*(YEAR-2014)+(0 female,1 male); so F2017=8, M2017=9."   # OpenAIMay31Maids


def rows_of(glyphs):
    """Cluster glyphs into text lines; returns the line-centre y for each glyph."""
    ys = sorted({round(g.get_center()[1], 3) for g in glyphs}, reverse=True)
    centers, cur = [], [ys[0]]
    for y in ys[1:]:
        if cur[-1] - y > 0.18:
            centers.append(np.mean(cur))
            cur = []
        cur.append(y)
    centers.append(np.mean(cur))
    return [min(centers, key=lambda c: abs(c - g.get_center()[1])) for g in glyphs]


class S05Compression(SwarmScene):
    def construct(self):
        hdr = problem_header(3)

        # ---- the clock and the long report
        RY = -0.3
        ring, frac = timer_ring(radius=1.2, color=C_CHAN, stroke=11)
        ring.move_to([-4.15, RY, 0])
        secs = tx("13 s", size=44, color=INK).move_to(ring[0])
        para = mono_para(" ".join(REPORT.split()), width=31, size=27, color=INK_2)
        para.next_to(ring, RIGHT, buff=1.0)
        para.align_to([0, RY + 0.85, 0], UP)
        XT = para.get_center()[0]
        glyphs = list(para.submobjects)
        row_y = rows_of(glyphs)
        N = len(glyphs)
        cut = int(N * 0.58)
        for g in glyphs:
            g.set_opacity(0)
        cursor = Rectangle(width=0.15, height=0.37, stroke_width=0, fill_color=C_CHAN, fill_opacity=1)
        cursor.move_to([para.get_left()[0] + 0.06, row_y[0], 0])

        def typing(_, a):
            k = int(a * cut)
            for i, g in enumerate(glyphs):
                g.set_opacity(1 if i < k else 0)
            if k > 0:
                g = glyphs[k - 1]
                cursor.move_to([g.get_right()[0] + 0.13, row_y[k - 1], 0])

        # ---- compressed forms
        first = mono(FIRST, size=56, color=C_CHAN, weight=BOLD).move_to([XT, RY + 0.3, 0])
        later = mono(LATER, size=32, color=DIM).next_to(first, DOWN, buff=0.45).align_to(first, RIGHT).shift(RIGHT * 0.8)
        pkt = packet(TOKEN, C_CHAN, size=46, pad=0.26).move_to([XT, RY + 0.4, 0])
        pkt_q = mono(TOKEN_Q, size=24, color=DIM).next_to(pkt, DOWN, buff=0.55)
        pkt_sig = tx("— SectorAgentJun15", size=24, color=DIM, italic=True).next_to(pkt_q, DOWN, buff=0.18).align_to(pkt_q, RIGHT)

        # ---- one number
        eq = MathTex(r"\text{CODE}", "=", "2", "+", "2", r"(\text{year}", "-", "2014)", "+", r"\text{sex}",
                     font_size=50, color=INK)
        eq[0].set_color(C_CHAN)
        eq.move_to([0, 2.05, 0])
        legend = MathTex(r"\text{sex} = 0\ \text{female},\;\; 1\ \text{male}", font_size=34, color=DIM)
        legend.next_to(eq, DOWN, buff=0.35)
        ex = MathTex(r"\text{F}\ 2017", r"\;\longrightarrow\;", r"2 + 2\cdot 3 + 0", "=", "8", font_size=42, color=INK)
        ex[0].set_color(INK_2)
        ex[4].set_color(C_CHAN)
        ex.move_to([0, 0.25, 0])
        nl = NumberLine(x_range=[0, 24, 1], length=10.0, color=DIM, stroke_width=2, tick_size=0.06,
                        numbers_to_include=[0, 4, 8, 12, 16, 20, 24], font_size=26,
                        numbers_with_elongated_ticks=[0, 4, 8, 12, 16, 20, 24], longer_tick_multiple=2)
        nl.numbers.set_color(DIM)
        nl.move_to([0, -1.05, 0])
        cap = quote_card(CODE_Q, sig="OpenAIMay31Maids", color=C_CHAN, width=70, size=20)
        cap.move_to([0, -2.6, 0])

        with self.beat("s05_b1") as b:
            self.play(Write(hdr), run_time=0.9)

            # some rounds allow thirteen seconds
            b.wait_word("Some", lead=0.1)
            self.play(Create(ring[0]), FadeIn(secs, scale=0.8), run_time=0.5)
            self.add(ring[1], para, cursor)
            b.wait_word("thirteen", lead=0.0)
            # the clock runs out before the report is written
            self.play(frac.animate.set_value(0), UpdateFromAlphaFunc(para, typing),
                      run_time=1.8, rate_func=linear)

            # so messages shrink: country first, details later
            shown = VGroup(*glyphs[:cut])
            self.remove(para)
            self.play(ReplacementTransform(shown, first), FadeOut(cursor), frac.animate.set_value(1.0), run_time=0.7)
            b.wait_word("country", lead=0.0)
            self.play(Indicate(first, color=C_CHAN, scale_factor=1.05), frac.animate.set_value(0.86), run_time=0.45,
                      rate_func=smooth)
            b.wait_word("details", lead=0.05)
            self.play(FadeIn(later, shift=LEFT * 0.3), frac.animate.set_value(0.45), run_time=0.8, rate_func=smooth)

            # a report becomes one token
            b.wait_word("report", lead=0.1)
            self.play(ReplacementTransform(VGroup(first, later), pkt), frac.animate.set_value(1.0), run_time=0.6)
            self.play(frac.animate.set_value(0.93), FadeIn(pkt_q, shift=UP * 0.1), FadeIn(pkt_sig, shift=UP * 0.1),
                      run_time=b.until_word("and", lead=0.1))

            # one protocol packs gender and year into a single number
            ring[1].clear_updaters()
            self.play(FadeOut(VGroup(ring, secs, pkt, pkt_q, pkt_sig)), run_time=0.3)
            self.play(Write(eq), Create(nl), run_time=0.75)
            b.wait_word("gender", lead=0.1)
            self.play(eq[9].animate.set_color(C_CHAN), FadeIn(legend, shift=DOWN * 0.1), run_time=0.35)
            b.wait_word("year", lead=0.1)
            self.play(eq[5][1:].animate.set_color(C_CHAN), run_time=0.35)
            self.play(FadeIn(ex, shift=DOWN * 0.1), FadeIn(cap, shift=UP * 0.15), run_time=b.until_word("single", lead=0.05))
            mark = Dot(nl.n2p(8), radius=0.09, color=C_CHAN)
            ring8 = Circle(radius=0.2, stroke_width=2.5, color=C_CHAN).move_to(nl.n2p(8))
            self.play(TransformFromCopy(ex[4], mark, path_arc=-0.4), Create(ring8),
                      nl.numbers[2].animate.set_color(C_CHAN), run_time=0.55)
            b.wait_until(b.duration - 0.1)
            self.play(FadeOut(Group(*self.mobjects)), run_time=0.4)
