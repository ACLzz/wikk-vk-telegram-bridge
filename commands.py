from database.db import execute
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from VK.main import oauth_link, login, get_api, get_conversations
from VK.worker import create_worker

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
    for part in url.split("="):
        if found:
            token = part.split("&")[0]
            break
        if "access_token" in part:
            found = True

    if token is None:
        return TOKEN
    result = login(uid, token)

    if result == 2:
        context.bot.send_message(chat_id=update.effective_chat.id, text='something went wrong, try again')
        return start_auth(update, context)

    context.bot.send_message(chat_id=update.effective_chat.id, text='You have signed in!\nCreate new chat and add me')


def list_convs(update, context, page=1, prev=False):
    uid = update.effective_user.id
    api = get_api(uid)
    max_convs_per_page = 5
    offset = (page-1)*max_convs_per_page
    convs = get_conversations(uid, api, offset=offset)
    keyboard = []

    i = 0
    for conv in convs['items']:
        if i == 0 and page > 1:
            keyboard.append([InlineKeyboardButton('<- Previous Page', callback_data=f'prev_page,{page-1}')])

        ctype = conv['conversation']['peer']['type']
        oid = conv['conversation']['peer']['id']
        if ctype == 'user':
            user = api.users.get(user_ids=[oid])[0]
            name = f"{user['first_name']} {user['last_name']}"
        elif ctype == 'group':
            group = api.groups.getById(group_id=[oid*(-1)])[0]
            name = f"{group['name']}"
        else:
            name = "unknown"

        keyboard.append([InlineKeyboardButton(f"{name}", callback_data=str(CONV) + str(oid))])
        i += 1
        if i == max_convs_per_page:
            keyboard.append([InlineKeyboardButton('Next Page ->', callback_data=f'next_page,{page+1}')])
            i = 0
            break

    markup = InlineKeyboardMarkup(keyboard)
    if page > 1 or prev:
        context.bot.edit_message_reply_markup(chat_id=update.effective_chat.id,
                                              message_id=update.effective_message.message_id, reply_markup=markup)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text='Choose conversation to start',
                                 reply_markup=markup)


def start_conv(update, context, vk_chat_id):
    uid = update.effective_user.id
    chat_id = update.effective_chat.id
    execute(f"insert into chats (chat_id, uid, vchat_id) values ({chat_id}, {uid}, {vk_chat_id}) "
            "on conflict do nothing;")

    create_worker(context.bot, uid)
    context.bot.send_message(chat_id=update.effective_chat.id, text='Good, your chat now is active, '
                                                                    'say hello to your friend)')


def callback(update, context):
    query = update.callback_query
    data = query.data

    if str(CONV) in data:
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
