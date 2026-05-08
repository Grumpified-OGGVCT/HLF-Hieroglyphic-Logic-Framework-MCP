import json
from pathlib import Path

from hlf_mcp import server

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_repo_mcp_json_points_to_packaged_hlf_stdio_server() -> None:
    config = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))

    hlf_server = config["mcpServers"]["hlf-mcp"]

    assert hlf_server["type"] == "stdio"
    assert hlf_server["command"] == "python"
    assert hlf_server["args"] == ["-m", "hlf_mcp.server"]
    assert hlf_server["env"]["HLF_TRANSPORT"] == "stdio"


def test_native_agent_prompt_and_first_contact_resources_are_registered() -> None:
    assert "hlf_native_agent" in server.REGISTERED_PROMPTS

    for resource_uri in (
        "hlf://agent/quickstart",
        "hlf://agent/protocol",
        "hlf://agent/current_authority",
        "hlf://agent/handoff_contract",
    ):
        assert resource_uri in server.REGISTERED_RESOURCES


def test_native_agent_loop_is_discoverable_without_source_edits() -> None:
    prompt = server.REGISTERED_PROMPTS["hlf_native_agent"]()
    quickstart = json.loads(server.REGISTERED_RESOURCES["hlf://agent/quickstart"]())
    handoff = json.loads(server.REGISTERED_RESOURCES["hlf://agent/handoff_contract"]())

    assert "NLP ingress" in prompt
    assert "HLF translation" in prompt
    assert "validation/compile proof" in prompt
    assert "hlf_do" in quickstart["hll_to_hlf_entrypoints"]
    assert "hlf_translate_to_hlf" in quickstart["hll_to_hlf_entrypoints"]
    assert handoff["mandatory_internal_loop"]["order"] == [
        "NLP ingress",
        "HLF translation",
        "validate/lint/compile",
        "governed execution or coordination",
        "NLP egress for humans",
    ]


async def test_hlf_native_agent_prompt_content_or_resource_fallback_is_non_empty() -> None:
    messages = await server.mcp._prompt_manager.render_prompt(
        "hlf_native_agent",
        {"tier": "forge", "language": "en", "swarm_mode": True},
    )
    prompt_text = messages[0].content.text if messages and hasattr(messages[0].content, "text") else ""

    quickstart = json.loads(server.REGISTERED_RESOURCES["hlf://agent/quickstart"]())
    fallback = quickstart["prompt_content_fallback"]

    assert fallback["prompt_name"] == "hlf_native_agent"
    assert fallback["resource_uri"] == "hlf://agent/quickstart"
    assert fallback["content_field"] == "prompt_content_fallback.prompt_text"
    assert "mandatory_internal_hlf_loop" in fallback["prompt_text"]
    assert prompt_text or fallback["prompt_text"]
    if prompt_text:
        assert "mandatory_internal_hlf_loop" in prompt_text
