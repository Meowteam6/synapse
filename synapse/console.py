"""
Renders a certification record to a static HTML console.

There is no build toolchain here on purpose. The facility's own machine
produces the artifact, as a single file with no scripts, no fonts, and no
network requests -- it renders identically with the wifi off, which is the
claim the rest of the product makes about everything else. It is also one
less thing that can break at 3:40pm.

The visual reference is a nurses' station at 3am rather than a SaaS
dashboard: a dark room, a call panel with a few lit indicators, and a chart
written in a fixed-width hand. Reading order follows the decision a
Director of Nursing actually makes -- may this run tonight, on what
evidence, against which standard, and where exactly did it fail.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

SEVERITY_RANK = {"high": 0, "med": 1, "low": 2}

CSS = """
:root{--bg:#0a0e13;--surface:#111823;--surface-2:#161f2c;--line:#1f2a38;
--line-bright:#2c3a4c;--text:#dbe3ed;--text-dim:#7a8b9e;--text-faint:#4d5c6d;
--pass:#4fb477;--fail:#e0553f;--warn:#d9a441;--info:#6ba8d6;
--fail-wash:rgba(224,85,63,.09);--gutter:clamp(1.25rem,4vw,3.5rem);
--mono:ui-monospace,"SF Mono",SFMono-Regular,Menlo,"Roboto Mono",monospace;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
*{box-sizing:border-box}
html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
font-family:var(--mono);font-size:15px;line-height:1.55;-webkit-font-smoothing:antialiased}
body{background-image:radial-gradient(120% 60% at 50% 0%,rgba(107,168,214,.06),transparent 60%);
background-repeat:no-repeat}
.shell{max-width:1100px;margin:0 auto;padding:0 var(--gutter) 5rem}
.masthead{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
flex-wrap:wrap;padding:1.75rem 0 1rem;border-bottom:1px solid var(--line)}
.wordmark{font-size:.95rem;font-weight:600;letter-spacing:.22em;text-transform:uppercase;margin:0}
.wordmark span{color:var(--text-faint);font-weight:400}
.masthead-meta{font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-faint)}
.record{display:grid;grid-template-columns:auto 1fr;gap:clamp(1.5rem,5vw,3.5rem);
align-items:center;padding:clamp(2rem,6vw,3.5rem) 0;border-bottom:1px solid var(--line)}
.stamp{--s:var(--fail);border:3px solid var(--s);color:var(--s);padding:.75rem 1.25rem .6rem;
transform:rotate(-3deg);text-align:center;animation:in .5s cubic-bezier(.16,1,.3,1) both}
.stamp[data-v="CLEARED"]{--s:var(--pass)}
.stamp-verdict{font-size:clamp(1.6rem,5vw,2.4rem);font-weight:700;letter-spacing:.1em;line-height:1;display:block}
.stamp-rule{height:1px;background:currentColor;opacity:.45;margin:.55rem 0 .4rem}
.stamp-caption{font-size:.6rem;letter-spacing:.2em;text-transform:uppercase;opacity:.85;display:block}
@keyframes in{from{opacity:0;transform:rotate(-3deg) scale(1.35)}to{opacity:1;transform:rotate(-3deg) scale(1)}}
.record-title{font-size:clamp(1.5rem,4vw,2.1rem);font-weight:600;margin:0 0 .4rem;letter-spacing:-.01em}
.record-line{color:var(--text-dim);font-size:.85rem;margin:0}
.record-consequence{margin:1rem 0 0;padding-left:.85rem;border-left:2px solid var(--fail);
font-size:.9rem;max-width:52ch}
.record-consequence[data-v="CLEARED"]{border-left-color:var(--pass)}
.section{padding:2.5rem 0 0}
.section-label{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:var(--text-faint);
margin:0 0 1rem;display:flex;align-items:center;gap:.75rem}
.section-label::after{content:"";flex:1;height:1px;background:var(--line)}
.provenance{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:1px;
background:var(--line);border:1px solid var(--line)}
.prov-cell{background:var(--surface);padding:.85rem 1rem}
.prov-key{font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--text-faint);margin-bottom:.3rem}
.prov-value{font-size:.86rem;word-break:break-word}
.tag{display:inline-block;font-size:.6rem;letter-spacing:.12em;text-transform:uppercase;
padding:.1rem .4rem;border:1px solid currentColor;margin-left:.4rem;vertical-align:1px}
.tag-local{color:var(--pass)}.tag-remote{color:var(--info)}
.rubric{border:1px solid var(--line);border-bottom:none}
.check{display:grid;grid-template-columns:4px 1fr auto auto;align-items:center;gap:0 1rem;
padding:.7rem 1rem .7rem 0;border-bottom:1px solid var(--line);background:var(--surface)}
.check[data-state="fail"]{background:var(--fail-wash)}
.check[data-state="skip"]{opacity:.55}
.check-bar{align-self:stretch;background:var(--pass)}
.check[data-state="fail"] .check-bar{background:var(--fail)}
.check[data-state="skip"] .check-bar{background:var(--text-faint)}
.check-id{font-size:.85rem}
.check-desc{font-size:.74rem;color:var(--text-dim);margin-top:.15rem;max-width:68ch}
.check-score{font-size:.8rem;color:var(--text-dim);font-variant-numeric:tabular-nums}
.check-sev{font-size:.6rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-faint);
padding-right:1rem;min-width:4.5rem;text-align:right}
.check[data-sev="high"] .check-sev{color:var(--warn)}
.finding{border:1px solid var(--line);border-left:3px solid var(--fail);background:var(--surface);margin-bottom:1rem}
.finding-head{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;
flex-wrap:wrap;padding:.85rem 1.1rem;border-bottom:1px solid var(--line)}
.finding-check{font-size:.85rem;color:var(--fail)}
.finding-tags{font-size:.62rem;letter-spacing:.14em;text-transform:uppercase;color:var(--text-faint)}
.finding-body{padding:1.1rem;display:grid;gap:1.1rem}
.utterance{font-family:var(--sans);font-size:1.02rem;line-height:1.5;border-left:2px solid var(--line-bright);
padding-left:.9rem;margin:0}
.utterance-who{display:block;font-family:var(--mono);font-size:.62rem;letter-spacing:.16em;
text-transform:uppercase;color:var(--text-faint);margin-bottom:.35rem}
.did{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;font-size:.85rem}
.did-key{font-size:.62rem;letter-spacing:.16em;text-transform:uppercase;color:var(--text-faint)}
.pill{border:1px solid var(--line-bright);padding:.15rem .55rem;font-size:.78rem;background:var(--surface-2)}
.why{font-family:var(--sans);font-size:.88rem;color:var(--text-dim);margin:0;max-width:74ch}
.why strong{color:var(--warn);font-family:var(--mono);font-size:.68rem;letter-spacing:.16em;
text-transform:uppercase;display:block;margin-bottom:.3rem;font-weight:400}
.footnote{margin-top:3rem;padding-top:1.25rem;border-top:1px solid var(--line);font-family:var(--sans);
font-size:.78rem;color:var(--text-faint);max-width:78ch;line-height:1.7}
@media(max-width:640px){.record{grid-template-columns:1fr}.stamp{justify-self:start}
.check{grid-template-columns:4px 1fr auto}.check-sev{display:none}}
@media(prefers-reduced-motion:reduce){*{animation:none!important}}
"""

PILL_FIELDS = ("urgency", "escalate_to", "outcome")


def esc(value: Any) -> str:
    """HTML-escape a value for safe interpolation."""
    return html.escape(str(value), quote=True)


def _order_checks(checks: list[dict]) -> list[dict]:
    """Order checks so what decides the verdict reads first."""
    return sorted(
        checks,
        key=lambda c: (
            SEVERITY_RANK.get(c["severity"], 3),
            0 if c["total"] and c["passed"] < c["total"] else 1,
            c["id"],
        ),
    )


def _check_state(check: dict) -> str:
    """Return the display state for a check row."""
    if check["total"] == 0:
        return "skip"
    return "pass" if check["passed"] == check["total"] else "fail"


def _pills(response: dict) -> list[str]:
    """Reduce an agent response to the fields that carry the decision."""
    found = [
        f"{field}: {response[field]}"
        for field in PILL_FIELDS
        if isinstance(response.get(field), str)
    ]
    return found or ["no decision returned"]


def _render_provenance(report: dict) -> str:
    """Render the provenance strip."""
    prov = report["provenance"]
    author = prov["author_model"]
    remote = author.startswith("cerebras:")

    cells = [
        (
            "Care tier",
            f'{esc(prov["care_model"])}<span class="tag tag-local">on-device</span>',
        ),
        (
            "Author tier",
            f'{esc(author.removeprefix("cerebras:"))}'
            f'<span class="tag {"tag-remote" if remote else "tag-local"}">'
            f'{"cerebras" if remote else "on-device"}</span>',
        ),
        ("Resident data egress", esc(prov["network_egress"])),
        ("Seed", f'{esc(prov["seed"])} &middot; reproducible'),
        ("Host", esc(prov["host"]["machine"])),
        ("Scenario source", "generated from rubric"),
    ]
    body = "".join(
        f'<div class="prov-cell"><div class="prov-key">{key}</div>'
        f'<div class="prov-value">{value}</div></div>'
        for key, value in cells
    )
    return f'<div class="provenance">{body}</div>'


def _render_checks(report: dict) -> str:
    """Render the rubric grid."""
    rows = []
    for check in _order_checks(report["checks"]):
        score = "not run" if check["total"] == 0 else f'{check["passed"]}/{check["total"]}'
        rows.append(
            f'<div class="check" data-state="{_check_state(check)}" '
            f'data-sev="{esc(check["severity"])}">'
            f'<div class="check-bar"></div>'
            f'<div><div class="check-id">{esc(check["id"])}</div>'
            f'<div class="check-desc">{esc(check["description"])}</div></div>'
            f'<div class="check-score">{score}</div>'
            f'<div class="check-sev">{esc(check["severity"])}</div></div>'
        )
    return f'<div class="rubric">{"".join(rows)}</div>'


def _render_findings(report: dict) -> str:
    """Render one card per failing scenario."""
    failures = [f for c in _order_checks(report["checks"]) for f in c["failures"]]
    if not failures:
        return ""

    cards = []
    for failure in failures:
        scenario = failure["scenario"]
        pills = "".join(f'<span class="pill">{esc(p)}</span>' for p in _pills(failure["response"]))
        cards.append(
            f'<article class="finding">'
            f'<div class="finding-head">'
            f'<span class="finding-check">{esc(failure["check_id"])}</span>'
            f'<span class="finding-tags">{esc(failure["severity"])} &middot; '
            f'{esc(scenario["difficulty"])} &middot; {esc(failure["layer"])}</span></div>'
            f'<div class="finding-body">'
            f'<blockquote class="utterance"><span class="utterance-who">'
            f'{esc(scenario["resident_name"])}, room {esc(scenario["room"])}, '
            f'{esc(scenario["time"])}</span>&ldquo;{esc(scenario["utterance"])}&rdquo;</blockquote>'
            f'<div class="did"><span class="did-key">Agent returned</span>{pills}</div>'
            f'<p class="why"><strong>Why it failed</strong>{esc(failure["reasoning"])}</p>'
            f'</div></article>'
        )

    plural = "scenario" if len(failures) == 1 else "scenarios"
    return (
        f'<section class="section"><h3 class="section-label">Findings &middot; '
        f'{len(failures)} failing {plural}</h3>{"".join(cards)}</section>'
    )


def render_record(report: dict) -> str:
    """Render one agent's certification record as an HTML fragment."""
    cleared = report["verdict"] == "CLEARED"
    blocking = report["blocking_failures"]
    high = sum(1 for c in report["checks"] if c["severity"] == "high")

    if cleared:
        consequence = (
            "Every blocking check held across all generated scenarios. "
            "This agent is cleared to run in a facility."
        )
    else:
        consequence = (
            f'{blocking} blocking {"failure" if blocking == 1 else "failures"} on '
            f"high-severity checks. A resident could be harmed. Deployment is "
            f"blocked until these are fixed and the agent re-certified."
        )

    return f"""
<section class="record">
  <div class="stamp" data-v="{esc(report["verdict"])}">
    <span class="stamp-verdict">{esc(report["verdict"])}</span>
    <div class="stamp-rule"></div>
    <span class="stamp-caption">{"may run tonight" if cleared else "may not run"}</span>
  </div>
  <div>
    <h2 class="record-title">{esc(report["agent"])}</h2>
    <p class="record-line">{len(report["checks"])} declared checks &middot; {high} blocking
      &middot; {report["scenarios_run"]} scenarios &middot;
      {round(report["pass_rate"] * 100)}% passed</p>
    <p class="record-consequence" data-v="{esc(report["verdict"])}">{esc(consequence)}</p>
  </div>
</section>
<section class="section"><h3 class="section-label">Provenance</h3>{_render_provenance(report)}</section>
<section class="section"><h3 class="section-label">Rubric &middot; declared by the agent,
  graded against itself</h3>{_render_checks(report)}</section>
{_render_findings(report)}
"""


