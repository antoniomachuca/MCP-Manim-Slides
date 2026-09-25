import {interpolate, useCurrentFrame} from "remotion";
import {loadFont as loadSans} from "@remotion/google-fonts/SourceSans3";
import {loadFont as loadMono} from "@remotion/google-fonts/JetBrainsMono";
import {
  PROMPT,
  REPLY_AT,
  SEND_AT,
  TOOLS_AT,
  TYPE_END,
  TYPE_START,
  colors,
} from "./theme";

const sans = loadSans("normal", {weights: ["400", "600"], subsets: ["latin"]});
const mono = loadMono("normal", {weights: ["400"], subsets: ["latin"]});

const tools: {name: string; at: number; rows: [string, string][]; progress?: boolean}[] = [
  {
    name: "math_derivation",
    at: TOOLS_AT,
    rows: [
      ["title", "Pythagorean theorem"],
      ["steps", "a^2 + b^2 = c^2,  3^2 + 4^2 = 5^2"],
    ],
  },
  {
    name: "execute_manim_code",
    at: TOOLS_AT + 52,
    progress: true,
    rows: [
      ["scenes", "TitleSlide, SquareProof, Check"],
      ["quality", "l"],
    ],
  },
  {
    name: "sync_deck",
    at: TOOLS_AT + 118,
    rows: [
      ["cached", "TitleSlide"],
      ["rendered", "SquareProof, Check"],
      ["dest", "deck.html"],
    ],
  },
  {
    name: "serve_revealjs_html",
    at: TOOLS_AT + 168,
    rows: [
      ["dest", "deck.html"],
      ["url", "http://127.0.0.1:8734/deck.html"],
    ],
  },
];

const fade = (frame: number, at: number) =>
  interpolate(frame, [at, at + 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

export const Desktop = () => {
  const frame = useCurrentFrame();
  const typed = Math.round(
    interpolate(frame, [TYPE_START, TYPE_END], [0, PROMPT.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
  );
  const sent = frame >= SEND_AT;
  const draft = sent ? "" : PROMPT.slice(0, typed);
  const caret = !sent && Math.floor(frame / 8) % 2 === 0;

  return (
    <div
      style={{
        width: 1180,
        height: 680,
        background: colors.app,
        borderRadius: 12,
        overflow: "hidden",
        display: "flex",
        boxShadow: "0 24px 60px rgba(0,0,0,0.35)",
        fontFamily: sans.fontFamily,
        color: colors.text,
      }}
    >
      <aside
        style={{
          width: 220,
          background: colors.sidebar,
          borderRight: `1px solid ${colors.line}`,
          padding: "18px 14px",
          boxSizing: "border-box",
        }}
      >
        <div style={{fontSize: 13, letterSpacing: 0.4, color: colors.muted}}>Claude</div>
        <div
          style={{
            marginTop: 18,
            fontSize: 14,
            padding: "8px 10px",
            borderRadius: 8,
            border: `1px solid ${colors.line}`,
          }}
        >
          New chat
        </div>
        <div style={{marginTop: 22, fontSize: 12, color: colors.dim}}>Recents</div>
        <div
          style={{
            marginTop: 8,
            fontSize: 14,
            padding: "8px 10px",
            borderRadius: 8,
            background: "#e7e3d9",
          }}
        >
          Pythagorean theorem
        </div>
      </aside>
      <main style={{flex: 1, display: "flex", flexDirection: "column", minWidth: 0}}>
        <header
          style={{
            height: 48,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "0 22px",
            borderBottom: `1px solid ${colors.line}`,
            fontSize: 14,
            color: colors.muted,
          }}
        >
          <span>manim-slides</span>
          <span>Sonnet</span>
        </header>
        <div style={{flex: 1, padding: "22px 36px", overflow: "hidden"}}>
          {sent ? (
            <div style={{display: "flex", justifyContent: "flex-end"}}>
              <div
                style={{
                  maxWidth: 640,
                  background: colors.user,
                  borderRadius: 16,
                  padding: "12px 16px",
                  fontSize: 16,
                  lineHeight: 1.45,
                }}
              >
                {PROMPT}
              </div>
            </div>
          ) : null}
          <div
            style={{
              marginTop: 18,
              fontSize: 16,
              lineHeight: 1.45,
              opacity: fade(frame, REPLY_AT),
              maxWidth: 680,
            }}
          >
            I'll take the math derivation prompt, render the scenes, and open the deck.
          </div>
          <div style={{marginTop: 16, display: "flex", flexDirection: "column", gap: 10}}>
            {tools.map((tool) => (
              <ToolCard key={tool.name} frame={frame} {...tool} />
            ))}
          </div>
        </div>
        <div style={{padding: "0 36px 28px"}}>
          <div
            style={{
              border: `1px solid ${colors.line}`,
              background: colors.card,
              borderRadius: 16,
              minHeight: 72,
              width: 620,
              padding: "14px 16px",
              fontSize: 22,
              lineHeight: 1.35,
              boxShadow: "0 1px 0 rgba(0,0,0,0.03)",
              whiteSpace: "pre-wrap",
            }}
          >
            {draft ? (
              <span>{draft}</span>
            ) : (
              <span style={{color: colors.dim}}>{sent ? "Reply to Claude" : "Message Claude"}</span>
            )}
            {caret ? (
              <span
                style={{
                  display: "inline-block",
                  width: 2,
                  height: 18,
                  background: colors.accent,
                  marginLeft: 1,
                  transform: "translateY(3px)",
                }}
              />
            ) : null}
          </div>
        </div>
      </main>
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
  rows: [string, string][];
  progress?: boolean;
}) => {
  const opacity = fade(frame, at);
  if (opacity <= 0) {
    return null;
  }
  const pct = progress
    ? Math.round(
        interpolate(frame, [at + 8, at + 48], [0, 100], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
      )
    : 100;
  const done = !progress || pct >= 100;

  return (
    <div
      style={{
        opacity,
        background: colors.card,
        border: `1px solid ${colors.line}`,
        borderRadius: 12,
        padding: "10px 14px",
        maxWidth: 680,
      }}
    >
      <div style={{display: "flex", justifyContent: "space-between", fontSize: 15}}>
        <span>
          <span style={{color: colors.dim, marginRight: 8}}>manim-slides</span>
          {name}
        </span>
        <span style={{color: done ? colors.ok : colors.muted, fontSize: 13}}>
          {done ? "Done" : "Running"}
        </span>
      </div>
      <div style={{marginTop: 6, fontFamily: mono.fontFamily, fontSize: 13, color: colors.muted}}>
        {rows.map(([key, value]) => (
          <div key={key} style={{display: "flex", gap: 12, lineHeight: 1.5}}>
            <span style={{width: 72, color: colors.dim}}>{key}</span>
            <span>{value}</span>
          </div>
        ))}
      </div>
      {progress ? (
        <div style={{marginTop: 8, height: 3, background: colors.line, borderRadius: 2}}>
          <div style={{width: `${pct}%`, height: "100%", background: colors.accent, borderRadius: 2}} />
        </div>
      ) : null}
    </div>
  );
};
