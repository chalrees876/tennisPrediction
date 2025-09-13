# scripts/build_gallery.py
from pathlib import Path
import base64
import datetime as dt

# 1) import your pipeline (adjust this import/name to match your code)
# e.g., from model import run_pipeline_from_csv
from models import run_pipeline_from_csv   # <- CHANGE if your module is named differently

CSV = "data/matches.csv"                  # <- CHANGE path if needed
OUT = Path("docs"); OUT.mkdir(exist_ok=True)
IMG = OUT / "img"; IMG.mkdir(exist_ok=True)

def write_png(name: str, b64: str | None):
    if not b64:
        return None
    fn = name.lower().replace(" ", "_").replace("/", "-") + ".png"
    (IMG / fn).write_bytes(base64.b64decode(b64))
    return f"img/{fn}"

def main():
    res = run_pipeline_from_csv(CSV)
    # Map your result keys -> readable titles (add/remove as your pipeline provides)
    figures = [
        ("Confusion Matrix",  res.get("heatmap_b64")),
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