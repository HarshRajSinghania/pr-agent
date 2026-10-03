"""Bedrock application inference profiles are per model, not per handler.

LiteLLM substitutes model_id for the model name when it builds the Bedrock
Runtime URL, so a profile configured for the primary model must not be sent
with a fallback model.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import pr_agent.algo.ai_handlers.litellm_ai_handler as litellm_handler

PRIMARY = "bedrock/anthropic.claude-sonnet-4-5"
FALLBACK = "bedrock/qwen.qwen3-235b-a22b-2507-v1:0"
PRIMARY_ARN = "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/primary"
FALLBACK_ARN = "arn:aws:bedrock:us-east-1:123456789012:application-inference-profile/fallback"


class FakeBox:
    def __init__(self, values=None, **attrs):
        self._values = values or {}
        for key, value in attrs.items():
            setattr(self, key, value)

    def get(self, key, default=None):
        return self._values.get(key, default)


class FakeSettings:
    def __init__(self, config_model, settings_values):
        self.config = FakeBox(
            reasoning_effort=None,
            ai_timeout=30,
            custom_reasoning_model=False,
            max_model_tokens=32000,
            verbosity_level=0,
            model=config_model,
        )
        self.litellm = FakeBox()
        self._settings_values = {
            "aws.AWS_ACCESS_KEY_ID": "test-access-key",
            "aws.AWS_SECRET_ACCESS_KEY": "test-secret-key",
            "aws.AWS_REGION_NAME": "us-east-1",
            **settings_values,
        }

    def get(self, key, default=None):
        return self._settings_values.get(key, default)


def _mock_response():
    mock = MagicMock()
    response = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    mock.__getitem__.side_effect = response.__getitem__
    mock.dict.return_value = response
    mock.usage = None
    return mock


async def _complete(monkeypatch, settings, model):
    monkeypatch.setattr(litellm_handler, "get_settings", lambda: settings)
    with patch(
        "pr_agent.algo.ai_handlers.litellm_ai_handler.acompletion",
        new_callable=AsyncMock,
    ) as mock_call:
        mock_call.return_value = _mock_response()
        handler = litellm_handler.LiteLLMAIHandler()
        await handler.chat_completion(model=model, system="sys", user="usr")
    return mock_call.call_args.kwargs


@pytest.mark.asyncio
async def test_scalar_model_id_is_sent_only_for_the_configured_model(monkeypatch):
    settings = FakeSettings(PRIMARY, {"litellm.model_id": PRIMARY_ARN})

    primary_kwargs = await _complete(monkeypatch, settings, PRIMARY)
    fallback_kwargs = await _complete(monkeypatch, settings, FALLBACK)

    assert primary_kwargs["model_id"] == PRIMARY_ARN
    assert "model_id" not in fallback_kwargs


@pytest.mark.asyncio
async def test_model_ids_mapping_assigns_each_model_its_own_profile(monkeypatch):
    settings = FakeSettings(
        PRIMARY,
        {
            "litellm.model_id": PRIMARY_ARN,
            "litellm.model_ids": {FALLBACK: FALLBACK_ARN, PRIMARY: "arn-from-map"},
        },
    )

    primary_kwargs = await _complete(monkeypatch, settings, PRIMARY)
    fallback_kwargs = await _complete(monkeypatch, settings, FALLBACK)

    # An explicit mapping entry wins over the scalar profile.
    assert primary_kwargs["model_id"] == "arn-from-map"
    assert fallback_kwargs["model_id"] == FALLBACK_ARN


@pytest.mark.asyncio
async def test_probe_does_not_attach_primary_profile_to_a_fallback_model(monkeypatch):
    settings = FakeSettings(PRIMARY, {"litellm.model_id": PRIMARY_ARN})
    monkeypatch.setattr(litellm_handler, "get_settings", lambda: settings)
    handler = litellm_handler.LiteLLMAIHandler()
    completion = AsyncMock(return_value=_mock_response())

    await handler.probe_completion(FALLBACK, _completion=completion)

    assert "model_id" not in completion.call_args.kwargs
