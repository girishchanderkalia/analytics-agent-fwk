"""Provider request and response mapping for the Model Gateway."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from bootstrap.model_gateway_adapter import (
    ModelGatewayResponseError,
)



def build_structured_request(
    *,
    model: str,
    system_prompt: str,
    input_text: str,
    output_schema: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the provider-neutral structured completion envelope."""

    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_text},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "agent_output",
                "strict": True,
                "schema": dict(output_schema),
            },
        },
    }


def parse_structured_response(response: Mapping[str, Any]) -> dict[str, Any]:
    """Parse structured output from supported gateway response envelopes."""

    direct = response.get("structured_output")
    if isinstance(direct, Mapping):
        return dict(direct)

    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, Mapping):
            message = first.get("message")
            if isinstance(message, Mapping):
                parsed = message.get("parsed")
                if isinstance(parsed, Mapping):
                    return dict(parsed)

                content = message.get("content")
                if isinstance(content, str):
                    try:
                        result = json.loads(content)
                    except json.JSONDecodeError as exc:
                        raise ModelGatewayResponseError(
                            "Model response content is not valid JSON"
                        ) from exc
                    if isinstance(result, dict):
                        return result

    raise ModelGatewayResponseError(
        "Model response does not contain structured output"
    )
