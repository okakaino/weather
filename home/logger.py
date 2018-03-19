# -*- coding: utf-8 -*-

import logging
from logging.handlers import RotatingFileHandler


def set_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s: %(message)s',
                                    datefmt='%b %d, %Y %H:%M:%S')
    handler = RotatingFileHandler('{}.log'.format(__name__), maxBytes=20*1024**2)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

logger = set_logger()