import logging
import os
from logging.handlers import TimedRotatingFileHandler

from config import LOG_DIR

LOG_FILE = str(LOG_DIR / 'monitor.log')


class WindowsSafeRotatingHandler(TimedRotatingFileHandler):
    """Windows 兼容的日志轮转处理器：处理 PermissionError"""
    def doRollover(self):
        if not os.path.exists(self.baseFilename):
            # 避免 Windows 下因文件被占用导致的轮转失败
            self.stream = None
            TimedRotatingFileHandler.doRollover(self)
            return
        try:
            TimedRotatingFileHandler.doRollover(self)
        except (PermissionError, OSError):
            # Windows 文件锁冲突时跳过轮转，继续写入当前文件
            self.stream = self._open()


def get_logger(name: str = 'car_monitor') -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = WindowsSafeRotatingHandler(
            LOG_FILE,
            when='midnight',
            interval=1,
            backupCount=8,
            encoding='utf-8'
        )
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(console_handler)

    return logger
