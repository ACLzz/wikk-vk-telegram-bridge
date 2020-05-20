from VK.main import get_session
from vk_api.longpoll import VkLongPoll, VkEventType

from database.db import execute
from secret import use_proxy

from multiprocessing import Process

from telegram import ChatAction
from telegram.error import BadRequest

workers = {}


def create_worker(bot, uid):
    if f'{uid}' in workers:
        return 0
    # Create worker process
    proc = Process(target=_create_worker, args=(bot, uid))
    workers[f'{uid}'] = proc
    proc.start()
    return 0


def _create_worker(bot, uid):
    worker = Worker(bot, uid)
    worker.start()


class Worker:
    def __init__(self, bot, uid):
        self.bot = bot
        self.session = get_session(uid, proxy=use_proxy)
        self.api = self.session.get_api()
        self.poll = VkLongPoll(self.session, mode=2)

        self.start()

    restricted_events = [VkEventType.MESSAGES_COUNTER_UPDATE]
    good_event = False
    event = None
    event_t = None          # Event type

    chat_id = None
    message_id = None
    attchs = []
    attchs_count = 0
    attchs_types = []
    cont_attchs = False     # Bool if containing attachments

    def start(self):
        for self.event in self.poll.listen():
            self.event_process()

            if self.good_event:
                if self.chat_id == 0:
                    continue

                if self.event_t == VkEventType.MESSAGE_NEW:
                    self.new_message()

                if self.event_t == VkEventType.USER_TYPING:
                    self.user_typing()

                if self.event_t == VkEventType.USER_ONLINE:
                    self.user_online(True)

                if self.event_t == VkEventType.USER_OFFLINE:
                    self.user_online(False)

                self.cleaner()
        exit(0)

    def event_process(self):
        self.good_event = not self.event.from_me and self.event.type not in self.restricted_events
        self.event_t = self.event.type

        if self.event_t == VkEventType.USER_ONLINE or self.event_t == VkEventType.USER_OFFLINE:
            self.chat_id = get_chat_id(self.event.user_id)

        if self.event_t == VkEventType.MESSAGE_NEW:
            self.chat_id = get_chat_id(self.event.user_id)
            attchs = self.event.attachments.values()
            self.message_id = self.event.message_id

            if attchs:
                self.cont_attchs = True
                attachments_from_msg = self.api.messages.getById(message_ids=self.message_id)['items'][0]['attachments']
                counter = 0
                for attach in attachments_from_msg:
                    atype = attach['type']
                    self.attchs_types.append(atype)

                    if atype == 'photo':
                        url = attach['photo']['sizes'][-1]['url']
                    elif atype == 'audio_message':
                        url = attach['audio_message']['link_ogg']
                    else:
                        raise Exception

                    self.attchs.append(url)
                    counter += 1
                self.attchs_count = counter
        else:
            self.cont_attchs = False

    def new_message(self):
        if self.cont_attchs:
            i = 0
            while i < self.attchs_count:
                if self.attchs_types[i] == 'photo':
                    text = self.event.text
                    if text:
                        self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[i], caption=text)
                    else:
                        self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[i])

                if self.attchs_types[i] == 'audio_message':
                    voice_url = self.attchs[i]
                    self.bot.send_voice(chat_id=self.chat_id, voice=voice_url)

                i += 1
        else:
            self.bot.send_message(chat_id=self.chat_id, text=self.event.text)

    def user_online(self, online):
        title = self.bot.get_chat(chat_id=self.chat_id)['title'][:-1]
        if online:
            title += "🌑"
        else:
            title += "🌕"

        try:
            self.bot.set_chat_title(chat_id=self.chat_id, title=title)
        except BadRequest:
            return 0

    def user_typing(self):
        self.bot.send_chat_action(chat_id=self.chat_id, action=ChatAction.TYPING)

    def cleaner(self):
        self.chat_id = None
        self.message_id = None
        self.attchs = []
        self.attchs_count = 0
        self.attchs_types = []
        self.cont_attchs = False


def get_chat_id(vk_chat_id):
    try:
        chat_id = execute(f"select chat_id from chats where vchat_id = {vk_chat_id};")[0][0]
        return chat_id
    except IndexError:
        # If vk chat stream not binded to telegram group
        return 0
