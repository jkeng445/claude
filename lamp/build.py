"""Build lamp-designer.html from template.html + every adire-*.svg in the repo root.

Pulls each file's <title> and its seamless <pattern id="tile"> block, so a new
pattern SVG dropped in the root shows up in the designer after a rebuild:

    python3 lamp/build.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent

patterns = []
for svg in sorted(ROOT.glob("adire-*.svg")):
    text = svg.read_text(encoding="utf-8")
    title = re.search(r"<title>(.*?)</title>", text, re.S).group(1).strip()
    tile = re.search(r'<pattern id="tile"(.*?)>(.*?)</pattern>', text, re.S)
    size = int(re.search(r'width="(\d+)"', tile.group(1)).group(1))
    body = re.sub(r"<!--.*?-->", "", tile.group(2), flags=re.S)
    body = re.sub(r"\s+", " ", body).strip()
    patterns.append({"id": svg.stem, "name": title.split("—")[0].strip(),
                     "size": size, "body": body})

template = (HERE / "template.html").read_text(encoding="utf-8")
out = template.replace("/*__PATTERNS__*/[]", json.dumps(patterns, ensure_ascii=False))
(HERE / "lamp-designer.html").write_text(out, encoding="utf-8")
print(f"Built lamp-designer.html with {len(patterns)} patterns")
