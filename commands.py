from database.db import execute
from database.db_manager import gen_password

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest

from VK.main import oauth_link, login, get_api, get_conversations, send_message, get_vk_info
from VK.worker import create_worker
from secret import max_convs_per_page

from requests import get
from psycopg2 import errors

from os import remove
from PIL import Image

OAUTH, TOKEN = range(0, 2)
CONV = range(1000000000, 1000000001)


def start(update, context):
    uid = update.effective_user.id
    context.bot.send_message(chat_id=update.message.chat_id, text="Hello, i'm Soock!"
                                                                  "\nDo you want to sign in? Write /auth")
    execute(f"insert into logins (uid) values ({uid}) on conflict do nothing")


def unknown(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='Unknown command')


def start_auth(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f'Go to\n{oauth_link}\nAnd copy url after grant '
                                                                    f'privileges to bot')
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
    result = login(uid, token)

    if result == 2:
        # If login unsuccessful
        context.bot.send_message(chat_id=update.effective_chat.id, text='something went wrong, try again')
        return start_auth(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text='You have signed in!\nCreate new chat and add me')


def list_convs(update, context, page=1, prev=False):
    uid = update.effective_user.id
    api = get_api(uid)
    offset = (page-1)*max_convs_per_page
    keyboard = []

    convs = get_conversations(uid, api, offset=offset)

    i = 0
    # Generating inlineKeyboard with conversation list
    for conv in convs['items']:
        if i == 0 and page > 1:
            keyboard.append([InlineKeyboardButton('<- Previous Page', callback_data=f'prev_page,{page-1}')])

        ctype = conv['conversation']['peer']['type']
        oid = conv['conversation']['peer']['id']
        vk_obj = get_vk_info(uid, oid, [])
        # Getting name of vk object in list
        if ctype == 'user':
            name = f"{vk_obj['first_name']} {vk_obj['last_name']}"
        elif ctype == 'group':
            name = f"{vk_obj['name']}"
        else:
            name = "unknown"

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
        execute(f"insert into chats (chat_id, uid, vchat_id) values ({chat_id}, {uid}, {vk_chat_id})")
    except errors.UniqueViolation:
        # If group already registred in db
        # Change vk chat stream for telegram group
        execute(f"update chats set vchat_id = {vk_chat_id} where chat_id = {chat_id}")

    update_conv(update, context)    # Update conversation information like in VK

    create_worker(context.bot, uid)
    context.bot.send_message(chat_id=update.effective_chat.id, text='Good, your chat now is active, '
                                                                    'say hello to your friend)')


def update_conv(update, context):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id

    vk_chat_id = execute(f"select vchat_id from chats where chat_id = {chat_id}")[0][0]
    try:
        update_group_info(uid, context, vk_chat_id, chat_id)
    except BadRequest:
        # If bot isn't group administrator
        context.bot.send_message(chat_id=update.effective_chat.id, text='Make bot administrator to get all features. '
                                                                        'And then try /grp_upd')


def update_group_info(uid, context, vk_chat_id, chat_id):
    if vk_chat_id > 0:
        user = get_vk_info(uid, vk_chat_id, ['status', 'photo_200'])
        title = f"{user['first_name']} {user['last_name']}"
        photo_url = user['photo_200']
        description = user['status']
    else:
        group = get_vk_info(uid, vk_chat_id, ['status', 'description'])
        title = group['name']
        photo_url = group['photo_200']
        description = f"{group['status']}\n\n{group['description']}"

    change_group_photo(context, chat_id, photo_url)
    try:
        context.bot.set_chat_title(chat_id=chat_id, title=title)
    except BadRequest:
        # If title the same
        pass

    try:
        context.bot.set_chat_description(chat_id=chat_id, description=description)
    except BadRequest:
        # If description the same
        pass


def change_group_photo(context, chat_id, photo_url):
    photo = get(photo_url).content
    # Creating temporary img file
    filename = gen_password(10) + ".png"
    with open(filename, "wb") as f:
        f.write(photo)
    # Convert it to png
    im = Image.open(filename)
    im.save(filename, "PNG")

    p = open(filename, "rb")
    context.bot.set_chat_photo(chat_id=chat_id, photo=p)
    p.close()
    remove(filename)


def send_msg(update, context):
    uid = update.effective_user.id
    msg = update.message.text
    chat_id = update.effective_chat.id

    send_message(uid, msg, chat_id)


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
