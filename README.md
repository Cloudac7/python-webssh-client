# Python WebSSH Client

一个原生 Python WebSocket SSH 客户端，用于通过 WebSocket 连接远程 SSH 服务。支持完整的终端交互、窗口大小同步和灵活的身份验证方式。

## 功能特性

- ✅ **WebSocket 连接**：通过 WebSocket 建立与远程 SSH 服务的连接
- ✅ **完整终端交互**：支持双向实时通信，完全兼容远程 Shell
- ✅ **终端大小同步**：自动检测本地终端大小变化并同步到远程
- ✅ **灵活身份验证**：支持配置文件或命令行参数两种方式传递认证信息
- ✅ **调试模式**：完整的日志输出，便于问题诊断
- ✅ **安全退出**：支持 `Ctrl + ]` 快捷键强制退出，确保终端恢复

## 系统要求

- Python 3.9 或更高版本
- Linux (WSL) / MacOS（需要 `termios`、`tty` 等 POSIX 终端模块）
- WebSocket 服务支持（通常是 SSH-over-WebSocket 服务）

## 安装

### 1. 克隆或下载项目

```bash
git clone <repository-url>
cd python-wssh-client
```

### 2. 安装依赖

#### 方式 A：使用 uv（推荐）

[uv](https://github.com/astral-sh/uv) 是一个快速的 Python 包管理工具和项目管理器。

**第一步：安装 uv**

如果还未安装 uv，运行：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

或使用其他包管理器安装（如 Homebrew、Conda 等）。

**第二步：创建虚拟环境并安装依赖**

```bash
# 创建虚拟环境并安装项目依赖
uv sync
```

这会：
- 创建一个虚拟环境（`.venv`）
- 安装 `pyproject.toml` 中定义的所有依赖
- 生成 `uv.lock` 文件用于锁定依赖版本

**第三步：激活虚拟环境（可选）**

```bash
source .venv/bin/activate
```

现在可以直接运行脚本：

```bash
python wssh_client.py wss://example.com/ssh -c config.json
```

#### 方式 B：使用 pip

如果不使用 uv，可以用 pip 安装项目依赖：

```bash
pip install -e .
```

或直接安装依赖包：

```bash
pip install websocket-client>=1.9.0
```

## 使用方法

### 基本语法

```bash
python wssh_client.py <WebSocket URL> [选项]
```

### 选项说明

| 选项 | 长选项 | 说明 | 必须 |
|------|--------|------|------|
| `<URL>` | - | WebSocket 服务 URL (如 `wss://example.com/ssh`) | ✅ 是 |
| `-c` | `--config` | 认证配置文件路径（JSON 格式） | 二选一 |
| `-a` | `--auth` | 认证信息 JSON 字符串 | 二选一 |
| `-d` | `--debug` | 启用调试模式，输出详细日志 | ❌ 否 |
| `-h` | `--help` | 显示帮助信息 | ❌ 否 |

### 认证方式

#### 方式 1：使用配置文件（推荐）

根据 Websocket 实际传入的消息 JSON，创建认证配置文件 `auth.json`：

```json
{
  "type": "connect",
  "message": {
    "room": "your_room_id",
    "account": "username",
    "stoken": "your_session_token",
    "userId": "your_user_id",
    "token": "your_auth_token"
  }
}
```

运行客户端：

```bash
python wssh_client.py wss://example.com/ssh -c auth.json
```

#### 方式 2：使用命令行参数

直接通过 `-a` 参数传递 JSON 字符串：

```bash
python wssh_client.py wss://example.com/ssh -a '{"type":"connect","message":{"room":"","account":"user","stoken":"","userId":"","token":""}}'
```

### 快速开始示例

**示例 1：使用配置文件连接**

```bash
# 创建配置文件
cat > config.json <<EOF
{
  "type": "connect",
  "message": {
    "room": "ssh-room-1",
    "account": "john",
    "stoken": "abc123token",
    "userId": "user-001",
    "token": "jwt-token-here"
  }
}
EOF

# 连接到 WebSSH 服务
python wssh_client.py wss://ssh.example.com/ssh -c config.json
```

**示例 2：启用调试模式**

```bash
python wssh_client.py wss://example.com/ssh -c config.json -d
```

此时会输出详细的调试信息，包括：
- WebSocket 连接状态
- 认证信息加载情况
- 终端大小同步信息
- 错误和异常详情

**示例 3：查看帮助信息**

```bash
python wssh_client.py -h
```

## 配置文件格式

认证配置文件应为 JSON 格式。参考示例：

```json
{
  "type": "connect",
  "message": {
    "room": "连接的房间/通道ID",
    "account": "用户名",
    "stoken": "会话令牌",
    "userId": "用户ID",
    "token": "认证令牌"
  }
}
```

**说明**：
- `type`：消息类型，通常为 `"connect"`
- `message`：包含认证信息的对象
  - `room`：WebSSH 服务中的房间/通道标识
  - `account`：登录用户名
  - `stoken`：会话令牌
  - `userId`：用户唯一标识
  - `token`：JWT 或其他认证令牌

## 运行时操作

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `Ctrl + ]` | 强制退出客户端并恢复终端 |
| `Ctrl + C` | 正常中断连接 |

### 终端大小同步

客户端自动检测本地终端大小变化，在以下情况下同步到远程：
- WebSocket 连接建立后
- 收到服务器的连接/就绪消息
- 终端窗口大小改变时（SIGWINCH 信号）

## 日志输出

### 正常模式日志

```
[INFO] WebSocket connected. Local terminal size: 120x40
[INFO] Closing connection...
```

### 调试模式日志（-d 选项）

```
[INFO] WebSocket connected. Local terminal size: 120x40
[DEBUG] Sent resize: 120x40
[DEBUG] Sent resize: 120x40
[INFO] Loaded auth payload from config: config.json
[DEBUG] Failed to send resize: ...
```

所有日志输出到 `stderr`，不会干扰 SSH 会话的正常输出。

## 故障排除

### 问题 1：连接失败

**症状**：
```
[ERROR] Config file not found: auth.json
```

**解决方案**：
- 检查配置文件路径是否正确
- 确保文件存在且可读
- 使用绝对路径以避免混淆

### 问题 2：认证错误

**症状**：
服务器返回错误消息，连接立即断开

**解决方案**：
- 验证配置文件中的认证信息是否正确
- 检查令牌是否过期
- 使用 `-d` 调试模式查看详细信息

### 问题 3：终端显示异常

**症状**：
字符显示错乱或不响应输入

**解决方案**：
- 按 `Ctrl + ]` 强制退出并恢复终端
- 如果仍有问题，运行 `reset` 命令恢复终端
- 增大终端窗口再试

### 问题 4：连接超时

**症状**：
长时间无响应，最后连接断开

**解决方案**：
- 检查网络连接
- 验证 WebSocket 服务地址是否可达
- 确保防火墙允许连接
- 尝试增加连接等待时间

## 开发和贡献

### 项目结构

```
python-wssh-client/
├── wssh_client.py          # 主客户端脚本
├── config.example.json     # 配置文件示例
├── pyproject.toml          # 项目配置
└── README.md              # 本文档
```

### 编码规范

- 使用 Python 3.9+ 语法
- 遵循 PEP 8 风格指南
- 使用标准 `logging` 模块进行日志输出
- 优先使用上下文管理器管理资源

### 常见修改场景

#### 修改认证流程

编辑 `on_open()` 函数中的认证发送逻辑：

```python
def on_open(ws):
    # 修改此处以自定义认证流程
    ws.send(json.dumps(AUTH_PAYLOAD))
```

#### 添加消息处理

编辑 `on_message()` 函数以处理特定的服务器消息：

```python
def on_message(ws, message):
    data = json.loads(message)
    msg_type = data.get("type", "")
    # 在此添加自定义处理逻辑
```

#### 修改输出编码

在 `input_loop()` 中调整编码处理：

```python
try:
    str_data = data.decode('utf-8')
except:
    str_data = data.decode('latin-1')  # 修改此处
```

## 安全建议

1. **保护配置文件**：配置文件包含敏感认证信息，应设置合适的文件权限
   ```bash
   chmod 600 config.json
   ```

2. **使用 HTTPS/WSS**：始终使用加密的 WebSocket 连接（`wss://` 而不是 `ws://`）

3. **避免在命令行传递凭证**：使用 `-a` 参数时要注意凭证可能暴露在进程列表中，优先使用配置文件

4. **定期更新令牌**：确保认证令牌未过期，定期刷新

5. **日志中的敏感信息**：调试模式会输出连接信息，不要在敏感环境中保存日志

## 许可证

请参考项目根目录的 LICENSE 文件。

## 联系方式

如有问题或建议，请提交 Issue 或 Pull Request。
