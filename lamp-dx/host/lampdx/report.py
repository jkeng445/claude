"""Self-contained HTML run report: verdicts, control checks and per-well curves."""
from __future__ import annotations

import html

COLORS = {"POSITIVE": "#C4622D", "NEGATIVE": "#1B2A6B", "INDETERMINATE": "#B08900"}


def _curve_svg(t, ys, threshold_tt, color, w=260, h=120, ymax=None):
    if not t:
        return ""
    tmax = max(t) or 1
    ymin = min(min(ys), 0)
    ymax = ymax or max(max(ys), 0.3)
    sx = lambda v: 30 + (w - 40) * v / tmax
    sy = lambda v: h - 20 - (h - 30) * (v - ymin) / ((ymax - ymin) or 1)
    pts = " ".join(f"{sx(a):.1f},{sy(b):.1f}" for a, b in zip(t, ys))
    tt = (f'<line x1="{sx(threshold_tt):.1f}" y1="8" x2="{sx(threshold_tt):.1f}" y2="{h-20}" '
          f'stroke="{color}" stroke-dasharray="3 3"/>') if threshold_tt is not None else ""
    return (f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
            f'<line x1="30" y1="{h-20}" x2="{w-10}" y2="{h-20}" stroke="#999"/>'
            f'<line x1="30" y1="8" x2="30" y2="{h-20}" stroke="#999"/>'
            f'<text x="{w-10}" y="{h-6}" font-size="10" text-anchor="end" fill="#666">{tmax:.0f} min</text>'
            f'{tt}<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>')


def render(run: dict) -> str:
    res = run["result"]
    t = run["t_min"]
    rows = "".join(
        f"<tr><td>{html.escape(sid)}</td><td>{html.escape(s['target'])}</td><td><b>{html.escape(s['verdict'])}</b></td>"
        f"<td>{'' if s['tt_min'] is None else f'{s['tt_min']:.1f}'}</td><td>{s['confidence']:.2f}</td></tr>"
        for sid, s in res["samples"].items())
    issues = "".join(f"<li>{html.escape(i)}</li>" for i in res["issues"]) or "<li>All controls passed</li>"
    cards = []
    for w in run["layout"]["wells"]:
        name = w["name"]
        r = res["wells"][name]
        sig = run["signals"][name]
        base = sorted(sig[: max(3, len(sig) // 8)])[len(sig[: max(3, len(sig) // 8)]) // 2] or 1
        rise = [(v - base) / abs(base) for v in sig]
        why = "".join(f"<li>{html.escape(x)}</li>" for x in r["reasons"])
        cards.append(
            f'<div class="card"><h3>{html.escape(name)} <small>{w["role"].upper()}</small></h3>'
            f'<p style="color:{COLORS[r["call"]]}"><b>{r["call"]}</b>'
            f'{"" if r["tt_min"] is None else f" · Tt {r["tt_min"]:.1f} min"} · conf {r["confidence"]:.2f}</p>'
            f'{_curve_svg(t, rise, r["tt_min"], COLORS[r["call"]])}<ul>{why}</ul></div>')
    status = "VALID" if res["run_valid"] else "INVALID"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>LAMP-Dx Run Report</title>
<style>
:root{{--bg:#fff;--ink:#1a1a1a;--muted:#666;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--ink:#eee;--muted:#aaa;--line:#333}}}}
body{{background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif;max-width:1000px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%}}td,th{{border-bottom:1px solid var(--line);padding:6px;text-align:left}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}}
.card{{border:1px solid var(--line);border-radius:8px;padding:10px}}.card h3{{margin:0}}small{{color:var(--muted)}}
.ruo{{background:#fff3cd;color:#664d03;padding:8px;border-radius:6px}}
</style></head><body>
<h1>KJG-2026-002 LAMP-Dx: run report</h1>
<p class="ruo"><b>For research use only.</b> Not for use in diagnostic procedures. Not cleared or approved by any regulator.</p>
<p>Run ID {html.escape(run['run_id'])} · {html.escape(run['started'])} · block {run['block_c']} °C · {run['mode']} · run is <b>{status}</b></p>
<h2>Controls</h2><ul>{issues}</ul>
<h2>Results</h2><table><tr><th>Sample</th><th>Target</th><th>Verdict</th><th>Tt (min)</th><th>Confidence</th></tr>{rows}</table>
<h2>Wells</h2><div class="grid">{''.join(cards)}</div>
<p><small>Calls are rule-based (threshold time, sigmoid fit, cutoff {run['cutoff_min']:.0f} min). Confidence comes from an advisory model ({run['model_trained_on']} labelled runs).</small></p>
</body></html>"""
