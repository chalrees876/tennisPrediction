# scripts/build_gallery.py
from pathlib import Path
import argparse, base64, importlib, sys, datetime as dt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # allow importing modules from repo root

def import_pipeline(module_name, func_name):
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name)
    return fn
CSV = "./data/matches.csv"                  # <- CHANGE path if needed
OUT = Path("docs"); OUT.mkdir(exist_ok=True)
IMG = OUT / "img"; IMG.mkdir(exist_ok=True)

def write_png(name: str, b64: str | None):
    if not b64:
        return None
    fn = name.lower().replace(" ", "_").replace("/", "-") + ".png"
    (IMG / fn).write_bytes(base64.b64decode(b64))
    return f"img/{fn}"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--csv", default="data/matches.csv")
    p.add_argument("--module", default=None, help="module path for pipeline, e.g. models or trainingModel")
    p.add_argument("--func", default=None, help="function name, e.g. run_pipeline_from_csv")
    args = p.parse_args()

    # try explicit module/func or common fallbacks
    candidates = []
    if args.module and args.func:
        candidates.append((args.module, args.func))
    candidates += [
        ("src", "trainingModel"),
        ("model", "run_pipeline"),
        ("trainingModel", "run_pipeline"),
        ("models", "run_pipeline"),
    ]

    pipeline = None
    errors = []
    for mod, fn in candidates:
        try:
            pipeline = import_pipeline(mod, fn)
            print(f"✓ Using pipeline {mod}.{fn}")
            break
        except Exception as e:
            errors.append(f"{mod}.{fn}: {e}")

    if pipeline is None:
        raise ImportError(
            "Could not import your pipeline function.\nTried:\n- " + "\n- ".join(errors) +
            "\n\nFix by passing --module and --func that match your project.\n"
            "Example: python scripts/build_gallery.py --module models --func run_pipeline_from_csv"
        )

    OUT = ROOT / "docs"
    IMG = OUT / "img"
    OUT.mkdir(exist_ok=True)

    res = pipeline(args.csv)  # must return dict of base64 images + text

    figures = [
        ("Confusion Matrix",  res.get("confusion_matrix")),
        ("Classification Report", res.get("classification_report")),
        ("Heatmap", res.get("heatmap")),
        ("ROC Curve",         res.get("auc_b64")),
        ("Decision Boundary", res.get("db64")),
        ("Feature Scatter",   res.get("scatter_b64")),
        ("First-Serve Sigmoid", res.get("fs_sigmoid64")),
        ("Double-Faults Sigmoid", res.get("df_sigmoid64")),
    ]

    items = []
    for title, b64 in figures:
        path = write_png(title, b64)
        if path:
            items.append((title, path))

    # Optional textual metrics
    cr_html = (res.get("classification_report") or "").replace("\n", "<br>")

    # Minimal gallery HTML
    html = f"""<!doctype html>
<html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Tennis ML — Results Gallery</title>
<style>
  body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Inter,Arial;margin:24px;background:#f6f8fb;color:#0a0a0a}}
  h1{{margin:.2em 0}} .sub{{color:#666}}
  .grid{{display:grid;gap:18px;grid-template-columns:repeat(auto-fit,minmax(320px,1fr))}}
  figure{{margin:0;background:#fff;border-radius:14px;box-shadow:0 8px 28px rgba(0,0,0,.06);padding:12px}}
  figcaption{{font-size:.95rem;opacity:.85;margin-top:8px}}
  img{{width:100%;height:auto;border-radius:10px;display:block}}
  pre{{background:#fff;border-radius:10px;padding:12px;overflow:auto;box-shadow:0 8px 28px rgba(0,0,0,.06)}}
</style>
<h1>Tennis Match Outcome — Results Gallery</h1>
<div class="sub">Generated {dt.datetime.now().strftime("%Y-%m-%d %H:%M")} • Static build</div>

<h2>Visualizations</h2>
<div class="grid">
  {''.join(f'<figure><img src="{p}" alt="{t}"><figcaption>{t}</figcaption></figure>' for t,p in items)}
</div>

<h2 style="margin-top:24px">Classification Report</h2>
<pre>{cr_html}</pre>
</html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"✅ Wrote docs/index.html with {len(items)} figures.")

if __name__ == "__main__":
    main()