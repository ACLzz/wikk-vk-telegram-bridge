from VK.main import get_session
from vk_api.longpoll import VkLongPoll, VkEventType

from database.db import execute, get_token
from secret import get_token as get_t

from multiprocessing import Process

from telegram import ChatAction, Bot
from telegram.error import BadRequest
from requests import post
import json

workers = {}
rebrand_api_key = "ac8965f9c18847099b7ea5d6ee3e4220"


def create_worker(bot, uid):
    if f'{uid}' in workers:
        return 0
    # Create worker process
    proc = Process(target=_create_worker, args=(uid,))
    workers[f'{uid}'] = proc
    proc.start()
    return 0


def _create_worker(uid):
    bot = Bot(token=get_t())
    worker = Worker(bot, uid)
    worker.start()


class Worker:
    def __init__(self, bot, uid):
        self.bot = bot
        self.uid = uid
        self.session = get_session(uid)
        self.api = self.session.get_api()
        self.poll = VkLongPoll(self.session, mode=2)

        self.start()

    restricted_events = [VkEventType.MESSAGES_COUNTER_UPDATE]
    good_event = False
    event = None
    event_t = None  # Event type

    chat_id = None
    message_id = None
    attchs = []
    attchs_count = 0
    attchs_types = []
    cont_attchs = False  # Bool if containing attachments
    video_dur = 0

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
        if not self.good_event:
            return 0

        self.event_t = self.event.type

        if self.event_t == VkEventType.USER_ONLINE or self.event_t == VkEventType.USER_OFFLINE \
                or self.event_t == VkEventType.USER_TYPING:
            self.chat_id = get_chat_id(self.event.user_id)

        if self.event_t == VkEventType.MESSAGE_NEW:
            if self.event.from_group:
                vid = self.event.group_id * (-1)
            else:
                vid = self.event.user_id

            self.chat_id = get_chat_id(vid)
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

                    elif atype == 'doc':
                        url = attach['doc']['url']

                    elif atype == 'video':
                        token = get_token(self.uid)
                        if token is None:
                            continue
                        video_id = f"{attach['video']['owner_id']}_{attach['video']['id']}_{attach['video']['access_key']}"

                        url = "https://api.vk.com/method/video.get"
                        data = {
                            "access_token": token,
                            "v": "5.103",
                            "videos": video_id
                        }
                        response = json.loads(post(url=url, data=data).content)
                        self.video_dur = response['response']['items'][0]['duration']
                        videos = response['response']['items'][0]['files']

                        if 'mp4_1080' in videos:
                            url = videos['mp4_1080']
                        elif 'mp4_720' in videos:
                            url = videos['mp4_720']
                        elif 'mp4_480' in videos:
                            url = videos['mp4_480']
                        elif 'mp4_240' in videos:
                            url = videos['mp4_240']
                        else:
                            url = list(videos.values())[-2]

                    else:
                        self.bot.send_message(chat_id=self.chat_id, text=f"Unsupported attachment '{atype}'.")
                        self.cleaner()
                        return

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

                if self.attchs_types[i] == 'video':
                    video_url = self.attchs[i]
                    text = self.event.text

                    if self.video_dur > 30:
                        video_url = short_url(video_url)
                        msg = text + '\n\nThis video is more than 30 seconds, so take url:\n' + video_url
                        i += 1
                        self.bot.send_message(chat_id=self.chat_id, text=msg)
                        continue

                    if text:
                        self.bot.send_video(chat_id=self.chat_id, video=video_url, caption=text)
                    else:
                        self.bot.send_video(chat_id=self.chat_id, video=video_url)

                if self.attchs_types[i] == 'doc':
                    doc_url = self.attchs[i]
                    text = self.event.text

                    if text:
                        self.bot.send_document(chat_id=self.chat_id, document=doc_url, caption=text)
                    else:
                        self.bot.send_document(chat_id=self.chat_id, document=doc_url)

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
        self.good_event = False
        self.chat_id = None
        self.message_id = None
        self.attchs.clear()
        self.attchs_count = 0
        self.attchs_types.clear()
        self.cont_attchs = False
        self.video_dur = 0


def get_chat_id(vk_chat_id):
    try:
        chat_id = execute(f"select chat_id from chats where vchat_id = {vk_chat_id};")[0][0]
        return chat_id
    except IndexError:
        # If vk chat stream not binded to telegram group
        return 0


def short_url(url):
    link_request = {
        "destination": url,
        "domain": {"fullName": "rebrand.ly"}
    }

    request_headers = {
        "Content-type": "application/json",
        "apikey": rebrand_api_key,
    }

    r = post("https://api.rebrandly.com/v1/links",
             data=json.dumps(link_request),
             headers=request_headers)
    return r.json()['shortUrl']
