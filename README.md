# wikk-vk-telegram-bot
## Used technologies:
- python-telegram-bot-api : as telegram bot API base
- vk_api by python273     : as vk API lib
- PostgreSQL              : as database
- Heroku                  : as hosting

## How to use on you machine
1) Run `./set_up.sh` to setup enivornment <br/>
2) Then run `while IFS= read -r line; do export $line; done < env_vars.txt` to setup environment variables <br/><br/>
To run bot use `./start.sh`

## Configuration
### Database
You can specify custom database, username, host, port and password in secrets.json

### Must-have environment variables:
All environment variables you can edit in `env_vars.txt`.<br/>
Update-workers run every UPDATE_INTERVAL to update chats' photo and description. They are running from FROM hour to TO hour. <br/>
Example: FROM=12 TO=4 UPDATE_INTERVAL=25. Updates will be every 25 minutes from 12:00 to 04:00. From 04:00 to 12:00 worker will sleep. <br/>
You can specify FROM=0 TO=0 and worker will never sleep.

- MODE              : `dev` for running on local machine or `prod` for running on heroku
- FROM              : Update-worker start hour
- TO                : Update-worker end hour
- UPDATE_INTERVAL   : Update-worker update chats interval in minutes
- POOL_WORKERS      : Count of update-workers that can run in one time (after update interval)
- REBRAND           : Rebrand API key
