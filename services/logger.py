"""This file contains logger logic."""

import logging
import os
from logging import Logger
from logging.handlers import RotatingFileHandler


def start_logger() -> Logger:
    """
    Loggers definition. Logger in logger.py is the highest (A), other are descendants:
    A.uti, A.db, etc.
    """
    gen_logger = logging.getLogger('A')
    gen_logger.setLevel(logging.DEBUG)
    gen_logger.propagate = False

    #  Logging to console.
    ch = logging.StreamHandler()
    #  Logging to file, continuous after bot restart.
    rh = RotatingFileHandler(
        filename=os.path.join('logger.log'),
        mode='a',
        maxBytes=1024 * 1024 * 5,
        backupCount=1,
    )
    ch_formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d - %(name)5s - %(levelname)8s:%(lineno)3d - \
        %(funcName)18s()] %(message)s',
        '%H:%M:%S',
    )
    rh_formatter = logging.Formatter(
        '[%(asctime)s.%(msecs)03d - %(name)5s - %(levelname)8s:%(lineno)3d - \
        %(funcName)18s() - %(filename)8s - %(threadName)10s] %(message)s',
        '%Y-%m-%d %H:%M:%S',
    )
    ch.setLevel(logging.DEBUG)
    rh.setLevel(logging.DEBUG)
    ch.setFormatter(ch_formatter)
    rh.setFormatter(rh_formatter)
    gen_logger.addHandler(ch)
    gen_logger.addHandler(rh)
    return gen_logger


logger = start_logger()
logger.info('Main logger started, __name__ is %s', __name__)
