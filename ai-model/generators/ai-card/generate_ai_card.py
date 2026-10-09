#!/usr/bin/env python3
"""
CVDLINK AI Card generator — driven by the model description.

Pipeline:  model description YAML  ->  validate (model-description.schema.json)  ->  AI Card HTML + JSON

ONE developer input (../../model-description.yaml) produces the AI Card here and the
AIMe entry via ../aime. This renderer reads only the AI-Card-relevant fields; the AIMe-only
sections (method_detail, reproducibility, privacy, epistasis) are ignored. The code
licence is read once from reproducibility.source_code.license.

Usage:
    python generate_ai_card.py                       # default: ../../model-description.yaml
    python generate_ai_card.py path/to/model.yaml    # a specific model description file
"""

import sys
import json
import html
from pathlib import Path

try:
    import yaml
    from jsonschema import Draft202012Validator
except ImportError:
    sys.exit("Missing deps. Run:  pip install -r requirements.txt")

SCRIPT_DIR = Path(__file__).parent
AI_MODEL_DIR = SCRIPT_DIR.parent.parent
SCHEMA = AI_MODEL_DIR / "model-description.schema.json"
DEFAULT_INPUT = AI_MODEL_DIR / "model-description.yaml"
OUTPUT_DIR = AI_MODEL_DIR


# ----------------------------------------------------------------------------
# Validation (against the canonical model description schema)
# ----------------------------------------------------------------------------
def validate(data):
    schema = json.loads(SCHEMA.read_text())
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    return ["/".join(str(p) for p in e.path) + ": " + e.message for e in errors]


# ----------------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------------
def esc(x):
    return html.escape(str(x))


def yn(v):
    return '<span class="yes">✓</span>' if v else '<span class="no">✗</span>'


def badge(label, value, kind):
    return f'<span class="badge badge-{kind}">{esc(label)}: <b>{esc(value)}</b></span>'


def section(title, body, wide=False):
    if not body:
        return ""
    cls = "card card--wide" if wide else "card"
    return f'<section class="{cls}"><h2>{esc(title)}</h2>{body}</section>'


def _norm(rows):
    for r in rows:
        yield r if len(r) == 3 else (r[0], r[1], False)


def kv_table(rows):
    cells = "".join(
        f'<tr><th>{esc(k)}</th><td>{v if html_safe else esc(v)}</td></tr>'
        for k, v, html_safe in _norm(rows) if v not in (None, "", [])
    )
    return f'<table class="kv">{cells}</table>' if cells else ""


def bullets(items):
    items = [i for i in (items or []) if i]
    return ("<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>") if items else ""


def grid_table(head_cells, rows):
    head = "<tr>" + "".join(f"<th>{esc(h)}</th>" for h in head_cells) + "</tr>"
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f'<table class="grid">{head}{body}</table>'


# ----------------------------------------------------------------------------
# Core section renderers
# ----------------------------------------------------------------------------
def render_components(components):
    rows = [[esc(c.get("name", "")),
             f'<span class="pill">{esc(c.get("type",""))}</span>',
             esc(c.get("version", "")),
             esc(c.get("documentation_link", ""))] for c in components]
    return grid_table(["Component", "Type", "Version", "Docs"], rows)


def render_datasets(data):
    rows = []
    for d in data.get("datasets", []):
        rows.append([
            esc(d.get("name", "")),
            f'<span class="pill">{esc(d.get("origin",""))}</span>',
            yn(d.get("personal_data")),
            esc(d.get("personal_data_category", "")),
            yn(d.get("dpia_conducted")) if "dpia_conducted" in d else "",
            yn(d.get("anonymised")) if "anonymised" in d else "",
            yn(d.get("licenced")) if "licenced" in d else "",
            esc(d.get("availability", "")),
        ])
    html = grid_table(["Dataset", "Origin", "Personal", "Category", "DPIA", "Anon", "Lic", "Avail."], rows)
    cohorts = [(d.get("name", ""), d.get("cohort"), d.get("used_for_training"))
               for d in data.get("datasets", []) if d.get("cohort")]
    if cohorts:
        html += "<h4>Cohort composition</h4>" + kv_table([
            (f"{name} (training)" if trains else name, cohort) for name, cohort, trains in cohorts
        ])
    return html


def humanize(value):
    return value.replace("_", " ").capitalize() if value else ""


def render_metrics(metrics):
    rows = []
    for m in metrics:
        arrow = (" ↑" if m["higher_is_better"] else " ↓") if "higher_is_better" in m else ""
        split = esc(humanize(m.get("split", "")))
        if m.get("split_detail"):
            split += f'<br><span class="muted">{esc(m["split_detail"])}</span>'
        rows.append([esc(m.get("name", "")) + arrow,
                     f'<b>{esc(m.get("value",""))}</b>',
                     esc(m.get("range", "")), esc(m.get("dataset", "")), split])
    return grid_table(["Metric", "Value", "Range", "Dataset", "Split"], rows)


