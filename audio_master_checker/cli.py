from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analyzer import analyze_files
from .fix import BIT_DEPTH_CODECS, fix_file
from .report_paths import report_paths
from .reports import write_json_report, write_markdown_report


def _fmt_db(value: float) -> str:
    return f"{value:.2f}"


def add_analyze_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("analyze", help="Analyze mastered audio files")
    parser.add_argument("files", nargs="+", help="Audio files to analyze")
    parser.add_argument("--out", default="./reports", help="Output directory")
    parser.add_argument("--report-name", help="Report filename stem; defaults to report")
    parser.add_argument("--timeout", type=int, default=300, help="Subprocess timeout in seconds")
    parser.add_argument("--no-codec-tests", action="store_true", help="Skip lossy codec stress tests")
    parser.set_defaults(func=run_analyze)


def add_fix_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("fix", help="Create a safer delivery WAV by lowering level")
    parser.add_argument("file", help="Audio file to trim")
    parser.add_argument("--trim", type=float, default=-1.5, help="Gain trim in dB; must be 0 or negative")
    parser.add_argument("--output", help="Optional output WAV path")
    parser.add_argument("--bit-depth", choices=sorted(BIT_DEPTH_CODECS), default="24", help="Output WAV bit depth")
    parser.add_argument("--out", default="./reports", help="Report output directory")
    parser.add_argument("--report-name", help="Report filename stem; defaults to report")
    parser.add_argument("--timeout", type=int, default=300, help="Subprocess timeout in seconds")
    parser.add_argument("--no-codec-tests", action="store_true", help="Skip lossy codec stress tests in the generated report")
    parser.add_argument("--compare", action="store_true", help="Also write an original-vs-fixed comparison report")
    parser.set_defaults(func=run_fix)


def add_compare_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("compare", help="Compare two analyzed audio files")
    parser.add_argument("files", nargs=2, metavar="file", help="Exactly two audio files to compare")
    parser.add_argument("--out", default="./reports", help="Output directory")
    parser.add_argument("--report-name", help="Report filename stem; defaults to report")
    parser.add_argument("--timeout", type=int, default=300, help="Subprocess timeout in seconds")
    parser.add_argument("--no-codec-tests", action="store_true", help="Skip lossy codec stress tests")
    parser.set_defaults(func=run_compare)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="audio-master-checker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_analyze_parser(subparsers)
    add_fix_parser(subparsers)
    add_compare_parser(subparsers)
    return parser


def run_analyze(args: argparse.Namespace) -> int:
    report = analyze_files(
        args.files,
        timeout=args.timeout,
        codec_tests=not args.no_codec_tests,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = report_paths(out_dir, args.report_name)
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)
    print(f"Wrote JSON report: {json_path}")
    print(f"Wrote Markdown report: {md_path}")
    return 0


def run_compare(args: argparse.Namespace) -> int:
    report = analyze_files(
        args.files,
        timeout=args.timeout,
        codec_tests=not args.no_codec_tests,
    )
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path, md_path = report_paths(out_dir, args.report_name)
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)
    print(f"Wrote comparison JSON report: {json_path}")
    print(f"Wrote comparison Markdown report: {md_path}")
    return 0


def run_fix(args: argparse.Namespace) -> int:
    result = fix_file(
        args.file,
        trim_db=args.trim,
        output_path=args.output,
        bit_depth=args.bit_depth,
        report_dir=args.out,
        report_name=args.report_name,
        compare=args.compare,
        timeout=args.timeout,
        codec_tests=not args.no_codec_tests,
    )
    print(f"Created: {result['output_path']}")
    print(f"Applied gain: {result['trim_db']:.1f} dB")
    print(f"Original true peak: {_fmt_db(result['original_true_peak_dbtp'])} dBTP")
    print(f"Estimated new true peak: {_fmt_db(result['estimated_new_true_peak_dbtp'])} dBTP")
    print(f"Measured new true peak: {_fmt_db(result['measured_new_true_peak_dbtp'])} dBTP")
    print(f"Measured LUFS: {_fmt_db(result['measured_lufs'])} LUFS")
    print(f"Codec Safety: {result['codec_safety']}")
    print(f"Report: {result['report_md_path']}")
    if result.get("compare_report_md_path"):
        print(f"Compare report: {result['compare_report_md_path']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
