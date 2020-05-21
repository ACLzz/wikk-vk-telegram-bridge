from vk_api import VkApi, exceptions, VkUpload

from requests.exceptions import ConnectionError

from database.db import execute
from secret import max_convs_per_page

import sys
from random import randint
from os import remove


import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
log = logging

sys.path.append('..')
from secret import get_proxy, use_proxy

PHONE, PASSWORD, LOGIN, CAPTCHA = range(0, 4)
oauth_link = "http://cuterme.herokuapp.com/lig6r"
apis = {}


def login(uid, token):
    api = get_api(uid, token, new=True, proxy=use_proxy)
    try:
        # Check for successful login
        api.messages.getConversations(count=1)
    except ConnectionError:
        # Proxy error
        log.error("Bot don't has access to VK.com")
        pass
    except exceptions.ApiError:
        # Unsuccessful login
        return 2

    execute(f"update logins set token = '{token}' where uid = {uid}")
    # Adding api object to memory
    apis[f"{uid}"] = api

    return 0


def get_api(uid, token=None, new=False, proxy=use_proxy):
    # Search for api object already in memory
    if f'{uid}' in apis and not new:
        return apis[f'{uid}']

    session = get_session(uid, token=token, proxy=proxy)
    api = session.get_api()

    apis[f'{uid}'] = api
    return api


def get_session(uid, token=None, proxy=True):
    if token is None:
        token = execute(f"select token from logins where uid = {uid}")

    if not token:
        # If user not authenticated
        raise IndexError

    session = VkApi(token=token)

    if proxy:
        # Add proxy if proxy enabled
        proxy = get_proxy()
        session.http.proxies = {"http": f"http://{proxy}",
                                "https": f"https://{proxy}",
                                "ftp": f"ftp://{proxy}"}
    return session


def get_conversations(uid, api=None, offset=0):
    if api is None:
        api = get_api(uid, proxy=use_proxy)
    convs = api.messages.getConversations(count=max_convs_per_page, offset=offset)
    return convs


def send_message(uid, chat_id, msg=None, photo=None, documents=None, audio=None, voice=None):
    try:
        session = get_session(uid, proxy=use_proxy)
        api = get_api(uid, proxy=use_proxy)
    except IndexError:
        return 0

    # Generate message id like in vk api
    msg_id = randint(1, 9223372036854775700)
    try:
        vchat_id = execute(f"select vchat_id from chats where chat_id = {chat_id}")[0][0]
    except IndexError:
        # If telegram group not binded to vk chat stream
        return

    attachments = []
    if photo or documents or audio or voice:
        uploader = VkUpload(session)

        if photo:
            photo_file = photo.get_file().download()
            photo_file = open(photo_file, 'rb')
            file_name = photo_file.name

            upload_response = uploader.photo_messages(photos=photo_file, peer_id=vchat_id)
            for file in upload_response:
                attachments.append(f"photo{file['owner_id']}_{file['id']}")

            photo_file.close()
            remove(file_name)

        if voice:
            voice_file = voice.get_file().download()
            voice_file = open(voice_file, 'rb')
            file_name = voice_file.name

            upload_response = uploader.audio_message(audio=voice_file, peer_id=vchat_id)
            audio = upload_response['audio_message']
            attachments.append(f"audio_message{audio['owner_id']}_{audio['id']}")

            voice_file.close()
            remove(file_name)

        attachments = ','.join(attachments)

    if msg is not None:
        api.messages.send(random_id=msg_id, message=msg, peer_id=vchat_id, attachment=attachments)
    else:
        api.messages.send(random_id=msg_id, peer_id=vchat_id, attachment=attachments)

    api.account.setOffline()


def get_vk_info(uid, vk_chat_id, fields=None):
    api = get_api(uid, proxy=use_proxy)

    if vk_chat_id > 0:
        # If chat with user
        obj = api.users.get(user_ids=[vk_chat_id], fields=fields)[0]
    else:
        # If chat with bot
        obj = api.groups.getById(group_id=[vk_chat_id*(-1)], fields=fields)[0]

    return obj
