from database.db import execute
from database.db_manager import gen_password

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from VK.main import oauth_link, login, get_api, get_conversations, send_message, get_vk_info
from VK.worker import create_worker
from telegram_bot.secret import max_convs_per_page

from requests import get
from psycopg2 import errors

from os import remove
from PIL import Image

OAUTH, TOKEN = range(0, 2)
CONV = range(1000000000, 1000000001)


# ############# auth ############# #
def start_auth(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f'Go to\n{oauth_link}\nAnd copy url, after grant '
                                                                    f'privileges, to bot')
    return TOKEN


def get_oauth_token(update, context):
    url = update.message.text
    uid = update.effective_user.id

    found = False
    token = None
    # Searching for token in url
    for part in url.split("="):
        if found:
            token = part.split("&")[0]
            break
        if "access_token" in part:
            found = True

    if token is None:
        return TOKEN
    # try to login
    result = login(uid, token, context.bot)

    if result == 2:
        # If login unsuccessful
        context.bot.send_message(chat_id=update.effective_chat.id, text='something went wrong, try again')
        return start_auth(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text='You have signed in!\nCreate new chat and add me')


# ############# conversation ############# #
def list_convs(update, context, page=1, prev=False):
    uid = update.effective_user.id
    try:
        api = get_api(uid)
    except IndexError:
        return 0
    offset = (page-1)*max_convs_per_page
    keyboard = []

    convs = get_conversations(uid, api, offset=offset)

    i = 0
    # Generating inlineKeyboard with conversation list
    for conv in convs['items']:
        if i == 0 and page > 1:
            keyboard.append([InlineKeyboardButton('<- Previous Page', callback_data=f'prev_page,{page-1}')])

        ctype = conv['conversation']['peer']['type']
        oid = conv['conversation']['peer']['id']            # Peer id
        vk_obj = get_vk_info(uid, oid, [], name=True)
        # Getting name of vk object in list
        if isinstance(vk_obj, str):
            name = vk_obj
        elif ctype == 'user':
            name = f"{vk_obj['first_name']} {vk_obj['last_name']}"
        elif ctype == 'group':
            name = f"{vk_obj['name']}"
        elif ctype == 'chat':
            name = vk_obj['chat_settings']['title']
        else:
            name = 'Unknown'

        # Add name of vk object into database
        query = f"insert into names (oid, name) values ({oid}, '{name}') on conflict do nothing;"
        execute(query)

        keyboard.append([InlineKeyboardButton(f"{name}", callback_data=str(CONV) + str(oid))])
        i += 1
        if i == max_convs_per_page:
            # If in keyboard max conversation buttons
            keyboard.append([InlineKeyboardButton('Next Page ->', callback_data=f'next_page,{page+1}')])
            i = 0
            break

    markup = InlineKeyboardMarkup(keyboard)
    if page > 1 or prev:
        # Update old keyboard
        context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                              message_id=update.effective_message.message_id, reply_markup=markup)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text='Choose conversation to start',
                                 reply_markup=markup)


def start_conv(update, context, vk_chat_id):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    try:
        if vk_chat_id >= 2000000000:
            execute(f"insert into chats (chat_id, uid, peer_id) values ({chat_id}, {uid}, {vk_chat_id})")
        else:
            execute(f"insert into chats (chat_id, uid, vchat_id) values ({chat_id}, {uid}, {vk_chat_id})")
    except errors.UniqueViolation:
        # If group already registred in db
        # Change vk chat stream for telegram group
        if vk_chat_id >= 2000000000:
            execute(f"update chats set peer_id = {vk_chat_id} where chat_id = {chat_id}")
        else:
            execute(f"update chats set vchat_id = {vk_chat_id} where chat_id = {chat_id}")

    update_conv(update, context)    # Update conversation information like in VK

    create_worker(context.bot, uid)
    context.bot.send_message(chat_id=update.effective_chat.id, text='Good, your chat now is active, '
                                                                    'say hello to your friend)')


def update_conv(update, context):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    vk_chat_id = execute(f"select vchat_id from chats where chat_id = {chat_id}")[0][0]
    # if chat is conference
    if vk_chat_id is None:
        vk_chat_id = execute(f"select peer_id from chats where chat_id = {chat_id}")[0][0]

    try:
        update_group_info(uid, context.bot, vk_chat_id, chat_id)
    except BadRequest:
        # If bot isn't group administrator
        context.bot.send_message(chat_id=update.effective_chat.id, text='Make bot administrator to get all features. '
                                                                        'And then try /grp_upd')


