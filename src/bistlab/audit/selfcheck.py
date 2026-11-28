"""Self-audit of bistlab's own information systems.

Automated controls inspired by the control areas of the Turkish Capital Markets Board's
information-systems regulation (VII-128.10, 2025; previously VII-128.9): secrets management,
change management, dependency management, data integrity, audit trail, backup and access.
Each control returns "Pass" or "Finding" with evidence; the result is written to docs/audit/
as a Markdown report.

This is not an official independent audit; it is a self-assessment that applies an audit
approach to our own system.

Control codes keep their original abbreviations for continuity with earlier reports:
BG = secrets, DY = change management, BY = dependencies, VB = data integrity,
DI = audit trail, YD = backup, ER = access.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, inspect, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from bistlab.data.db import FundHolding, Price, Security, get_engine

SECRET = re.compile(
    r"(?i)(api[_-]?key|secret|password|passwd|token)\s*[=:]\s*[\"']?([A-Za-z0-9_\-]{12,})"
)
PLACEHOLDER_WORDS = ("example", "your", "xxx", "changeme", "placeholder")
ALLOW_MARKER = "selfcheck: allow"  # deliberate fake keys (test fixtures)
PR_SUFFIX = re.compile(r"\(#\d+\)\s*$")


@dataclass(frozen=True)
class Finding:
    code: str
    area: str
    control: str
    passed: bool
    evidence: str
    risk: str = "Medium"  # severity if the control fails

    @property
    def status(self) -> str:
        return "Pass" if self.passed else f"Finding ({self.risk})"


# ---- pure helpers (testable) ----


def gitignore_covers(text: str, name: str) -> bool:
    patterns = {line.strip() for line in text.splitlines() if line.strip()}
    return name in patterns or f"/{name}" in patterns or f"{name}*" in patterns


def find_secrets(text: str) -> list[str]:
    """Names of assignments that look like real secrets."""
    hits = []
    scanned = "\n".join(line for line in text.splitlines() if ALLOW_MARKER not in line)
    for match in SECRET.finditer(scanned):
        value = match[2]
        if any(word in value.casefold() for word in PLACEHOLDER_WORDS):
            continue
        if not (re.search(r"\d", value) and re.search(r"[A-Za-z]", value)):
            continue
        hits.append(match[1])
    return hits


def ci_missing_steps(text: str, steps: Iterable[str]) -> list[str]:
    return [step for step in steps if step not in text]


def pr_ratio(subjects: list[str]) -> float:
    """Share of commits on main that come from a squashed PR ('... (#12)')."""
    if not subjects:
        return 0.0
    return sum(bool(PR_SUFFIX.search(s)) for s in subjects) / len(subjects)


def bad_weight_sums(sums: dict[str, float], tolerance: float = 0.02) -> list[str]:
    return [key for key, total in sums.items() if abs(total - 1) > tolerance]


def render_markdown(findings: list[Finding], day: dt.date) -> str:
    passed = sum(f.passed for f in findings)
    lines = [
        f"# bistlab information systems self-audit — {day.isoformat()}",
        "",
        f"Result: {passed} of {len(findings)} controls pass, {len(findings) - passed} findings.",
        "",
        "| Code | Area | Control | Status | Evidence |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in findings:
        evidence = f.evidence.replace("|", "/")
        lines.append(f"| {f.code} | {f.area} | {f.control} | {f.status} | {evidence} |")
    lines += [
        "",
        "Not an official independent audit; a self-assessment inspired by the VII-128.10 "
        "control areas.",
    ]
    return "\n".join(lines) + "\n"


# ---- controls ----


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, check=False)


def secret_checks(root: Path) -> list[Finding]:
    gitignore = (root / ".gitignore").read_text() if (root / ".gitignore").exists() else ""
    tracked_env = run("git", "ls-files", "--error-unmatch", ".env").returncode == 0
    history = run("git", "log", "--all", "--pretty=format:", "--name-only", "--", ".env")
    hits: list[str] = []
    for name in run("git", "ls-files").stdout.splitlines():
        path = root / name
        if name == "uv.lock" or not path.is_file() or path.stat().st_size > 1_000_000:
            continue
        try:
            found = find_secrets(path.read_text(encoding="utf-8"))
        except UnicodeDecodeError:
            continue
        hits += [f"{name}: {key}" for key in found]
    return [
        Finding(
            "BG-01",
            "Secrets",
            ".env listed in .gitignore",
            gitignore_covers(gitignore, ".env"),
            ".gitignore lines checked",
            "High",
        ),
        Finding(
            "BG-02",
            "Secrets",
            ".env not tracked by git",
            not tracked_env,
            "git ls-files .env",
            "High",
        ),
        Finding(
            "BG-03",
            "Secrets",
            ".env never committed",
            not history.stdout.strip(),
            "git log --all -- .env",
            "High",
        ),
        Finding(
            "BG-04",
            "Secrets",
            "No key patterns in tracked files",
            not hits,
            ", ".join(hits) or "all scanned files clean",
            "High",
        ),
    ]


def change_checks(root: Path) -> list[Finding]:
    protection = run("gh", "api", "repos/{owner}/{repo}/branches/main/protection")
    subjects = run("git", "log", "main", "--first-parent", "--pretty=%s").stdout.splitlines()
    ratio = pr_ratio(subjects)
    ci = root / ".github" / "workflows" / "ci.yml"
    missing = ci_missing_steps(ci.read_text() if ci.exists() else "", ["ruff", "mypy", "pytest"])
    return [
        Finding(
            "DY-01",
            "Change management",
            "main branch protected (PR + CI required)",
            protection.returncode == 0,
            "gh api .../branches/main/protection",
        ),
        Finding(
            "DY-02",
            "Change management",
            "≥90% of changes to main come through a PR",
            ratio >= 0.9,
            f"{len(subjects)} commits, PR share {ratio * 100:.0f}%",
            "Low",
        ),
        Finding(
            "DY-03",
            "Change management",
            "CI runs lint, type and test steps",
            not missing,
            "missing: " + ", ".join(missing) if missing else "ruff, mypy, pytest present",
        ),
        Finding(
            "DY-04",
            "Change management",
            "pre-commit hooks defined",
            (root / ".pre-commit-config.yaml").exists(),
            ".pre-commit-config.yaml",
            "Low",
        ),
        Finding(
            "BY-01",
            "Dependency management",
            "Dependency versions locked",
            (root / "uv.lock").exists(),
            "uv.lock",
            "Medium",
        ),
    ]


def data_checks(engine: Engine) -> list[Finding]:
    today = dt.date.today()
    with Session(engine) as session:
        bad_prices = (
            session.scalar(select(func.count()).select_from(Price).where(Price.close <= 0)) or 0
        )
        last_dates = session.execute(
            select(Security.ticker, func.max(Price.date))
            .join(Price, Price.security_id == Security.id)
            .group_by(Security.ticker)
        ).all()
        sums = session.execute(
            select(
                FundHolding.fund_id, FundHolding.report_date, func.sum(FundHolding.weight)
            ).group_by(FundHolding.fund_id, FundHolding.report_date)
        ).all()
    stale = [t for t, last in last_dates if last is not None and (today - last).days > 10]
    bad_sums = bad_weight_sums({f"{f}/{d}": float(s) for f, d, s in sums})
    columns = {c["name"] for c in inspect(engine).get_columns("prices")}
    lineage = {"source", "fetched_at"} <= columns
    return [
        Finding(
            "VB-01",
            "Data integrity",
            "No zero or negative close prices",
            bad_prices == 0,
            f"{bad_prices} invalid rows",
        ),
        Finding(
            "VB-02",
            "Data integrity",
            "Fund weights sum to ≈100%",
            not bad_sums,
            f"{len(sums)} reports; off: {', '.join(bad_sums) or 'none'}",
        ),
        Finding(
            "VB-03",
            "Data integrity",
            "Price series up to date (≤10 days)",
            not stale,
            f"{len(last_dates)} series; stale: {', '.join(stale[:8]) or 'none'}",
            "Low",
        ),
        Finding(
            "DI-01",
            "Audit trail",
            "Price records carry source and fetch time",
            lineage,
            "prices columns: " + ", ".join(sorted(columns)),
        ),
    ]


def lineage_check(engine: Engine) -> list[Finding]:
    """DI-01 checks that the column exists (design); this checks it is filled (operation)."""
    recent = dt.date.today() - dt.timedelta(days=7)
    with Session(engine) as session:
        total = (
            session.scalar(select(func.count()).select_from(Price).where(Price.date >= recent)) or 0
        )
        missing = (
            session.scalar(
                select(func.count())
                .select_from(Price)
                .where(Price.date >= recent, Price.fetched_at.is_(None))
            )
            or 0
        )
    return [
        Finding(
            "DI-02",
            "Audit trail",
            "fetched_at filled for the last 7 days of prices (operation)",
            total > 0 and missing == 0,
            f"{missing}/{total} records missing",
        )
    ]


MAX_BACKUP_AGE_DAYS = 7


def audit_vulnerabilities(report: str) -> list[str]:
    """'package version: advisory' list from pip-audit JSON output."""
    data = json.loads(report)
    found = []
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            found.append(f"{dep['name']} {dep.get('version', '?')}: {vuln['id']}")
    return found


def restore_verdict(
    restored_rows: int, restored_tables: str, live_tables: str, age_days: float
) -> tuple[bool, str]:
    """Is the restored copy usable, and is the backup recent enough."""
    problems = []
    if restored_rows <= 0:
        problems.append("restored prices table is empty")
    if restored_tables != live_tables:
        problems.append("table list differs from the live database")
    if age_days > MAX_BACKUP_AGE_DAYS:
        problems.append(f"backup is {age_days:.0f} days old (> {MAX_BACKUP_AGE_DAYS})")
    detail = f"{restored_rows} price rows restored, backup is {age_days:.1f} days old"
    return not problems, "; ".join(problems) or detail


def psql(database: str, *args: str, data: bytes | None = None) -> str:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "exec",
            "-T",
            "db",
            "psql",
            "-q",
            "-v",
            "ON_ERROR_STOP=1",
            "-U",
            "bistlab",
            "-d",
            database,
            *args,
        ],
        input=data if data is not None else b"",
        capture_output=True,
        check=True,
    )
    return result.stdout.decode().strip()


def dependency_check(root: Path) -> list[Finding]:
    requirements = root / "backups" / "requirements-audit.txt"
    requirements.parent.mkdir(exist_ok=True)
    exported = subprocess.run(
        [
            "uv",
            "export",
            "--format",
            "requirements-txt",
            "--no-hashes",
            "--no-emit-project",
            "-o",
            str(requirements),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=root,
    )
    audit = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip_audit",
            "-r",
            str(requirements),
            "--no-deps",
            "--disable-pip",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if exported.returncode != 0 or not audit.stdout.strip():
        evidence = "pip-audit could not run: " + (audit.stderr or exported.stderr)[-120:]
        return [
            Finding(
                "BY-02",
                "Dependency management",
                "No known vulnerabilities",
                False,
                evidence.replace("\n", " "),
                "Medium",
            )
        ]
    vulns = audit_vulnerabilities(audit.stdout)
    return [
        Finding(
            "BY-02",
            "Dependency management",
            "No known vulnerabilities (pip-audit)",
            not vulns,
            ", ".join(vulns[:5]) or "no advisories in scanned dependencies",
            "High",
        )
    ]


def restore_check(root: Path) -> list[Finding]:
    """Restores the latest backup into a temporary restore_check database; never touches live."""
    backups = sorted((root / "backups").glob("bistlab-*.sql.gz"))
    if not backups:
        return [Finding("YD-02", "Backup", "Latest backup can be restored", False, "no backup")]
    latest = backups[-1]
    age_days = (time.time() - latest.stat().st_mtime) / 86400
    tables_sql = (
        "SELECT string_agg(table_name, ',' ORDER BY table_name) FROM information_schema.tables "
        "WHERE table_schema = 'public'"
    )
    try:
        psql(
            "bistlab",
            "-c",
            "DROP DATABASE IF EXISTS restore_check;",
            "-c",
            "CREATE DATABASE restore_check;",
        )
        psql("restore_check", data=gzip.decompress(latest.read_bytes()))
        rows = int(psql("restore_check", "-tAc", "SELECT count(*) FROM prices") or 0)
        restored_tables = psql("restore_check", "-tAc", tables_sql)
        live_tables = psql("bistlab", "-tAc", tables_sql)
    except (subprocess.CalledProcessError, ValueError, OSError) as error:
        return [
            Finding(
                "YD-02",
                "Backup",
                "Latest backup can be restored",
                False,
                f"{latest.name}: restore error ({type(error).__name__})",
            )
        ]
    finally:
        subprocess.run(
            [
                "docker",
                "compose",
                "exec",
                "-T",
                "db",
                "psql",
                "-q",
                "-U",
                "bistlab",
                "-d",
                "bistlab",
                "-c",
                "DROP DATABASE IF EXISTS restore_check;",
            ],
            input=b"",
            capture_output=True,
            check=False,
        )
    passed, evidence = restore_verdict(rows, restored_tables, live_tables, age_days)
    return [
        Finding(
            "YD-02",
            "Backup",
            "Latest backup restores and is ≤ 7 days old",
            passed,
            f"{latest.name}: {evidence}",
        )
    ]


def quality_verdict(statuses: dict[str, str]) -> tuple[bool, str]:
    """VB-04 verdict from series statuses (ticker → Good/Warning/Problem)."""
    values = list(statuses.values())
    bad = sorted(code for code, status in statuses.items() if status == "Problem")
    summary = (
        f"{len(values)} series: {values.count('Good')} good, {values.count('Warning')} warning, "
        f"{len(bad)} problem"
    )
    if bad:
        summary += " (" + ", ".join(bad[:5]) + (" …" if len(bad) > 5 else "") + ")"
    return not bad, summary


def price_quality_check() -> list[Finding]:
    """Turns the price-quality report (bistlab.quality.prices) into an audit control."""
    control = "No problem price series (quality report)"
    try:
        from bistlab.quality.prices import assess_all, load_bars

        results = assess_all(load_bars())
    except (Exception, SystemExit) as error:
        return [Finding("VB-04", "Data integrity", control, False, f"could not run: {error}")]
    passed, evidence = quality_verdict({q.ticker: q.status for q in results})
    return [Finding("VB-04", "Data integrity", control, passed, evidence)]


def operations_checks(root: Path) -> list[Finding]:
    compose = root / "docker-compose.yml"
    compose_text = compose.read_text() if compose.exists() else ""
    default_password = "POSTGRES_PASSWORD: bistlab" in compose_text
    backups = list((root / "scripts").glob("backup*")) if (root / "scripts").exists() else []
    return [
        Finding(
            "YD-01",
            "Backup",
            "Database backup script exists",
            bool(backups),
            ", ".join(p.name for p in backups) or "scripts/backup* missing",
        ),
        Finding(
            "ER-01",
            "Access",
            "Database password not hard-coded",
            not default_password,
            "docker-compose.yml",
            "Low",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="bistlab information systems self-audit")
    parser.add_argument("--no-report", action="store_true", help="do not write the Markdown report")
    args = parser.parse_args()

    root = Path(run("git", "rev-parse", "--show-toplevel").stdout.strip() or ".")
    findings = (
        secret_checks(root)
        + change_checks(root)
        + data_checks(get_engine())
        + lineage_check(get_engine())
        + price_quality_check()
        + dependency_check(root)
        + restore_check(root)
        + operations_checks(root)
    )
    for f in findings:
        mark = "✓" if f.passed else "✗"
        print(f"{mark} {f.code:<6} {f.control:<45} {f.status:<16} {f.evidence[:60]}")
    passed = sum(f.passed for f in findings)
    print(f"\n{len(findings)} controls: {passed} pass, {len(findings) - passed} findings")
    if not args.no_report:
        day = dt.date.today()
        path = root / "docs" / "audit" / f"self-audit-{day.isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(findings, day), encoding="utf-8")
        print(f"Report: {path.relative_to(root)}")


if __name__ == "__main__":
    main()
