"""Quantitative corporate-governance scorecard from the KAP Corporate Governance Information Form.

The "EXCEL" download on a company's KAP page (Corporate Governance tab) is actually an HTML
table. Factual answers in the form (voting privileges, share of independent members, whether
policies exist ...) are turned into 0–1 indicators; the regulator's four main sections are
combined with the official weights: shareholders 25%, disclosure & transparency 25%,
stakeholders 15%, board of directors 35%.

This is not a rating: it relies on the company's own disclosure and is not verified on site.

The form is in Turkish, so the question texts, column names and answer values matched below
(e.g. "Oy hakkında imtiyaz", "Bağımsız Üye", "evet") intentionally stay in Turkish.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pandas as pd

SECTION_WEIGHTS = {
    "Shareholders": 0.25,
    "Disclosure & transparency": 0.25,
    "Stakeholders": 0.15,
    "Board of directors": 0.35,
}
EMPTY = {"", "-", "nan", "none"}
NO_ANSWER = "no answer"


@dataclass(frozen=True)
class GovernanceForm:
    answers: dict[str, str]
    board: pd.DataFrame
    committees: pd.DataFrame


@dataclass(frozen=True)
class Indicator:
    section: str
    name: str
    score: float | None  # None: no answer in the form
    raw: str


def read_form(html: str) -> GovernanceForm:
    answers: dict[str, str] = {}
    board = pd.DataFrame()
    committees = pd.DataFrame()
    for table in pd.read_html(StringIO(html)):
        columns = [str(c) for c in table.columns]
        if "Adı-Soyadı" in columns and "Cinsiyet" in columns:  # board members table
            board = table
        elif "Komitede Bağımsız Üyelerin Oranı" in columns:  # board committees table
            committees = table
        elif table.shape[1] == 3:
            for question, answer, _ in table.itertuples(index=False):
                answers[str(question).strip()] = str(answer).strip()
    return GovernanceForm(answers, board, committees)


def find(form: GovernanceForm, key: str) -> str | None:
    """First answer whose question text contains `key` (case-insensitive)."""
    needle = key.casefold()
    for question, answer in form.answers.items():
        if needle in question.casefold():
            return answer
    return None


def is_present(text: str | None) -> bool:
    return text is not None and text.strip().casefold() not in EMPTY


def is_yes(text: str | None) -> bool:
    return text is not None and text.strip().casefold().startswith("evet")  # "yes"


def parse_ratio(text: str | None) -> float | None:
    """'%74,20' -> 0.742, '1/9' -> 0.111..., '%100' -> 1.0"""
    if not is_present(text):
        return None
    assert text is not None
    if match := re.search(r"(\d+)\s*/\s*(\d+)", text):
        return int(match[1]) / int(match[2])
    if match := re.search(r"(\d+(?:[.,]\d+)?)", text):
        return float(match[1].replace(",", ".")) / 100
    return None


def capped(value: float | None, target: float) -> float | None:
    """1 once the target is reached, proportional below it."""
    return None if value is None else min(1.0, value / target)


def board_ratio(board: pd.DataFrame, column: str, match: Callable[[str], bool]) -> float | None:
    if board.empty or column not in board.columns:
        return None
    values = [str(v).strip() for v in board[column]]
    return sum(match(v) for v in values) / len(values)


def score_form(form: GovernanceForm) -> list[Indicator]:
    def flag(section: str, name: str, key: str, test: Callable[[str | None], bool]) -> Indicator:
        raw = find(form, key)
        score = None if raw is None else float(test(raw))
        return Indicator(section, name, score, raw or NO_ANSWER)

    # Turkish strings below are question texts / values from the KAP form.
    owner = parse_ratio(find(form, "En büyük pay sahibinin ortaklık oranı"))
    owner_score = None if owner is None else min(1.0, max(0.0, (0.75 - owner) / 0.50))
    independent = board_ratio(
        form.board, "Bağımsız Yönetim Kurulu Üyesi Olup Olmadığı", lambda v: v == "Bağımsız Üye"
    )
    women = board_ratio(form.board, "Cinsiyet", lambda v: v.casefold() == "kadın")
    non_executive = board_ratio(
        form.board, "İcrada Görevli Olup Olmadığı", lambda v: "değil" in v.casefold()
    )
    chair = find(form, "Yönetim kurulu başkanının adı")
    ceo = find(form, "İcra başkanı / genel müdürün adı")
    split = None if chair is None or ceo is None else float(chair.casefold() != ceo.casefold())
    attendance = parse_ratio(find(form, "toplantılarına ortalama katılım oranı"))
    audit = None
    if not form.committees.empty:
        rows = form.committees[
            form.committees.iloc[:, 0].astype(str).str.contains("Denetim Komitesi")
        ]
        if not rows.empty:
            audit = parse_ratio(str(rows["Komitede Bağımsız Üyelerin Oranı"].iloc[0]))

    def pct(value: float | None) -> str:
        return NO_ANSWER if value is None else f"{value * 100:.1f}%"

    sh, dt_, st, bd = SECTION_WEIGHTS
    return [
        flag(sh, "No voting privileges", "Oy hakkında imtiyaz", lambda t: not is_yes(t)),
        flag(sh, "Extended minority rights", "Azlık haklarının", is_yes),
        Indicator(sh, "Largest shareholder ≤ 25% (≥ 75% → 0)", owner_score, pct(owner)),
        flag(sh, "Dividend policy on website", "kar dağıtım politikasının", is_present),
        flag(dt_, "Website in English", "hazırlandığı diller", lambda t: "ngilizce" in str(t)),
        flag(
            dt_, "AGM documents in English at the same time", "eşanlı olarak İngilizce", is_present
        ),
        flag(
            dt_, "Donation policy on website", "bağış ve yardımlara ilişkin politikanın", is_present
        ),
        flag(dt_, "Remuneration policy on website", "ücretlendirme politikası", is_present),
        flag(st, "Severance policy on website", "tazminat politikasının", is_present),
        flag(
            st,
            "Employees represented in management",
            "Çalışanların temsil edildiği yönetim organları",
            lambda t: is_present(t) and "bulunmamaktadır" not in str(t).casefold(),
        ),
        flag(
            st,
            "Employee share plan",
            "Pay edindirme planı",
            lambda t: "bulunmuyor" not in str(t).casefold() and is_present(t),
        ),
        flag(st, "Code of ethics", "etik kurallar politikasının", is_present),
        flag(st, "Anti-corruption measures", "yolsuzlukla mücadele", is_present),
        Indicator(bd, "Independent members ≥ 1/3", capped(independent, 1 / 3), pct(independent)),
        Indicator(bd, "Women members ≥ 25%", capped(women, 0.25), pct(women)),
        Indicator(bd, "Share of non-executive members", non_executive, pct(non_executive)),
        Indicator(bd, "Chair and CEO are different people", split, f"{chair} / {ceo}"),
        flag(bd, "Independent experts in board evaluation", "bağımsız uzmanlardan", is_yes),
        Indicator(bd, "Board meeting attendance ≥ 90%", capped(attendance, 0.9), pct(attendance)),
        Indicator(bd, "Audit committee fully independent", audit, pct(audit)),
        flag(bd, "Board diversity policy (women)", "çeşitlilik politikası", is_present),
    ]


def section_scores(indicators: list[Indicator]) -> dict[str, float]:
    """Each section: mean of the indicators that have an answer (0–1)."""
    scores: dict[str, float] = {}
    for section in SECTION_WEIGHTS:
        values = [i.score for i in indicators if i.section == section and i.score is not None]
        if values:
            scores[section] = sum(values) / len(values)
    return scores


def total_score(scores: dict[str, float]) -> float:
    """Weighted total on a 0–10 scale (the weight of a missing section is redistributed)."""
    weight = sum(SECTION_WEIGHTS[s] for s in scores)
    return 10 * sum(SECTION_WEIGHTS[s] * v for s, v in scores.items()) / weight


def main() -> None:
    parser = argparse.ArgumentParser(description="KAP corporate governance form scorecard")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--detail", action="store_true", help="print every indicator")
    args = parser.parse_args()

    print(f"{'Company':<10}" + "".join(f"{s[:12]:>14}" for s in SECTION_WEIGHTS) + f"{'Total':>9}")
    for path in args.files:
        indicators = score_form(read_form(path.read_text(encoding="utf-8")))
        scores = section_scores(indicators)
        name = path.stem.split("_")[0].upper()
        cells = "".join(
            f"{scores[s] * 10:>14.1f}" if s in scores else f"{'-':>14}" for s in SECTION_WEIGHTS
        )
        print(f"{name:<10}{cells}{total_score(scores):>9.1f}")
        if args.detail:
            for item in indicators:
                mark = "  ?" if item.score is None else f"{item.score:>3.1f}"
                print(f"    {mark}  {item.section[:12]:<12}  {item.name:<45} {item.raw[:40]}")
    print("\n0–10 scale; regulator weights: shareholders 25%, disclosure & transparency 25%,")
    print("stakeholders 15%, board of directors 35%. Based on company self-disclosure; not a")
    print("rating and not investment advice.")


if __name__ == "__main__":
    main()
