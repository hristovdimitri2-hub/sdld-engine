import pathlib
import zipfile

root = pathlib.Path(".").resolve()
# e2e* = работни копия от доказателните прогони (не се пакетират)
skip_dirs = {"__pycache__", ".pytest_cache", ".ai-brain", ".git"}
out = root.parent / "sdld-engine-v0.2.0.zip"

count = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in skip_dirs for part in p.parts):
            continue
        if any(part.startswith("e2e") for part in p.parts):
            continue
        if p.suffix == ".pyc" or p.name == "make_zip.py":
            continue
        z.write(p, p.relative_to(root).as_posix())
        count += 1

print(f"records={count} size={out.stat().st_size} bytes -> {out.name}")
