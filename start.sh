echo >> LOGS.log
echo >> LOGS.log
echo "---------- NEW LOG ENTRY `date` ----------" >> LOGS.log

pipenv run python update_chats.py &
pipenv run python bot.py
