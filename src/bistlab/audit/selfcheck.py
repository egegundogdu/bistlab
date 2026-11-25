"""bistlab'ın kendi bilgi sistemleri öz denetimi.

SPK'nın bilgi sistemleri yönetimi düzenlemesindeki (VII-128.10, 2025; önceki VII-128.9)
kontrol alanlarından esinlenen otomatik kontroller: gizli bilgi yönetimi, değişiklik yönetimi,
bağımlılık yönetimi, veri bütünlüğü, denetim izi, yedekleme ve erişim. Her kontrol kanıtıyla
birlikte "Uygun" ya da "Bulgu" döner; sonuç docs/audit/ altına Markdown rapor olarak yazılır.

Resmî bir bağımsız denetim değildir; denetim yaklaşımını kendi sistemimize uygulayan bir
öz değerlendirmedir.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import subprocess
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
PR_SUFFIX = re.compile(r"\(#\d+\)\s*$")


@dataclass(frozen=True)
class Finding:
    code: str
    area: str
    control: str
    passed: bool
    evidence: str
    risk: str = "Orta"  # bulgu olursa önem derecesi

    @property
    def status(self) -> str:
        return "Uygun" if self.passed else f"Bulgu ({self.risk})"


# ---- saf yardımcılar (testlenebilir) ----


def gitignore_covers(text: str, name: str) -> bool:
    patterns = {line.strip() for line in text.splitlines() if line.strip()}
    return name in patterns or f"/{name}" in patterns or f"{name}*" in patterns


def find_secrets(text: str) -> list[str]:
    """Gerçek gizli anahtara benzeyen atamaların anahtar adlarını döner."""
    hits = []
    for match in SECRET.finditer(text):
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
    """main'deki commit'lerin ne kadarı squash edilmiş PR'dan geliyor ('... (#12)')."""
    if not subjects:
        return 0.0
    return sum(bool(PR_SUFFIX.search(s)) for s in subjects) / len(subjects)


def bad_weight_sums(sums: dict[str, float], tolerance: float = 0.02) -> list[str]:
    return [key for key, total in sums.items() if abs(total - 1) > tolerance]


def render_markdown(findings: list[Finding], day: dt.date) -> str:
    passed = sum(f.passed for f in findings)
    lines = [
        f"# bistlab bilgi sistemleri öz denetimi — {day.isoformat()}",
        "",
        f"Sonuç: {len(findings)} kontrolden {passed} uygun, {len(findings) - passed} bulgu.",
        "",
        "| Kod | Alan | Kontrol | Durum | Kanıt |",
        "| --- | --- | --- | --- | --- |",
    ]
    for f in findings:
        evidence = f.evidence.replace("|", "/")
        lines.append(f"| {f.code} | {f.area} | {f.control} | {f.status} | {evidence} |")
    lines += [
        "",
        "Resmî bağımsız denetim değildir; VII-128.10 kontrol alanlarından esinlenen öz "
        "değerlendirmedir.",
    ]
    return "\n".join(lines) + "\n"


# ---- kontroller ----


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
            "Gizli bilgi",
            ".env .gitignore'da",
            gitignore_covers(gitignore, ".env"),
            ".gitignore satırları kontrol edildi",
            "Yüksek",
        ),
        Finding(
            "BG-02",
            "Gizli bilgi",
            ".env git'te izlenmiyor",
            not tracked_env,
            "git ls-files .env",
            "Yüksek",
        ),
        Finding(
            "BG-03",
            "Gizli bilgi",
            ".env hiçbir commit'e girmemiş",
            not history.stdout.strip(),
            "git log --all -- .env",
            "Yüksek",
        ),
        Finding(
            "BG-04",
            "Gizli bilgi",
            "İzlenen dosyalarda anahtar kalıbı yok",
            not hits,
            ", ".join(hits) or "taranan tüm dosyalar temiz",
            "Yüksek",
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
            "Değişiklik yönetimi",
            "main dalı korumalı (PR + CI zorunlu)",
            protection.returncode == 0,
            "gh api .../branches/main/protection",
        ),
        Finding(
            "DY-02",
            "Değişiklik yönetimi",
            "main'e giren değişikliklerin ≥%90'ı PR'dan",
            ratio >= 0.9,
            f"{len(subjects)} commit, PR oranı %{ratio * 100:.0f}",
            "Düşük",
        ),
        Finding(
            "DY-03",
            "Değişiklik yönetimi",
            "CI'da lint, tip ve test adımları",
            not missing,
            "eksik: " + ", ".join(missing) if missing else "ruff, mypy, pytest var",
        ),
        Finding(
            "DY-04",
            "Değişiklik yönetimi",
            "pre-commit kancaları tanımlı",
            (root / ".pre-commit-config.yaml").exists(),
            ".pre-commit-config.yaml",
            "Düşük",
        ),
        Finding(
            "BY-01",
            "Bağımlılık yönetimi",
            "Bağımlılık sürümleri kilitli",
            (root / "uv.lock").exists(),
            "uv.lock",
            "Orta",
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
            "Veri bütünlüğü",
            "Sıfır/negatif kapanış fiyatı yok",
            bad_prices == 0,
            f"{bad_prices} hatalı satır",
        ),
        Finding(
            "VB-02",
            "Veri bütünlüğü",
            "Fon ağırlıkları toplamı ≈ %100",
            not bad_sums,
            f"{len(sums)} rapor; sapan: {', '.join(bad_sums) or 'yok'}",
        ),
        Finding(
            "VB-03",
            "Veri bütünlüğü",
            "Fiyat serileri güncel (≤10 gün)",
            not stale,
            f"{len(last_dates)} seri; eski: {', '.join(stale[:8]) or 'yok'}",
            "Düşük",
        ),
        Finding(
            "DI-01",
            "Denetim izi",
            "Fiyat kayıtlarında kaynak ve çekilme zamanı",
            lineage,
            "prices sütunları: " + ", ".join(sorted(columns)),
        ),
    ]


