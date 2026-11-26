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


def test_tool_endpoints() -> None:
    c = client(FakeSource())
    opt = c.get("/derivatives/option", params={"spot": 100, "strike": 105, "type": "put"})
    assert opt.status_code == 200 and opt.json()["option"] == "put"
    assert c.get("/derivatives/option", params={"spot": -1, "strike": 100}).status_code == 422
    iv = c.get("/derivatives/implied-vol", params={"price": 5, "spot": 100, "strike": 100})
    assert iv.status_code == 200
    hedge = c.get(
        "/derivatives/futures-hedge", params={"tickers": ["THYAO", "ASELS"], "index": "XU100"}
    )
    assert hedge.status_code == 200
    assert c.get("/funds/IKP/xray", params={"compare": "KVT"}).status_code == 200
    assert c.get("/funds/YOK/xray").status_code == 404


def test_catalog_and_prices() -> None:
    c = client(FakeSource())
    tickers = [r["ticker"] for r in c.get("/securities").json()["results"]]
    assert tickers == sorted(tickers) and "THYAO" in tickers
    prices = c.get("/prices/thyao", params={"since": "2026-01-01"}).json()
    assert prices["ticker"] == "THYAO" and prices["points"][0]["date"] >= "2026-01-01"
    assert c.get("/prices/YOK").status_code == 404


def test_cors_allows_local_frontend_only() -> None:
    c = client(FakeSource())
    ok = c.get("/health", headers={"Origin": "http://localhost:3000"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:3000"
    other = c.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
