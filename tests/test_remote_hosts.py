from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture()
def remote_hosts_module():
    module_path = Path(__file__).resolve().parents[1] / "__init__.py"
    spec = importlib.util.spec_from_file_location("remote_hosts_plugin_under_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _host(module, **overrides):
    values = {
        "alias": "box",
        "host": "box.example.com",
        "user": "donovan",
        "allowed_roots": ["/srv/project"],
    }
    values.update(overrides)
    return module.HostConfig(**values)


def _payload(result: str) -> dict:
    return json.loads(result)


def test_parse_host_defaults_and_safe_remote_paths(remote_hosts_module):
    host = remote_hosts_module._parse_host(
        "box",
        {
            "host": "box.example.com",
            "user": "donovan",
            "workdir": "~/src",
            "allowed_roots": ["~/src", "/opt/project"],
        },
    )

    assert host.allow_read is False
    assert host.allow_write is False
    assert host.workdir == "~/src"
    assert host.allowed_roots == ["~/src", "/opt/project"]


def test_parse_host_rejects_root_config_paths(remote_hosts_module):
    with pytest.raises(ValueError, match="host box: workdir.*filesystem root"):
        remote_hosts_module._parse_host(
            "box",
            {"host": "box.example.com", "user": "donovan", "workdir": "/"},
        )

    with pytest.raises(ValueError, match="host box: workdir.*filesystem root"):
        remote_hosts_module._parse_host(
            "box",
            {"host": "box.example.com", "user": "donovan", "workdir": "//"},
        )

    with pytest.raises(ValueError, match="host box: allowed_roots entries.*filesystem root"):
        remote_hosts_module._parse_host(
            "box",
            {
                "host": "box.example.com",
                "user": "donovan",
                "allowed_roots": ["~"],
            },
        )

    with pytest.raises(ValueError, match="host box: allowed_roots entries.*filesystem root"):
        remote_hosts_module._parse_host(
            "box",
            {
                "host": "box.example.com",
                "user": "donovan",
                "allowed_roots": ["~/.."],
            },
        )


def test_parse_host_rejects_relative_config_paths(remote_hosts_module):
    with pytest.raises(ValueError, match="host box: workdir.*absolute or ~-anchored"):
        remote_hosts_module._parse_host(
            "box",
            {"host": "box.example.com", "user": "donovan", "workdir": "relative/path"},
        )

    with pytest.raises(ValueError, match="host box: allowed_roots entries.*absolute or ~-anchored"):
        remote_hosts_module._parse_host(
            "box",
            {
                "host": "box.example.com",
                "user": "donovan",
                "allowed_roots": ["src"],
            },
        )


def test_parse_host_omits_disabled_hosts(remote_hosts_module):
    assert remote_hosts_module._parse_host(
        "old-box",
        {"enabled": False, "host": "old.example.com", "user": "donovan"},
    ) is None


def test_read_file_requires_allow_read_and_constrained_access(remote_hosts_module, monkeypatch):
    calls = []
    monkeypatch.setattr(
        remote_hosts_module,
        "_run_remote_python",
        lambda *args, **kwargs: calls.append(args) or None,
    )

    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, allow_read=False)},
    )
    result = _payload(remote_hosts_module.remote_read_file({"host": "box", "path": "/srv/project/a.txt"}))
    assert result["success"] is False
    assert "disabled" in result["error"]
    assert calls == []

    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, allow_read=True, allowed_roots=[])},
    )
    result = _payload(remote_hosts_module.remote_read_file({"host": "box", "path": "/srv/project/a.txt"}))
    assert result["success"] is False
    assert "allowed_roots or workdir_only" in result["error"]
    assert calls == []


