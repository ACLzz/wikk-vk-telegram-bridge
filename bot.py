import logging
from wikk_bot.disaptcher import updater, init_handlers, init_workers
from wikk_bot.secret import get_token
from VK.worker import workers
import psutil

from os import remove, listdir, environ

from signal import signal, SIGINT

log_file = 'LOGS.log'
level = logging.INFO
handlers = [logging.FileHandler(log_file), logging.StreamHandler()]

logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=handlers)
log = logging
mode = environ.get("MODE")


def stop(signum, frame):
    log.info("Shutting down bot...")
    # Getting every worker one by one
    for worker in workers.values():
        parent = psutil.Process(worker.pid)
        for child in parent.children(recursive=True):
            # Joining childs of every worker
            child.join()
        # Killing worker
        parent.kill()
    log.info("Workers stopped")

    for file in listdir():
        if '.png' in file or ('file' in file and 'Pip' not in file and 'Proc' not in file):
            remove(file)
    log.info("All unsent files cleaned")

    updater.stop()
    log.info("Stopped.")


def start():
    log.info("Initialization...")

    init_handlers()
    init_workers()

    log.info("Initialized. Starting polling")

    if mode == 'dev':
        updater.start_polling()
    elif mode == 'prod':
        port = int(environ.get("PORT", "8443"))
        app_name = environ.get("HEROKU_APP_NAME")
        token = get_token()

        updater.start_webhook(listen="0.0.0.0",
                              port=port,
                              url_path=token)
        updater.bot.set_webhook("https://{}.herokuapp.com/{}".format(app_name, token))
        log.info(f"{app_name}: start")
    else:
        raise Exception()

    log.info("Polling started")


if __name__ == "__main__":
    signal(SIGINT, stop)
    start()
