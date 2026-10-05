import io
from types import SimpleNamespace

from pr_agent import cli
from pr_agent.config_loader import get_settings
from pr_agent.servers import utils as server_utils


class _Log:
    def __init__(self):
        self.infos = []

    def info(self, message, *args, **kwargs):
        self.infos.append(message)

    def warning(self, message, *args, **kwargs):
        self.infos.append(message)

    def debug(self, message, *args, **kwargs):
        return None

    def exception(self, message, *args, **kwargs):
        return None


def _provider(*, source="feature", target="main", title="Add feature", labels=None, author="alice", repo="org/repo"):
    return SimpleNamespace(
        get_title=lambda: title,
        get_pr_branch=lambda: source,
        get_pr_labels=lambda: list(labels or []),
        repo=repo,
        pr=SimpleNamespace(
            user=SimpleNamespace(login=author),
            base=SimpleNamespace(ref=target),
        ),
    )


def _run(monkeypatch, provider, command_ran, log):
    async def fake_handle_request(*_args, **_kwargs):
        command_ran.append(True)
        return True

    monkeypatch.setattr(cli, "inject_artifact_context", lambda: None)
    monkeypatch.setattr(cli, "litellm_callbacks_registered", lambda: False)
    monkeypatch.setattr(cli, "PRAgent", lambda: SimpleNamespace(handle_request=fake_handle_request))
    monkeypatch.setattr(server_utils, "get_logger", lambda: log)

    import pr_agent.git_providers as providers
    import pr_agent.git_providers.utils as provider_utils

    monkeypatch.setattr(provider_utils, "apply_repo_settings", lambda _url: None)
    monkeypatch.setattr(providers, "get_git_provider_with_context", lambda _url: provider)

    return cli.run(inargs=["--pr_url=https://github.com/org/repo/pull/1", "review"])


def test_cli_skips_matching_source_branch(monkeypatch):
    get_settings().set("CONFIG.IGNORE_PR_SOURCE_BRANCHES", ["^renovate/"])
    command_ran = []
    log = _Log()
    status = _run(monkeypatch, _provider(source="renovate/lockfile"), command_ran, log)
    assert status == 0
    assert command_ran == []
    assert any("ignore_pr_source_branches" in message for message in log.infos)
    get_settings().set("CONFIG.IGNORE_PR_SOURCE_BRANCHES", [])


def test_cli_runs_non_matching_source_branch(monkeypatch):
    get_settings().set("CONFIG.IGNORE_PR_SOURCE_BRANCHES", ["^renovate/"])
    command_ran = []
    status = _run(monkeypatch, _provider(source="feature/widget"), command_ran, _Log())
    assert status is None
    assert command_ran == [True]
    get_settings().set("CONFIG.IGNORE_PR_SOURCE_BRANCHES", [])


def test_cli_skips_matching_label(monkeypatch):
    get_settings().set("CONFIG.IGNORE_PR_LABELS", ["do-not-merge"])
    command_ran = []
    log = _Log()
    status = _run(monkeypatch, _provider(labels=["do-not-merge", "bug"]), command_ran, log)
    assert status == 0
    assert command_ran == []
    assert any("ignore_pr_labels" in message for message in log.infos)
    get_settings().set("CONFIG.IGNORE_PR_LABELS", [])


def test_cli_skips_matching_title(monkeypatch):
    original = get_settings().get("CONFIG.IGNORE_PR_TITLE", [])
    get_settings().set("CONFIG.IGNORE_PR_TITLE", [r"^\\[Auto\\]"])
    command_ran = []
    log = _Log()
    status = _run(monkeypatch, _provider(title="[Auto] bump deps"), command_ran, log)
    assert status == 0
    assert command_ran == []
    assert any("ignore_pr_title" in message for message in log.infos)
    get_settings().set("CONFIG.IGNORE_PR_TITLE", original)


def test_cli_ignore_uses_pr_author(monkeypatch):
    get_settings().set("CONFIG.IGNORE_PR_AUTHORS", ["^renovate"])
    command_ran = []
    log = _Log()
    status = _run(monkeypatch, _provider(author="renovate[bot]"), command_ran, log)
    assert status == 0
    assert command_ran == []
    assert any("ignore_pr_authors" in message for message in log.infos)
    get_settings().set("CONFIG.IGNORE_PR_AUTHORS", [])


def test_plain_diff_does_not_evaluate_ignore_rules(monkeypatch):
    called = []

    def fail_if_called(_url):
        called.append(True)
        return False

    monkeypatch.setattr(cli, "_cli_should_process_pr", fail_if_called)
    monkeypatch.setattr(cli, "inject_artifact_context", lambda: None)
    monkeypatch.setattr(cli, "litellm_callbacks_registered", lambda: False)

    async def fake_handle_request(*_args, **_kwargs):
        return True

    monkeypatch.setattr(cli, "PRAgent", lambda: SimpleNamespace(handle_request=fake_handle_request))
    monkeypatch.setattr("sys.stdin", io.StringIO("diff --git a/a b/a\n"))
    status = cli.run(inargs=["--stdin", "review"])
    assert called == []
    assert status is None
