import datetime as dt

from bistlab.audit.selfcheck import (
    Finding,
    bad_weight_sums,
    ci_missing_steps,
    find_secrets,
    gitignore_covers,
    pr_ratio,
    render_markdown,
)


def test_gitignore_covers() -> None:
    assert gitignore_covers(".venv\n.env\n", ".env")
    assert gitignore_covers("/.env\n", ".env")
    assert not gitignore_covers(".env.example\n", ".env")


def test_find_secrets_flags_real_looking_keys() -> None:
    assert find_secrets('EVDS_API_KEY="aB3dE5fG7hJ9kL"') == ["API_KEY"]  # selfcheck: allow
    assert find_secrets("password: s3cretValue2026") == ["password"]  # selfcheck: allow


def test_find_secrets_ignores_placeholders_and_short_values() -> None:
    assert find_secrets("EVDS_API_KEY=your-key-here-123") == []
    assert find_secrets("POSTGRES_PASSWORD: bistlab") == []
    assert find_secrets("token = abcdefghijklmnop") == []  # rakam yok


def test_ci_missing_steps() -> None:
    assert ci_missing_steps("uv run ruff check\nuv run pytest", ["ruff", "mypy", "pytest"]) == [
        "mypy"
    ]


def test_pr_ratio() -> None:
    subjects = ["feat: a (#21)", "feat: b (#22)", "ilk commit", "fix: c (#23)"]
    assert pr_ratio(subjects) == 0.75
    assert pr_ratio([]) == 0.0


def test_bad_weight_sums() -> None:
    assert bad_weight_sums({"IKP": 1.0002, "KVT": 0.95}) == ["KVT"]


def test_render_markdown() -> None:
    findings = [
        Finding("BG-01", "Gizli bilgi", ".env .gitignore'da", True, "ok"),
        Finding("YD-01", "Yedekleme", "Yedek betiği", False, "yok | eksik", "Medium"),
    ]
    text = render_markdown(findings, dt.date(2026, 11, 26))
    assert "Result: 1 of 2 controls pass, 1 finding" in text
    assert "| YD-01 | Yedekleme | Yedek betiği | Finding (Medium) | yok / eksik |" in text


def test_find_secrets_respects_allow_marker() -> None:
    text = (
        "token = Zx9Yw8Vu7Ts6Rq  # selfcheck: allow\npassword: Qq1Ww2Ee3Rr4Tt"  # selfcheck: allow
    )
    assert find_secrets(text) == ["password"]
