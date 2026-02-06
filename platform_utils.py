"""
平台特定的终端处理逻辑
"""
import sys
import logging

logger = logging.getLogger(__name__)

class TerminalHandler:
    """终端处理的抽象基类"""
    
    def __init__(self):
        self.old_settings = None
    
    def get_terminal_size(self):
        """获取终端大小，返回 (cols, rows)"""
        raise NotImplementedError
    
    def setup_terminal(self):
        """设置终端为原始模式"""
        raise NotImplementedError
    
    def restore_terminal(self):
        """恢复终端设置"""
        raise NotImplementedError
    
    def read_input(self):
        """读取用户输入，返回字节数据"""
        raise NotImplementedError
    
    def setup_resize_handler(self, callback):
        """设置窗口大小变化的处理器"""
        raise NotImplementedError


class UnixTerminalHandler(TerminalHandler):
    """Unix/Linux 终端处理"""
    
    def __init__(self):
        super().__init__()
        import signal
        import tty
        import termios
        self.signal = signal
        self.tty = tty
        self.termios = termios
        self.fd = sys.stdin.fileno()
    
    def get_terminal_size(self):
        """获取终端大小"""
        import fcntl
        import struct
        
        for fd in [sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno()]:
            try:
                s = struct.pack("HHHH", 0, 0, 0, 0)
                t = fcntl.ioctl(fd, self.termios.TIOCGWINSZ, s)
                h, w, hp, wp = struct.unpack("HHHH", t)
                if w > 0 and h > 0:
                    logger.debug(f"Got terminal size from fd {fd}: {w}x{h}")
                    return w, h
            except Exception as e:
                logger.debug(f"Failed to get terminal size from fd {fd}: {e}")
                continue
        
        logger.warning("Failed to get terminal size, using default 80x24")
        return 80, 24
    
    def setup_terminal(self):
        """设置原始终端模式"""
        self.old_settings = self.termios.tcgetattr(self.fd)
        self.tty.setraw(self.fd)
    
    def restore_terminal(self):
        """恢复终端设置"""
        if self.old_settings:
            self.termios.tcsetattr(self.fd, self.termios.TCSADRAIN, self.old_settings)
    
    def read_input(self, timeout=0.05):
        """使用select读取输入"""
        import select
        import os
        
        try:
            r, w, e = select.select([self.fd], [], [], timeout)
            if self.fd in r:
                data = os.read(self.fd, 4096)
                return data if data else None
        except (OSError, Exception) as e:
            logger.debug(f"Error reading input: {e}")
        return None
    
    def setup_resize_handler(self, callback):
        """设置SIGWINCH信号处理器"""
        self.signal.signal(self.signal.SIGWINCH, lambda signum, frame: callback())


class WindowsTerminalHandler(TerminalHandler):
    """Windows 终端处理"""
    
    def __init__(self):
        super().__init__()
        try:
            import msvcrt
            self.msvcrt = msvcrt
        except ImportError:
            logger.error("msvcrt module not available on this Windows system")
    
    def get_terminal_size(self):
        """获取Windows终端大小"""
        try:
            # 尝试使用shutil获取终端大小（Python 3.3+）
            import shutil
            cols, rows = shutil.get_terminal_size(fallback=(80, 24))
            logger.debug(f"Got terminal size: {cols}x{rows}")
            return cols, rows
        except Exception as e:
            logger.debug(f"Failed to get terminal size: {e}")
            return 80, 24
    
    def setup_terminal(self):
        """Windows不需要终端模式切换"""
        logger.debug("Windows terminal setup (no-op)")
    
    def restore_terminal(self):
        """Windows不需要恢复"""
        logger.debug("Windows terminal restore (no-op)")
    
    def read_input(self, timeout=0.05):
        """使用msvcrt读取Windows输入"""
        import time
        try:
            if self.msvcrt.kbhit():
                data = self.msvcrt.getch()
                return data if data else None
            time.sleep(timeout)
        except Exception as e:
            logger.debug(f"Error reading input: {e}")
        return None
    
    def setup_resize_handler(self, callback):
        """Windows的控制台不容易检测大小变化，这里先空实现"""
        logger.debug("Windows resize handler registration (no-op)")


def get_terminal_handler():
    """根据平台返回对应的终端处理器"""
    if sys.platform in ['linux', 'linux2', 'darwin']:
        logger.info("Using Unix/Linux terminal handler")
        return UnixTerminalHandler()
    elif sys.platform == 'win32':
        logger.info("Using Windows terminal handler")
        return WindowsTerminalHandler()
    else:
        logger.warning(f"Unknown platform: {sys.platform}, trying Unix handler")
        return UnixTerminalHandler()
