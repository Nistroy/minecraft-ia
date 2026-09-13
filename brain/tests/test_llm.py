import pytest
from google.genai import errors, types

from minecraft_ia.llm import GeminiLLM, LLMError, LLMQuotaError, Message, ToolCall, ToolSpec

SPEC = ToolSpec("search_knowledge", "Cherche", {"type": "object", "properties": {"query": {"type": "string"}}})


class FakeModels:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append((model, contents, config))
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class FakeClient:
    def __init__(self, result):
        self.models = FakeModels(result)


def response(*parts):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


def test_function_call_step_and_request_shape():
    client = FakeClient(response(types.Part.from_function_call(name="search_knowledge", args={"query": "aether"})))
    llm = GeminiLLM(api_key="k", model="gemini-3.8-flash", thinking_level="high", client=client)
    step = llm.step("système", [Message("user", text="comment aller dans l'aether ?")], [SPEC])
    assert step.calls == [ToolCall("search_knowledge", {"query": "aether"})]
    assert step.text is None
    model, contents, config = client.models.calls[0]
    assert model == "gemini-3.8-flash"
    assert contents[0].role == "user" and contents[0].parts[0].text == "comment aller dans l'aether ?"
    assert config.system_instruction == "système"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.HIGH
    assert config.automatic_function_calling.disable is True
    assert config.tools[0].function_declarations[0].name == "search_knowledge"


def test_history_replays_model_content_and_tool_results():
    raw = types.Content(role="model", parts=[types.Part.from_function_call(name="search_knowledge", args={})])
    client = FakeClient(response(types.Part.from_text(text="fini")))
    llm = GeminiLLM(api_key="k", model="m", thinking_level="low", client=client)
    step = llm.step(
        "s",
        [
            Message("user", text="q"),
            Message("model", raw=raw),
            Message("tool", results=[("search_knowledge", {"results": []})]),
        ],
        [SPEC],
    )
    assert step.text == "fini" and step.calls == []
    contents = client.models.calls[0][1]
    assert contents[1] is raw  # signatures de pensée conservées
    assert contents[2].parts[0].function_response.name == "search_knowledge"


def test_quota_and_other_errors_are_mapped():
    quota = errors.ClientError(429, {"error": {"code": 429, "message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    with pytest.raises(LLMQuotaError):
        GeminiLLM(api_key="k", model="m", thinking_level="low", client=FakeClient(quota)).step("s", [], [SPEC])
    server = errors.ServerError(503, {"error": {"code": 503, "message": "down", "status": "UNAVAILABLE"}})
    with pytest.raises(LLMError):
        GeminiLLM(api_key="k", model="m", thinking_level="low", client=FakeClient(server)).step("s", [], [SPEC])
