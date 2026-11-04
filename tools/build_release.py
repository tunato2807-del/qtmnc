"""Đóng gói các file đã stage/track; không lấy secret hoặc dữ liệu bị Git bỏ qua."""
import hashlib
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/download/NetWatch_Lab_Moi.zip"


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    manifest, count = [], 0
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(p for p in paths if p):
            path = ROOT / name
            if path == OUTPUT or name.endswith(".sha256"):
                continue
            if not path.is_file():
                raise ValueError("File đã track không tồn tại: " + name)
            if (path.name.startswith(".env") and path.name != ".env.example") or name.startswith(("data/", ".local/", ".venv", "lab/generated/")):
                raise ValueError("Không được đưa file cục bộ vào gói: " + name)
            data = path.read_bytes()
            if path.suffix.lower() in (".cmd", ".ps1"):
                data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            archive.writestr("NetWatch_Lab_Moi/" + name, data)
            manifest.append(hashlib.sha256(data).hexdigest() + "  " + name)
            count += 1
        archive.writestr("NetWatch_Lab_Moi/MANIFEST.sha256", "\n".join(manifest) + "\n")
    OUTPUT.with_suffix(".zip.sha256").write_text(hashlib.sha256(OUTPUT.read_bytes()).hexdigest() + "  " + OUTPUT.name + "\n", encoding="ascii")
    print(f"{OUTPUT.relative_to(ROOT)} — {count} file + manifest, {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
