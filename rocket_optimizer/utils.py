import logging
import os
from typing import Optional

from .config import RESULTS_DIR


def setup_logger(name: str, log_file: Optional[str] = None, level=logging.INFO):
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        if log_file:
            handler = logging.FileHandler(log_file)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

    return logger


if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

logger = setup_logger("rocket_optimizer", log_file=os.path.join(RESULTS_DIR, "app.log"))
