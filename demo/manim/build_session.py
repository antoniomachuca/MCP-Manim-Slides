"""Write compositions/session.html from the real MCP results in mcp_results.json.

The terminal copy shown in the film is taken from the tool results the MCP server
returned when the deck was rendered (see ../README.md). Run from demo/:

    python3 manim/build_session.py
"""

import html
import json
import pathlib

HERE = pathlib.Path(__file__).parent
OUT = HERE.parent / "compositions" / "session.html"
R = json.loads((HERE / "mcp_results.json").read_text())

LINE = 42  # px, 28 px mono at 1.5
GAP = 16  # px before each new block
VIEW_H = 940


def json_lines(key):
    return R["_result_line_counts"][key]


def e(s):
    return html.escape(s, quote=False)


PROMPT = [
    "Make a three-slide deck on the Pythagorean theorem:",
    "the statement, a visual proof, the 3-4-5 check.",
]
SCENES = '["TitleSlide", "SquareProof", "Check"]'
sync = R["3_sync_deck"]
rendered = json.dumps(sync["rendered"])
reused = json.dumps(sync["reused"])
export = R["5_export_video"]
sheet1 = R["2_contact_sheet_v1"]

# (id, kind, [html lines], at seconds, block start?)
ROWS = [
    ("hist", "hist", [e(x) for x in PROMPT], 2.88, True),
    (
        "say1",
        "say",
        [e("I'll write the three Manim scenes and render them.")],
        3.15,
        True,
    ),
    (
        "t-exec",
        "tool",
        [
            '<b>manim-slides - execute_manim_code</b> (MCP)(code: "from',
            e('manim import …", scenes: ' + SCENES + ","),
            e('quality: "h")'),
        ],
        3.45,
        True,
    ),
    ("r-exec", "res", ["&nbsp;"], 3.6, False),
    (
        "r-exec2",
        "cont",
        [e(f"… +{json_lines('1_execute_manim_code') - 2} lines (ctrl+r to expand)")],
        6.1,
        False,
    ),
    (
        "t-sheet",
        "tool",
        [
            "<b>manim-slides - contact_sheet</b> (MCP)(scenes: [",
            e('"TitleSlide", "SquareProof", "Check"], dest:'),
            e('"contact_sheet_v1.png")'),
        ],
        6.5,
        True,
    ),
    (
        "r-sheet",
        "res",
        [
            e(
                f'"success": {str(sheet1["success"]).lower()}, '
                f'"slide_count": {sheet1["slide_count"]}, '
                f'"rows": {sheet1["rows"]}, "columns": {sheet1["columns"]}'
            )
        ],
        6.9,
        False,
    ),
    (
        "say2",
        "say",
        [
            e("The side labels in SquareProof are too small to read."),
            e("I'll enlarge them and re-sync only that scene."),
        ],
        7.7,
        True,
    ),
    ("t-edit", "tool", ["<b>Update</b>(pythagoras.py)"], 8.6, True),
    (
        "r-edit",
        "res",
        [e("Updated pythagoras.py with 3 additions and 3 removals")],
        8.8,
        False,
    ),
    (
        "d-minus",
        "minus",
        [e(' 97 -  label_a = MathTex("a = 3", font_size=40,')],
        8.95,
        False,
    ),
    (
        "d-plus",
        "plus",
        [e(' 97 +  label_a = MathTex("a = 3", font_size=100,')],
        9.05,
        False,
    ),
    (
        "t-sync",
        "tool",
        [
            '<b>manim-slides - sync_deck</b> (MCP)(code: "from manim',
            e('import …", scenes: ' + SCENES + ","),
            e('dest: "deck.html", quality: "h")'),
        ],
        9.6,
        True,
    ),
    (
        "r-sync",
        "res",
        ['"rendered": <span class="hl" id="ss-hl1">' + e(rendered) + "</span>,"],
        11.0,
        False,
    ),
    (
        "r-sync2",
        "cont",
        ['"reused": <span class="ok">' + e(reused) + "</span>,"],
        11.1,
        False,
    ),
    (
        "r-sync3",
        "cont",
        [e(f"… +{json_lines('3_sync_deck') - 3} lines (ctrl+r to expand)")],
        11.2,
        False,
    ),
    (
        "t-sheet2",
        "tool",
        ['<b>manim-slides - contact_sheet</b> (MCP)(dest: "contact_sheet.png")'],
        11.6,
        True,
    ),
    (
        "r-sheet2",
        "res",
        [e('"success": true, "dest": "…/contact_sheet.png"')],
        11.9,
        False,
    ),
    (
        "t-export",
        "tool",
        [
            '<b>manim-slides - export_video</b> (MCP)(dest: "deck.mp4",',
            e('fps: 60, transition: "fade")'),
        ],
        12.4,
        True,
    ),
    (
        "r-export",
        "res",
        [
            e(
                f'"success": true, "slide_count": {export["slide_count"]}, '
                f'"duration": {export["duration"]}'
            )
        ],
        12.9,
        False,
    ),
    (
        "say3",
        "say",
        [
            "Done: <u>deck.html</u> and <u>deck.mp4</u>, 6 slides at 1080p60.",
            e("Only SquareProof was rendered again; the other two"),
            e("scenes came from the cache."),
        ],
        13.35,
        True,
    ),
]

