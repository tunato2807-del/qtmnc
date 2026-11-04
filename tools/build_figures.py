"""Dựng SVG/PNG từ sơ đồ DOT; cần Graphviz cài trên máy dựng tài liệu."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "docs/figures"
for source in sorted(root.glob("*.dot")):
    for extension in ("svg", "png"):
        subprocess.run(["dot", "-T" + extension, str(source), "-o", str(source.with_suffix("." + extension))], check=True)
        print(source.with_suffix("." + extension).name)
