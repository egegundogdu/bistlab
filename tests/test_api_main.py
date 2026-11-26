from api_fake import FakeSource
from fastapi.testclient import TestClient

from bistlab.api.main import app, get_source


def client(source: FakeSource) -> TestClient:
    app.dependency_overrides[get_source] = lambda: source
    return TestClient(app)


def test_health() -> None:
    assert client(FakeSource()).get("/health").json() == {"status": "ok", "database": True}
    assert client(FakeSource(healthy=False)).get("/health").json()["database"] is False


def test_endpoints_return_json() -> None:
    c = client(FakeSource())
    assert c.get("/quality/prices").status_code == 200
    returns = c.get("/real/returns", params={"tickers": ["thyao"]}).json()
    assert [r["ticker"] for r in returns["results"]] == ["XU100", "THYAO"]
    assert c.get("/real/fcf", params={"tickers": ["THYAO"]}).json()["results"][0]["factor"] == 1.0
    stress = c.get("/stress/macro", params={"tickers": ["THYAO", "ASELS"]})
    assert stress.status_code == 200 and len(stress.json()["scenarios"]) == 3


def test_validation_and_unavailable() -> None:
    c = client(FakeSource())
    assert c.get("/real/returns", params={"tickers": ["DROP TABLE"]}).status_code == 422
    assert c.get("/stress/macro", params={"years": 0}).status_code == 422
    assert client(FakeSource(with_macro=False)).get("/real/returns").status_code == 503


def test_core_endpoints() -> None:
    c = client(FakeSource())
    assert c.get("/credit/scores", params={"tickers": ["ASELS"]}).status_code == 200
    merton = c.get("/credit/merton", params={"tickers": ["ASELS"], "rate": 0.4})
    assert merton.status_code == 200 and merton.json()["results"][0]["ticker"] == "ASELS"
    assert c.get("/credit/merton", params={"rate": 5}).status_code == 422
    assert c.get("/valuation/multiples", params={"tickers": ["ASELS"]}).status_code == 200
    assert c.get("/governance/scores").json()["results"] == []
