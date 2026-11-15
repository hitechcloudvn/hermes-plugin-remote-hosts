<div align="center">

# hermes-plugin-remote-hosts

**Plugin Hermes Agent: cổng điều khiển SSH tường minh cho các máy chủ từ xa đã cấu hình**

**Hermes Agent plugin: explicit SSH control plane for configured remote host aliases**

[![CI](https://github.com/hitechcloudvn/hermes-plugin-remote-hosts/actions/workflows/ci.yml/badge.svg)](https://github.com/hitechcloudvn/hermes-plugin-remote-hosts/actions/workflows/ci.yml)
[![Release](https://github.com/hitechcloudvn/hermes-plugin-remote-hosts/actions/workflows/release.yml/badge.svg)](https://github.com/hitechcloudvn/hermes-plugin-remote-hosts/actions/workflows/release.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Made in Vietnam](https://img.shields.io/badge/Made%20in-Vietnam-DA251D?style=flat-square)](https://hitechcloud.vn)

**Tiếng Việt** | **English**

[GitHub](https://github.com/hitechcloudvn/hermes-plugin-remote-hosts) · [GitLab](https://gitlab.com/hitechcloudvn/hermes-plugin-remote-hosts)

</div>

---

## 🇻🇳 Tiếng Việt

### Giới thiệu

`hermes-plugin-remote-hosts` là [plugin cho Hermes Agent](https://hermes-agent.nousresearch.com) độc lập, dùng một cổng Hermes sống lâu (long-lived gateway) làm cổng điều khiển SSH tường minh cho các bí danh máy chủ từ xa đã cấu hình.

Plugin này cố ý **không** thay thế backend `terminal()` có sẵn. Terminal cục bộ vẫn ổn định; mô hình phải chủ động thực thi từ xa bằng cách gọi `remote_terminal(host=...)`, `remote_read_file(host=...)` hoặc `remote_write_file(host=...)` nhắm vào một bí danh do con người cấu hình.

### Tính năng

- **Thực thi từ xa tường minh** — mọi thao tác SSH chỉ nhắm vào bí danh đã cấu hình; mô hình không thể tự đặt đích SSH tùy ý
- **Bốn công cụ** — `remote_hosts_list`, `remote_terminal`, `remote_read_file`, `remote_write_file`
- **Đọc/ghi tệp có kiểm soát** — `allow_read` / `allow_write` mặc định tắt; cần `allowed_roots` khác rỗng hoặc `workdir_only: true`
- **Ghi tệp nguyên tử** — ghi đè tệp văn bản bằng helper `python3` từ xa, truyền JSON qua stdin/stdout; giữ nguyên quyền (mode) của tệp cũ
- **Chống lệnh nguy hiểm** — `remote_terminal` chạy guard lệnh nguy hiểm sẵn có của Hermes với ngữ cảnh SSH; fail-closed nếu guard không sẵn sàng
- **Kiểm tra nghiêm ngặt** — bí danh, `user`, `host`, cổng, timeout, đường dẫn `workdir`/`allowed_roots` đều được kiểm tra hợp lệ trước khi dùng

### Cài đặt

1. Cài plugin qua Hermes CLI:
   ```bash
   hermes plugins install hitechcloudvn/hermes-plugin-remote-hosts --enable
   ```
   Hoặc, nếu đã cài sẵn:
   ```bash
   hermes plugins enable remote-hosts
   ```
   Hoặc clone thủ công vào thư mục plugin của Hermes:
   ```bash
   git clone https://github.com/hitechcloudvn/hermes-plugin-remote-hosts.git ~/.hermes/plugins/hermes-plugin-remote-hosts
   ```
2. Khởi động lại tiến trình gateway của Hermes sau khi đổi cấu hình plugin hoặc `remote_hosts`.

### Yêu cầu

- `ssh` phải được cài trên máy chạy cổng Hermes.
- Máy chủ từ xa phải có `python3` và `bash`.
- Xác thực bằng khóa SSH phải hoạt động không tương tác. Plugin chạy SSH với `BatchMode=yes`.
- Khóa máy chủ (host key) nên đã có trong `known_hosts` cục bộ khi dùng `strict_host_key_checking: true` — đây là mặc định.

### Cấu hình

Thêm bí danh máy chủ vào `config.yaml`:

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

Cũng hỗ trợ dạng viết tắt:

```yaml
remote_hosts:
  hosts:
    homelab: donovan@homelab
```

Máy chủ bị tắt sẽ được bỏ qua:

```yaml
remote_hosts:
  hosts:
    old-box:
      enabled: false
      host: old-box.example.com
      user: donovan
```

### Sử dụng

- `remote_hosts_list()` — liệt kê các bí danh đã bật, không lộ `identity_file` hay tuỳ chọn SSH thô.
- `remote_terminal(host, command, workdir?, timeout?)` — chạy lệnh tiền cảnh bằng `bash -lc` từ xa.
- `remote_read_file(host, path, offset?, limit?)` — đọc văn bản có phân trang theo dòng bằng helper `python3` từ xa; bị tắt trừ khi host có `allow_read: true`.
- `remote_write_file(host, path, content)` — ghi đè nguyên tử tệp văn bản bằng helper `python3` từ xa; bị tắt trừ khi host có `allow_write: true`. Nội dung lớn hơn 200.000 ký tự bị từ chối trước khi chạy SSH.

Công cụ đọc và ghi cũng yêu cầu `allowed_roots` khác rỗng hoặc `workdir_only: true`; truy cập tệp từ xa không bị ràng buộc sẽ bị từ chối.

### Bảo mật

- Mô hình chỉ có thể nhắm vào các bí danh đã cấu hình. Không thể cung cấp đích SSH tùy ý.
- SSH cục bộ được gọi dưới dạng danh sách argv với `shell=False`.
- SSH dùng `BatchMode=yes`, `RequestTTY=no`, `ConnectTimeout`, `ServerAliveInterval`, `ServerAliveCountMax`, và `StrictHostKeyChecking=yes` theo mặc định.
- `user`, `host`, bí danh, cổng, timeout, đường dẫn identity file, `workdir` và `allowed_roots` được kiểm tra hợp lệ trước khi dùng.
- `workdir` và `allowed_roots` phải là đường dẫn từ xa tuyệt đối không phải gốc, hoặc neo theo `~/...` như `~/src`; đường dẫn tương đối, `/` và `~` trần bị từ chối.
- `remote_terminal` chạy guard lệnh nguy hiểm sẵn có của Hermes với ngữ cảnh SSH trước khi thực thi. Nếu guard đó không import được hoặc gặp lỗi, lệnh từ xa fail-closed thay vì chạy không có bảo vệ.
- `remote_read_file` và `remote_write_file` truyền JSON qua stdin/stdout; nội dung tệp không bị nhúng vào shell.
- `allow_read` và `allow_write` mặc định là `false`.
- `allowed_roots` giới hạn đường dẫn đọc/ghi tệp từ xa và là bắt buộc với công cụ tệp trừ khi đặt `workdir_only: true`. Đây là cơ chế phòng vệ do helper thực thi, không phải sandbox của hệ điều hành.
- `workdir_only: true` giới hạn công cụ tệp trong `workdir` đã cấu hình và tắt ghi đè workdir theo từng lời gọi.
- `remote_write_file` giữ nguyên quyền (mode) của tệp đích hiện có khi thay thế. Siêu dữ liệu khác như chủ sở hữu, nhóm, ACL, thuộc tính mở rộng và mốc thời gian có thể thay đổi.
- Timeout của công cụ bao gồm cả thời gian kết nối SSH và thực thi helper. `remote_terminal(timeout=...)` theo từng lời gọi chỉ có thể hạ `command_timeout` của host, không thể nâng lên. Tiến trình phía máy chủ từ xa có thể tiếp tục chạy nếu tiến trình SSH cục bộ bị kết thúc bởi timeout cục bộ.

Plugin này là ranh giới định tuyến, không phải sandbox. Lệnh từ xa vẫn có mọi quyền mà người dùng SSH có trên máy từ xa; tránh cấu hình tài khoản SSH đặc quyền cao trừ khi chấp nhận rủi ro vận hành một cách có chủ đích.

### Kiểm thử

Cài `pytest` và chạy bộ kiểm thử:

```bash
pip install pytest
python -m pytest -q
```

### Giấy phép

MIT — xem [LICENSE](LICENSE). © 2026 HiTechCloud.VN.

---

## 🇬🇧 English

### Overview

`hermes-plugin-remote-hosts` is a standalone [Hermes Agent](https://hermes-agent.nousresearch.com) plugin that uses one long-lived Hermes gateway as an explicit SSH control plane for configured remote host aliases.

This is intentionally **not** a replacement for the built-in `terminal()` backend. The normal local terminal stays stable; the model must opt into remote execution by calling `remote_terminal(host=...)`, `remote_read_file(host=...)`, or `remote_write_file(host=...)` against a human-configured alias.

### Features

- **Explicit remote execution** — every SSH operation targets a configured alias; the model cannot provide arbitrary SSH destinations
- **Four tools** — `remote_hosts_list`, `remote_terminal`, `remote_read_file`, `remote_write_file`
- **Constrained file access** — `allow_read` / `allow_write` default to off; non-empty `allowed_roots` or `workdir_only: true` is required
- **Atomic file writes** — overwrites text files through a remote `python3` helper with JSON over stdin/stdout; preserves the existing file's mode
- **Dangerous-command guard** — `remote_terminal` runs Hermes' existing dangerous-command guard with SSH semantics and fails closed when the guard is unavailable
- **Strict validation** — alias, `user`, `host`, port, timeouts, and `workdir`/`allowed_roots` paths are all validated before use

### Installation

1. Install the plugin via the Hermes CLI:
   ```bash
   hermes plugins install hitechcloudvn/hermes-plugin-remote-hosts --enable
   ```
   Or, if already installed:
   ```bash
   hermes plugins enable remote-hosts
   ```
   Or clone it manually into your Hermes plugins directory:
   ```bash
   git clone https://github.com/hitechcloudvn/hermes-plugin-remote-hosts.git ~/.hermes/plugins/hermes-plugin-remote-hosts
   ```
2. Restart the Hermes gateway after changing plugin or `remote_hosts` config.

### Prerequisites

- Local `ssh` must be installed on the Hermes gateway host.
- Remote hosts must provide `python3` and `bash`.
- SSH key authentication must work non-interactively. The plugin runs SSH with `BatchMode=yes`.
- Host keys should already be present in local `known_hosts` when `strict_host_key_checking: true` is used, which is the default.

### Configuration

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

### Usage

- `remote_hosts_list()` — lists enabled aliases without exposing `identity_file` or raw SSH options.
- `remote_terminal(host, command, workdir?, timeout?)` — runs a foreground command with remote `bash -lc`.
- `remote_read_file(host, path, offset?, limit?)` — reads text with line pagination using a remote `python3` helper; disabled unless the host has `allow_read: true`.
- `remote_write_file(host, path, content)` — atomically overwrites a text file using a remote `python3` helper; disabled unless the host has `allow_write: true`. Content above 200,000 characters is rejected before SSH.

Read and write tools also require either non-empty `allowed_roots` or `workdir_only: true`; unconstrained remote file access is rejected.

### Security

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

### Tests

Install `pytest` and run the test suite:

```bash
pip install pytest
python -m pytest -q
```

### License

MIT — see [LICENSE](LICENSE). © 2026 HiTechCloud.VN.
