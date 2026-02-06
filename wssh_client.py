import websocket
import threading
import sys
import json
import tty
import termios
import ssl
import signal
import fcntl
import struct
import select
import time
import os
import argparse
import logging

# ================= 日志配置 =================
logger = logging.getLogger(__name__)

def setup_logger(debug_mode):
    """配置日志处理器"""
    log_level = logging.DEBUG if debug_mode else logging.INFO
    logger.setLevel(log_level)
    
    # 创建控制台处理器
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(log_level)
    
    # 设置日志格式
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    
    # 清空现有处理器（避免重复）
    logger.handlers.clear()
    logger.addHandler(handler)

# ================= 全局变量 =================
WS_URL = None
AUTH_PAYLOAD = None

is_running = True
ws_global = None
debug_mode = False
last_terminal_size = None  # 跟踪上次发送的终端大小，避免重复发送

# ===========================================

def load_auth_payload(config_path):
    """从配置文件加载 AUTH_PAYLOAD"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        logger.info(f"Successfully loaded auth payload from config: {config_path}")
        return config
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        sys.exit(1)

def load_auth_from_string(auth_json_str):
    """从 JSON 字符串解析 AUTH_PAYLOAD"""
    try:
        return json.loads(auth_json_str)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON string: {e}")
        sys.exit(1)

def get_terminal_size():
    """
    获取终端大小，通过多个文件描述符尝试
    尝试顺序: stdin(0) -> stdout(1) -> stderr(2)
    """
    for fd in [sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno()]:
        try:
            s = struct.pack("HHHH", 0, 0, 0, 0)
            t = fcntl.ioctl(fd, termios.TIOCGWINSZ, s)
            h, w, hp, wp = struct.unpack("HHHH", t)
            if w > 0 and h > 0:  # 确保获取到有效的大小
                logger.debug(f"Got terminal size from fd {fd}: {w}x{h}")
                return w, h
        except Exception as e:
            logger.debug(f"Failed to get terminal size from fd {fd}: {e}")
            continue
    
    # 如果所有尝试都失败，返回默认值并记录警告
    logger.warning("Failed to get terminal size from all file descriptors, using default 80x24")
    return 80, 24

def send_resize():
    global last_terminal_size, ws_global
    if not ws_global or not ws_global.sock or not ws_global.sock.connected:
        return
    cols, rows = get_terminal_size()
    
    # 避免重复发送相同的大小，但允许发送变化后的大小
    if last_terminal_size == (cols, rows):
        logger.debug(f"Terminal size unchanged: {cols}x{rows}, skipping resize")
        return
    
    # ⚠️ 保持之前的 Resize 格式
    payload = { "type": "resize", "message": { "cols": cols, "rows": rows } }
    try:
        ws_global.send(json.dumps(payload))
        last_terminal_size = (cols, rows)
        logger.debug(f"Sent resize: {cols}x{rows}")
    except Exception as e:
        logger.debug(f"Failed to send resize: {e}")

def on_window_resize(signum, frame):
    send_resize()

def close_app():
    """统一的退出清理函数"""
    global is_running
    if not is_running: return
    is_running = False
    logger.info("Closing connection...")
    if ws_global:
        ws_global.close()

def on_message(ws, message):
    global is_running, ws_global
    try:
        data = json.loads(message)
        content = data.get("message", "")
        msg_type = data.get("type", "")
        
        # ------------------------------------------------
        # 修复 3: 认证成功后立即发送窗口大小
        # ------------------------------------------------
        # 检测服务器的成功响应或初始 Shell 提示，立即同步窗口大小
        if msg_type in ["connected", "ready"] or (isinstance(content, str) and content.strip() and "logout" not in content.lower()):
            # 在认证完成、准备就绪时立即发送窗口大小
            # 使用 send_resize() 内部的逻辑来避免重复发送
            time.sleep(0.05)  # 给服务器很短的时间初始化
            send_resize()
        
        # ------------------------------------------------
        # 修复 2: 自动检测 "logout" 关键字
        # ------------------------------------------------
        # 很多服务器只会发送文本 "logout" 而不关闭 Socket
        # 我们检测到这个词后，给一点缓冲时间自动退出
        if "logout" in content.strip().lower():
            # 先打印出来
            if isinstance(content, str):
                sys.stdout.buffer.write(content.encode('utf-8'))
            else:
                sys.stdout.buffer.write(content)
            sys.stdout.buffer.flush()
            
            # 标记结束
            is_running = False
            # 这里的 exit 只能退出回调线程，主线程需要配合 input_loop 退出
            ws.close()
            return

        # 正常输出处理
        if isinstance(content, str):
            sys.stdout.buffer.write(content.encode('utf-8'))
        else:
            sys.stdout.buffer.write(content)
        sys.stdout.buffer.flush()
        
    except:
        if isinstance(message, str):
            sys.stdout.buffer.write(message.encode('utf-8'))
        sys.stdout.buffer.flush()

def on_error(ws, error):
    pass

def on_close(ws, close_status_code, close_msg):
    global is_running
    is_running = False

def on_open(ws):
    global ws_global, last_terminal_size
    ws_global = ws
    cols, rows = get_terminal_size()
    last_terminal_size = (cols, rows)
    logger.info(f"WebSocket connected. Local terminal size: {cols}x{rows}")
    
    # 立即发送认证
    ws.send(json.dumps(AUTH_PAYLOAD))
    
    def delayed_actions():
        # 在认证消息发送后立即尝试发送窗口大小，然后定期重试
        time.sleep(0.1)  # 给服务器最少延迟
        
        # 前2秒内每200ms重试一次，确保远程Shell能收到正确的窗口大小
        for i in range(10):
            send_resize()
            time.sleep(0.2)
    
    threading.Thread(target=delayed_actions, daemon=True).start()
    threading.Thread(target=input_loop, daemon=True).start()

def input_loop():
    """
    增加了 Ctrl+] 检测的输入循环
    """
    global is_running
    fd = sys.stdin.fileno()
    
    while is_running:
        try:
            r, w, e = select.select([fd], [], [], 0.05)
            if fd in r:
                data = os.read(fd, 4096)
                if not data: # EOF
                    break
                
                # ------------------------------------------------
                # 修复 1: 手动强退热键 Ctrl + ] (ASCII \x1d)
                # ------------------------------------------------
                if b'\x1d' in data:
                    # 恢复终端并在本地打印提示
                    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                    logger.info("Force quit detected (Ctrl+]). Exiting...")
                    is_running = False
                    ws_global.close()
                    os._exit(0) # 暴力退出进程

                # 正常发送
                try:
                    str_data = data.decode('utf-8')
                except:
                    str_data = data.decode('latin-1')

                payload = {"type": "command", "message": str_data}
                ws_global.send(json.dumps(payload))
                
        except (OSError, Exception):
            break
            
    # 循环结束，触发关闭
    if ws_global: ws_global.close()

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Native WebSSH Client")
    parser.add_argument("ws_url", help="WebSocket URL (e.g., wss://example.com/ssh)")
    parser.add_argument("-c", "--config", help="Path to auth config file (JSON)")
    parser.add_argument("-a", "--auth", help="Auth payload as JSON string")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # 设置全局变量
    WS_URL = args.ws_url
    debug_mode = args.debug
    
    # 配置日志
    setup_logger(debug_mode)
    
    # 初始化终端大小
    cols, rows = get_terminal_size()
    last_terminal_size = (cols, rows)
    logger.debug(f"Initial terminal size: {cols}x{rows}")
    
    # 加载 AUTH_PAYLOAD
    if args.config:
        AUTH_PAYLOAD = load_auth_payload(args.config)
    elif args.auth:
        AUTH_PAYLOAD = load_auth_from_string(args.auth)
        logger.info("Loaded auth payload from command line")
    else:
        logger.error("Either --config or --auth must be provided")
        parser.print_help()
        sys.exit(1)
    
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    signal.signal(signal.SIGWINCH, on_window_resize)

    print("---------------------------------------------------")
    print(" Native WebSSH Client")
    print(f" WS URL: {WS_URL}")
    print(" Tips: Use 'Ctrl + ]' to force quit if stuck.")
    if debug_mode:
        print(" Debug mode enabled")
    print("---------------------------------------------------")
    time.sleep(1) # 给用户1秒钟看提示

    try:
        tty.setraw(fd)
        ws = websocket.WebSocketApp(
            WS_URL, on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close
        )
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("\nSession Closed.")
