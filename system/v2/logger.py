import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f'weibo.{name}')
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    try:
        log_dir = Path(__file__).resolve().parents[2] / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'main.log'

        fh = TimedRotatingFileHandler(
            str(log_file), when='midnight', interval=1,
            backupCount=8, encoding='utf-8', delay=True
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"文件日志初始化失败: {e}")

    return logger