def render_predetermined(changes):
    rows = [[esc(c.get("subject", "")), esc(c.get("frequency", "")),
             yn(c.get("impact_on_performance")), yn(c.get("impact_on_risks"))] for c in changes]
    return grid_table(["Subject", "Frequency", "→ perf", "→ risk"], rows)


def render_governance(gov, code_license):
    body = kv_table([("Code licence", code_license)])  # sourced from reproducibility.source_code.license
    for reg in gov.get("regulations", []):
        body += kv_table([(reg.get("name", "regulation"),
                           f'{reg.get("jurisdiction","")} — {reg.get("assessment_type","")}')])
    stds = gov.get("standards", [])
    if stds:
        body += "<h4>Standards</h4>" + bullets(
            [f'{s.get("name","")}{" (" + s.get("year","") + ")" if s.get("year") else ""}'
             f'{" · certifiable" if s.get("certifiable") else ""}' for s in stds])
    if gov.get("codes_of_conduct"):
        body += "<h4>Codes of conduct</h4>" + bullets(gov["codes_of_conduct"])
    return body


# ----------------------------------------------------------------------------
# Archetype module renderers (switched on by which modules are present)
# ----------------------------------------------------------------------------
def render_task(t):
    return kv_table([("Prediction target", t.get("prediction_target")),
                     ("Evaluation protocol", t.get("evaluation_protocol"))])


def render_representation(r):
    body = kv_table([("Pretraining objective", r.get("pretraining_objective")),
                     ("What it embeds", r.get("embeds"))])
    body += "<h4>Downstream tasks</h4>" + bullets(r.get("downstream_tasks"))
    if r.get("fine_tuning_methods"):
        body += "<h4>Fine-tuning methods</h4>" + bullets(r["fine_tuning_methods"])
    return body


def render_discovery(d):
    return kv_table([("Discovers", d.get("discovers")),
                     ("Validation method", d.get("validation_method")),
                     ("Decisions about individuals", yn(d.get("produces_decisions")), True)])


def render_deployment(dep):
    body = kv_table([("Deployer", dep.get("deployer")),
                     ("AI subject (who is affected)", dep.get("ai_subject")),
                     ("Automation level", dep.get("automation_level")),
                     ("Human oversight", dep.get("human_oversight"))])
    actors = dep.get("actors", [])
    if actors:
        rows = [[esc(a.get("role", "")), yn(a.get("intended")), yn(a.get("active")),
                 yn(a.get("informed")), esc(a.get("control", ""))] for a in actors]
        body += "<h4>Human involvement</h4>" + grid_table(
            ["Actor", "Intended", "Active", "Informed", "Control"], rows)
    risks = dep.get("risk_profile", {}).get("risks", [])
    if risks:
        rows = [[esc(r.get("impact_area", "")), esc(r.get("likelihood", "")), esc(r.get("severity", "")),
                 esc(r.get("residual_risk", "")), esc(", ".join(r.get("mitigations", [])))] for r in risks]
        body += "<h4>Risk profile (EU AI Act)</h4>" + grid_table(
            ["Impact area", "Likelihood", "Severity", "Residual", "Mitigations"], rows)
    return body


# (key, title, renderer, wide)
MODULE_RENDERERS = [
    ("task", "Predictive Task", render_task, False),
    ("representation", "Representation / Foundation", render_representation, False),
    ("discovery", "Unsupervised Discovery", render_discovery, False),
    ("deployment", "Deployment, Human Involvement & Risk", render_deployment, True),
]


