"""Tripwire for guarded LiteLLM private-API imports.

Eight LiteLLM symbols are imported under ``try: ... except ImportError: X = None``
and only checked at call time. A LiteLLM bump that moves or deletes one of them
passes import and most of CI, then fails in production with
``RuntimeError: LiteLLM interface ... is unavailable; request isolation cannot
be guaranteed``.

LiteLLM's stability policy covers the proxy HTTP API, not these internals;
``litellm.utils.prompt_token_calculator`` was deleted in a minor bump (1.100.0).
This module fails CI the moment any guarded name binds to ``None``.

Does not change ``cloud_auth.py``, ``litellm_ai_handler.py``, or
``_require_litellm_interface``. See issue #3608.
"""
from pr_agent.algo.ai_handlers import cloud_auth
from pr_agent.algo.ai_handlers import litellm_ai_handler


def test_cloud_auth_guarded_imports_are_bound():
    assert cloud_auth.AnthropicModelInfo is not None, (
        "AnthropicModelInfo is None: cloud_auth cannot inspect Anthropic model "
        "metadata. Look at litellm.llms.anthropic.common_utils."
    )
    assert cloud_auth.JSONProviderRegistry is not None, (
        "JSONProviderRegistry is None: custom/openai-like provider lookup is "
        "unavailable. Look at litellm.llms.openai_like.json_loader."
    )
    assert cloud_auth._get_model_info_helper is not None, (
        "_get_model_info_helper is None: model-info resolution used for request "
        "isolation cannot run. Look at litellm.utils."
    )
    assert cloud_auth.BedrockMantleAuthMixin is not None, (
        "BedrockMantleAuthMixin is None: Bedrock Mantle request signing cannot "
        "be installed. Look at litellm.llms.bedrock_mantle.common_utils."
    )


def test_litellm_ai_handler_guarded_imports_are_bound():
    assert litellm_ai_handler.AnthropicModelInfo is not None, (
        "AnthropicModelInfo is None on the handler: Anthropic model metadata is "
        "unavailable. Look at litellm.llms.anthropic.common_utils."
    )
    assert litellm_ai_handler.JSONProviderRegistry is not None, (
        "JSONProviderRegistry is None on the handler: openai-like provider "
        "routing will raise at call time. Look at litellm.llms.openai_like.json_loader."
    )
    assert litellm_ai_handler._get_model_info_helper is not None, (
        "_get_model_info_helper is None on the handler: model-info resolution "
        "cannot guarantee request isolation. Look at litellm.utils."
    )
    assert litellm_ai_handler.BedrockMantleAuthMixin is not None, (
        "BedrockMantleAuthMixin is None on the handler: Bedrock Mantle signing "
        "is unavailable. Look at litellm.llms.bedrock_mantle.common_utils."
    )
    assert litellm_ai_handler.MANTLE_HOST_RE is not None, (
        "MANTLE_HOST_RE is None: Bedrock Mantle host matching cannot run. Look "
        "at litellm.llms.bedrock_mantle.common_utils."
    )
