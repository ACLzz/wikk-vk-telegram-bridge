from psycopg2 import connect, errors
from string import ascii_letters, punctuation
from random import choice
import sys

sys.path.append("..")

from secret import get_db_pass, write_db_pass


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


def dconnect(username='wikk', db=None):
    host = '127.0.0.1'
    port = '5432'

    password = get_db_pass(username)
    if db is None:
        db = username

    c = connect(database=db, user=username, password=password, host=host, port=port)
    c.autocommit = True
    return c


def execute(c, query):
    cur = c.cursor()
    try:
        cur.execute(query)
    except errors.DuplicateDatabase:
        pass
    cur.close()


def create_user(username='wikk'):
    password = gen_password()
    write_db_pass(username, password)

    c = dconnect('postgres')

    try:
        execute(c, f"CREATE USER {username} WITH ENCRYPTED PASSWORD '{password}';")
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
    c = dconnect()
    execute(c, "create database wikk_logins;")
    c.close()

    c = dconnect(db='wikk_logins')
    execute(c, "create table logins (uid INT PRIMARY KEY, token VARCHAR(85));")
    execute(c, "create table chats (chat_id INT PRIMARY KEY, uid INT REFERENCES logins, vchat_id INT);")
    c.close()
    print("Database created successfully")


def clear():
    c = dconnect('postgres')

    try:
        execute(c, "drop database wikk;")
    except errors.InvalidCatalogName:
        pass
    try:
        execute(c, "drop database wikk_logins;")
    except errors.InvalidCatalogName:
        pass
    try:
        execute(c, "drop user wikk;")
    except errors.UndefinedObject:
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
        if args_cnt > 2:
            create_user(sys.argv[2])
        else:
            create_user()

        create_database()
    else:
        pr_help()
