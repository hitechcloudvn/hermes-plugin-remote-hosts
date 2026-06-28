# Remote Hosts

Standalone Hermes Agent plugin for using one long-lived Hermes gateway as an explicit SSH control plane for configured remote host aliases.

This is intentionally **not** a replacement for the built-in `terminal()` backend. The normal local terminal stays stable; the model must opt into remote execution by calling `remote_terminal(host=...)`, `remote_read_file(host=...)`, or `remote_write_file(host=...)` against a human-configured alias.

## Install

```bash
hermes plugins install donovan-yohan/hermes-plugin-remote-hosts --enable
```

Or, if already installed:

```bash
hermes plugins enable remote-hosts
```

Restart the Hermes gateway after changing plugin or `remote_hosts` config.

## Prerequisites

- Local `ssh` must be installed on the Hermes gateway host.
- Remote hosts must provide `python3` and `bash`.
- SSH key authentication must work non-interactively. The plugin runs SSH with `BatchMode=yes`.
- Host keys should already be present in local `known_hosts` when `strict_host_key_checking: true` is used, which is the default.

## Configure

Add host aliases to `config.yaml`:

```yaml
remote_hosts:
  hosts:
    desktop:
      host: desktop.example.com
      user: donovan
      port: 22
      identity_file: ~/.ssh/id_ed25519
      workdir: ~/Documents/Programs
      enabled: true
      connect_timeout: 10
      command_timeout: 120
      strict_host_key_checking: true
      allow_read: false
      allow_write: false
      allowed_roots:
        - ~/Documents/Programs
      workdir_only: false
```

Shorthand is also supported:

```yaml
remote_hosts:
  hosts:
    homelab: donovan@homelab
```

Disabled hosts are omitted:

```yaml
remote_hosts:
  hosts:
    old-box:
      enabled: false
      host: old-box.example.com
      user: donovan
```

## Tools

- `remote_hosts_list()` — lists enabled aliases without exposing `identity_file` or raw SSH options.
- `remote_terminal(host, command, workdir?, timeout?)` — runs a foreground command with remote `bash -lc`.
- `remote_read_file(host, path, offset?, limit?)` — reads text with line pagination using a remote `python3` helper; disabled unless the host has `allow_read: true`.
- `remote_write_file(host, path, content)` — atomically overwrites a text file using a remote `python3` helper; disabled unless the host has `allow_write: true`. Content above 200,000 characters is rejected before SSH.

Read and write tools also require either non-empty `allowed_roots` or `workdir_only: true`; unconstrained remote file access is rejected.

## Security model

- The model can only target configured aliases. It cannot provide arbitrary SSH destinations.
- Local SSH is invoked as an argv list with `shell=False`.
- SSH uses `BatchMode=yes`, `RequestTTY=no`, `ConnectTimeout`, `ServerAliveInterval`, `ServerAliveCountMax`, and `StrictHostKeyChecking=yes` by default.
- `user`, `host`, alias, port, timeouts, identity file paths, `workdir`, and `allowed_roots` are validated before use.
- `workdir` and `allowed_roots` must be non-root absolute remote paths or `~/...`-anchored remote paths such as `~/src`; relative paths, `/`, and bare `~` are rejected.
- `remote_terminal` runs Hermes' existing dangerous-command guard with SSH semantics before execution. If that guard cannot be imported or fails, remote command execution fails closed instead of running unguarded.
- `remote_read_file` and `remote_write_file` pass JSON over stdin/stdout; file contents are not shell-embedded.
- `allow_read` and `allow_write` default to `false`.
- `allowed_roots` restricts remote file read/write paths and is required for file tools unless `workdir_only: true` is set. It is a guardrail enforced by the helper, not an OS sandbox.
- `workdir_only: true` restricts file tools to the configured `workdir` and disables per-call terminal workdir overrides.
- `remote_write_file` preserves an existing target file's mode when replacing it. Other metadata such as owner, group, ACLs, extended attributes, and timestamps may change.
- Tool timeouts include SSH connection and helper execution. A per-call `remote_terminal(timeout=...)` can only lower the host's `command_timeout`, not raise it. Remote-side processes may continue if the SSH client is killed by a local timeout.

This plugin is a routing boundary, not a sandbox. Remote commands still have whatever permissions the SSH user has on the remote machine; avoid configuring high-privilege SSH accounts unless the operational risk is intentional.
