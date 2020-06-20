from json import loads, dumps
import os
from requests import get

secrets_path = '/'.join(os.path.realpath(__file__).split('/')[:-2]) + '/secrets.json'
proxies_path = '/'.join(os.path.realpath(__file__).split('/')[:-2]) + '/http_proxies.txt'

proxies = []
max_convs_per_page = 5


def get_secrets():
    with open(secrets_path, 'r') as f:
        secrets = loads(f.read())
    return secrets


def get_token():
    return get_secrets()['token']


def get_db_info():
    try:
        return get_secrets()['db']
    except KeyError:
        return None


def load_proxies():
    with open(proxies_path, 'r') as f:
        for line in f.readlines():
            proxies.append(line)


def check_proxy(proxy):
    proxy_dict = {
        "http": f"http://{proxy}",
        "https": f"https://{proxy}",
        "ftp": f"ftp://{proxy}"
    }
    try:
        get("https://vk.com", proxies=proxy_dict, timeout=5)
        return True
    except Exception as e:
        return False
