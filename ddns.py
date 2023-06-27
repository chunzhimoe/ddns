import os
import random
import csv
import requests
import CloudFlare
from netaddr import IPNetwork
import socket
import subprocess
import platform
import time
from tqdm import tqdm

# Cloudflare 设置
CLOUDFLARE_EMAIL = "your_email"
CLOUDFLARE_API_TOKEN = "your_api_token"
ZONE_NAME = "your_domain.com"
SUBDOMAIN_NAME = "subdomain.your_domain.com"
RECORDS_COUNT = 10

cf = CloudFlare.CloudFlare(email=CLOUDFLARE_EMAIL, token=CLOUDFLARE_API_TOKEN)

def get_ip_list(url):
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if "addresses" in data:
            ip_data = data["addresses"]
            ip_list = []
            for item in ip_data:
                ip_network = IPNetwork(item)
                if ip_network.version == 4:  # 只解析 IPv4 地址
                    ip_list.extend(list(ip_network))
            return ip_list
        else:
            print("JSON 数据中未找到 'addresses' 键")
            return []
    else:
        print("获取 IP 列表失败")
        return []

def ping(ip):
    param = "-n" if platform.system().lower() == "windows" else "-c"
    start_time = time.time()
    is_alive = subprocess.call(["ping", param, "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    end_time = time.time()
    elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒
    return is_alive, elapsed_time

def scan_ips(ip_list, filename):
    total_ips = len(ip_list)
    progress_bar = tqdm(total=total_ips, desc="扫描进度", ncols=100)

    with open(filename, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["IP Address"])

        for current_ip in ip_list:
            is_alive, elapsed_time = ping(str(current_ip))
            if is_alive and elapsed_time < 150:  # 添加延迟小于 150ms 的条件
                try:
                    response = requests.get(f"http://{current_ip}:443", timeout=5)
                    if response.status_code == 400:  # 检查状态码是否为 400
                        csvwriter.writerow([str(current_ip)])  # 将 IP 地址写入 CSV 文件
                except Exception as e:
                    print(f"Error accessing {current_ip}: {e}")

            progress_bar.update(1)
    progress_bar.close()

def read_ips(file):
    with open(file) as f:
        reader = csv.reader(f)
        ips = [row[0] for row in reader]
    return ips

def set_ddns(ips):
    zone_id = cf.zones.get(params={'name':ZONE_NAME})[0]['id']
    dns_records = cf.zones.dns_records.get(zone_id)
    for record in dns_records:
        if record['name'] == SUBDOMAIN_NAME:
            cf.zones.dns_records.delete(zone_id, record['id'])
    selected_ips = random.sample(ips, min(RECORDS_COUNT, len(ips)))
    for ip in selected_ips:
        try:
            cf.zones.dns_records.post(zone_id, data={'type':'A', 'name':SUBDOMAIN_NAME, 'content':ip, 'proxied':False})
            print(f"记录添加成功: {ip}")
        except Exception as e:
            print(f"记录添加失败: {ip}，错误: {e}")

if __name__ == "__main__":
    url = "https://api.gcore.com/cdn/public-ip-list"
    ip_list = get_ip_list(url)
    filename = "working_ips.csv"
    scan_ips(ip_list, filename)
    print("已将可用 IP 地址保存到 working_ips.csv 文件中。")
    ips = read_ips(filename)
    set_ddns(ips)
