from telegram import Bot
from telegram.ext import Updater
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, Filters

from telegram_bot.secret import get_token

from telegram_bot.commands import start, start_auth, get_oauth_token, unknown, callback, list_convs, send_msg, update_conv, \
    service_msg_cleaner, new_chat, user_leave, status_messages_ignore
from telegram_bot.commands import TOKEN

from database.db import execute
from VK.worker import create_worker

# ####### Telegram api objects ####### #
bot = Bot(token=get_token())
updater = Updater(token=get_token(), use_context=True)
dp = updater.dispatcher

# ####### Handlers ####### #
start_handler = CommandHandler('start', start)
unknown_handler = MessageHandler(Filters.command, unknown)
callback_handler = CallbackQueryHandler(callback)
status_messages_ignore_handler = MessageHandler(Filters.status_update, status_messages_ignore)
user_leave_handler = MessageHandler(Filters.status_update.left_chat_member, user_leave)
new_chat_handler = MessageHandler(Filters.status_update.chat_created, new_chat)
update_conv_handler = CommandHandler("grp_upd", update_conv)
chat_photo_update_handler = MessageHandler(Filters.status_update.new_chat_photo, service_msg_cleaner)
chat_title_update_handler = MessageHandler(Filters.status_update.new_chat_title, service_msg_cleaner)
send_msg_handler = MessageHandler(Filters.group, send_msg)
list_convs_handler = CommandHandler('lc', list_convs)
login_handler = ConversationHandler(entry_points=[CommandHandler('auth', start_auth)],
                                    states={
                                        TOKEN: [MessageHandler(Filters.text, get_oauth_token)],
                                    },
                                    fallbacks={})


def init_handlers():
    dp.add_handler(new_chat_handler)
    dp.add_handler(start_handler)
    dp.add_handler(login_handler)
    dp.add_handler(list_convs_handler)
    dp.add_handler(update_conv_handler)
    dp.add_handler(chat_photo_update_handler)
    dp.add_handler(chat_title_update_handler)
    dp.add_handler(user_leave_handler)

    dp.add_handler(status_messages_ignore_handler)
    dp.add_handler(send_msg_handler)
    dp.add_handler(callback_handler)
    dp.add_handler(unknown_handler)


def init_workers():
    conversations = execute("select distinct uid from chats;")
    for uid in conversations:
        create_worker(bot, uid[0])
