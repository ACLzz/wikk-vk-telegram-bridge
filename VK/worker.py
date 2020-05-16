from VK.main import get_session
from database.db import execute
from vk_api.longpoll import VkLongPoll, VkEventType
from multiprocessing import Process
from secret import use_proxy

workers = {}


def create_worker(bot, uid):
    if f'{uid}' in workers:
        return 0

    proc = Process(target=worker, args=(bot, uid))
    workers[f'{uid}'] = proc
    proc.start()
    return 0


def worker(bot, uid):
    session = get_session(uid, proxy=use_proxy)
    poll = VkLongPoll(session)
    for event in poll.listen():
        if event.type == VkEventType.MESSAGE_NEW:
            if not event.from_me:
                chat_id = execute(f"select chat_id from chats where vchat_id = {event.peer_id};")[0][0]
                bot.send_message(chat_id=chat_id, text=event.text)

    exit(0)
