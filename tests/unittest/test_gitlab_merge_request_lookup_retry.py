from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from gitlab import GitlabGetError

from pr_agent.git_providers.gitlab_provider import GitLabProvider


def _provider():
    provider = GitLabProvider.__new__(GitLabProvider)
    provider.id_project = "group/project"
    provider.id_mr = 39
    provider.gl = MagicMock()
    return provider


def test_set_merge_request_retries_initial_404_then_loads_diff():
    provider = _provider()
    provider._parse_merge_request_url = MagicMock(return_value=("group/project", 39))
    missing = GitlabGetError("404 Not found", response_code=404)
    merge_request = SimpleNamespace(diffs=MagicMock())
    merge_request.diffs.list.return_value = [SimpleNamespace(id=1)]
    provider._get_merge_request = MagicMock(side_effect=[missing, missing, merge_request])

    with patch("pr_agent.git_providers.gitlab_provider.time.sleep") as sleep:
        provider._set_merge_request("https://gitlab.example.com/group/project/-/merge_requests/39")

    assert provider.mr is merge_request
    assert provider._get_merge_request.call_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2]
    merge_request.diffs.list.assert_called_once_with(page=1, per_page=1, get_all=False)


def test_set_merge_request_does_not_retry_non_404():
    provider = _provider()
    provider._parse_merge_request_url = MagicMock(return_value=("group/project", 39))
    provider._get_merge_request = MagicMock(side_effect=GitlabGetError("403 Forbidden", response_code=403))

    with patch("pr_agent.git_providers.gitlab_provider.time.sleep") as sleep:
        with pytest.raises(GitlabGetError, match="403"):
            provider._set_merge_request("https://gitlab.example.com/group/project/-/merge_requests/39")

    sleep.assert_not_called()
    assert provider._get_merge_request.call_count == 1


def test_initial_lookup_raises_after_retrying_persistent_404():
    provider = _provider()
    provider._get_merge_request = MagicMock(side_effect=GitlabGetError("404 Not found", response_code=404))

    with patch("pr_agent.git_providers.gitlab_provider.time.sleep") as sleep:
        with pytest.raises(GitlabGetError, match="404"):
            provider._get_merge_request_retrying_not_found()

    assert provider._get_merge_request.call_count == 4
    assert [call.args[0] for call in sleep.call_args_list] == [1, 2, 4]
