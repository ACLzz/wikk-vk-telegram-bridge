pipenv run python update_chats.py &
echo "\n\n---------- NEW LOG ENTRY `date` ----------\n\n" >> LOGS.log
pipenv run python bot.py >> LOGS.log
