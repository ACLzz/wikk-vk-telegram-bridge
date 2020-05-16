import logging
from disaptcher import updater, init_handlers
from secret import load_proxies

from signal import signal, SIGINT

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
log = logging


def stop(signum, frame):
    log.info("Shutting down bot...")
    updater.stop()


def start():
    log.info("Starting bot...")
    load_proxies()
    init_handlers()
    updater.start_polling()


if __name__ == "__main__":
    signal(SIGINT, stop)
    start()
