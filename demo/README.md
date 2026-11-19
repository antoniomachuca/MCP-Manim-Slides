# Demo video

The README demo (`../assets/demo.mp4`, `../assets/demo.gif`) is a [HyperFrames](https://hyperframes.heygen.com) project.

- `index.html` mounts five scenes from `compositions/`: ask, byhand, session, result, end.
- `manim/pythagoras.py` is the deck the video shows. It was rendered through this server's tools;
  their real results are in `manim/mcp_results.json` (paths anonymised, render logs omitted).
- `compositions/session.html` is generated: edit `manim/session.template.html` or
  `manim/build_session.py`, then run `python3 manim/build_session.py`.
- `assets/deck.mp4` and the contact sheets are the files `export_video` and `contact_sheet` wrote.

```bash
npx hyperframes preview                                # edit in the browser
npx hyperframes render -q delivery -o renders/demo.mp4 # render
```
