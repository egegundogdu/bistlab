import json

from bistlab.audit.selfcheck import audit_vulnerabilities, restore_verdict


def test_audit_vulnerabilities_lists_package_and_id() -> None:
    report = json.dumps(
        {
            "dependencies": [
                {"name": "requests", "version": "2.0.0", "vulns": [{"id": "PYSEC-1"}]},
                {"name": "pandas", "version": "3.0.0", "vulns": []},
            ]
        }
    )
    assert audit_vulnerabilities(report) == ["requests 2.0.0: PYSEC-1"]
    assert audit_vulnerabilities(json.dumps({"dependencies": []})) == []


def test_restore_verdict_passes_for_fresh_complete_copy() -> None:
    passed, evidence = restore_verdict(78000, "funds,prices", "funds,prices", 0.5)
    assert passed
    assert "78000" in evidence


def test_restore_verdict_flags_problems() -> None:
    passed, evidence = restore_verdict(0, "prices", "funds,prices", 10)
    assert not passed
    assert "empty" in evidence and "table list" in evidence and "10 days old" in evidence
