"""Seul module d'accès au LLM. Changer de fournisseur = réécrire GeminiLLM, rien d'autre.

Format neutre : Message (user / model / tool) → Step (texte ou appels d'outils).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import httpx
from google import genai
from google.genai import errors, types


class LLMError(Exception):
    pass


class LLMQuotaError(LLMError):
    """Limite du fournisseur atteinte (HTTP 429)."""


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict  # JSON Schema


@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict


@dataclass
class Message:
    role: Literal["user", "model", "tool"]
    text: str | None = None
    calls: list[ToolCall] = field(default_factory=list)
    results: list[tuple[str, dict]] = field(default_factory=list)
    raw: Any = None  # contenu natif du fournisseur, rejoué tel quel


@dataclass(frozen=True)
class Step:
    text: str | None
    calls: list[ToolCall]
    raw: Any


class LLM(Protocol):
    def step(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> Step: ...


class GeminiLLM:
    def __init__(
        self, api_key: str, model: str, thinking_level: str, client: Any = None, timeout_ms: int = 90_000
    ) -> None:
        self._client = client or genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=timeout_ms))
        self._model = model
        self._thinking = types.ThinkingLevel(thinking_level.upper())

    def step(self, system: str, messages: list[Message], tools: list[ToolSpec]) -> Step:
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name, description=t.description, parameters_json_schema=t.parameters
                        )
                        for t in tools
                    ]
                )
            ],
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking),
            # La boucle d'outils est à nous (sources contrôlées), pas au SDK.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client.models.generate_content(
                model=self._model, contents=[self._content(m) for m in messages], config=config
            )
        except errors.ClientError as e:
            if e.code == 429:
                raise LLMQuotaError(str(e)) from e
            raise LLMError(str(e)) from e
        except (errors.APIError, httpx.HTTPError) as e:
            raise LLMError(str(e)) from e
        calls = [ToolCall(c.name, dict(c.args or {})) for c in (response.function_calls or [])]
        raw = response.candidates[0].content if response.candidates else None
        return Step(text=None if calls else response.text, calls=calls, raw=raw)

    @staticmethod
    def _content(message: Message) -> types.Content:
        if message.raw is not None:
            # Gemini exige de renvoyer ses signatures de pensée : on rejoue son contenu natif.
            return message.raw
        if message.role == "user":
            return types.Content(role="user", parts=[types.Part.from_text(text=message.text or "")])
        if message.role == "tool":
            return types.Content(
                role="user",
                parts=[
                    types.Part.from_function_response(name=name, response=result) for name, result in message.results
                ],
            )
        parts = [types.Part.from_function_call(name=c.name, args=c.args) for c in message.calls]
        return types.Content(role="model", parts=parts or [types.Part.from_text(text=message.text or "")])
