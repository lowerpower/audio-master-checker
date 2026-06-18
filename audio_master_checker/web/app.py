from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Annotated

import markdown as markdown_lib
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from audio_master_checker.analyzer import analyze_files
from audio_master_checker.fix import fix_file
from audio_master_checker.reports import write_json_report, write_markdown_report

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_RUNS_DIR = Path("web-runs")


def create_app(runs_dir: str | Path = DEFAULT_RUNS_DIR) -> FastAPI:
    app = FastAPI(title="Audio Master Checker")
    app.state.runs_dir = Path(runs_dir)
    app.state.runs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=PACKAGE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=PACKAGE_DIR / "templates")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html", {})

    @app.post("/analyze", response_class=HTMLResponse)
    async def analyze_route(
        request: Request,
        files: Annotated[list[UploadFile], File()],
        codec_tests: Annotated[bool, Form()] = False,
    ) -> HTMLResponse:
        if not files:
            raise HTTPException(status_code=400, detail="Upload at least one audio file")
        job = _create_job_dir(app.state.runs_dir)
        input_paths = [_save_upload(job / "uploads", item) for item in files]
        report = analyze_files(input_paths, codec_tests=codec_tests)
        _write_report(job, report)
        return _render_report(request, templates, job, report, title="Analysis Report")

    @app.post("/fix", response_class=HTMLResponse)
    async def fix_route(
        request: Request,
        file: Annotated[UploadFile, File()],
        trim: Annotated[float, Form()] = -1.5,
        bit_depth: Annotated[str, Form()] = "24",
        compare: Annotated[bool, Form()] = False,
        codec_tests: Annotated[bool, Form()] = False,
    ) -> HTMLResponse:
        job = _create_job_dir(app.state.runs_dir)
        input_path = _save_upload(job / "uploads", file)
        fixed_path = job / "outputs" / _delivery_filename(input_path.name, trim)
        result = fix_file(
            input_path,
            trim_db=trim,
            output_path=fixed_path,
            bit_depth=bit_depth,
            report_dir=job,
            report_name="fixed",
            compare=compare,
            codec_tests=codec_tests,
        )
        report_path = result["compare_report_md_path"] or result["report_md_path"]
        json_path = result["compare_report_json_path"] or result["report_json_path"]
        report = result["compare_report"] or result["report"]
        return _render_report(
            request,
            templates,
            job,
            report,
            title="Fixed Delivery Report",
            fixed_path=result["output_path"],
            report_md_path=report_path,
            report_json_path=json_path,
        )

    @app.post("/compare", response_class=HTMLResponse)
    async def compare_route(
        request: Request,
        original: Annotated[UploadFile, File()],
        fixed: Annotated[UploadFile, File()],
        codec_tests: Annotated[bool, Form()] = False,
    ) -> HTMLResponse:
        job = _create_job_dir(app.state.runs_dir)
        original_path = _save_upload(job / "uploads", original)
        fixed_path = _save_upload(job / "uploads", fixed)
        report = analyze_files([original_path, fixed_path], codec_tests=codec_tests)
        _write_report(job, report)
        return _render_report(request, templates, job, report, title="Comparison Report")

    @app.get("/jobs/{job_id}/{filename}")
    async def download(job_id: str, filename: str) -> FileResponse:
        path = _resolve_job_file(app.state.runs_dir, job_id, filename)
        return FileResponse(path, filename=path.name)

    return app


def _create_job_dir(runs_dir: Path) -> Path:
    job = runs_dir / uuid.uuid4().hex
    (job / "uploads").mkdir(parents=True)
    (job / "outputs").mkdir()
    return job


def _safe_filename(name: str) -> str:
    return Path(name).name.replace("/", "_").replace("\\", "_") or "upload.wav"


def _save_upload(directory: Path, upload: UploadFile) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / _safe_filename(upload.filename or "upload.wav")
    with path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return path


def _delivery_filename(filename: str, trim: float) -> str:
    path = Path(filename)
    trim_text = f"{trim:.6f}".rstrip("0").rstrip(".")
    return f"{path.stem} [{trim_text}dB delivery].wav"


def _write_report(job: Path, report: dict) -> tuple[Path, Path]:
    json_path = job / "report.json"
    md_path = job / "report.md"
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)
    return json_path, md_path


def _render_report(
    request: Request,
    templates: Jinja2Templates,
    job: Path,
    report: dict,
    title: str,
    fixed_path: Path | None = None,
    report_md_path: Path | None = None,
    report_json_path: Path | None = None,
) -> HTMLResponse:
    md_path = report_md_path or job / "report.md"
    json_path = report_json_path or job / "report.json"
    markdown_text = md_path.read_text(encoding="utf-8")
    html_report = markdown_lib.markdown(markdown_text, extensions=["tables"])
    job_id = job.name
    downloads = [
        ("Markdown", f"/jobs/{job_id}/{md_path.name}"),
        ("JSON", f"/jobs/{job_id}/{json_path.name}"),
    ]
    if fixed_path is not None:
        downloads.append(("Fixed WAV", f"/jobs/{job_id}/{fixed_path.name}"))
    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "title": title,
            "report": report,
            "html_report": html_report,
            "downloads": downloads,
        },
    )


def _resolve_job_file(runs_dir: Path, job_id: str, filename: str) -> Path:
    if Path(job_id).name != job_id or Path(filename).name != filename:
        raise HTTPException(status_code=404, detail="File not found")
    job = runs_dir / job_id
    candidates = [job / filename, job / "outputs" / filename, job / "uploads" / filename]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    raise HTTPException(status_code=404, detail="File not found")


app = create_app()
