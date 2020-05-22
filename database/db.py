from psycopg2 import connect, errors
import sys

sys.path.append("..")
from secret import get_db_pass


def conn(db=None):
    login = 'zizzwejopwyskk'
    host = 'ec2-54-246-90-10.eu-west-1.compute.amazonaws.com'
    port = '5432'
    if db is None:
        db = 'd7iteodg9f7sr3'
    password = 'd0c709cd8ad20b99c7b65d9a6313e6db6db446000121da12e28d6cb2bd4485a5'

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
