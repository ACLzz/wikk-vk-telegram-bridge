from commands import update_group_info
from database.db import execute
from disaptcher import bot as b
from time import sleep
from datetime import datetime
import pytz
import logging
from signal import signal, SIGINT
from telegram import error
from multiprocessing import Pool
from os import environ, listdir, remove

local_tz = pytz.timezone('Europe/Zaporozhye')
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
log = logging
workers = int(environ.get("POOL_WORKERS"))


def run(bot):
    chats = execute("select * from chats;")

    data = []
    for chat in chats:
        data.append([chat, bot])

    with Pool(workers) as p:
        p.map(_update, data)

    for file in listdir():
        if '.png' in file or ('file' in file and 'Pip' not in file and 'Proc' not in file):
            remove(file)
    log.info("Chats updated")


def _update(data):
    chat, bot = data
    chat_id = chat[0]
    uid = chat[1]
    vk_chat_id = chat[2]
    if vk_chat_id == 0:
        return

    try:
        update_group_info(uid, bot, vk_chat_id, chat_id)
    except error.BadRequest:
        pass


def utc_to_local(utc_dt):
    local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(local_tz)
    return local_tz.normalize(local_dt)


def stop(signum, frame):
    exit(0)


if __name__ == '__main__':
    signal(SIGINT, stop)
    log.info("Start update chats worker")

    while True:
        sleep(25*60)
        hour = int(utc_to_local(datetime.utcnow()).strftime('%H'))
        if 12 >= hour < 4:
            continue

        run(b)
