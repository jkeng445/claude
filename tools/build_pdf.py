"""Render a set of markdown files into one styled, printable HTML document."""

import csv
import html
import re
import sys
from pathlib import Path

import markdown

CSS = """
@page { size: A4; margin: 20mm 18mm 16mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
body { font: 10.5pt/1.55 "Source Serif 4","Georgia",serif; color:#1a1d24; margin:0; }
h1,h2,h3,h4 { font-family:"Inter","Helvetica Neue",Arial,sans-serif; color:#0f1838;
              line-height:1.2; }
h1 { font-size:20pt; margin:0 0 .5em; padding-bottom:.25em; border-bottom:2.5pt solid #1d6fd0;
     break-before:page; break-after:avoid; }
h1.first { break-before:avoid; }
h2 { font-size:14pt; margin:1.5em 0 .4em; break-after:avoid; }
h3 { font-size:11.5pt; margin:1.2em 0 .3em; break-after:avoid; }
h4 { font-size:10.5pt; margin:1em 0 .3em; break-after:avoid; }
p, li { orphans:3; widows:3; }
p { margin:.5em 0; }
ul,ol { margin:.5em 0; padding-left:1.3em; }
li { margin:.22em 0; }
strong { color:#0f1838; }
code { font-family:"SF Mono",Menlo,Consolas,monospace; font-size:.85em;
       background:#f1f3f7; padding:.1em .3em; border-radius:2px; }
pre { background:#f6f7f9; border-left:3pt solid #c9d2e0; padding:.7em .9em;
      font-size:8.5pt; line-height:1.4; overflow-wrap:anywhere; white-space:pre-wrap;
      break-inside:avoid; margin:.7em 0; }
pre code { background:none; padding:0; font-size:inherit; }
blockquote { margin:.8em 0; padding:.5em .9em; border-left:3pt solid #1d6fd0;
             background:#f4f7fc; break-inside:avoid; }
blockquote p { margin:.25em 0; }
table { border-collapse:collapse; width:100%; margin:.8em 0; font-size:9pt;
        break-inside:auto; font-family:"Inter",Arial,sans-serif; }
thead { display:table-header-group; }
tr { break-inside:avoid; }
th,td { border:.5pt solid #ccd3df; padding:.38em .5em; text-align:left; vertical-align:top; }
th { background:#eef2f8; font-weight:600; font-size:8.2pt; text-transform:uppercase;
     letter-spacing:.04em; color:#3b4557; }
tbody tr:nth-child(even) { background:#fafbfd; }
hr { border:0; border-top:.5pt solid #d8dee8; margin:1.4em 0; }
a { color:#1d6fd0; text-decoration:none; }
input[type=checkbox] { margin-right:.3em; }

/* Cover */
.cover { height:297mm; padding:40mm 24mm 24mm; display:flex; flex-direction:column;
         break-after:page; background:#0f1838; color:#fff; }
.cover .kicker { font-family:"Inter",Arial,sans-serif; font-size:9pt; letter-spacing:.22em;
                 text-transform:uppercase; color:#7fb0ef; margin-bottom:10mm; }
.cover h1 { font-size:34pt; border:0; color:#fff; margin:0 0 6mm; break-before:avoid;
            line-height:1.1; }
.cover .sub { font-size:13pt; color:#c7d2e6; max-width:120mm; line-height:1.5; }
.cover .spacer { flex:1; }
.cover .meta { font-family:"Inter",Arial,sans-serif; font-size:8.5pt; color:#8fa0c0;
               border-top:.5pt solid #33406b; padding-top:4mm; }
.cover .rule { width:28mm; height:3pt; background:#1d6fd0; margin:8mm 0; }

/* Contents */
.toc { break-after:page; }
.toc h1 { break-before:avoid; }
.toc ol { list-style:none; padding:0; counter-reset:toc; font-family:"Inter",Arial,sans-serif; }
.toc li { counter-increment:toc; padding:.42em 0; border-bottom:.5pt dotted #d2d9e4;
          font-size:10.5pt; }
.toc li::before { content:counter(toc) ". "; color:#1d6fd0; font-weight:600; }
.toc .note { font-family:"Source Serif 4",Georgia,serif; font-size:9.5pt; color:#5a6478;
             margin-top:1.5em; border-bottom:0; }
"""


def md_to_html(text: str) -> str:
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
    )


def csv_to_html(path: Path) -> str:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    head, body = rows[0], rows[1:]
    out = ["<table><thead><tr>"]
    out += [f"<th>{html.escape(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for r in body:
        out.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in r) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def build(title: str, subtitle: str, sections: list[tuple[str, Path]], out: Path) -> None:
    parts = [
        f"""<!doctype html><html><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>""",
        f"""<div class="cover"><div class="kicker">Working document</div>
<h1>{html.escape(title)}</h1><div class="rule"></div>
<div class="sub">{html.escape(subtitle)}</div><div class="spacer"></div>
<div class="meta">Prepared with Claude Code &middot; October 2026</div></div>""",
        '<div class="toc"><h1 class="first">Contents</h1><ol>',
    ]
    parts += [f"<li>{html.escape(name)}</li>" for name, _ in sections]
    parts.append(
        '<p class="note">Figures for growth, timelines and prices in this document are '
        "planning estimates, not measured research. Test them against your own results "
        "and adjust.</p></ol></div>"
    )

    for name, path in sections:
        if path.suffix == ".csv":
            body = csv_to_html(path)
            parts.append(f"<h1>{html.escape(name)}</h1>{body}")
            continue
        text = path.read_text(encoding="utf-8")
        # Drop the file's own H1 — the section heading replaces it.
        text = re.sub(r"\A\s*#\s+.*\n", "", text, count=1)
        parts.append(f"<h1>{html.escape(name)}</h1>{md_to_html(text)}")

    parts.append("</body></html>")
    out.write_text("".join(parts), encoding="utf-8")


if __name__ == "__main__":
    import json

    spec = json.loads(Path(sys.argv[1]).read_text())
    build(
        spec["title"],
        spec["subtitle"],
        [(n, Path(p)) for n, p in spec["sections"]],
        Path(spec["out"]),
    )
    print("wrote", spec["out"])