TOOL_DONE = {
    "t-exec": 6.1,
    "t-sheet": 6.9,
    "t-edit": 8.8,
    "t-sync": 11.0,
    "t-sheet2": 11.9,
    "t-export": 12.9,
}
SPIN = [(3.45, 6.1, "Rendering…"), (9.6, 11.0, "Syncing…"), (12.4, 12.9, "Exporting…")]

progress = [p["message"] for p in R["progress"] if "frames" in p["message"]]
step = max(1, len(progress) // 14)
progress = progress[::step][:14] + [progress[-1]]

WELCOME_H = 3 * LINE + 2 * 18 + 4 + 28  # box + margin below


def row_html(rid, kind, lines):
    gutter = {
        "hist": "&gt;",
        "say": '<span class="b w">⏺</span>',
        "tool": f'<span class="b st" id="ss-b-{rid}">⏺</span>',
        "res": "&nbsp;&nbsp;⎿",
        "cont": "",
        "minus": "",
        "plus": "",
    }[kind]
    body = "\n".join(f'<div class="l">{ln}</div>' for ln in lines)
    return (
        f'      <div id="ss-{rid}" class="row {kind} hide">'
        f'<div class="g">{gutter}</div><div class="t">{body}</div></div>'
    )


rows_html = "\n".join(row_html(r[0], r[1], r[2]) for r in ROWS)

# Content bottom after each row appears (fixed line metrics, no measuring).
bottoms = []
y = WELCOME_H
for _rid, _kind, lines, at, block in ROWS:
    if block:
        y += GAP
    y += len(lines) * LINE
    bottoms.append((at, y))
FOOTER = LINE + 12 + (2 * LINE + 24)  # spinner row + input box (2 lines)

scroll = []
prev = 0
for at, bottom in bottoms:
    target = min(0, VIEW_H - (bottom + FOOTER))
    if target != prev:
        scroll.append((at, prev, target))
        prev = target

js_rows = json.dumps([[r[0], r[3]] for r in ROWS])
js_tools = json.dumps(TOOL_DONE)
js_spin = json.dumps(SPIN)
js_scroll = json.dumps(scroll)
js_progress = json.dumps(progress)
prompt_text = json.dumps("\n".join(PROMPT))

TEMPLATE = (HERE / "session.template.html").read_text()
out = (
    TEMPLATE.replace("__ROWS__", rows_html)
    .replace("__JS_ROWS__", js_rows)
    .replace("__JS_TOOLS__", js_tools)
    .replace("__JS_SPIN__", js_spin)
    .replace("__JS_SCROLL__", js_scroll)
    .replace("__JS_PROGRESS__", js_progress)
    .replace("__PROMPT__", prompt_text)
)
OUT.write_text(out)
print(f"wrote {OUT} ({len(ROWS)} rows, final scroll {prev}px)")
