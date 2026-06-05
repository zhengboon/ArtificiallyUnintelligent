"""Extract per-file code + reviews from a workflow output JSON and write
them to the target paths. Also generate a consolidated review summary."""

import json
import sys
from pathlib import Path


def main():
    src = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])
    summary_out = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    data = json.loads(src.read_text(encoding="utf-8"))
    result = data.get("result", data)
    if isinstance(result, str):
        result = json.loads(result)

    files = result.get("files", [])
    cross = result.get("cross_audit", {}) or {}

    summary_lines = ["# Workflow Output Summary", ""]
    summary_lines.append(f"Total files: {len(files)}")
    summary_lines.append("")

    for f in files:
        path_rel = f["path"]
        impl = f.get("impl") or {}
        reviews = f.get("reviews") or []

        code = impl.get("code") if isinstance(impl, dict) else None
        notes = impl.get("notes", "") if isinstance(impl, dict) else ""

        if not code:
            print(f"SKIP {path_rel}: no code in impl", file=sys.stderr)
            continue

        target = repo_root / "semifinal" / path_rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        print(f"WROTE {target}  ({len(code)} bytes)")

        # Roll up reviews per file
        summary_lines.append(f"## {path_rel}")
        summary_lines.append(f"- code size: {len(code)} bytes")
        if notes:
            summary_lines.append(f"- impl notes: {notes}")

        all_issues = []
        verdicts = []
        for r in reviews:
            if r is None:
                continue
            if isinstance(r, dict):
                verdicts.append(r.get("verdict", "?"))
                for iss in r.get("issues") or []:
                    all_issues.append(iss)

        summary_lines.append(f"- verdicts: {verdicts}")
        summary_lines.append(f"- total issues raised: {len(all_issues)}")

        critical = [i for i in all_issues if i.get("severity") == "critical"]
        high = [i for i in all_issues if i.get("severity") == "high"]
        if critical or high:
            summary_lines.append("- CRITICAL/HIGH issues:")
            for i in critical + high:
                where = i.get("where", "?")
                desc = i.get("description", "?")
                fix = i.get("suggested_fix", "")
                summary_lines.append(f"  - [{i.get('severity').upper()}] {where}: {desc}")
                if fix:
                    summary_lines.append(f"    -> fix: {fix}")
        summary_lines.append("")

    # Cross-module audit
    summary_lines.append("## Cross-module audit")
    if cross:
        summary_lines.append(f"- verdict: {cross.get('verdict', '?')}")
        if cross.get("summary"):
            summary_lines.append(f"- summary: {cross.get('summary')}")
        issues = cross.get("issues") or []
        summary_lines.append(f"- issues: {len(issues)}")
        for i in issues:
            sev = i.get("severity", "?")
            where = i.get("where", "?")
            desc = i.get("description", "?")
            fix = i.get("suggested_fix", "")
            summary_lines.append(f"- [{sev.upper()}] {where}: {desc}")
            if fix:
                summary_lines.append(f"  -> fix: {fix}")

    if summary_out:
        summary_out.write_text("\n".join(summary_lines), encoding="utf-8")
        print(f"\nSummary -> {summary_out}", file=sys.stderr)


if __name__ == "__main__":
    main()