def test_write_file_requires_allow_write_and_constrained_access(remote_hosts_module, monkeypatch):
    calls = []
    monkeypatch.setattr(
        remote_hosts_module,
        "_run_remote_python",
        lambda *args, **kwargs: calls.append(args) or None,
    )

    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, allow_write=False)},
    )
    result = _payload(
        remote_hosts_module.remote_write_file({"host": "box", "path": "/srv/project/a.txt", "content": "x"})
    )
    assert result["success"] is False
    assert "disabled" in result["error"]

    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, allow_write=True, allowed_roots=[])},
    )
    result = _payload(
        remote_hosts_module.remote_write_file({"host": "box", "path": "/srv/project/a.txt", "content": "x"})
    )
    assert result["success"] is False
    assert "allowed_roots or workdir_only" in result["error"]
    assert calls == []


def test_write_file_rejects_oversized_content_before_ssh(remote_hosts_module, monkeypatch):
    calls = []
    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, allow_write=True)},
    )
    monkeypatch.setattr(
        remote_hosts_module,
        "_run_remote_python",
        lambda *args, **kwargs: calls.append(args) or None,
    )

    result = _payload(
        remote_hosts_module.remote_write_file(
            {
                "host": "box",
                "path": "/srv/project/a.txt",
                "content": "x" * (remote_hosts_module.MAX_WRITE_CHARS + 1),
            }
        )
    )

    assert result["success"] is False
    assert "exceeds remote_write_file limit" in result["error"]
    assert calls == []


def test_read_and_write_call_remote_helper_with_expected_payload(remote_hosts_module, monkeypatch):
    calls = []

    def fake_run(host, helper, payload, timeout):
        calls.append((host, helper, payload, timeout))
        if "content" in payload:
            stdout = json.dumps({"path": "/srv/project/a.txt", "bytes": 5})
        else:
            stdout = json.dumps(
                {
                    "path": "/srv/project/a.txt",
                    "offset": 1,
                    "limit": 200,
                    "total_lines": 1,
                    "content": "hello",
                    "truncated": False,
                }
            )
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {
            "box": _host(
                remote_hosts_module,
                allow_read=True,
                allow_write=True,
                command_timeout=9,
                connect_timeout=2,
            )
        },
    )
    monkeypatch.setattr(remote_hosts_module, "_run_remote_python", fake_run)

    read_result = _payload(remote_hosts_module.remote_read_file({"host": "box", "path": "/srv/project/a.txt"}))
    write_result = _payload(
        remote_hosts_module.remote_write_file({"host": "box", "path": "/srv/project/a.txt", "content": "hello"})
    )

    assert read_result["success"] is True
    assert write_result["success"] is True
    assert calls[0][2]["allowed_roots"] == ["/srv/project"]
    assert calls[0][2]["workdir_only"] is False
    assert calls[0][3] == 11
    assert calls[1][2]["content"] == "hello"


def test_ssh_argv_shape(remote_hosts_module):
    host = _host(
        remote_hosts_module,
        port=2222,
        identity_file="/tmp/id_ed25519",
        strict_host_key_checking=False,
    )

    argv = remote_hosts_module._ssh_argv(host, "python3 -c 'print(1)'")

    assert argv[0] == "ssh"
    assert "shell=True" not in argv
    assert ["-p", "2222"] == argv[argv.index("-p") : argv.index("-p") + 2]
    assert ["-i", "/tmp/id_ed25519"] == argv[argv.index("-i") : argv.index("-i") + 2]
    assert "StrictHostKeyChecking=no" in argv
    assert "--" in argv
    assert argv[-2] == "donovan@box.example.com"
    assert argv[-1] == "python3 -c 'print(1)'"


