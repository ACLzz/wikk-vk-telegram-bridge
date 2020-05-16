import logging
from disaptcher import updater, init_handlers, init_workers
from secret import load_proxies, use_proxy
from VK.worker import workers
import psutil


from signal import signal, SIGINT

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
log = logging


def stop(signum, frame):
    log.info("Shutting down bot...")
    for worker in workers.values():
        parent = psutil.Process(worker.pid)
        for child in parent.children(recursive=True):  # or parent.children() for recursive=False
            child.join()
        parent.kill()
    log.info("Workers stopped")
    updater.stop()
    log.info("Stopped.")


def start():
    log.info("Initialization...")

    if use_proxy:
        load_proxies()
    init_handlers()
    init_workers()

    log.info("Initialized. Starting polling")
    updater.start_polling()
    log.info("Polling started")


if __name__ == "__main__":
    signal(SIGINT, stop)
    start()
