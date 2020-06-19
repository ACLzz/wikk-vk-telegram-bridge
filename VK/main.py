from vk_api import VkApi, exceptions, VkUpload

from requests.exceptions import ConnectionError

from database.db import execute
from telegram_bot.secret import max_convs_per_page

import sys
from random import randint
from os import remove

import logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
log = logging

sys.path.append('..')
from telegram_bot.secret import get_proxy, use_proxy

PHONE, PASSWORD, LOGIN, CAPTCHA = range(0, 4)
oauth_link = "https://rebrand.ly/afvs861"
apis = {}


def login(uid, token, bot):
    api = get_api(uid, token, new=True)
    try:
        # Check for successful login
        api.messages.getConversations(count=1)
    except ConnectionError:
        # Proxy error
        log.error("Bot don't has access to VK.com")
        return 1
    except exceptions.ApiError:
        # Unsuccessful login
        return 2

    chats = execute(f"select chat_id from chats where uid = {uid} and vchat_id != 0;")
    if chats:
        for chat in chats:
            bot.send_message(chat_id=chat[0], text="This chat has been deactivated because"
                                                   " you've logout from your account.\nUse /lc to choose new one")
    execute(f"delete from chats where uid = {uid} and vchat_id != 0;")

    execute(f"update logins set token = '{token}' where uid = {uid}")
    # Adding api object to memory
    apis[f"{uid}"] = api

    return 0


def get_api(uid, token=None, new=False):
    # Search for api object already in memory
    if f'{uid}' in apis and not new:
        return apis[f'{uid}']

    session = get_session(uid, token=token)
    api = session.get_api()

    apis[f'{uid}'] = api
    return api


def get_session(uid, token=None):
    if token is None:
        token = execute(f"select token from logins where uid = {uid}")

    if not token:
        # If user not authenticated
        raise IndexError

    session = VkApi(token=token, api_version='5.103')

    if use_proxy:
        # Add proxy if proxy enabled
        proxy = get_proxy()
        session.http.proxies = {"http": f"http://{proxy}",
                                "https": f"https://{proxy}",
                                "ftp": f"ftp://{proxy}"}
    return session


def get_conversations(uid, api=None, offset=0):
    if api is None:
        api = get_api(uid)
    convs = api.messages.getConversations(count=max_convs_per_page, offset=offset)
    return convs


def send_message(uid, chat_id, msg=None, photo=None, documents=None, audio=None, voice=None, video=None):
    try:
        session = get_session(uid)
        api = get_api(uid)
    except IndexError:
        return 0

    # Generate message id like in vk api
    msg_id = randint(1, 9223372036854775700)
    try:
        vchat_id = execute(f"select vchat_id from chats where chat_id = {chat_id}")[0][0]
        # if chat is conference
        if vchat_id is None:
            vchat_id = execute(f"select peer_id from chats where chat_id = {chat_id}")[0][0]
    except IndexError:
        # If telegram group not binded to vk chat stream
        return

    attachments = []
    if photo or documents or audio or voice or video:
        if photo:
            attach = photo
        elif documents:
            attach = documents
        elif audio:
            attach = audio
        elif voice:
            attach = voice
        elif video:
            attach = video
        else:
            attach = None

        uploader = VkUpload(session)
        attach_file = attach.get_file().download()
        attach_file = open(attach_file, 'rb')
        file_name = attach_file.name

        if photo:
            upload_response = uploader.photo_messages(photos=attach_file, peer_id=vchat_id)
            for file in upload_response:
                attachments.append(f"photo{file['owner_id']}_{file['id']}")

        if voice:
            upload_response = uploader.audio_message(audio=attach_file, peer_id=vchat_id)
            audio = upload_response['audio_message']
            attachments.append(f"audio_message{audio['owner_id']}_{audio['id']}")

        if documents:
            upload_response = uploader.document_message(attach_file, peer_id=vchat_id)
            doc = upload_response['doc']
            attachments.append(f"doc{doc['owner_id']}_{doc['id']}")

        if video:
            video = uploader.video(attach_file, is_private=True)
            attachments.append(f"video{video['owner_id']}_{video['video_id']}")

        attach_file.close()
        remove(file_name)

        attachments = ','.join(attachments)

    if msg is not None:
        api.messages.send(random_id=msg_id, message=msg, peer_id=vchat_id, attachment=attachments)
    else:
        api.messages.send(random_id=msg_id, peer_id=vchat_id, attachment=attachments)

    api.account.setOffline()


def get_vk_info(uid, vk_chat_id, fields=None, name=False):
    api = get_api(uid)
    if name:
        query = f"select name from names where oid = {vk_chat_id}"
        db_resp = execute(query)
        if db_resp:
            return db_resp[0]

    if 2000000000 > vk_chat_id > 0:
        # If chat with user
        obj = api.users.get(user_ids=[vk_chat_id], fields=fields)[0]
    elif vk_chat_id >= 2000000000:
        obj = api.messages.getConversationsById(peer_ids=[vk_chat_id])['items'][0]
        print(obj)
    else:
        # If chat with bot
        obj = api.groups.getById(group_id=[vk_chat_id*(-1)], fields=fields)[0]

    return obj
