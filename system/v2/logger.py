import logging
from logging.handlers import TimedRotatingFileHandler

from config import LOG_DIR

LOG_FILE = str(LOG_DIR / 'monitor.log')


def get_logger(name: str = 'car_monitor') -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = TimedRotatingFileHandler(
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
