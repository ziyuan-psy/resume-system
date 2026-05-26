from __future__ import annotations

import csv
import hashlib
import re
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw_overleaf_exports"
EXTRACTED_DIR = ROOT / "extracted"
PROJECT_ZIPS_DIR = EXTRACTED_DIR / "project_zips"
TEX_FILES_DIR = EXTRACTED_DIR / "tex_files"
MANIFESTS_DIR = EXTRACTED_DIR / "manifests"
LOG_PATH = EXTRACTED_DIR / "extraction_log.md"


def slugify(value: str, fallback: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "_", ascii_value).strip("_").lower()
    return slug or fallback


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_member(zip_file: zipfile.ZipFile, member: zipfile.ZipInfo, destination: Path) -> Path:
    member_path = Path(member.filename.replace("\\", "/"))
    if member_path.is_absolute() or ".." in member_path.parts:
        raise ValueError(f"Unsafe zip path: {member.filename}")
    output_path = destination / member_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zip_file.open(member, "r") as source, output_path.open("wb") as target:
        target.write(source.read())
    return output_path


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if not RAW_DIR.exists():
        raise SystemExit(f"Missing source directory: {RAW_DIR}")

    outer_zips = sorted(RAW_DIR.glob("*.zip"))
    if not outer_zips:
        raise SystemExit(f"No .zip files found under {RAW_DIR}")

    PROJECT_ZIPS_DIR.mkdir(parents=True, exist_ok=True)
    TEX_FILES_DIR.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    zip_rows: list[dict[str, object]] = []
    tex_rows: list[dict[str, object]] = []
    failures: list[str] = []

    for outer_index, outer_zip_path in enumerate(outer_zips, start=1):
        outer_zip_id = slugify(outer_zip_path.stem, f"outer_{outer_index:03d}")
        outer_project_dir = PROJECT_ZIPS_DIR / outer_zip_id
        outer_project_dir.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(outer_zip_path, "r") as outer_zip:
            nested_entries = [
                entry
                for entry in outer_zip.infolist()
                if not entry.is_dir() and entry.filename.lower().endswith(".zip")
            ]

            for project_index, entry in enumerate(sorted(nested_entries, key=lambda item: item.filename), start=1):
                project_zip_name = Path(entry.filename).name
                source_project = Path(project_zip_name).stem
                source_project_id = f"project_{project_index:03d}_{slugify(source_project, 'project')}"

                nested_zip_output = outer_project_dir / f"{source_project_id}.zip"
                with outer_zip.open(entry, "r") as source, nested_zip_output.open("wb") as target:
                    target.write(source.read())

                row_base = {
                    "original_zip_name": outer_zip_path.name,
                    "original_zip_path": str(outer_zip_path.relative_to(ROOT)),
                    "original_zip_sha256": sha256_file(outer_zip_path),
                    "source_project_zip": project_zip_name,
                    "source_project": source_project,
                    "source_project_id": source_project_id,
                    "nested_zip_entry": entry.filename,
                    "extracted_project_zip_path": str(nested_zip_output.relative_to(ROOT)),
                    "nested_zip_size_bytes": entry.file_size,
                }
                zip_rows.append(row_base)

                project_tex_dir = TEX_FILES_DIR / source_project_id
                project_tex_dir.mkdir(parents=True, exist_ok=True)

                try:
                    with zipfile.ZipFile(nested_zip_output, "r") as nested_zip:
                        tex_entries = [
                            tex_entry
                            for tex_entry in nested_zip.infolist()
                            if not tex_entry.is_dir() and tex_entry.filename.lower().endswith(".tex")
                        ]
                        if not tex_entries:
                            failures.append(f"{project_zip_name}: no .tex files found")
                            continue
                        for tex_entry in sorted(tex_entries, key=lambda item: item.filename):
                            extracted_tex_path = safe_extract_member(nested_zip, tex_entry, project_tex_dir)
                            tex_rows.append(
                                {
                                    **row_base,
                                    "source_tex_file": tex_entry.filename,
                                    "extracted_tex_path": str(extracted_tex_path.relative_to(ROOT)),
                                    "tex_size_bytes": tex_entry.file_size,
                                }
                            )
                except zipfile.BadZipFile as exc:
                    failures.append(f"{project_zip_name}: cannot read nested zip ({exc})")

    write_csv(
        MANIFESTS_DIR / "zip_manifest.csv",
        zip_rows,
        [
            "original_zip_name",
            "original_zip_path",
            "original_zip_sha256",
            "source_project_zip",
            "source_project",
            "source_project_id",
            "nested_zip_entry",
            "extracted_project_zip_path",
            "nested_zip_size_bytes",
        ],
    )
    write_csv(
        MANIFESTS_DIR / "tex_manifest.csv",
        tex_rows,
        [
            "original_zip_name",
            "original_zip_path",
            "original_zip_sha256",
            "source_project_zip",
            "source_project",
            "source_project_id",
            "nested_zip_entry",
            "extracted_project_zip_path",
            "nested_zip_size_bytes",
            "source_tex_file",
            "extracted_tex_path",
            "tex_size_bytes",
        ],
    )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as handle:
        handle.write("# Extraction Log\n\n")
        handle.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n\n")
        handle.write("## Import\n\n")
        handle.write(f"- Raw source directory: `{RAW_DIR.relative_to(ROOT)}`\n")
        handle.write(f"- Outer ZIP files found: {len(outer_zips)}\n")
        handle.write(f"- Nested project ZIP files found: {len(zip_rows)}\n")
        handle.write(f"- TeX files extracted: {len(tex_rows)}\n")
        handle.write(f"- Import failures: {len(failures)}\n")
        if failures:
            handle.write("\n### Import Failures\n\n")
            for failure in failures:
                handle.write(f"- {failure}\n")

    print(f"Outer ZIP files found: {len(outer_zips)}")
    print(f"Nested project ZIP files found: {len(zip_rows)}")
    print(f"TeX files extracted: {len(tex_rows)}")
    print(f"Import failures: {len(failures)}")
    print(f"Wrote {MANIFESTS_DIR / 'zip_manifest.csv'}")
    print(f"Wrote {MANIFESTS_DIR / 'tex_manifest.csv'}")
    print(f"Wrote {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
