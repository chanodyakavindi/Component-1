from app.main import DemoModelAdapter, PredictRequest


def test_demo_adapter_canonical_child():
    adapter = DemoModelAdapter()
    out = adapter.predict(PredictRequest(child_pseudonymous_id="C-1042", visit_number=2))
    assert out.mode == "DEMO"
    assert out.risk_score == 0.59
    assert out.status == "wasting"
    assert len(out.latent_embedding) in {64, 128}


def test_demo_adapter_is_deterministic():
    adapter = DemoModelAdapter()
    a = adapter.predict(PredictRequest(child_pseudonymous_id="C-1999", visit_number=0, anthropometric={"weight_kg": 8, "height_cm": 72, "muac_cm": 12}))
    b = adapter.predict(PredictRequest(child_pseudonymous_id="C-1999", visit_number=0, anthropometric={"weight_kg": 8, "height_cm": 72, "muac_cm": 12}))
    assert a.risk_score == b.risk_score
    assert a.latent_embedding == b.latent_embedding
