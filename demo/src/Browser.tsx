import {OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from "remotion";
import {loadFont as loadSans} from "@remotion/google-fonts/SourceSans3";
import {BROWSER_AT, DECK_FRAMES} from "./theme";

const sans = loadSans("normal", {weights: ["400"], subsets: ["latin"]});

export const Browser = () => {
  const frame = useCurrentFrame();
  const local = Math.max(0, frame - BROWSER_AT);
  const index = local < 69 ? 0 : local < 181 ? 1 : 2;
  const open = interpolate(local, [0, 14], [0.94, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = interpolate(local, [0, 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: 1180,
        height: 680,
        background: "#dee1e6",
        borderRadius: 12,
        overflow: "hidden",
        boxShadow: "0 24px 60px rgba(0,0,0,0.35)",
        transform: `scale(${open})`,
        opacity,
        fontFamily: sans.fontFamily,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div style={{height: 46, display: "flex", alignItems: "center", gap: 14, padding: "0 14px"}}>
        <div style={{display: "flex", gap: 6}}>
          <Dot color="#ff5f57" />
          <Dot color="#febc2e" />
          <Dot color="#28c840" />
        </div>
        <div
          style={{
            flex: 1,
            background: "#ffffff",
            borderRadius: 8,
            height: 28,
            display: "flex",
            alignItems: "center",
            padding: "0 12px",
            fontSize: 13,
            color: "#3c4043",
          }}
        >
          127.0.0.1:8734/deck.html
        </div>
      </div>
      <div style={{flex: 1, background: "#000", position: "relative"}}>
        <Sequence from={BROWSER_AT} durationInFrames={DECK_FRAMES} layout="none">
          <OffthreadVideo
            src={staticFile("slides/deck.mp4")}
            style={{
              position: "absolute",
              inset: 0,
              width: "100%",
              height: "100%",
              objectFit: "contain",
              background: "#000",
            }}
          />
        </Sequence>
        <div
          style={{
            position: "absolute",
            right: 18,
            bottom: 12,
            color: "#9a968c",
            fontSize: 13,
          }}
        >
          {index + 1} / 3
        </div>
      </div>
    </div>
  );
};

const Dot = ({color}: {color: string}) => (
  <div style={{width: 11, height: 11, borderRadius: 11, background: color}} />
);
