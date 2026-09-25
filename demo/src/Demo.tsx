import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {Browser} from "./Browser";
import {Desktop} from "./Desktop";
import {
  BROWSER_AT,
  ZOOM_IN_END,
  ZOOM_IN_START,
  ZOOM_OUT_END,
  ZOOM_OUT_START,
  colors,
} from "./theme";

export const Demo = () => {
  const frame = useCurrentFrame();
  const zoom = interpolate(
    frame,
    [ZOOM_IN_START, ZOOM_IN_END, ZOOM_OUT_START, ZOOM_OUT_END],
    [1, 1.72, 1.72, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.inOut(Easing.cubic),
    },
  );
  const toBrowser = interpolate(frame, [BROWSER_AT - 8, BROWSER_AT + 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background: colors.desk,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          opacity: 1 - toBrowser,
          transform: `scale(${zoom})`,
          transformOrigin: "42% 90%",
        }}
      >
        <Desktop />
      </div>
      <AbsoluteFill
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          opacity: toBrowser,
        }}
      >
        <Browser />
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
