pipenv run python update_chats.py &
echo >> LOGS.log
echo >> LOGS.log
echo "---------- NEW LOG ENTRY `date` ----------" >> LOGS.log
pipenv run python bot.py
