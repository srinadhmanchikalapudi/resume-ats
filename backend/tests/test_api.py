from app import llm


def test_health_needs_no_token(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_settings_require_token(client):
    assert client.get("/settings").status_code == 401
    assert client.get("/settings", headers={"X-App-Token": "wrong"}).status_code == 401


def test_settings_roundtrip(client, auth):
    initial = client.get("/settings", headers=auth).json()
    assert initial["model"] == ""
    assert initial["has_api_key"] is False

    response = client.put(
        "/settings",
        headers=auth,
        json={"base_url": "https://openrouter.ai/api/v1/", "model": " openai/gpt-5 "},
    )
    assert response.status_code == 200
    saved = client.get("/settings", headers=auth).json()
    assert saved["model"] == "openai/gpt-5"
    assert saved["base_url"] == "https://openrouter.ai/api/v1"


def test_rejects_bad_base_url(client, auth):
    response = client.put("/settings", headers=auth, json={"base_url": "ftp://nope"})
    assert response.status_code == 422


def test_api_key_is_stored_in_secret_store_not_settings(client, auth, store, tmp_path):
    assert client.put("/settings/api-key", headers=auth, json={"api_key": " sk-test "}).status_code == 204
    assert store.value == "sk-test"
    assert client.get("/settings", headers=auth).json()["has_api_key"] is True
    assert "sk-test" not in client.get("/settings", headers=auth).text
    assert not any("sk-test" in p.read_text() for p in tmp_path.glob("*.json"))

    assert client.delete("/settings/api-key", headers=auth).status_code == 204
    assert client.get("/settings", headers=auth).json()["has_api_key"] is False


def test_empty_api_key_rejected(client, auth):
    assert client.put("/settings/api-key", headers=auth, json={"api_key": "  "}).status_code == 422


def test_connection_test_requires_key_and_model(client, auth):
    assert client.post("/settings/test", headers=auth).json()["ok"] is False
    client.put("/settings/api-key", headers=auth, json={"api_key": "sk-test"})
    result = client.post("/settings/test", headers=auth).json()
    assert result == {"ok": False, "message": "Choose a model first."}


def test_models_endpoint(client, auth, monkeypatch):
    async def fake_list(base_url, api_key):
        return [llm.ModelInfo(id="a/b", name="B")]

    monkeypatch.setattr(llm, "list_models", fake_list)
    assert client.get("/models", headers=auth).json()[0]["id"] == "a/b"


def test_models_upstream_failure_is_502(client, auth, monkeypatch):
    async def boom(base_url, api_key):
        raise llm.LlmError("down")

    monkeypatch.setattr(llm, "list_models", boom)
    assert client.get("/models", headers=auth).status_code == 502


def test_parse_models_openrouter_shape():
    models = llm.parse_models(
        {
            "data": [
                {
                    "id": "z/json",
                    "name": "Z",
                    "context_length": 1000,
                    "pricing": {"prompt": "0.000001", "completion": "0.000002"},
                    "supported_parameters": ["temperature", "response_format"],
                },
                {"id": "a/plain", "supported_parameters": ["temperature"]},
                {"id": "m/unknown"},
                {"name": "no id, skipped"},
            ]
        }
    )
    assert [m.id for m in models] == ["a/plain", "m/unknown", "z/json"]
    by_id = {m.id: m for m in models}
    assert by_id["z/json"].supports_json is True
    assert by_id["z/json"].prompt_price == 0.000001
    assert by_id["a/plain"].supports_json is False
    assert by_id["m/unknown"].supports_json is None
    assert by_id["m/unknown"].name == "m/unknown"
