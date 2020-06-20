#!/bin/python
from psycopg2 import connect, errors
from string import ascii_letters, punctuation
from random import choice
import sys
from os import environ

sys.path.append("..")

from wikk_bot.secret import get_db_info
mode = environ.get("MODE")


def gen_password(length=25):
    numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 0]

    all_chars = []
    all_chars.extend(numbers)
    all_chars.extend(ascii_letters)
    all_chars.extend(punctuation)
    all_chars.remove("'")
    all_chars.remove("/")

    password = ''.join(str(choice(all_chars)) for i in range(length))

    return password


def dconnect(db=None, username=None):
    db_info = get_db_info()
    if db is None:
        db = db_info['db']

    if username is None:
        username = db_info['username']
    c = connect(database=db, user=username, password=db_info['password'],
                host=db_info['host'], port=db_info['port'])
    c.autocommit = True
    return c


def execute(c, query):
    cur = c.cursor()
    try:
        cur.execute(query)
    except errors.DuplicateDatabase:
        pass
    except errors.DuplicateTable:
        pass
    cur.close()


def create_user(username=None):
    db_info = get_db_info()
    if username is None:
        username = db_info['username']

    c = dconnect(db='postgres', username='postgres')

    try:
        execute(c, f"CREATE USER {username} WITH ENCRYPTED PASSWORD '{db_info['password']}';")
    except errors.DuplicateObject:
        pass
    try:
        execute(c, f"create database {username};""")
    except errors.DuplicateDatabase:
        pass

    execute(c, f"alter database {username} owner to {username};")
    execute(c, f"ALTER USER {username} CREATEDB;")

    c.close()
    print(f"User {username} created successfully")


def create_database():
    db_info = get_db_info()
    c = dconnect(username='postgres', db='postgres')
    execute(c, f"create database {db_info['db']};")
    execute(c, f"alter database {db_info['db']} owner to {db_info['username']};")
    c.close()

    c = dconnect()
    execute(c, "create table logins (uid INT PRIMARY KEY, token VARCHAR(85));")
    execute(c, "create table chats (chat_id INT PRIMARY KEY, uid INT REFERENCES logins, vchat_id INT, peer_id INT);")
    execute(c, "create table names (oid INT PRIMARY KEY, name VARCHAR(128));")
    c.close()
    print("Database created successfully")


def clear():
    c = dconnect(username='postgres', db='postgres')
    db_info = get_db_info()

    if mode == 'dev':
        try:
            execute(c, f"drop database {db_info['db']};")
            execute(c, f"drop database {db_info['username']};")
        except errors.InvalidCatalogName:
            pass
        try:
            execute(c, f"drop user {db_info['username']};")
        except errors.UndefinedObject:
            pass
    else:
        try:
            execute(c, 'drop table chats')
        except errors.UndefinedTable:
            pass
        try:
            execute(c, 'drop table logins;')
        except errors.UndefinedTable:
            pass
        try:
            execute(c, 'drop table names;')
        except errors.UndefinedTable:
            pass

    c.close()
    print("Cleaning finished")


def pr_help():
    print(f"""
    Usage: {sys.argv[0]} [all | cr-user | cr-dbs | clean] ARGUMENTS...
    """)


if __name__ == "__main__":
    args_cnt = len(sys.argv)
    if args_cnt == 1:
        pr_help()
        exit(0)

    act = sys.argv[1]
    if act == 'cr-user':
        if args_cnt > 2:
            create_user(sys.argv[2])
        else:
            create_user()
    elif act == 'cr-dbs':
        create_database()
    elif act == 'clean':
        clear()
    elif act == 'all':
        if mode == 'dev':
            if args_cnt > 2:
                create_user(sys.argv[2])
            else:
                create_user()

        create_database()
    else:
        pr_help()
