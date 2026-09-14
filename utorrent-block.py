import requests
import json
import re
import time
import os
import sys
import threading
from requests.auth import HTTPBasicAuth

# 配置参数
URL = "http://127.0.0.1:10000/gui/"
USER = "admin"  # 替换为你的用户名
PASS = "123456"  # 替换为你的密码
IPFILTER = r'C:\Users\**\AppData\Roaming\uTorrent\ipfilter.dat'
PATTERN = r"(?i)(-XL0012-|Xunlei|QQDownload|\.\./torrent|aria2|Gopeed)"

# 全局变量
TOKEN = ""
COOKIE = None
SHUTDOWN = False  # 用于控制程序退出的标志

def http_get_url(url):
    try:
        response = requests.get(
            url,
            cookies=COOKIE,
            auth=HTTPBasicAuth(USER, PASS),
            timeout=5
        )
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print("请求错误，确认 uTorrent 是否运行，并开启网页界面")
        sys.exit(3)

def get_token():
    global TOKEN, COOKIE
    new_url = URL + "token.html"
    try:
        response = requests.get(
            new_url,
            auth=HTTPBasicAuth(USER, PASS),
            timeout=5
        )
        if response.status_code > 200:
            print("无法获取 token 信息，请确认账号密码是否正确。")
            sys.exit(1)
        COOKIE = response.cookies
        body = response.text
        match = re.search(r"<html><div id='token' .*>(.*?)</div></html>", body)
        if match:
            TOKEN = match.group(1)
        else:
            print("无法解析 token")
            sys.exit(1)
    except requests.exceptions.RequestException as e:
        print("请求错误，请确认 URL 是否正确。")
        sys.exit(2)

def parse_torrents(data):
    try:
        result = json.loads(data)
        torrents = result.get("torrents", [])
        return [torrent[0] for torrent in torrents]
    except json.JSONDecodeError as e:
        print(f"解析 JSON 错误: {e}")
        sys.exit(1)

def get_hash():
    new_url = URL + f"?token={TOKEN}&list=1"
    data = http_get_url(new_url)
    return parse_torrents(data)

def parse_peers(data, peers_list):
    try:
        result = json.loads(data)
        peers = result.get("peers", [])
        if len(peers) > 1:
            for peer in peers[1]:
                ip = peer[1]
                client = peer[5]
                peers_list.append([ip, client])
    except json.JSONDecodeError as e:
        print(f"解析 JSON 错误: {e}")
        sys.exit(1)

def get_peers(hash, peers_list):
    new_url = URL + f"?token={TOKEN}&action=getpeers&hash={hash}"
    data = http_get_url(new_url)
    parse_peers(data, peers_list)

def get_all_peers(hash_list):
    peers_list = []
    for h in hash_list:
        get_peers(h, peers_list)
    return peers_list

def reload_ut():
    new_url = URL + f"?token={TOKEN}&action=setsetting&s=ipfilter.enable&v=1"
    http_get_url(new_url)

def write_ipfilter(ip_list):
    try:
        with open(IPFILTER, "a") as f:
            for ip in ip_list:
                f.write(f"{ip}\n")
        reload_ut()
    except IOError as e:
        print(f"写入文件错误: {e}")
        sys.exit(1)

def truncate_file():
    try:
        with open(IPFILTER, "w") as f:
            f.truncate(0)
    except IOError as e:
        print(f"清空文件错误: {e}")
        sys.exit(1)

def block(peers_list):
    block_list = []
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"{current_time} 屏蔽信息:")
    for peer in peers_list:
        client = peer[1].replace("\r", "")
        if re.search(PATTERN, client):
            block_list.append(peer[0])
            print(f"    IP: {peer[0]}, Client: {client}")

    # 去重
    unique_block_list = list(set(block_list))
    if unique_block_list:
        write_ipfilter(unique_block_list)

def clear_ip_list():
    global SHUTDOWN
    if SHUTDOWN:
        return
    current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    print(f"{current_time} 运行两小时，清空 IP 列表")
    truncate_file()
    reload_ut()
    # 重新设置定时器
    threading.Timer(2 * 3600 + 10, clear_ip_list).start()

def run():
    global SHUTDOWN
    # 启动定时器
    threading.Timer(2 * 3600 + 10, clear_ip_list).start()

    try:
        while not SHUTDOWN:
            hash_list = get_hash()
            peers_list = get_all_peers(hash_list)
            block(peers_list)
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在退出...")
        SHUTDOWN = True
        truncate_file()
        sys.exit(0)

if __name__ == "__main__":
    if not USER or not PASS:
        print("账号密码不能为空")
        sys.exit(1)

    get_token()
    run()