# ----------------------------------------------------------------------------
# HTML assembly
# ----------------------------------------------------------------------------
def render_html(data):
    ident = data.get("identity", {})
    meta = data.get("card_metadata", {})
    prov = data.get("provenance", {})
    intended = data.get("intended", {})
    io = data.get("io", {})
    code_license = data.get("reproducibility", {}).get("source_code", {}).get("license", "")
    contact = meta.get("contact") or (prov.get("contacts", [{}])[0].get("email", ""))

    badges = (badge("type", ident.get("model_type", ""), "type")
              + badge("role", ident.get("artifact_role", ""), "role")
              + badge("modality", ident.get("modality", ""), "mod"))

    parts = []
    parts.append(section("Identity & provenance", kv_table([
        ("System", ident.get("system_name")),
        ("Version", ident.get("version")),
        ("Techniques", ", ".join(ident.get("ai_techniques", []))),
        ("Providers", ", ".join(prov.get("providers", []))),
        ("Developers", ", ".join(prov.get("developers", []))),
        ("Contacts", ", ".join(f'{c.get("name","")} ({c.get("institution","")})' for c in prov.get("contacts", []))),
        ("Funding", prov.get("funding")),
        ("Paper", prov.get("paper_url")),
    ])))
    intended_body = kv_table([
        ("Domain", intended.get("domain")),
        ("Purpose", intended.get("purpose")),
        ("Capability", intended.get("capability")),
    ])
    if intended.get("out_of_scope_uses"):
        intended_body += "<h4>Out-of-scope uses</h4>" + bullets(intended["out_of_scope_uses"])
    parts.append(section("Intended use", intended_body))
    parts.append(section("Input / Output", kv_table([
        ("Input", io.get("input_description")),
        ("Output", io.get("output_description")),
    ])))
    parts.append(section("Key components", render_components(data.get("components", [])), wide=True))
    parts.append(section("Data processing", render_datasets(data.get("data", {})), wide=True))
    parts.append(section("Quality / metrics", render_metrics(data.get("metrics", [])), wide=True))

    for key, title, fn, wide in MODULE_RENDERERS:
        if key in data:
            parts.append(section(title, fn(data[key]), wide=wide))

    if data.get("predetermined_changes"):
        parts.append(section("Pre-determined changes", render_predetermined(data["predetermined_changes"])))

    lim = data.get("limitations", {})
    lim_html = bullets(lim.get("known_limitations"))
    if lim.get("groups_with_lower_performance"):
        lim_html += "<h4>Groups with lower performance</h4>" + bullets(lim["groups_with_lower_performance"])
    parts.append(section("Caveats & limitations", lim_html))

    if data.get("governance") or code_license:
        parts.append(section("Regulations & certification", render_governance(data.get("governance", {}), code_license)))

    spec = meta.get("spec_url")
    spec_link = f' · <a href="{esc(spec)}">machine-readable spec</a>' if spec else ""

    return f"""<!doctype html>
<html lang="{esc(meta.get('card_language','en'))}"><head><meta charset="utf-8">
<title>AI Card — {esc(ident.get('system_name',''))}</title>
<style>
  :root {{ --ink:#1f2933; --muted:#647280; --line:#e1e7ec; --accent:#2b6cb0; }}
  body {{ font-family:-apple-system,Segoe UI,Roboto,sans-serif; color:var(--ink); max-width:1080px; margin:1.5rem auto; padding:0 1rem; line-height:1.4; font-size:14px; }}
  header {{ border-bottom:3px solid var(--accent); padding-bottom:.5rem; margin-bottom:1rem; }}
  h1 {{ margin:0; font-size:1.4rem; }}
  .sub {{ color:var(--muted); font-size:.8rem; }}
  .sub a {{ color:var(--accent); }}
  .badges {{ margin:.5rem 0; }}
  .badge {{ display:inline-block; padding:.15rem .5rem; border-radius:999px; font-size:.72rem; margin:.1rem .3rem .1rem 0; }}
  .badge-type {{ background:#e6f0fb; color:#1a4e8a; }}
  .badge-role {{ background:#eafaf1; color:#1d7a4d; }}
  .badge-mod  {{ background:#f1ecfb; color:#5a3a9a; }}
  main.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:.8rem; align-items:start; }}
  .card {{ border:1px solid var(--line); border-radius:8px; padding:.6rem .8rem; }}
  .card--wide {{ grid-column:1/-1; }}
  h2 {{ font-size:.92rem; margin:.1rem 0 .5rem; color:var(--accent); }}
  h4 {{ margin:.6rem 0 .2rem; font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.03em; }}
  table {{ border-collapse:collapse; width:100%; font-size:.82rem; }}
  table.kv th {{ text-align:left; width:34%; vertical-align:top; color:var(--muted); font-weight:600; padding:.18rem .4rem; }}
  table.kv td {{ padding:.18rem .4rem; }}
  table.grid th, table.grid td {{ border:1px solid var(--line); padding:.25rem .45rem; text-align:left; }}
  table.grid th {{ background:#f5f7fa; font-size:.74rem; }}
  .pill {{ padding:.05rem .4rem; border-radius:4px; font-size:.74rem; background:#eef2f6; }}
  .muted {{ color:var(--muted); font-size:.74rem; }}
  .yes {{ color:#1d7a4d; font-weight:700; }} .no {{ color:#b03030; }}
  ul {{ margin:.2rem 0 .2rem 1.1rem; padding:0; }} li {{ margin:.05rem 0; }}
</style></head>
<body>
<header>
  <h1>{esc(ident.get('system_name',''))} <span class="sub">v{esc(ident.get('version',''))}</span></h1>
  <div class="sub">{esc(meta.get('card_publisher',''))} · card {esc(meta.get('card_version',''))} · {esc(contact)}{spec_link}</div>
  <div class="badges">{badges}</div>
</header>
<main class="grid">
{''.join(parts)}
</main>
</body></html>
"""


# ----------------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------------
def process(path):
    data = yaml.safe_load(Path(path).read_text())
    errors = validate(data)
    name = Path(path).stem
    if errors:
        print(f"✗ {name}: INVALID against model-description.schema.json")
        for e in errors:
            print(f"    - {e}")
        return False
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / f"{name}.html").write_text(render_html(data))
    (OUTPUT_DIR / f"{name}.jsonld").write_text(json.dumps(data, indent=2))
    active = [k for k, _, _, _ in MODULE_RENDERERS if k in data]
    print(f"✓ {name}: valid · type={data['identity']['model_type']} · modules=[{', '.join(active)}] -> {name}.html")
    return True


def main():
    args = sys.argv[1:]
    paths = [Path(a) for a in args] if args else [DEFAULT_INPUT]
    ok = all(process(p) for p in paths)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
