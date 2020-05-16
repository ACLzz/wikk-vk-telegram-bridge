from telegram.ext import Updater
from telegram.ext import CommandHandler, ConversationHandler, MessageHandler, CallbackQueryHandler, Filters

from secret import get_token

from commands import start, start_auth, get_oauth_token, unknown, callback
from commands import TOKEN

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


def init_handlers():
    dp.add_handler(start_handler)
    dp.add_handler(login_handler)
    dp.add_handler(unknown_handler)
    dp.add_handler(callback_handler)
