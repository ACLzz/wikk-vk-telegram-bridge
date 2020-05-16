from psycopg2 import connect, errors
import sys

sys.path.append("..")
from secret import get_db_pass


def conn(db=None):
    login = 'soock'
    host = '127.0.0.1'
    port = '5432'
    if db is None:
        db = 'soock_logins'
    password = get_db_pass(login)

    c = connect(database=db, user=login, password=password, host=host, port=port)
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
