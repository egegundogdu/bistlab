from bistlab.audit.selfcheck import quality_verdict


def test_quality_verdict_passes_without_problem_series() -> None:
    passed, evidence = quality_verdict({"THYAO": "İyi", "SOL.MC": "Dikkat", "XU100": "İyi"})
    assert passed
    assert evidence == "3 seri: 2 iyi, 1 dikkat, 0 sorunlu"


def test_quality_verdict_lists_problem_series() -> None:
    passed, evidence = quality_verdict({"B": "Sorunlu", "A": "Sorunlu", "C": "İyi"})
    assert not passed
    assert evidence.endswith("2 sorunlu (A, B)")
