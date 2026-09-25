import numpy as np
from manim import (
    BLACK,
    DOWN,
    Create,
    FadeIn,
    GrowFromCenter,
    ORIGIN,
    Polygon,
    Text,
    UP,
    VGroup,
    WHITE,
    Write,
)
from manim_slides import Slide


def _square(p, q, interior, fill):
    p = np.array(p, dtype=float)
    q = np.array(q, dtype=float)
    interior = np.array(interior, dtype=float)
    edge = q - p
    normal = np.array([-edge[1], edge[0], 0.0])
    mid = (p + q) / 2
    if np.dot(normal, interior - mid) > 0:
        normal = -normal
    normal = normal / np.linalg.norm(normal) * np.linalg.norm(edge)
    return Polygon(
        p,
        q,
        q + normal,
        p + normal,
        color="#d9d4c8",
        stroke_width=2,
        fill_color=fill,
        fill_opacity=1,
    )


def _centroid(poly):
    return np.mean(poly.get_vertices(), axis=0)


class TitleSlide(Slide):
    def construct(self):
        title = Text("The Pythagorean theorem", font_size=52, color=WHITE)
        subtitle = Text(
            "In a right triangle, a² + b² = c².",
            font_size=30,
            color="#c8c4b8",
        )
        subtitle.next_to(title, DOWN, buff=0.45)
        self.play(Write(title), run_time=1.1)
        self.play(FadeIn(subtitle, shift=UP * 0.12), run_time=0.7)
        self.wait(0.5)


class SquareProof(Slide):
    def construct(self):
        origin = np.array([0.0, 0.0, 0.0])
        side_b = np.array([4.0, 0.0, 0.0])
        side_a = np.array([0.0, 3.0, 0.0])
        interior = (origin + side_a + side_b) / 3
        square_a = _square(origin, side_a, interior, "#2a211c")
        square_b = _square(origin, side_b, interior, "#1b2430")
        square_c = _square(side_a, side_b, interior, "#1a261c")
        triangle = Polygon(
            origin,
            side_b,
            side_a,
            color=WHITE,
            stroke_width=2.5,
            fill_color=BLACK,
            fill_opacity=1,
        )

        def edge_label(p, q, text):
            mid = (np.array(p) + np.array(q)) / 2
            direction = interior - mid
            direction = direction / np.linalg.norm(direction)
            return Text(text, font_size=28, color=WHITE).move_to(mid + direction * 0.32)

        label_a = edge_label(origin, side_a, "a")
        label_b = edge_label(origin, side_b, "b")
        label_c = edge_label(side_a, side_b, "c")
        area_a = Text("9", font_size=32, color=WHITE).move_to(_centroid(square_a))
        area_b = Text("16", font_size=32, color=WHITE).move_to(_centroid(square_b))
        area_c = Text("25", font_size=32, color=WHITE).move_to(_centroid(square_c))
        diagram = VGroup(
            square_b,
            square_a,
            square_c,
            triangle,
            label_a,
            label_b,
            label_c,
            area_a,
            area_b,
            area_c,
        )
        diagram.scale(0.58).move_to(ORIGIN)

        self.play(Create(triangle), run_time=1.0)
        self.play(FadeIn(label_a), FadeIn(label_b), FadeIn(label_c), run_time=0.45)
        self.play(GrowFromCenter(square_a), FadeIn(area_a), run_time=0.55)
        self.play(GrowFromCenter(square_b), FadeIn(area_b), run_time=0.55)
        self.play(GrowFromCenter(square_c), FadeIn(area_c), run_time=0.7)
        self.wait(0.45)


class Check(Slide):
    def construct(self):
        equation = Text("3² + 4² = 5²", font_size=60, color=WHITE)
        result = Text("9 + 16 = 25", font_size=44, color="#c8c4b8")
        result.next_to(equation, DOWN, buff=0.45)
        self.play(Write(equation), run_time=1.0)
        self.play(Write(result), run_time=0.8)
        self.wait(0.55)
