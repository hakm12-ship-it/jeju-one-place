"""Build the GitHub Pages demo using the same comparisons as the desktop app."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine import catalog, center_comparison, compare, field_checks

OUTPUT = ROOT / "docs"
VILLAGE_FILES = {"금능리": "geumneung", "유수암리": "yusuam", "봉성리": "bongseong"}
CANONICAL = "https://hakm12-ship-it.github.io/jeju-one-place/"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build():
    data_dir = OUTPUT / "data"
    data_dir.mkdir(exist_ok=True, parents=True)
    registry = catalog()
    index = {}
    for village, slug in VILLAGE_FILES.items():
        record = registry[village]
        index[village] = {**record, "file": slug}
        for mask in range(1 << len(record["homes"])):
            onsite = [home["id"] for i, home in enumerate(record["homes"]) if mask & (1 << i)]
            cases = {}
            for threshold in (0, 100, 300, 500):
                for goal in ("reach", "distance"):
                    for center in (False, True):
                        result = compare(village, goal, threshold, onsite, center=center)
                        result["center_comparison"] = center_comparison(result)
                        result["field_checks"] = field_checks(result)
                        cases[f"{goal}-{threshold}-{int(center)}"] = result
            write_json(data_dir / f"{slug}-{mask}.json", cases)
    write_json(data_dir / "catalog.json", index)
    for name in ("screen.js", "screen.css"):
        shutil.copyfile(ROOT / "web" / name, OUTPUT / name)
    for name in ("index.html", "public.js", "demo.css"):
        shutil.copyfile(ROOT / "demo" / name, OUTPUT / name)
    (OUTPUT / ".nojekyll").write_bytes(b"")
    (OUTPUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {CANONICAL}sitemap.xml\n", encoding="ascii")
    (OUTPUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"<url><loc>{CANONICAL}</loc></url></urlset>\n", encoding="utf-8")


if __name__ == "__main__":
    build()
