python telegram_bot/update_chats.py &
echo "\n\n---------- NEW LOG ENTRY `date` ----------\n\n" >> LOGS.log
python telegram_bot/bot.py >> LOGS.log