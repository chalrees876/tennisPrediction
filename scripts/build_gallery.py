
# scripts/build_gallery.py
from pathlib import Path
import argparse, base64, importlib, sys, datetime as dt
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # import from repo root

def import_pipeline(module_name: str, func_name: str):
    mod = importlib.import_module(module_name)
    fn = getattr(mod, func_name)
    return fn

def _strip_data_uri(s: str) -> str:
    # handles "data:image/png;base64,AAAA..." and plain "AAAA..."
    return s.split(",")[-1].strip()

def _ensure_list(x: Any) -> list:
    if x is None:
        return []
    if isinstance(x, (list, tuple)):
        return list(x)
    return [x]

def save_images(out_dir: Path, title: str, payload: Any) -> list[str]:
    """
    Accepts:
      - base64 string
      - list/tuple of base64 strings
      - (optionally) Matplotlib Figure objects
    Writes PNG(s) and returns relative paths like ["img/foo.png", ...]
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    items = _ensure_list(payload)
    paths: list[str] = []

    for idx, item in enumerate(items):
        fn_base = title.lower().replace(" ", "_").replace("/", "-")
        fn = f"{fn_base}.png" if len(items) == 1 else f"{fn_base}_{idx+1}.png"
        dest = out_dir / fn

        try:
            if isinstance(item, str):
                # base64 str (with or without data URI prefix)
                b64 = _strip_data_uri(item)
                dest.write_bytes(base64.b64decode(b64))
                paths.append(f"img/{fn}")
            elif hasattr(item, "savefig"):  # Matplotlib Figure
                # lazy import to avoid hard dependency
                import io
                buf = io.BytesIO()
                item.savefig(buf, format="png", bbox_inches="tight")
                dest.write_bytes(buf.getvalue())
                paths.append(f"img/{fn}")
            elif isinstance(item, bytes):
                dest.write_bytes(item)
                paths.append(f"img/{fn}")
            else:
                print(f"[warn] Skipping unsupported type for '{title}': {type(item).__name__}")
        except Exception as e:
            print(f"[warn] Failed to save '{title}' item #{idx+1}: {e}")

    return paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="Path to CSV, e.g. data/matches.csv")
    ap.add_argument("--module", required=True, help="Module with pipeline, e.g. src.trainingModel")
    ap.add_argument("--func", required=True, help="Function name, e.g. run_pipeline")
    args = ap.parse_args()

    pipeline = import_pipeline(args.module, args.func)
    print(f"✓ Using pipeline {args.module}.{args.func}")

    OUT = ROOT / "docs"
    IMG = OUT / "img"
    OUT.mkdir(exist_ok=True)

    # Run user pipeline; expected to return a dict of visuals & text
    res = pipeline(args.csv)

    # Map keys -> titles. Add/remove keys to match what your pipeline returns.
    FIG_MAP: list[tuple[str, str]] = [
        ("Confusion Matrix",    "heatmap_b64"),
        ("ROC Curve",           "auc_b64"),
        ("Classification Report", "classification_report"),
        ("Heatmap", "heatmap"),
        ("ROC Curve", "auc_b64"),
        ("Decision Boundary",   "db64"),
        ("Feature Scatter",     "scatter_b64"),
        ("First-Serve Sigmoid", "fs_sigmoid64"),
        ("Double-Fault Sigmoid","df_sigmoid64"),
    ]

    gallery_items: list[tuple[str, list[str]]] = []
    for title, key in FIG_MAP:
        payload = res.get(key)
        paths = save_images(IMG, title, payload)
        if paths:
            gallery_items.append((title, paths))

    cr_html = (res.get("classification_report") or "").replace("\n", "<br>")

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
  {''.join(
    ''.join(f'<figure><img src="{p}" alt="{t}"><figcaption>{t}{(" #" + str(i+1)) if len(paths)>1 else ""}</figcaption></figure>'
            for i, p in enumerate(paths))
    for t, paths in gallery_items
  )}
</div>

<h2 style="margin-top:24px">Classification Report</h2>
<pre>{cr_html}</pre>
</html>"""
    (OUT / "index.html").write_text(html, encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    print(f"✅ Wrote docs/index.html with {sum(len(p) for _, p in gallery_items)} figure(s).")

if __name__ == "__main__":
    main()
