#!/usr/bin/env python3
"""
Native WebSSH Client - Main Entry Point
支持 Windows 和 Unix/Linux
"""
import argparse
import sys
import time
import logging

from wssh_client import (
    setup_logger,
    load_auth_payload,
    load_auth_from_string,
    create_websocket,
    send_resize,
)
import wssh_client
from platform_utils import get_terminal_handler

logger = logging.getLogger(__name__)


def setup_global_variables(ws_url, auth_payload, debug_mode):
    """设置全局变量"""
    wssh_client.WS_URL = ws_url
    wssh_client.AUTH_PAYLOAD = auth_payload
    wssh_client.debug_mode = debug_mode
    wssh_client.setup_logger(debug_mode)


def input_loop(terminal_handler):
    """处理用户输入的循环"""
    wssh_client.is_running = True
    
    while wssh_client.is_running:
        try:
            data = terminal_handler.read_input()
            
            if data is None:
                continue
            
            # Unix特定：检测 Ctrl+] (ASCII \x1d)
            if sys.platform in ['linux', 'linux2', 'darwin']:
                if b'\x1d' in data:
                    logger.info("Force quit detected (Ctrl+]). Exiting...")
                    wssh_client.is_running = False
                    if wssh_client.ws_global:
                        wssh_client.ws_global.close()
                    sys.exit(0)
            
            # 发送数据
            if wssh_client.ws_global:
                try:
                    str_data = data.decode('utf-8')
                except:
                    str_data = data.decode('latin-1')
                
                import json
                payload = {"type": "command", "message": str_data}
                wssh_client.ws_global.send(json.dumps(payload))
                
        except (OSError, Exception) as e:
            logger.debug(f"Input loop error: {e}")
            break
    
    if wssh_client.ws_global:
        wssh_client.ws_global.close()


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="Native WebSSH Client (Windows & Unix)")
    parser.add_argument("ws_url", help="WebSocket URL (e.g., wss://example.com/ssh)")
    parser.add_argument("-c", "--config", help="Path to auth config file (JSON)")
    parser.add_argument("-a", "--auth", help="Auth payload as JSON string")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()
    
    # 设置全局变量
    setup_global_variables(args.ws_url, None, args.debug)
    
    # 加载 AUTH_PAYLOAD
    if args.config:
        wssh_client.AUTH_PAYLOAD = load_auth_payload(args.config)
    elif args.auth:
        wssh_client.AUTH_PAYLOAD = load_auth_from_string(args.auth)
        logger.info("Loaded auth payload from command line")
    else:
        logger.error("Either --config or --auth must be provided")
        parser.print_help()
        sys.exit(1)
    
    # 获取平台特定的终端处理器
    terminal_handler = get_terminal_handler()
    
    # 打印启动信息
    print("---------------------------------------------------")
    print(" Native WebSSH Client")
    print(f" Platform: {sys.platform}")
    print(f" WS URL: {args.ws_url}")
    if sys.platform.startswith('linux') or sys.platform == 'darwin':
        print(" Tips: Use 'Ctrl + ]' to force quit if stuck.")
    else:
        print(" Tips: Close this window or press Ctrl+C to quit.")
    if args.debug:
        print(" Debug mode enabled")
    print("---------------------------------------------------")
    time.sleep(1)
    
    # 设置终端
    terminal_handler.setup_terminal()
    
    # 初始化终端大小
    cols, rows = terminal_handler.get_terminal_size()
    wssh_client.last_terminal_size = (cols, rows)
    logger.debug(f"Initial terminal size: {cols}x{rows}")
    
    # 设置窗口大小变化处理
    def on_resize():
        send_resize(terminal_handler.get_terminal_size)
    
    terminal_handler.setup_resize_handler(on_resize)
    
    # 创建WebSocket并启动输入循环
    try:
        ws = create_websocket(
            terminal_handler.get_terminal_size,
            on_resize
        )
        
        # 启动输入循环线程
        import threading
        input_thread = threading.Thread(
            target=input_loop,
            args=(terminal_handler,),
            daemon=True
        )
        input_thread.start()
        
        # 运行WebSocket
        ws.run_forever(sslopt={"cert_reqs": __import__('ssl').CERT_NONE})
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        terminal_handler.restore_terminal()
        print("\nSession Closed.")


if __name__ == "__main__":
    main()
