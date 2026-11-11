from app import create_app


def test_health_endpoint():
    client = create_app().test_client()
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_index_renders():
    client = create_app().test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"PhantomPass" in resp.data
