"""KAP Kurumsal Yönetim Bilgi Formu'ndan (KYBF) nicel kurumsal yönetim karnesi.

KAP'ta şirket sayfası > Kurumsal Yönetim > EXCEL ile inen dosya aslında bir HTML tablosudur.
Formdaki olgusal yanıtlardan (oy imtiyazı, bağımsız üye oranı, politikaların varlığı...)
0-1 arası göstergeler üretilir; SPK'nın dört ana bölümü resmî ağırlıklarla birleştirilir:
pay sahipleri %25, kamuyu aydınlatma %25, menfaat sahipleri %15, yönetim kurulu %35.

Bu bir derecelendirme notu değildir: şirket beyanına dayanır, yerinde doğrulanmamıştır.
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


@dataclass(frozen=True)
class GovernanceForm:
    answers: dict[str, str]
    board: pd.DataFrame
    committees: pd.DataFrame


@dataclass(frozen=True)
class Indicator:
    section: str
    name: str
    score: float | None  # None: formda yanıt yok
    raw: str


def read_form(html: str) -> GovernanceForm:
    answers: dict[str, str] = {}
    board = pd.DataFrame()
    committees = pd.DataFrame()
    for table in pd.read_html(StringIO(html)):
        columns = [str(c) for c in table.columns]
        if "Adı-Soyadı" in columns and "Cinsiyet" in columns:
            board = table
        elif "Komitede Bağımsız Üyelerin Oranı" in columns:
            committees = table
        elif table.shape[1] == 3:
            for question, answer, _ in table.itertuples(index=False):
                answers[str(question).strip()] = str(answer).strip()
    return GovernanceForm(answers, board, committees)


def find(form: GovernanceForm, key: str) -> str | None:
    """Soru metninde `key` geçen ilk yanıt (büyük/küçük harf duyarsız)."""
    needle = key.casefold()
    for question, answer in form.answers.items():
        if needle in question.casefold():
            return answer
    return None


def is_present(text: str | None) -> bool:
    return text is not None and text.strip().casefold() not in EMPTY


def is_yes(text: str | None) -> bool:
    return text is not None and text.strip().casefold().startswith("evet")


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
    """Hedefe ulaşınca 1, altında orantılı."""
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
        return Indicator(section, name, score, raw or "yanıt yok")

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
        return "yanıt yok" if value is None else f"%{value * 100:.1f}"

    p, k, m, y = SECTION_WEIGHTS
    return [
        flag(p, "Oyda imtiyaz yok", "Oy hakkında imtiyaz", lambda t: not is_yes(t)),
        flag(p, "Azlık hakları genişletilmiş", "Azlık haklarının", is_yes),
        Indicator(p, "En büyük ortak ≤ %25 (≥ %75 → 0)", owner_score, pct(owner)),
        flag(p, "Kâr dağıtım politikası sitede", "kar dağıtım politikasının", is_present),
        flag(k, "İnternet sitesi İngilizce", "hazırlandığı diller", lambda t: "ngilizce" in str(t)),
        flag(k, "Genel kurul belgeleri eşanlı İngilizce", "eşanlı olarak İngilizce", is_present),
        flag(k, "Bağış politikası sitede", "bağış ve yardımlara ilişkin politikanın", is_present),
        flag(k, "Ücretlendirme politikası sitede", "ücretlendirme politikası", is_present),
        flag(m, "Tazminat politikası sitede", "tazminat politikasının", is_present),
        flag(
            m,
            "Çalışanlar yönetimde temsil ediliyor",
            "Çalışanların temsil edildiği yönetim organları",
            lambda t: is_present(t) and "bulunmamaktadır" not in str(t).casefold(),
        ),
        flag(
            m,
            "Çalışanlara pay edindirme planı",
            "Pay edindirme planı",
            lambda t: "bulunmuyor" not in str(t).casefold() and is_present(t),
        ),
        flag(m, "Etik kurallar politikası", "etik kurallar politikasının", is_present),
        flag(m, "Yolsuzlukla mücadele önlemleri", "yolsuzlukla mücadele", is_present),
        Indicator(y, "Bağımsız üye ≥ 1/3", capped(independent, 1 / 3), pct(independent)),
        Indicator(y, "Kadın üye ≥ %25", capped(women, 0.25), pct(women)),
        Indicator(y, "İcracı olmayan üye oranı", non_executive, pct(non_executive)),
        Indicator(y, "Başkan ve genel müdür ayrı kişi", split, f"{chair} / {ceo}"),
        flag(y, "Performans değerlendirmesinde bağımsız uzman", "bağımsız uzmanlardan", is_yes),
        Indicator(y, "YK toplantılarına katılım ≥ %90", capped(attendance, 0.9), pct(attendance)),
        Indicator(y, "Denetim komitesi tamamen bağımsız", audit, pct(audit)),
        flag(y, "Kadın üye çeşitlilik politikası", "çeşitlilik politikası", is_present),
    ]


def section_scores(indicators: list[Indicator]) -> dict[str, float]:
    """Her bölüm: yanıtı olan göstergelerin ortalaması (0-1)."""
    scores: dict[str, float] = {}
    for section in SECTION_WEIGHTS:
        values = [i.score for i in indicators if i.section == section and i.score is not None]
        if values:
            scores[section] = sum(values) / len(values)
    return scores


def total_score(scores: dict[str, float]) -> float:
    """Ağırlıklı toplam, 0-10 ölçeğinde (eksik bölümün ağırlığı dağıtılır)."""
    weight = sum(SECTION_WEIGHTS[s] for s in scores)
    return 10 * sum(SECTION_WEIGHTS[s] * v for s, v in scores.items()) / weight


def main() -> None:
    parser = argparse.ArgumentParser(description="KAP Kurumsal Yönetim Bilgi Formu karnesi")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--detail", action="store_true", help="Göstergeleri tek tek yaz")
    args = parser.parse_args()

    print(f"{'Şirket':<10}" + "".join(f"{s[:12]:>14}" for s in SECTION_WEIGHTS) + f"{'Toplam':>9}")
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
                print(f"    {mark}  {item.section[:9]:<9}  {item.name:<45} {item.raw[:40]}")
    print("\n0-10 ölçeği; ağırlıklar SPK: pay sahipleri %25, kamuyu aydınlatma %25,")
    print("menfaat sahipleri %15, yönetim kurulu %35. Şirket beyanına dayalı, derecelendirme")
    print("notu değildir; yatırım tavsiyesi değildir.")


if __name__ == "__main__":
    main()
