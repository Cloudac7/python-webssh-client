import websocket
import threading
import sys
import json
import ssl
import time
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
last_terminal_size = None

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

def close_app():
    """统一的退出清理函数"""
    global is_running
    if not is_running: return
    is_running = False
    logger.info("Closing connection...")
    if ws_global:
        ws_global.close()

def send_resize(get_terminal_size_func):
    global last_terminal_size, ws_global
    if not ws_global or not ws_global.sock or not ws_global.sock.connected:
        return
    cols, rows = get_terminal_size_func()
    
    # 避免重复发送相同的大小
    if last_terminal_size == (cols, rows):
        logger.debug(f"Terminal size unchanged: {cols}x{rows}, skipping resize")
        return
    
    payload = { "type": "resize", "message": { "cols": cols, "rows": rows } }
    try:
        ws_global.send(json.dumps(payload))
        last_terminal_size = (cols, rows)
        logger.debug(f"Sent resize: {cols}x{rows}")
    except Exception as e:
        logger.debug(f"Failed to send resize: {e}")

def on_message(ws, message):
    global is_running, ws_global
    try:
        data = json.loads(message)
        content = data.get("message", "")
        msg_type = data.get("type", "")
        
        if msg_type in ["connected", "ready"] or (isinstance(content, str) and content.strip() and "logout" not in content.lower()):
            time.sleep(0.05)
            pass
        
        if "logout" in content.strip().lower():
            if isinstance(content, str):
                sys.stdout.buffer.write(content.encode('utf-8'))
            else:
                sys.stdout.buffer.write(content)
            sys.stdout.buffer.flush()
            
            is_running = False
            ws.close()
            return

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

def on_open(ws, get_terminal_size_func, send_resize_func):
    global ws_global, last_terminal_size
    ws_global = ws
    cols, rows = get_terminal_size_func()
    last_terminal_size = (cols, rows)
    logger.info(f"WebSocket connected. Local terminal size: {cols}x{rows}")
    
    ws.send(json.dumps(AUTH_PAYLOAD))
    
    def delayed_actions():
        time.sleep(0.1)
        for i in range(10):
            send_resize_func()
            time.sleep(0.2)
    
    threading.Thread(target=delayed_actions, daemon=True).start()

def create_websocket(get_terminal_size_func, send_resize_func):
    """创建并返回WebSocket应用"""
    ws = websocket.WebSocketApp(
        WS_URL,
        on_open=lambda ws: on_open(ws, get_terminal_size_func, send_resize_func),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    return ws