def render_console(reports: list[dict]) -> str:
    """Render the full console page for every published record.

    Args:
        reports: certification records, as written by `synapse certify`.

    Returns:
        A complete, self-contained HTML document.
    """
    if not reports:
        body = (
            '<section class="section"><div class="prov-cell">'
            "No certification records published yet. Run "
            "<code>synapse certify night-triage</code> then "
            "<code>synapse publish</code>.</div></section>"
        )
        generated = ""
    else:
        body = "".join(render_record(r) for r in reports)
        generated = esc(reports[0]["generated_at"])

    care = reports[0]["provenance"]["care_model"] if reports else "the facility model"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synapse &mdash; certification record</title>
<meta name="description" content="Certification records for on-device healthcare agents.
Every agent is tested against its own declared rubric before it runs in a facility.">
<style>{CSS}</style>
</head>
<body>
<main class="shell">
  <header class="masthead">
    <h1 class="wordmark">Synapse <span>/ certification record</span></h1>
    <div class="masthead-meta">{generated}</div>
  </header>
  {body}
  <p class="footnote">
    Every resident on this page is fictional and was generated on the certifying
    machine from the agent&rsquo;s own rubric. No patient data was used to produce
    this record, and none is required to reproduce it: the same rubric and the same
    seed yield the same scenarios and the same verdict. Care-tier inference ran on
    {esc(care)} on that host and never left it.
  </p>
</main>
</body>
</html>
"""


def write_console(reports: list[dict], out_dir: Path) -> Path:
    """Write the console to disk as a single static file.

    Args:
        reports: certification records to render.
        out_dir: directory to write into; created if absent.

    Returns:
        The path to index.html.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "index.html"
    path.write_text(render_console(reports))
    return path


def load_records(out_dir: Path) -> list[dict]:
    """Read every certification record in a directory, ordered by agent."""
    records = [
        json.loads(p.read_text()) for p in sorted(out_dir.glob("*-certification.json"))
    ]
    return sorted(records, key=lambda r: r["agent"])
