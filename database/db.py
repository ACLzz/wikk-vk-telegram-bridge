from psycopg2 import connect, errors
import sys

sys.path.append("..")
from wikk_bot.secret import get_db_info


def conn(db=None):
    db_info = get_db_info()
    c = connect(database=db_info['db'], user=db_info['username'], password=db_info['password'],
                host=db_info['host'], port=db_info['port'])
    c.autocommit = True
    return c


def execute(query, c=None):
    if c is None:
        c = conn()
    cur = c.cursor()
    cur.execute(query)
    try:
        resp = cur.fetchall()
    except errors.ProgrammingError:
        resp = None
    cur.close()
    return resp


def get_token(uid):
    c = conn()
    cur = c.cursor()
    cur.execute(f'select token from logins where uid = {uid}')
    try:
        resp = cur.fetchone()
    except errors.ProgrammingError:
        resp = None
    cur.close()
    return resp
