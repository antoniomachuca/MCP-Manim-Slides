"""The deck the demo video shows: rendered through the MCP server's sync_deck."""

import numpy as np
from manim import (
    DOWN,
    LEFT,
    ORIGIN,
    UP,
    Create,
    FadeIn,
    FadeOut,
    LaggedStart,
    MathTex,
    Polygon,
    Square,
    SurroundingRectangle,
    Text,
    Transform,
    VGroup,
    Write,
    config,
)
from manim_slides import Slide

BG = "#16171B"
INK = "#F2EFE8"
DIM = "#8B8A86"
CORAL = "#E07A5F"
BLUE = "#6C8EBF"
GREEN = "#87C2A5"
FONT = "Helvetica Neue"

config.background_color = BG


def unit_cells(origin, u, v, rows, cols, color):
    """Unit squares tiling a rows x cols square spanned by unit vectors u, v."""
    angle = np.arctan2(u[1], u[0])
    cells = VGroup()
    for i in range(cols):
        for j in range(rows):
            center = origin + (i + 0.5) * u + (j + 0.5) * v
            cell = Square(
                side_length=0.92, stroke_width=0, fill_color=color, fill_opacity=1
            )
            cell.rotate(angle).move_to(center)
            cells.add(cell)
    return cells


def square_outline(p, u, v, n, color):
    return Polygon(
        p, p + n * u, p + n * u + n * v, p + n * v, color=color, stroke_width=3
    )


class TitleSlide(Slide):
    def construct(self):
        title = Text(
            "The Pythagorean theorem", font=FONT, font_size=64, color=INK, weight="BOLD"
        )
        formula = MathTex("a^2", "+", "b^2", "=", "c^2", font_size=96, color=INK)
        formula[0].set_color(CORAL)
        formula[2].set_color(BLUE)
        formula[4].set_color(GREEN)
        VGroup(title, formula).arrange(DOWN, buff=0.7)
        self.play(Write(title), run_time=1.2)
        self.play(
            LaggedStart(
                *[FadeIn(part, shift=UP * 0.2) for part in formula], lag_ratio=0.18
            )
        )
        self.wait(0.6)
        self.next_slide()
        self.play(
            FadeOut(title, shift=UP * 0.3),
            FadeOut(formula, shift=UP * 0.3),
            run_time=0.6,
        )


class SquareProof(Slide):
    def construct(self):
        x = np.array([1.0, 0, 0])
        y = np.array([0, 1.0, 0])
        o = ORIGIN.astype(float)
        hyp_u = np.array([4.0, -3.0, 0]) / 5
        hyp_v = np.array([3.0, 4.0, 0]) / 5
        top = 3 * y

        triangle = Polygon(o, 4 * x, top, color=INK, stroke_width=4)
        cells_a = unit_cells(-3 * x, x, y, 3, 3, CORAL)
        cells_b = unit_cells(-4 * y, x, y, 4, 4, BLUE)
        target_c = unit_cells(top, hyp_u, hyp_v, 5, 5, GREEN)
        outline_c = square_outline(top, hyp_u, hyp_v, 5, GREEN)

        label_a = MathTex("a = 3", font_size=100, color=CORAL).next_to(
            -3 * x + 1.5 * y, LEFT, buff=0.35
        )
        label_b = MathTex("b = 4", font_size=100, color=BLUE).next_to(
            2 * x - 4 * y, DOWN, buff=0.3
        )
        label_c = MathTex("c = 5", font_size=100, color=GREEN).move_to(
            top + 2.5 * hyp_u + 6.5 * hyp_v
        )
        area_a = MathTex("9", font_size=96, color=INK).move_to(-1.5 * x + 1.5 * y)
        area_b = MathTex("16", font_size=96, color=INK).move_to(2 * x - 2 * y)
        area_c = MathTex("25", font_size=120, color=INK).move_to(
            top + 2.5 * hyp_u + 2.5 * hyp_v
        )

        diagram = VGroup(
            triangle,
            cells_a,
            cells_b,
            target_c,
            outline_c,
            label_a,
            label_b,
            label_c,
            area_a,
            area_b,
            area_c,
        )
        diagram.scale(0.6).move_to(ORIGIN)

        self.play(Create(triangle), run_time=1.0)
        self.play(
            LaggedStart(*[FadeIn(c, scale=0.4) for c in cells_a], lag_ratio=0.08),
            FadeIn(label_a),
            run_time=1.0,
        )
        self.play(FadeIn(area_a, scale=1.4), run_time=0.4)
        self.play(
            LaggedStart(*[FadeIn(c, scale=0.4) for c in cells_b], lag_ratio=0.06),
            FadeIn(label_b),
            run_time=1.2,
        )
        self.play(FadeIn(area_b, scale=1.4), run_time=0.4)
        self.next_slide()

        self.play(Create(outline_c), FadeIn(label_c), run_time=0.8)
        movers = VGroup(*cells_a.copy(), *cells_b.copy())
        cells_a.set_fill(opacity=0.22)
        cells_b.set_fill(opacity=0.22)
        self.add(movers)
        self.play(
            LaggedStart(
                *[
                    Transform(m, t.copy().set_fill(m.get_fill_color()), path_arc=-0.9)
                    for m, t in zip(movers, target_c, strict=False)
                ],
                lag_ratio=0.05,
            ),
            FadeOut(area_a),
            FadeOut(area_b),
            run_time=2.6,
        )
        self.play(FadeIn(area_c, scale=1.4), run_time=0.5)
        self.wait(0.8)


class Check(Slide):
    def construct(self):
        step1 = MathTex("3^2", "+", "4^2", "=", "5^2", font_size=110, color=INK)
        step2 = MathTex("9", "+", "16", "=", "25", font_size=110, color=INK)
        for step in (step1, step2):
            step[0].set_color(CORAL)
            step[2].set_color(BLUE)
            step[4].set_color(GREEN)
        caption = Text(
            "Every right triangle, every time.", font=FONT, font_size=34, color=DIM
        )
        caption.next_to(step1, DOWN, buff=0.9)

        self.play(Write(step1), run_time=1.2)
        self.next_slide()
        self.play(
            LaggedStart(
                *[Transform(a, b) for a, b in zip(step1, step2, strict=False)],
                lag_ratio=0.12,
            ),
            run_time=1.0,
        )
        box = SurroundingRectangle(
            step1, color=GREEN, buff=0.35, corner_radius=0.15, stroke_width=4
        )
        self.play(Create(box), FadeIn(caption, shift=UP * 0.2), run_time=0.8)
        self.wait(1.0)
