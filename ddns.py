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
CLOUDFLARE_EMAIL = "你的邮箱"
CLOUDFLARE_API_TOKEN = "你的 API Token"
ZONE_NAME = "你的域名.com"
SUBDOMAIN_NAME = "子域名.你的域名.com"
NEW_SUBDOMAIN_NAME = "新的子域名.你的域名.com"
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
                if ip_network.version == 4:  # 仅解析 IPv4 地址
                    ip_list.extend(list(ip_network))
            return ip_list
        else:
            print("JSON 数据不包含 'addresses' 键")
            return []
    else:
        print("获取 IP 列表失败")
        return []

def ping(ip):
    ping_param = "-n" if platform.system().lower() == "windows" else "-c"
    start_time = time.time()
    is_alive = subprocess.call(["ping", ping_param, "1", ip], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    end_time = time.time()
    elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒
    return is_alive, elapsed_time

def check_ip(ip, domain):
    try:
        headers = {"Host": domain}
        response = requests.get(f"https://{ip}", headers=headers, timeout=5)
        if response.status_code == 200:  # 检查状态码是否为 200
            return True
    except Exception as e:
        print(f"访问 {ip} 出错：{e}")
    return False

def scan_ips(ip_list, filename):
    total_ips = len(ip_list)
    progress_bar = tqdm(total=total_ips, desc="扫描进度", ncols=100)

    with open(filename, "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["IP Address"])

        for current_ip in ip_list:
            is_alive, elapsed_time = ping(str(current_ip))
            if is_alive and elapsed_time < 200:  # 添加延迟小于 200ms 的条件
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

def set_ddns(ips, subdomain_name):
    zone_id = cf.zones.get(params={'name':ZONE_NAME})[0]['id']
    dns_records = cf.zones.dns_records.get(zone_id)
    for record in dns_records:
        if record['name'] == subdomain_name:
            cf.zones.dns_records.delete(zone_id, record['id'])
    selected_ips = random.sample(ips, min(RECORDS_COUNT, len(ips)))
    for ip in selected_ips:
        try:
            cf.zones.dns_records.post(zone_id, data={'type':'A', 'name':subdomain_name, 'content':ip, 'proxied':False})
            print(f"记录添加成功：{ip}")
        except Exception as e:
            print(f"添加记录失败：{ip}，错误：{e}")

    # 将 IP 写入文本文件
    with open("working_ips.txt", "w") as f:
        for ip in ips:
            f.write(f"{ip}\n")

def run_speed_test(filename):
    with open(filename) as f:
        ips = [line.strip() for line in f]

    with open("result.csv", "w", newline="") as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["IP 地址", "发送", "接收", "丢包率", "平均延迟", "下载速度（MB/s）"])

        for ip in ips:
            try:
                speed_test_output = subprocess.check_output(["./CloudflareST", "-url", "https:demopage.gcdn.co/videos/2675_xMbWbUSuvJ8NX2/480.mp4", "-n", "4", "-ip", ip])
                speed_test_output = speed_test_output.decode("utf-8").split("\n")

                sent = speed_test_output[0].split(":")[1].strip()
                received = speed_test_output[1].split(":")[1].strip()
                packet_loss = speed_test_output[2].split(":")[1].strip()
                avg_latency = speed_test_output[3].split(":")[1].strip()
                download_speed = speed_test_output[4].split(":")[1].strip()

                csvwriter.writerow([ip, sent, received, packet_loss, avg_latency, download_speed])
                print(f"{ip} 的速度测试已完成")
            except Exception as e:
                print(f"无法运行 {ip} 的速度测试，错误：{e}")

    # 为 result.csv 中的 IP 设置 DDNS
    ips = []
    with open("result.csv") as f:
        reader = csv.reader(f)
        next(reader)  # 跳过标题行
        for row in reader:
            ips.append(row[0])
    set_ddns(ips, NEW_SUBDOMAIN_NAME)

def main():
    url = "https:gh.lovemoe.net/https:raw.githubusercontent.com/chunzhimoe/cdniplist/main/ip_list.json"
    ip_list = get_ip_list(url)
    filename = "working_ips.csv"
    scan_ips(ip_list, filename)
    print("可用的 IP 地址已保存到 working_ips.csv 文件中。")
    ips = read_ips(filename)
    set_ddns(ips, SUBDOMAIN_NAME)
    run_speed_test("working_ips.txt")

    # 为 result.csv 中的 IP 设置 DDNS
    ips = []
    with open("result.csv") as f:
        reader = csv.reader(f)
        next(reader)  # 跳过标题行
        for row in reader:
            ips.append(row[0])
    set_ddns(ips, NEW_SUBDOMAIN_NAME)

if __name__ == "__main__":
    main()
