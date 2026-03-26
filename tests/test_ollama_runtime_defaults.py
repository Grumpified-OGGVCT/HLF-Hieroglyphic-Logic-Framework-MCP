import os

from hlf.ollama_cloud_gateway import ModelGateway
from hlf.profile_config import HLFProfile, get_ollama_base_url, get_profile_config


def test_profile_config_prefers_local_ollama_for_workstation(monkeypatch) -> None:
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    monkeypatch.delenv("HLF_OLLAMA_USE_CLOUD_DIRECT", raising=False)

    config = get_profile_config(HLFProfile.P1_WORKSTATION)

    assert config.use_cloud_direct is False
    assert config.use_local_daemon is True
    assert get_ollama_base_url(config) == "http://localhost:11434"


def test_profile_config_allows_explicit_cloud_override(monkeypatch) -> None:
    monkeypatch.setenv("HLF_OLLAMA_USE_CLOUD_DIRECT", "1")
    monkeypatch.delenv("OLLAMA_HOST", raising=False)

    config = get_profile_config(HLFProfile.P1_WORKSTATION)

    assert config.use_cloud_direct is True
    assert get_ollama_base_url(config) == "https://ollama.com/api"


def test_profile_config_prefers_explicit_host(monkeypatch) -> None:
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setenv("HLF_OLLAMA_USE_CLOUD_DIRECT", "1")

    config = get_profile_config(HLFProfile.P1_WORKSTATION)

    assert get_ollama_base_url(config) == "http://127.0.0.1:11434"


def test_model_gateway_uses_local_first(monkeypatch) -> None:
    gateway = ModelGateway(use_cloud_direct=True, prefer_local=True)

    def fake_local(messages, **kwargs):
        from hlf.ollama_cloud_gateway import OllamaResponse

        return OllamaResponse(
            content="local",
            model="gpt-oss:20b-cloud",
            usage={},
            success=True,
        )

    monkeypatch.setattr(gateway, "_local_chat", fake_local)

    cloud_called = {"value": False}

    class FakeCloud:
        def chat(self, messages, **kwargs):
            cloud_called["value"] = True
            raise AssertionError("cloud path should not run when local succeeds")

    gateway.cloud = FakeCloud()

    response = gateway.chat([{"role": "user", "content": "hello"}])

    assert response.success is True
    assert response.content == "local"
    assert cloud_called["value"] is False


def test_model_gateway_uses_cloud_backup_when_local_fails(monkeypatch) -> None:
    gateway = ModelGateway(use_cloud_direct=True, prefer_local=True)

    def fake_local(messages, **kwargs):
        from hlf.ollama_cloud_gateway import OllamaResponse

        return OllamaResponse(
            content="",
            model="gpt-oss:20b-cloud",
            usage={},
            success=False,
            error="local down",
        )

    monkeypatch.setattr(gateway, "_local_chat", fake_local)
    monkeypatch.setattr(gateway, "_check_cloud", lambda: True)

    class FakeCloud:
        def chat(self, messages, **kwargs):
            from hlf.ollama_cloud_gateway import OllamaResponse

            return OllamaResponse(
                content="cloud",
                model="gpt-oss:20b-cloud",
                usage={},
                success=True,
            )

    gateway.cloud = FakeCloud()

    response = gateway.chat([{"role": "user", "content": "hello"}])

    assert response.success is True
    assert response.content == "cloud"