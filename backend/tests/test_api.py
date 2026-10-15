from fastapi.testclient import TestClient

from backend.main import app

LOW = dict(Pregnancies=1, Glucose=118, BloodPressure=76, SkinThickness=25, Insulin=0, BMI=24.8, DiabetesPedigreeFunction=0.35, Age=24)
HIGH = dict(Pregnancies=6, Glucose=170, BloodPressure=80, SkinThickness=35, Insulin=200, BMI=36, DiabetesPedigreeFunction=0.9, Age=50)


def test_all():
    with TestClient(app) as c:
        assert c.get("/health").json() == {"status": "ok", "model_loaded": True}
        assert c.get("/model-info").json()["model"]

        r = c.post("/predict", json=LOW).json()
        assert not r["flagged_higher_risk"] and r["counterfactuals"] is None
        assert "Insulin" in r["not_measured"]

        r = c.post("/predict", json=HIGH).json()
        assert r["flagged_higher_risk"] and r["factors"][0]["feature"] == "Glucose"
        assert r["counterfactuals"]["options"]

        # missing optional fields are fine
        p = {k: v for k, v in HIGH.items() if k not in ("Insulin", "SkinThickness")}
        assert c.post("/predict", json=p).status_code == 200

        # validation
        assert c.post("/predict", json={**LOW, "Age": 300}).status_code == 422
        assert c.post("/predict", json={**LOW, "Glucose": -5}).status_code == 422
        assert c.post("/predict", json={k: v for k, v in LOW.items() if k != "Age"}).status_code == 422

        w = c.post("/what-if", json={"patient": HIGH, "changes": {"Glucose": 100}}).json()
        assert w["after"] < w["before"]
        assert c.post("/what-if", json={"patient": HIGH, "changes": {"Age": 20}}).status_code == 422

        assert c.get("/global-importance").json()["factors"][0]["feature"] == "Glucose"

        h = c.options("/predict", headers={"Origin": "https://health-lens-theta.vercel.app", "Access-Control-Request-Method": "POST"})
        assert h.headers.get("access-control-allow-origin") == "https://health-lens-theta.vercel.app"
        h = c.options("/predict", headers={"Origin": "https://evil.com", "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in h.headers