def operations_checks(root: Path) -> list[Finding]:
    compose = root / "docker-compose.yml"
    compose_text = compose.read_text() if compose.exists() else ""
    default_password = "POSTGRES_PASSWORD: bistlab" in compose_text
    backups = list((root / "scripts").glob("backup*")) if (root / "scripts").exists() else []
    return [
        Finding(
            "YD-01",
            "Yedekleme",
            "Veritabanı yedekleme betiği var",
            bool(backups),
            ", ".join(p.name for p in backups) or "scripts/backup* yok",
        ),
        Finding(
            "ER-01",
            "Erişim",
            "Veritabanı parolası koda gömülü değil",
            not default_password,
            "docker-compose.yml",
            "Düşük",
        ),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="bistlab bilgi sistemleri öz denetimi")
    parser.add_argument("--no-report", action="store_true", help="Markdown rapor yazma")
    args = parser.parse_args()

    root = Path(run("git", "rev-parse", "--show-toplevel").stdout.strip() or ".")
    findings = (
        secret_checks(root)
        + change_checks(root)
        + data_checks(get_engine())
        + operations_checks(root)
    )
    for f in findings:
        mark = "✓" if f.passed else "✗"
        print(f"{mark} {f.code:<6} {f.control:<45} {f.status:<14} {f.evidence[:60]}")
    passed = sum(f.passed for f in findings)
    print(f"\n{len(findings)} kontrol: {passed} uygun, {len(findings) - passed} bulgu")
    if not args.no_report:
        day = dt.date.today()
        path = root / "docs" / "audit" / f"oz-denetim-{day.isoformat()}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(render_markdown(findings, day), encoding="utf-8")
        print(f"Rapor: {path.relative_to(root)}")


if __name__ == "__main__":
    main()
