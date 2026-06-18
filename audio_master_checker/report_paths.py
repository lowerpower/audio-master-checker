from __future__ import annotations

from pathlib import Path


def report_paths(out_dir: str | Path, report_name: str | None = None) -> tuple[Path, Path]:
    base = "report" if report_name is None else validate_report_name(report_name)
    directory = Path(out_dir)
    return directory / f"{base}.json", directory / f"{base}.md"


def validate_report_name(report_name: str) -> str:
    name = report_name.strip()
    if not name:
        raise ValueError("Report name cannot be empty")
    if Path(name).name != name:
        raise ValueError("Report name must be a filename stem, not a path")
    if name.endswith(".json") or name.endswith(".md"):
        name = Path(name).stem
    if not name:
        raise ValueError("Report name cannot be empty")
    return name