def update_group_info(uid, bot, vk_chat_id, chat_id):
    # User chat
    if 2000000000 > vk_chat_id > 0:
        try:
            user = get_vk_info(uid, vk_chat_id, ['status', 'photo_200', 'online'])
        except IndexError:
            return 0
        description = user['status']

        title = f"{user['first_name']} {user['last_name']}"
        if user['online']:
            description += "\nonline 🌕"
        else:
            description += "\noffline 🌑"

        photo_url = user['photo_200']
    elif vk_chat_id >= 2000000000:
        try:
            conference = get_vk_info(uid, vk_chat_id)["chat_settings"]
        except IndexError:
            return 0

        title = conference['title']
        photo_url = conference['photo']['photo_200']
        description = f'{conference["members_count"]} members'
    else:
        try:
            group = get_vk_info(uid, vk_chat_id, ['status', 'description'])
        except IndexError:
            return 0

        title = group['name']
        photo_url = group['photo_200']
        description = f"{group['status']}\n\n{group['description']}"

    change_group_photo(bot, chat_id, photo_url)
    change_group_title(bot, chat_id, title)
    change_group_description(bot, chat_id, description)


def change_group_photo(bot, chat_id, photo_url):
    photo = get(photo_url).content
    # Creating temporary img file
    filename = gen_password(10) + ".png"
    with open(filename, "wb") as f:
        f.write(photo)
    # Convert it to png
    im = Image.open(filename)
    im.save(filename, "PNG")

    p = open(filename, "rb")
    bot.set_chat_photo(chat_id=chat_id, photo=p)
    p.close()
    remove(filename)


def change_group_title(bot, chat_id, title):
    try:
        bot.set_chat_title(chat_id=chat_id, title=title)
    except BadRequest:
        # If title the same
        return


def change_group_description(bot, chat_id, description):
    try:
        bot.set_chat_description(chat_id=chat_id, description=description)
    except BadRequest:
        # If description the same
        return


# ############# VK ############# #
def send_msg(update, context):
    uid = update.effective_user.id
    try:
        msg = update.message.text
    except AttributeError:
        # If action is message edit
        return
    photo = update.message.photo
    video = update.message.video
    documents = update.message.document
    audio = update.message.audio
    voice = update.message.voice
    sticker = update.message.sticker
    chat_id = update.effective_chat.id
    print(sticker)

    if msg is None:
        msg = update.message.caption
    if photo:
        photo = photo[-1]

    send_message(uid, chat_id, msg=msg, photo=photo, documents=documents,
                 audio=audio, voice=voice, video=video, sticker=sticker)


# ############# service ############# #
def start(update, context):
    uid = update.effective_user.id
    chat_id = update.message.chat_id
    context.bot.send_message(chat_id=update.message.chat_id, text="Hello, i'm Wikk!"
                                                                  "\nDo you want to sign in? Write /auth")
    execute(f"insert into logins (uid) values ({uid}) on conflict do nothing")
    # Insert chat with bot
    execute(f"insert into chats (uid, chat_id, vchat_id) values ({uid}, {chat_id}, 0) on conflict do nothing")


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='Unknown command')


def service_msg_cleaner(update, context):
    message_id = update.effective_message.message_id
    chat_id = update.effective_chat.id
    context.bot.deleteMessage(chat_id=chat_id, message_id=message_id)


def new_chat(update, context):
    greeting = "You need to make me admin, i can update info about your friends and change their online status.\n\n" \
               "After you've made me admin, type /lc for list conversations and choose conversation with your friend."
    context.bot.send_message(chat_id=update.effective_chat.id, text=greeting)


def user_leave(update, context):
    uid = update.effective_user.id
    chat_id = update.message.chat_id
    execute(f"delete from chats where uid = {uid} and chat_id = {chat_id}")


def status_messages_ignore(update, context):
    pass


def callback(update, context):
    query = update.callback_query
    data = query.data

    if str(CONV) in data:
        # User binding vk chat stream to telegram group
        conv = data[len(str(CONV)):]
        start_conv(update, context, int(conv))
    elif 'next_page' in data:
        data = data.split(",")[1:]
        list_convs(update, context, page=int(data[0]))
    elif 'prev_page' in data:
        data = data.split(",")[1:]
        list_convs(update, context, page=int(data[0]), prev=True)
    else:
        unknown(update, context)
