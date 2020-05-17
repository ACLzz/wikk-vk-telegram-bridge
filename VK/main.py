from vk_api import VkApi, exceptions

from requests.exceptions import ConnectionError

from database.db import execute
from secret import max_convs_per_page

import sys
from random import randint


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
    api = get_api(uid, token, new=True)
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
        api = get_api(uid)
    convs = api.messages.getConversations(count=max_convs_per_page, offset=offset)
    return convs


def send_message(uid, msg, chat_id):
    try:
        api = get_api(uid)
    except IndexError:
        return 0

    # Generate message id like in vk api
    msg_id = randint(1, 9223372036854775700)
    try:
        vchat_id = execute(f"select vchat_id from chats where chat_id = {chat_id}")[0][0]
    except IndexError:
        # If telegram group not binded to vk chat stream
        return

    api.messages.send(random_id=msg_id, message=msg, peer_id=vchat_id)


def get_vk_info(uid, vk_chat_id, fields=None):
    api = get_api(uid)

    if vk_chat_id > 0:
        # If chat with user
        obj = api.users.get(user_ids=[vk_chat_id], fields=fields)[0]
    else:
        # If chat with bot
        obj = api.groups.getById(group_id=[vk_chat_id*(-1)], fields=fields)[0]

    return obj