def test_command_guard_fails_closed_when_unavailable(remote_hosts_module, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "tools.terminal_tool":
            raise ImportError("missing guard")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result = remote_hosts_module._check_command_allowed("rm -rf /", _host(remote_hosts_module))

    assert result["approved"] is False
    assert "Remote command guard unavailable" in result["message"]


def test_remote_terminal_rejects_relative_workdir_override(remote_hosts_module, monkeypatch):
    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {"box": _host(remote_hosts_module, command_timeout=20, connect_timeout=3)},
    )
    monkeypatch.setattr(
        remote_hosts_module,
        "_check_command_allowed",
        lambda command, host: {"approved": True},
    )
    monkeypatch.setattr(
        remote_hosts_module,
        "_run_remote_python",
        lambda *args, **kwargs: pytest.fail("ssh should not be called"),
    )

    result = _payload(
        remote_hosts_module.remote_terminal(
            {"host": "box", "command": "pwd", "workdir": "relative/path"}
        )
    )

    assert result["success"] is False
    assert "workdir override" in result["error"]
    assert "absolute or ~-anchored" in result["error"]


def test_remote_terminal_uses_guard_and_clamps_timeout(remote_hosts_module, monkeypatch):
    calls = {}
    host = _host(remote_hosts_module, command_timeout=20, connect_timeout=3)
    monkeypatch.setattr(remote_hosts_module, "_load_hosts", lambda: {"box": host})
    monkeypatch.setattr(
        remote_hosts_module,
        "_check_command_allowed",
        lambda command, host: {"approved": True},
    )

    def fake_run(host, helper, payload, timeout):
        calls["payload"] = payload
        calls["timeout"] = timeout
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps({"stdout": "ok", "stderr": "", "exit_code": 0, "truncated": False}),
            stderr="",
        )

    monkeypatch.setattr(remote_hosts_module, "_run_remote_python", fake_run)

    result = _payload(
        remote_hosts_module.remote_terminal({"host": "box", "command": "pwd", "timeout": 99})
    )

    assert result["success"] is True
    assert calls["payload"]["command"] == "pwd"
    assert calls["timeout"] == 28


def test_remote_hosts_list_reports_enabled_hosts_without_private_identity(remote_hosts_module, monkeypatch):
    monkeypatch.setattr(
        remote_hosts_module,
        "_load_hosts",
        lambda: {
            "box": _host(
                remote_hosts_module,
                identity_file="/tmp/private-key",
                allow_read=True,
                allow_write=True,
            )
        },
    )

    result = _payload(remote_hosts_module.remote_hosts_list({}))

    assert result["success"] is True
    assert result["hosts"][0]["allow_read"] is True
    assert result["hosts"][0]["allow_write"] is True
    assert "identity_file" not in result["hosts"][0]


def test_registers_expected_tools_with_fake_context(remote_hosts_module):
    class FakeCtx:
        def __init__(self):
            self.tools = []

        def register_tool(self, **kwargs):
            self.tools.append(kwargs)

    ctx = FakeCtx()

    remote_hosts_module.register(ctx)

    names = [tool["name"] for tool in ctx.tools]
    assert names == [
        "remote_hosts_list",
        "remote_terminal",
        "remote_read_file",
        "remote_write_file",
    ]
    schemas = {tool["name"]: tool["schema"] for tool in ctx.tools}
    assert "allow_read=true" in schemas["remote_read_file"]["description"]
    assert str(remote_hosts_module.MAX_WRITE_CHARS) in schemas["remote_write_file"]["description"]


def test_write_helper_preserves_existing_file_mode(remote_hosts_module, tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("old", encoding="utf-8")
    os.chmod(target, 0o640)
    # Windows does not enforce POSIX modes; assert whatever mode exists is preserved.
    expected_mode = stat.S_IMODE(target.stat().st_mode)

    proc = subprocess.run(
        [sys.executable, "-c", remote_hosts_module.WRITE_HELPER],
        input=json.dumps(
            {
                "path": str(target),
                "content": "new",
                "allowed_roots": [str(tmp_path)],
                "workdir_only": False,
                "workdir": str(tmp_path),
            }
        ),
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    assert target.read_text(encoding="utf-8") == "new"
    assert stat.S_IMODE(target.stat().st_mode) == expected_mode
