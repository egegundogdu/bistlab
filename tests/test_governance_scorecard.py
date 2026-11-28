import pytest

from bistlab.governance.scorecard import (
    find,
    parse_ratio,
    read_form,
    score_form,
    section_scores,
    total_score,
)


def qa_table(title: str, rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<tr><td>{q}</td><td>{a}</td><td></td></tr>" for q, a in rows)
    return f"<table><tr><th>{title}</th><th></th><th></th></tr>{body}</table>"


BOARD = """
<table>
<tr><th>Adı-Soyadı</th><th>Cinsiyet</th><th>İcrada Görevli Olup Olmadığı</th>
<th>Bağımsız Yönetim Kurulu Üyesi Olup Olmadığı</th></tr>
<tr><td>A</td><td>Kadın</td><td>İcrada Görevli Değil</td><td>Bağımsız Üye</td></tr>
<tr><td>B</td><td>Erkek</td><td>İcrada Görevli</td><td>Bağımsız Üye Değil</td></tr>
<tr><td>C</td><td>Erkek</td><td>İcrada Görevli Değil</td><td>Bağımsız Üye Değil</td></tr>
<tr><td>D</td><td>Kadın</td><td>İcrada Görevli Değil</td><td>Bağımsız Üye</td></tr>
</table>
"""
COMMITTEES = """
<table>
<tr><th>Yönetim Kurulu Komitelerinin Adları</th><th>Komitede Bağımsız Üyelerin Oranı</th></tr>
<tr><td>Denetim Komitesi (Audit Committee)</td><td>%50</td></tr>
</table>
"""
HTML = (
    qa_table(
        "1.4. Oy Hakları",
        [
            ("Oy hakkında imtiyaz bulunup bulunmadığı", "Evet (Yes)"),
            ("En büyük pay sahibinin ortaklık oranı", "%50,00"),
        ],
    )
    + qa_table("2.1. Kurumsal İnternet Sitesi", [("Sitenin hazırlandığı diller", "Türkçe")])
    + qa_table(
        "4.2. Yönetim Kurulunun Faaliyet Esasları",
        [
            ("Yönetim kurulu başkanının adı", "Ali Veli"),
            ("İcra başkanı / genel müdürün adı", "ali veli"),
            ("Yönetim kurulu toplantılarına ortalama katılım oranı", "%45"),
        ],
    )
    + BOARD
    + COMMITTEES
)


def test_parse_ratio() -> None:
    assert parse_ratio("%74,20") == pytest.approx(0.742)
    assert parse_ratio("1/9") == pytest.approx(1 / 9)
    assert parse_ratio("-") is None


def test_read_form_splits_tables() -> None:
    form = read_form(HTML)
    assert find(form, "oy hakkında imtiyaz") == "Evet (Yes)"
    assert len(form.board) == 4
    assert not form.committees.empty


def test_score_form_indicators() -> None:
    scores = {i.name: i.score for i in score_form(read_form(HTML))}
    assert scores["Oyda imtiyaz yok"] == 0.0
    assert scores["En büyük ortak ≤ %25 (≥ %75 → 0)"] == pytest.approx(0.5)
    assert scores["İnternet sitesi İngilizce"] == 0.0
    assert scores["Bağımsız üye ≥ 1/3"] == 1.0  # 2/4
    assert scores["Kadın üye ≥ %25"] == 1.0  # 2/4
    assert scores["İcracı olmayan üye oranı"] == pytest.approx(0.75)
    assert scores["Başkan ve genel müdür ayrı kişi"] == 0.0  # aynı kişi
    assert scores["YK toplantılarına katılım ≥ %90"] == pytest.approx(0.5)
    assert scores["Denetim komitesi tamamen bağımsız"] == pytest.approx(0.5)
    assert scores["Tazminat politikası sitede"] is None  # formda yok


def test_total_score_reweights_missing_sections() -> None:
    assert total_score({"Shareholders": 1.0, "Board of directors": 0.0}) == pytest.approx(
        10 * 0.25 / 0.60
    )


def test_section_scores_skip_unanswered() -> None:
    sections = section_scores(score_form(read_form(HTML)))
    assert "Stakeholders" not in sections
    assert 0 <= sections["Board of directors"] <= 1
