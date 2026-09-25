import {interpolate, useCurrentFrame} from "remotion";
import {loadFont as loadSerif} from "@remotion/google-fonts/LibreBaskerville";
import {loadFont as loadMono} from "@remotion/google-fonts/JetBrainsMono";
import {RESULT_AT, colors} from "./theme";

const serif = loadSerif("normal", {
  weights: ["400"],
  subsets: ["latin"],
});
const mono = loadMono("normal", {
  weights: ["400"],
  subsets: ["latin"],
});

const TITLE_END = 56;
const PROOF_END = 168;

type Pt = {x: number; y: number};

const squareOutward = (p: Pt, q: Pt, interior: Pt): Pt[] => {
  const dx = q.x - p.x;
  const dy = q.y - p.y;
  const len = Math.hypot(dx, dy);
  const n1 = {x: -dy, y: dx};
  const mid = {x: (p.x + q.x) / 2, y: (p.y + q.y) / 2};
  const toward = {x: interior.x - mid.x, y: interior.y - mid.y};
  const sign = n1.x * toward.x + n1.y * toward.y > 0 ? -1 : 1;
  const nx = (sign * n1.x * len) / Math.hypot(n1.x, n1.y);
  const ny = (sign * n1.y * len) / Math.hypot(n1.x, n1.y);
  return [p, q, {x: q.x + nx, y: q.y + ny}, {x: p.x + nx, y: p.y + ny}];
};

const poly = (pts: Pt[]) => pts.map((p) => `${p.x},${p.y}`).join(" ");

const centroid = (pts: Pt[]): Pt => ({
  x: pts.reduce((s, p) => s + p.x, 0) / pts.length,
  y: pts.reduce((s, p) => s + p.y, 0) / pts.length,
});

export const Slides = () => {
  const frame = useCurrentFrame();
  const local = frame - RESULT_AT;
  const index = local < TITLE_END ? 0 : local < PROOF_END ? 1 : 2;
  const slideStart = index === 0 ? 0 : index === 1 ? TITLE_END : PROOF_END;
  const enter = interpolate(local - slideStart, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: colors.slide,
        color: colors.chalk,
        fontFamily: serif.fontFamily,
        position: "relative",
      }}
    >
      <div style={{opacity: enter, width: "100%", height: "100%"}}>
        {index === 0 ? <TitleSlide /> : null}
        {index === 1 ? <ProofSlide local={local - TITLE_END} /> : null}
        {index === 2 ? <CheckSlide /> : null}
      </div>
      <div
        style={{
          position: "absolute",
          left: 48,
          bottom: 28,
          fontFamily: mono.fontFamily,
          fontSize: 14,
          color: colors.dim,
          letterSpacing: 0.3,
        }}
      >
        deck.html
        <span style={{margin: "0 10px", color: colors.line}}>/</span>
        {index + 1} / 3
      </div>
    </div>
  );
};

const TitleSlide = () => (
  <div
    style={{
      height: "100%",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      padding: "0 120px",
    }}
  >
    <div style={{fontSize: 64, lineHeight: 1.15, maxWidth: 900}}>
      The Pythagorean theorem
    </div>
    <div
      style={{
        marginTop: 28,
        fontSize: 32,
        color: colors.chalkDim,
      }}
    >
      In a right triangle, a² + b² = c².
    </div>
  </div>
);

const inward = (p: Pt, q: Pt, interior: Pt, dist: number): Pt => {
  const mid = {x: (p.x + q.x) / 2, y: (p.y + q.y) / 2};
  const dx = interior.x - mid.x;
  const dy = interior.y - mid.y;
  const len = Math.hypot(dx, dy) || 1;
  return {x: mid.x + (dx / len) * dist, y: mid.y + (dy / len) * dist};
};

const ProofSlide = ({local}: {local: number}) => {
  const unit = 64;
  const o: Pt = {x: 0, y: 0};
  const b: Pt = {x: 4 * unit, y: 0};
  const a: Pt = {x: 0, y: -3 * unit};
  const interior = {
    x: (o.x + b.x + a.x) / 3,
    y: (o.y + b.y + a.y) / 3,
  };
  const sqA = squareOutward(o, a, interior);
  const sqB = squareOutward(o, b, interior);
  const sqC = squareOutward(a, b, interior);
  const all = [...sqA, ...sqB, ...sqC];
  const minX = Math.min(...all.map((p) => p.x)) - 36;
  const minY = Math.min(...all.map((p) => p.y)) - 36;
  const maxX = Math.max(...all.map((p) => p.x)) + 36;
  const maxY = Math.max(...all.map((p) => p.y)) + 28;
  const labelA = inward(o, a, interior, 16);
  const labelB = inward(o, b, interior, 16);
  const labelC = inward(a, b, interior, 18);
  const showA = interpolate(local, [8, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const showB = interpolate(local, [16, 28], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const showC = interpolate(local, [24, 36], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg
      width="1280"
      height="640"
      viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`}
      style={{display: "block", margin: "28px auto 0"}}
    >
      <Square pts={sqB} label="16" opacity={showB} fill="#1c2430" />
      <Square pts={sqA} label="9" opacity={showA} fill="#241c18" />
      <Square pts={sqC} label="25" opacity={showC} fill="#1a261c" />
      <polygon
        points={poly([o, b, a])}
        fill="#161614"
        stroke={colors.chalk}
        strokeWidth={2.5}
      />
      <EdgeLabel x={labelA.x} y={labelA.y} text="a" />
      <EdgeLabel x={labelB.x} y={labelB.y} text="b" />
      <EdgeLabel x={labelC.x} y={labelC.y} text="c" />
    </svg>
  );
};

const Square = ({
  pts,
  label,
  opacity,
  fill,
}: {
  pts: Pt[];
  label: string;
  opacity: number;
  fill: string;
}) => {
  const c = centroid(pts);
  return (
    <g opacity={opacity}>
      <polygon
        points={poly(pts)}
        fill={fill}
        stroke={colors.chalkDim}
        strokeWidth={1.5}
      />
      <text
        x={c.x}
        y={c.y}
        textAnchor="middle"
        dominantBaseline="middle"
        fill={colors.chalk}
        fontSize={28}
        fontFamily={serif.fontFamily}
      >
        {label}
      </text>
    </g>
  );
};

const EdgeLabel = ({x, y, text}: {x: number; y: number; text: string}) => (
  <text
    x={x}
    y={y}
    fill={colors.chalk}
    fontSize={26}
    fontFamily={serif.fontFamily}
    textAnchor="middle"
  >
    {text}
  </text>
);

const CheckSlide = () => (
  <div
    style={{
      height: "100%",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      padding: "0 120px",
      fontSize: 54,
      lineHeight: 1.45,
    }}
  >
    <div>3² + 4² = 5²</div>
    <div style={{color: colors.chalkDim}}>9 + 16 = 25</div>
  </div>
);
