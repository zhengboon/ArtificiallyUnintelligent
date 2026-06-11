"""Extract fixed files + audit from a v2 fix workflow output."""
import json, sys
from pathlib import Path

def main():
    src = Path(sys.argv[1])
    repo_root = Path(sys.argv[2])
    summary_out = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    data = json.loads(src.read_text(encoding="utf-8"))
    result = data.get("result", data)
    if isinstance(result, str):
        result = json.loads(result)

    fixes = result.get("fixes", [])
    audit = result.get("audit", {}) or {}

    lines = ["# Fix Workflow Output Summary", ""]
    for f in fixes:
        path = f["path"]
        r = f.get("result") or {}
        code = r.get("code") if isinstance(r, dict) else None
        notes = r.get("fix_notes", "") if isinstance(r, dict) else ""
        if not code:
            print(f"SKIP {path}: no code", file=sys.stderr)
            continue
        target = repo_root / "semifinal" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(code, encoding="utf-8")
        print(f"WROTE {target}  ({len(code)} bytes)")
        lines.append(f"## {path}")
        lines.append(f"- size: {len(code)} bytes")
        if notes:
            lines.append(f"- fix_notes: {notes}")
        lines.append("")

    lines.append("## Re-audit")
    if audit:
        lines.append(f"- verdict: {audit.get('verdict', '?')}")
        if audit.get("summary"):
            lines.append(f"- summary: {audit['summary']}")
        for i in audit.get("issues") or []:
            sev = i.get("severity", "?")
            where = i.get("where", "?")
            desc = i.get("description", "?")
            fix = i.get("suggested_fix", "")
            lines.append(f"- [{sev.upper()}] {where}: {desc}")
            if fix:
                lines.append(f"  -> fix: {fix}")

    if summary_out:
        summary_out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\nSummary -> {summary_out}", file=sys.stderr)

if __name__ == "__main__":
    main()
