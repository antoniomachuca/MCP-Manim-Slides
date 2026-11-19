# SPEC: MCP-Manim-Slides demo film

GOAL:    a developer sees Claude Code call the manim-slides MCP tools and get a real, animated
         Manim deck back, then wants to star and clone the repo.
OUTPUT:  HyperFrames, 1920 x 1080, 30 fps. English copy (the repo is in English).
TIME:    40 s x 30 = 1200 frames. Placed SFX only (no music catalog sign-in).

STORY:   one task, one piece of data: "a three-slide deck on the Pythagorean theorem".
         It is asked for, done the slow way (code + CLI), redone by Claude Code through the MCP,
         and the real deck it produced plays. Grammar taken from the two reference films the
         person gave (light question pill, a Human/Agent toggle flooding into a dark Claude Code
         session, a result card popping out of the terminal, light end card with command + Star).

LOOK:
  ground light   #F1F0EC flat, no texture (asks, by-hand world, end card)
  ground dark    #0D0D0F flat (Claude Code world), terminal ink #E8E6E1, dim #7D7B76
  ink            #17171A
  accent         #E07A5F coral (the deck's a² colour): one word per shot, the pay-off underline,
                 the toggle's active half, the end-card "$". Claude Code's own orange #D97757 only
                 on its own UI (welcome star, spinner).
  deck colours   coral #E07A5F, blue #6C8EBF, green #87C2A5 come from the rendered deck itself.
  display        Inter 900, -3% tracking; titles 76-96 px; UI copy Inter 600 34 px
  terminal       JetBrains Mono 400/700 26 px, line-height 1.5 (the real TUI's mono)
  depth          cards: 0 24px 60px rgba(0,0,0,.18), radius 18 px. No glow, no gradients.

OBJECTS:
  question pill  white, 1000 x 96 px, radius 48, magnifier glyph, return-key chip
  editor+shell   the real demo/manim/pythagoras.py scrolling, the real manim-slides CLI commands
  counter chip   black pill top-right: files · lines · commands, ticking up as they happen
  toggle         "By hand | Agent" pill; the cursor clicks Agent and its fill floods the frame
  Claude Code    the real TUI: welcome box, "> " prompt, "⏺ manim-slides - tool (MCP)(…)" calls,
                 "⎿" results copied from the real MCP JSON (demo/manim/mcp_results.json)
  result card    the real contact_sheet.png the MCP produced, tilted 3°, pops out of the terminal
  deck player    the real deck.mp4 exported by export_video, inside a browser window "deck.html"

MOTION:
  enter   expo.out 0.5-0.7 s;  move/camera power2.inOut 0.6 s;  exit power3.in 0.3 s
  springs back.out(1.4) on the result card scale only
  typing  ~28 chars/s prompts, ~60 chars/s code; stagger lines 60 ms

SHOTS:
  0.0-3.4    ask      pill types "Make a three-slide deck on the Pythagorean theorem"
  3.4-10.2   byhand   pill parks as the task header; pythagoras.py scrolls, shell runs render +
                      convert, counter reaches 1 file · 189 lines · 2 commands; cursor clicks
                      "With the MCP"
  9.5-27.0   session  iris from the click into Claude Code: prompt; execute_manim_code with live
                      progress; contact_sheet card pops, ring on the SquareProof tile; Claude says
                      the labels are too small; Update diff (font_size 40 -> 100); sync_deck
                      returns rendered ["SquareProof"], reused ["TitleSlide", "Check"]; the card's
                      sheet swaps to the fixed one; export_video; summary; card carried to centre
  27.0-34.4  result   card grows into the deck.mp4 player, night floods to light, cells fly into c²
  34.2-40.0  end      wordmark, git clone typed, cursor clicks Star -> Starred, hold
BANNED:  dark void with floating smalls; glow/particles; purple-blue gradients; glass cards;
         everything fading + sliding up; three cards in a row; logo docked in a corner;
         invented UI or numbers that the MCP did not return; redrawn Manim logo.
QA:      t=2.5 pill readable; t=8.5 counter + toggle; t=15 tool call legible; t=19 card;
         t=27 deck mid-proof full size; t=34 end card with Starred.
