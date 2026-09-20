"""Blank qdrant.url from the secrets template must be treated as unset (#3546)."""
import inspect

import pr_agent.tools.pr_similar_issue as psi


def test_qdrant_block_rejects_blank_url_before_client_init():
    source = inspect.getsource(psi.PRSimilarIssue.__init__)
    qdrant_block = source.split('elif get_settings().pr_similar_issue.vectordb == "qdrant":', 1)[1]
    client_init = qdrant_block.split("self.qdrant = qdrant_client.QdrantClient", 1)[0]
    assert 'if not (url or "").strip():' in client_init
    assert 'Please set qdrant url and api key in secrets file' in client_init


def test_blank_api_key_is_not_required_by_the_url_guard():
    """Self-hosted Qdrant without auth is valid; only url emptiness is checked."""
    source = inspect.getsource(psi.PRSimilarIssue.__init__)
    qdrant_block = source.split('elif get_settings().pr_similar_issue.vectordb == "qdrant":', 1)[1]
    client_init = qdrant_block.split("self.qdrant = qdrant_client.QdrantClient", 1)[0]
    assert "if not (api_key" not in client_init
    assert 'if not (url or "").strip():' in client_init
