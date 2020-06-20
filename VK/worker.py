from VK.main import get_session, get_vk_info
from vk_api.longpoll import VkLongPoll, VkEventType

from database.db import execute, get_token
from wikk_bot.secret import get_token as get_t

from multiprocessing import Process
from datetime import datetime

from telegram import ChatAction, Bot
from telegram.error import BadRequest

from requests import post, exceptions
import json
import traceback
from os import environ

workers = {}
rebrand_api_key = environ.get("REBRAND")


def create_worker(uid):
    if f'{uid}' in workers:
        return 0
    # Create worker process
    proc = Process(target=_create_worker, args=(uid,))
    workers[f'{uid}'] = proc
    proc.start()
    return 0


def _create_worker(uid):
    bot = Bot(token=get_t())
    while True:
        try:
            worker = Worker(bot, uid)
            worker.start()
            break
        except exceptions.ReadTimeout:
            pass
        except Exception as err:
            print("\nWORKER EXITED WITH ERROR:\n")
            print(traceback.format_exc())
            print("RESTARTING WORKER\n")


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
    user_actions = [VkEventType.USER_ONLINE, VkEventType.USER_OFFLINE, VkEventType.USER_TYPING]

    chat_id = None
    message_id = None
    extended_message = None
    text = ""
    attchs = []
    attchs_count = 0
    attchs_types = []
    forwards_root = False
    forwards = []
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

        if self.event_t in self.user_actions:
            self.chat_id = get_chat_id(self.event.user_id)

        if self.event_t == VkEventType.MESSAGE_NEW:
            if self.event.from_group:
                vid = self.event.group_id * (-1)
                peer = False
            else:
                vid = self.event.user_id
                peer = self.event.peer_id

            if peer:
                if peer >= 2000000000:
                    self.chat_id = get_chat_id(peer_id=peer)
                    # if message from user
                    if vid > 0:
                        user = get_vk_info(self.uid, vid, name=True)
                        if isinstance(user, str):
                            self.text += f"{user}:\n"
                        else:
                            self.text += f"{user['first_name']} {user['last_name']}:\n"
                    # if message from bot
                    else:
                        group = get_vk_info(self.uid, vid, name=True)
                        if isinstance(group, str):
                            self.text += f"{group}:\n"
                        else:
                            self.text += f"{group['name']}:\n"
                else:
                    self.chat_id = get_chat_id(vid)
            else:
                self.chat_id = get_chat_id(vid)

            self.text += self.event.text
            message_id = self.event.message_id

            if not self.chat_id:
                # Chat with bot
                self.chat_id = execute(f"select chat_id from chats where uid = {self.uid} and vchat_id = 0;")[0][0]

                # Getting user name
                try:
                    user_obj = get_vk_info(self.uid, vid, name=True)
                except IndexError:
                    user_obj = ''

                if isinstance(user_obj, str):
                    name = user_obj
                else:
                    # User chat
                    if 2000000000 > vid > 0:
                        name = f"{user_obj['first_name']} {user_obj['last_name']}"
                    else:
                        name = user_obj['name']

                text = f"{name}:\n"
                text += self.text
                self.text = "You have new message, create new chat to reply\n\n" + text
            attchs = self.event.attachments.values()

            if attchs:
                self.attachments_process(message_id)
            else:
                self.cont_attchs = False

    def attachments_process(self, message_id):
        self.extended_message = self.api.messages.getById(message_ids=message_id)['items'][0]
        attachments_from_msg = self.extended_message['attachments']

        if attachments_from_msg:
            self.cont_attchs = True

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

            elif atype == 'audio':
                audio = attach['audio']
                minutes = int(audio['duration'] / 60)
                seconds = audio['duration'] - (minutes * 60)

                audio_wrap = f"{audio['title']} -- {audio['artist']}\n"
                audio_wrap += f"♪ ———————————— {minutes}:{seconds}"
                url = audio_wrap

            elif atype == 'link':
                url = attach['link']['url']

            elif atype == 'graffiti':
                url = attach['graffiti']['url']

            elif atype == 'sticker':
                url = attach['sticker']['images'][2]['url']     # 256x256 sticker

            else:
                self.bot.send_message(chat_id=self.chat_id, text=f"Unsupported attachment '{atype}'.")
                self.cleaner()
                return

            self.attchs.append(url)
            counter += 1

        if self.extended_message['fwd_messages']:
            self.forwards_root = True

        self.attchs_count = counter

    def forwards_process(self, forwards, i=0):
        i += 1
        for forward in forwards:
            self.attchs.clear()
            self.cont_attchs = False
            self.text = ">" * i

            self.attachments_process(forward['id'])
            self.forwards_root = False
            vk_id = self.extended_message['from_id']

            # Load user name from memory

            vk_obj = get_vk_info(uid=self.uid, vk_chat_id=vk_id)
            # If user
            if isinstance(vk_obj, str):
                name = vk_obj
            elif 2000000000 > vk_id > 0:
                name = f" {vk_obj['first_name']} {vk_obj['last_name']}"
            # If chat
            elif vk_id > 2000000000:
                name = ' ' + vk_obj['items'][0]['chat_settings']['title']
            # If group
            else:
                name = ' ' + vk_obj['name']

            self.text += name

            timestamp = forward['date']
            time = datetime.fromtimestamp(timestamp)
            self.text += ": " + time.strftime("%H:%M %d.%m.%Y")

            if forward['text']:
                self.text += "\n" + forward['text']

            self.new_message()

            try:
                self.forwards_process(forward['fwd_messages'], i)
            except KeyError:
                pass

    def new_message(self):
        if self.cont_attchs:
            i = 0
            while i < self.attchs_count:
                if self.attchs_types[i] == 'photo':
                    self.attch_photo(i)

                if self.attchs_types[i] == 'audio_message':
                    self.attch_voice(i)

                if self.attchs_types[i] == 'video':
                    self.attch_video(i)

                if self.attchs_types[i] == 'doc':
                    self.attch_doc(i)

                if self.attchs_types[i] == 'audio':
                    self.attch_audio(i)

                if self.attchs_types[i] == 'link':
                    self.attch_link(i)

                if self.attchs_types[i] == 'graffiti':
                    self.attch_graffiti(i)

                if self.attchs_types[i] == 'sticker':
                    self.attch_sticker(i)

                i += 1
        else:
            try:
                self.bot.send_message(chat_id=self.chat_id, text=self.text)
            except BadRequest:          # Empty forward
                pass

        if self.forwards_root:
            self.forwards_process(self.extended_message['fwd_messages'])

    def attch_photo(self, index):
        if self.text:
            self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[index], caption=self.text)
        else:
            self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[index])

    def attch_voice(self, index):
        voice_url = self.attchs[index]
        self.bot.send_voice(chat_id=self.chat_id, voice=voice_url)

    def attch_video(self, index):
        video_url = self.attchs[index]
        if self.video_dur > 30:
            video_url = short_url(video_url)
            msg = self.text + '\n\nThis video is more than 30 seconds, so take url:\n' + video_url
            self.bot.send_message(chat_id=self.chat_id, text=msg)
            return

        if self.text:
            self.bot.send_video(chat_id=self.chat_id, video=video_url, caption=self.text)
        else:
            self.bot.send_video(chat_id=self.chat_id, video=video_url)

    def attch_doc(self, index):
        doc_url = self.attchs[index]

        if self.text:
            self.bot.send_document(chat_id=self.chat_id, document=doc_url, caption=self.text)
        else:
            self.bot.send_document(chat_id=self.chat_id, document=doc_url)

    def attch_audio(self, index):
        audio_wrap = self.attchs[index]
        text = self.text + '\n\n' + audio_wrap
        self.bot.send_message(chat_id=self.chat_id, text=text)

    def attch_link(self, index):
        text = self.text
        self.bot.send_message(chat_id=self.chat_id, text=text)

    def attch_graffiti(self, index):
        self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[index])

    def attch_sticker(self, index):
        self.bot.send_photo(chat_id=self.chat_id, photo=self.attchs[index])

    def user_online(self, online):
        description = self.bot.get_chat(chat_id=self.chat_id)['description'].split("\no")[0]
        if online:
            description += "\nonline 🌕"
        else:
            description += "\noffline 🌑"

        try:
            self.bot.set_chat_description(chat_id=self.chat_id, description=description)
        except BadRequest:
            return 0

    def user_typing(self):
        self.bot.send_chat_action(chat_id=self.chat_id, action=ChatAction.TYPING)

    def cleaner(self):
        self.good_event = False
        self.chat_id = None
        self.message_id = None
        self.extended_message = None
        self.text = ""
        self.attchs.clear()
        self.attchs_count = 0
        self.attchs_types.clear()
        self.forwards_root = False
        self.forwards.clear()
        self.cont_attchs = False
        self.video_dur = 0


def get_chat_id(vk_chat_id=None, peer_id=None):
    try:
        if peer_id:
            chat_id = execute(f"select chat_id from chats where peer_id = {peer_id};")[0][0]
        else:
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
