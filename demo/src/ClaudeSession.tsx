import {interpolate, useCurrentFrame} from "remotion";
import {loadFont as loadMono} from "@remotion/google-fonts/JetBrainsMono";
import {
  PROMPT_END,
  PROMPT_START,
  REPLY_AT,
  TOOLS_AT,
  colors,
} from "./theme";

const {fontFamily} = loadMono("normal", {
  weights: ["400"],
  subsets: ["latin"],
});

const PROMPT =
  "Build a three-slide deck of the Pythagorean theorem: the statement, the squares on each side, and the 3-4-5 check.";

const REPLY =
  "I'll take the math derivation prompt, render the scenes, and sync only what changed.";

type Row = {key: string; value: string};

const tools: {name: string; at: number; rows: Row[]; progress?: boolean}[] = [
  {
    name: "math_derivation",
    at: TOOLS_AT,
    rows: [
      {key: "title", value: "Pythagorean theorem"},
      {
        key: "steps",
        value: "a^2 + b^2 = c^2,  3^2 + 4^2 = 5^2,  9 + 16 = 25",
      },
    ],
  },
  {
    name: "execute_manim_code",
    at: TOOLS_AT + 58,
    progress: true,
    rows: [
      {key: "scenes", value: "TitleSlide, SquareProof, Check"},
      {key: "quality", value: "l"},
    ],
  },
  {
    name: "sync_deck",
    at: TOOLS_AT + 128,
    rows: [
      {key: "cached", value: "TitleSlide"},
      {key: "rendered", value: "SquareProof, Check"},
      {key: "dest", value: "deck.html"},
    ],
  },
  {
    name: "contact_sheet",
    at: TOOLS_AT + 186,
    rows: [
      {key: "dest", value: "contact_sheet.png"},
      {key: "slides", value: "3"},
    ],
  },
];

const fade = (frame: number, at: number) =>
  interpolate(frame, [at, at + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const ClaudeSession = () => {
  const frame = useCurrentFrame();
  const typed = Math.round(
    interpolate(frame, [PROMPT_START, PROMPT_END], [0, PROMPT.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const prompt = PROMPT.slice(0, typed);
  const caretOn = Math.floor(frame / 8) % 2 === 0 && frame < PROMPT_END + 16;
  const replyOpacity = fade(frame, REPLY_AT);

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: colors.bg,
        color: colors.text,
        fontFamily,
        padding: "54px 72px",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          marginBottom: 28,
          color: colors.dim,
          fontSize: 15,
          letterSpacing: 0.4,
        }}
      >
        <span>claude</span>
        <span>manim-slides</span>
      </div>

      <div style={{fontSize: 22, lineHeight: 1.45, minHeight: 78}}>
        <span style={{color: colors.accent, marginRight: 12}}>&gt;</span>
        <span>{prompt}</span>
        {caretOn ? (
          <span
            style={{
              display: "inline-block",
              width: 10,
              height: 22,
              background: colors.accent,
              marginLeft: 2,
              transform: "translateY(4px)",
            }}
          />
        ) : null}
      </div>

      <div
        style={{
          marginTop: 22,
          fontSize: 18,
          lineHeight: 1.5,
          color: colors.muted,
          opacity: replyOpacity,
          maxWidth: 920,
        }}
      >
        {REPLY}
      </div>

      <div style={{marginTop: 28, display: "flex", flexDirection: "column", gap: 14}}>
        {tools.map((tool) => (
          <ToolCard key={tool.name} frame={frame} {...tool} />
        ))}
      </div>
    </div>
  );
};

const ToolCard = ({
  frame,
  name,
  at,
  rows,
  progress,
}: {
  frame: number;
  name: string;
  at: number;
  rows: Row[];
  progress?: boolean;
}) => {
  const opacity = fade(frame, at);
  if (opacity <= 0) {
    return null;
  }
  const pct = progress
    ? Math.round(
        interpolate(frame, [at + 12, at + 68], [0, 100], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      )
    : 0;

  return (
    <div
      style={{
        opacity,
        borderLeft: `2px solid ${colors.accent}`,
        padding: "8px 0 8px 16px",
      }}
    >
      <div style={{fontSize: 18, color: colors.text}}>{name}</div>
      <div style={{marginTop: 6}}>
        {rows.map((row) => (
          <div
            key={row.key}
            style={{
              display: "flex",
              gap: 16,
              fontSize: 15,
              lineHeight: 1.55,
              color: colors.muted,
            }}
          >
            <span style={{width: 88, color: colors.dim}}>{row.key}</span>
            <span>{row.value}</span>
          </div>
        ))}
        {progress ? (
          <div style={{marginTop: 8, display: "flex", alignItems: "center", gap: 12}}>
            <div
              style={{
                width: 220,
                height: 4,
                background: colors.line,
                borderRadius: 2,
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  width: `${pct}%`,
                  height: "100%",
                  background: colors.ok,
                }}
              />
            </div>
            <span style={{fontSize: 14, color: colors.dim}}>
              SquareProof {pct}%
            </span>
          </div>
        ) : null}
      </div>
    </div>
  );
};
