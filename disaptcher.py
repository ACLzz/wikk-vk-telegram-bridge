from telegram import Bot
from telegram.ext import Updater
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, Filters

from secret import get_token

from commands import start, start_auth, get_oauth_token, unknown, callback, list_convs, send_msg
from commands import TOKEN

from database.db import execute
from VK.worker import create_worker

bot = Bot(token=get_token())
updater = Updater(token=get_token(), use_context=True)
dp = updater.dispatcher

start_handler = CommandHandler('start', start)
unknown_handler = MessageHandler(Filters.command, unknown)
callback_handler = CallbackQueryHandler(callback)
login_handler = ConversationHandler(entry_points=[CommandHandler('auth', start_auth)],
                                    states={
                                        TOKEN: [MessageHandler(Filters.text, get_oauth_token)],
                                    },
                                    fallbacks={})
list_convs_handler = CommandHandler('lc', list_convs)
send_msg_handler = MessageHandler(Filters.group, send_msg)


def init_handlers():
    dp.add_handler(start_handler)
    dp.add_handler(login_handler)
    dp.add_handler(list_convs_handler)
    dp.add_handler(send_msg_handler)

    dp.add_handler(callback_handler)
    dp.add_handler(unknown_handler)


def init_workers():
    conversations = execute("select uid from chats;")
    for uid in conversations:
        create_worker(bot, uid[0])
