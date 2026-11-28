from bistlab.audit.selfcheck import quality_verdict


def test_quality_verdict_passes_without_problem_series() -> None:
    passed, evidence = quality_verdict({"THYAO": "Good", "SOL.MC": "Warning", "XU100": "Good"})
    assert passed
    assert evidence == "3 series: 2 good, 1 warning, 0 problem"


def test_quality_verdict_lists_problem_series() -> None:
    passed, evidence = quality_verdict({"B": "Problem", "A": "Problem", "C": "Good"})
    assert not passed
    assert evidence.endswith("2 problem (A, B)")
