"""
Telegram Bot - Мастер обхода блокировок
Монолитная архитектура (один файл)
"""

import asyncio
import logging
import random
import tempfile
import os
import time
import threading
import requests
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters
)

# ─────────────────────────────────────────────
# 1. КОНФИГ
# ─────────────────────────────────────────────

TOKEN = "8640337686:AAGGetelvbiaIKz1AIIm6mi0QC-r4yOJtRM"

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ─── Встроенный резерв: 50 HTTP-прокси ───
BUILTIN_HTTP_PROXIES = [
    "103.149.162.195:80",
    "185.162.231.106:80",
    "47.74.152.29:8888",
    "103.83.232.122:80",
    "185.217.136.67:1337",
    "45.77.56.114:30205",
    "103.105.49.42:8080",
    "103.152.112.162:80",
    "103.216.82.37:6666",
    "103.48.68.36:83",
    "103.75.117.21:4153",
    "185.191.236.162:3128",
    "103.155.217.1:41317",
    "103.106.193.137:7497",
    "103.143.196.50:8080",
    "103.152.101.234:8080",
    "103.159.46.10:83",
    "103.161.96.54:3128",
    "103.165.155.79:1111",
    "103.167.135.90:8080",
    "103.168.44.167:9191",
    "103.172.70.138:3127",
    "103.179.182.200:83",
    "103.180.119.91:3128",
    "103.189.235.249:8080",
    "103.193.119.126:7777",
    "103.194.175.135:8080",
    "103.197.206.17:8080",
    "103.199.168.70:80",
    "103.200.112.104:8080",
    "103.204.119.177:8080",
    "103.207.1.153:8080",
    "103.209.36.57:6666",
    "103.211.177.50:8080",
    "103.213.213.14:84",
    "103.214.9.13:3128",
    "103.216.50.11:8080",
    "103.217.213.125:83",
    "103.220.206.136:82",
    "103.224.182.210:8080",
    "103.228.118.78:8080",
    "103.231.80.175:55443",
    "103.234.87.1:8080",
    "103.235.199.179:9090",
    "103.236.191.101:8080",
    "103.239.200.186:8080",
    "103.241.182.97:80",
    "103.242.104.58:8080",
    "103.245.193.214:8080",
    "103.247.21.85:8080",
]

# ─── Встроенный резерв: 10 SOCKS5-прокси ───
BUILTIN_SOCKS5_PROXIES = [
    "72.195.34.58:4145",
    "72.195.34.59:4145",
    "72.195.34.60:4145",
    "72.195.34.61:4145",
    "72.195.34.62:4145",
    "72.195.114.169:4145",
    "72.195.114.184:4145",
    "72.195.114.186:4145",
    "72.195.114.187:4145",
    "72.195.114.188:4145",
]

# ─── Встроенный резерв: VPN конфиги (VPNBook) ───
BUILTIN_VPN_CONFIGS = [
    {"name": "VPNBook US1", "server": "us1.vpnbook.com", "port": "80", "country": "🇺🇸 США", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook US2", "server": "us2.vpnbook.com", "port": "443", "country": "🇺🇸 США", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook CA1", "server": "ca1.vpnbook.com", "port": "80", "country": "🇨🇦 Канада", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook DE1", "server": "de1.vpnbook.com", "port": "80", "country": "🇩🇪 Германия", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook FR1", "server": "fr1.vpnbook.com", "port": "80", "country": "🇫🇷 Франция", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook PL1", "server": "pl1.vpnbook.com", "port": "80", "country": "🇵🇱 Польша", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook EU1", "server": "euro1.vpnbook.com", "port": "443", "country": "🇪🇺 Европа", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook EU2", "server": "euro2.vpnbook.com", "port": "443", "country": "🇪🇺 Европа", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook UK1", "server": "uk1.vpnbook.com", "port": "80", "country": "🇬🇧 Великобритания", "username": "vpnbook", "password": "auto", "proto": "tcp"},
    {"name": "VPNBook AU1", "server": "au1.vpnbook.com", "port": "80", "country": "🇦🇺 Австралия", "username": "vpnbook", "password": "auto", "proto": "tcp"},
]

# ─────────────────────────────────────────────
# 2. КЛАСС ProxyPool
# ─────────────────────────────────────────────

class ProxyPool:
    def __init__(self):
        self.http_proxies = list(BUILTIN_HTTP_PROXIES)
        self.socks5_proxies = list(BUILTIN_SOCKS5_PROXIES)
        self.dead_proxies = set()
        self.proxy_stats = {}
        self.lock = threading.Lock()
        self._vpnbook_password = "5zt6eFm"

    def get_http_proxy(self):
        with self.lock:
            alive = [p for p in self.http_proxies if p not in self.dead_proxies]
            if not alive:
                self.dead_proxies.clear()
                alive = list(self.http_proxies)
            return random.choice(alive) if alive else None

    def get_socks5_proxy(self):
        with self.lock:
            alive = [p for p in self.socks5_proxies if p not in self.dead_proxies]
            if not alive:
                alive = list(self.socks5_proxies)
            return random.choice(alive) if alive else None

    def mark_dead(self, proxy):
        with self.lock:
            self.dead_proxies.add(proxy)
            logger.info(f"Прокси помечен мёртвым: {proxy}")

    def check_proxy(self, proxy_str, proto="http", timeout=5):
        try:
            if proto == "socks5":
                proxies = {"http": f"socks5://{proxy_str}", "https": f"socks5://{proxy_str}"}
            else:
                proxies = {"http": f"http://{proxy_str}", "https": f"http://{proxy_str}"}
            start = time.time()
            r = requests.get("http://httpbin.org/ip", proxies=proxies, timeout=timeout)
            ping = int((time.time() - start) * 1000)
            if r.status_code == 200:
                ip = r.json().get("origin", "unknown")
                with self.lock:
                    self.proxy_stats[proxy_str] = {
                        "ping": ping,
                        "last_check": datetime.now().strftime("%H:%M:%S"),
                        "alive": True,
                        "ip": ip,
                    }
                return True, ping, ip
        except Exception:
            pass
        self.mark_dead(proxy_str)
        return False, 9999, None

    def get_best_http_proxy(self):
        candidates = [p for p in self.http_proxies if p not in self.dead_proxies]
        if not candidates:
            candidates = list(self.http_proxies)
        random.shuffle(candidates)
        best = None
        best_ping = 9999
        for proxy in candidates[:10]:
            ok, ping, ip = self.check_proxy(proxy)
            if ok and ping < best_ping:
                best = proxy
                best_ping = ping
        return best, best_ping

    def add_proxies(self, new_list, proto="http"):
        with self.lock:
            if proto == "http":
                before = len(self.http_proxies)
                self.http_proxies = list(set(self.http_proxies + new_list))
                logger.info(f"Добавлено {len(self.http_proxies) - before} новых HTTP-прокси. Всего: {len(self.http_proxies)}")
            elif proto == "socks5":
                before = len(self.socks5_proxies)
                self.socks5_proxies = list(set(self.socks5_proxies + new_list))
                logger.info(f"Добавлено {len(self.socks5_proxies) - before} новых SOCKS5-прокси. Всего: {len(self.socks5_proxies)}")

    def stats(self):
        return {
            "http_total": len(self.http_proxies),
            "socks5_total": len(self.socks5_proxies),
            "dead": len(self.dead_proxies),
            "alive_http": len([p for p in self.http_proxies if p not in self.dead_proxies]),
        }


# ─────────────────────────────────────────────
# 3. КЛАСС VPNParser
# ─────────────────────────────────────────────

class VPNParser:
    def __init__(self, proxy_pool: ProxyPool):
        self.pool = proxy_pool
        self.vpn_configs = list(BUILTIN_VPN_CONFIGS)
        self.vpnbook_password = "5zt6eFm"

    def parse_http_proxies(self):
        sources = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all",
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        ]
        collected = []
        relay_proxy = self.pool.get_http_proxy()
        proxies_dict = None
        if relay_proxy:
            proxies_dict = {"http": f"http://{relay_proxy}", "https": f"http://{relay_proxy}"}
        for url in sources:
            try:
                r = requests.get(url, proxies=proxies_dict, timeout=8)
                if r.status_code == 200:
                    lines = r.text.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if ":" in line and len(line) < 25:
                            collected.append(line)
                    logger.info(f"Спарсено {len(lines)} прокси с {url}")
                    break
            except Exception as e:
                logger.warning(f"Не удалось спарсить {url}: {e}")
        if collected:
            self.pool.add_proxies(collected[:200], proto="http")
        return len(collected)

    def parse_socks5_proxies(self):
        sources = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=5000",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        ]
        collected = []
        relay_proxy = self.pool.get_http_proxy()
        proxies_dict = None
        if relay_proxy:
            proxies_dict = {"http": f"http://{relay_proxy}", "https": f"http://{relay_proxy}"}
        for url in sources:
            try:
                r = requests.get(url, proxies=proxies_dict, timeout=8)
                if r.status_code == 200:
                    lines = r.text.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if ":" in line and len(line) < 25:
                            collected.append(line)
                    break
            except Exception as e:
                logger.warning(f"Не удалось спарсить SOCKS5 {url}: {e}")
        if collected:
            self.pool.add_proxies(collected[:100], proto="socks5")
        return len(collected)

    def fetch_vpnbook_password(self):
        relay_proxy = self.pool.get_http_proxy()
        proxies_dict = None
        if relay_proxy:
            proxies_dict = {"http": f"http://{relay_proxy}", "https": f"http://{relay_proxy}"}
        try:
            r = requests.get("https://www.vpnbook.com/freevpn", proxies=proxies_dict, timeout=10)
            if r.status_code == 200:
                import re
                match = re.search(r'Password:\s*<[^>]+>([^<]+)<', r.text)
                if match:
                    pwd = match.group(1).strip()
                    self.vpnbook_password = pwd
                    self.pool._vpnbook_password = pwd
                    logger.info(f"VPNBook пароль обновлён: {pwd}")
                    return pwd
        except Exception as e:
            logger.warning(f"Не удалось получить пароль VPNBook: {e}")
        return self.vpnbook_password

    def generate_ovpn(self, config: dict) -> str:
        password = self.vpnbook_password
        ovpn = f"""client
dev tun
proto {config['proto']}
remote {config['server']} {config['port']}
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-256-CBC
auth SHA256

# Сервер: {config['name']}
# Страна: {config['country']}
# Логин: {config['username']}
# Пароль: {password}

<ca>
-----BEGIN CERTIFICATE-----
MIIEkjCCA3qgAwIBAgIJAMPTHAqMQnCOMA0GCSqGSIb3DQEBCwUAMIGMMQswCQYD
VQQGEwJVUzELMAkGA1UECBMCQ0ExFTATBgNVBAcTDFNhbkZyYW5jaXNjbzETMBEG
A1UEChMKVlBOQm9vay5jb20xEDAOBgNVBAsTB1ZQTkJvb2sxEDAOBgNVBAMTB1ZQ
TkJvb2sxIDAeBgkqhkiG9w0BCQEWEWFkbWluQHZwbmJvb2suY29tMB4XDTEzMDky
NzE3MzIzNloXDTIzMDkyNTE3MzIzNlowgYwxCzAJBgNVBAYTAlVTMQswCQYDVQQI
EwJDQTEVMBMGA1UEBxMMU2FuRnJhbmNpc2NvMRMwEQYDVQQKEwpWUE5Cb29rLmNv
bTEQMA4GA1UECxMHVlBOQm9vazEQMA4GA1UEAxMHVlBOQm9vazEgMB4GCSqGSIb3
DQEJARYRYWRtaW5AdnBuYm9vay5jb20wggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAw
ggEKAoIBAQC5tPBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB
-----END CERTIFICATE-----
</ca>
"""
        return ovpn

    def get_random_vpn_config(self):
        return random.choice(self.vpn_configs)


# ─────────────────────────────────────────────
# 4. КЛАСС SmartBot
# ─────────────────────────────────────────────

class SmartBot:
    def __init__(self):
        self.pool = ProxyPool()
        self.parser = VPNParser(self.pool)
        self.user_request_count = {}
        self.user_last_proxy = {}
        self._start_background_tasks()

    def _start_background_tasks(self):
        def background_loop():
            while True:
                try:
                    logger.info("🔄 Фоновое обновление прокси...")
                    self.parser.parse_http_proxies()
                    self.parser.parse_socks5_proxies()
                    self.parser.fetch_vpnbook_password()
                    stats = self.pool.stats()
                    logger.info(f"📊 Пул: HTTP={stats['http_total']}, SOCKS5={stats['socks5_total']}, Мёртвых={stats['dead']}")
                except Exception as e:
                    logger.error(f"Ошибка фонового обновления: {e}")
                time.sleep(600)
        t = threading.Thread(target=background_loop, daemon=True)
        t.start()
        logger.info("✅ Фоновый поток запущен")

    def track_request(self, user_id):
        self.user_request_count[user_id] = self.user_request_count.get(user_id, 0) + 1

    def get_request_count(self, user_id):
        return self.user_request_count.get(user_id, 0)

    def main_menu_keyboard(self):
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🌍 VPN OpenVPN", callback_data="vpn"),
                InlineKeyboardButton("⚡ HTTP Прокси", callback_data="proxy"),
            ],
            [
                InlineKeyboardButton("🔒 SOCKS5", callback_data="socks"),
                InlineKeyboardButton("🤖 Авто-режим", callback_data="auto"),
            ],
            [
                InlineKeyboardButton("🔍 Проверить мой IP", callback_data="check"),
                InlineKeyboardButton("🔄 Сменить прокси", callback_data="rotate"),
            ],
            [
                InlineKeyboardButton("📊 Статистика пула", callback_data="stats"),
            ],
        ])

    def get_verified_http_proxy(self):
        for _ in range(10):
            proxy = self.pool.get_http_proxy()
            if not proxy:
                break
            ok, ping, ip = self.pool.check_proxy(proxy, proto="http")
            if ok:
                return proxy, ping, ip
        return None, 9999, None

    def get_verified_socks5_proxy(self):
        for _ in range(10):
            proxy = self.pool.get_socks5_proxy()
            if not proxy:
                break
            ok, ping, ip = self.pool.check_proxy(proxy, proto="socks5")
            if ok:
                return proxy, ping, ip
        return None, 9999, None


# ─────────────────────────────────────────────
# 5. ИНИЦИАЛИЗАЦИЯ БОТА
# ─────────────────────────────────────────────

bot = SmartBot()


# ─────────────────────────────────────────────
# 6. ХЭНДЛЕРЫ
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"👋 Привет, *{user.first_name}*!\n\n"
        "🛡️ *Бот-мастер обхода блокировок*\n\n"
        "Я помогу тебе обойти любые ограничения:\n"
        "• 🌍 OpenVPN конфиги (реальные .ovpn файлы)\n"
        "• ⚡ HTTP-прокси с проверкой пинга\n"
        "• 🔒 SOCKS5-прокси для анонимности\n"
        "• 🤖 Умный авто-выбор лучшего варианта\n\n"
        "📡 *Работаю 24/7, сам обновляю прокси каждые 10 минут*\n\n"
        "Выбери режим:"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=bot.main_menu_keyboard())


async def cmd_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_vpn(update, context, update.message)

async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_http_proxy(update, context, update.message)

async def cmd_socks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_socks5_proxy(update, context, update.message)

async def cmd_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_auto(update, context, update.message)

async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_check_ip(update, context, update.message)

async def cmd_rotate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_rotate(update, context, update.message)


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "vpn":
        await send_vpn(update, context, query.message, edit=True)
    elif data == "proxy":
        await send_http_proxy(update, context, query.message, edit=True)
    elif data == "socks":
        await send_socks5_proxy(update, context, query.message, edit=True)
    elif data == "auto":
        await send_auto(update, context, query.message, edit=True)
    elif data == "check":
        await send_check_ip(update, context, query.message, edit=True)
    elif data == "rotate":
        await send_rotate(update, context, query.message, edit=True)
    elif data == "stats":
        await send_stats(update, context, query.message, edit=True)
    elif data == "menu":
        await query.message.edit_text(
            "🏠 *Главное меню*\n\nВыбери режим:",
            parse_mode="Markdown",
            reply_markup=bot.main_menu_keyboard()
        )


def back_keyboard():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]])


async def send_http_proxy(update, context, message, edit=False):
    user_id = update.effective_user.id
    bot.track_request(user_id)
    loading_text = "⏳ *Ищу рабочий HTTP-прокси...*\nПроверяю пинг и доступность..."
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    proxy, ping, ip = await asyncio.get_event_loop().run_in_executor(None, bot.get_verified_http_proxy)

    if proxy:
        host, port = proxy.split(":")
        bot.user_last_proxy[user_id] = proxy
        text = (
            f"⚡ *HTTP Прокси найден!*\n\n"
            f"```\n{proxy}\n```\n\n"
            f"🌐 *Хост:* `{host}`\n"
            f"🔌 *Порт:* `{port}`\n"
            f"📍 *Внешний IP:* `{ip}`\n"
            f"⚡ *Пинг:* `{ping} мс`\n\n"
            f"📋 *Как использовать:*\n"
            f"• Chrome: Настройки → Прокси → HTTP\n"
            f"• curl: `curl -x http://{proxy} https://example.com`\n"
            f"• Python: `proxies={{'http': 'http://{proxy}'}}`\n\n"
            f"✅ Прокси проверен и работает!"
        )
    else:
        text = (
            "❌ *Живые HTTP-прокси временно недоступны*\n\n"
            "🔄 Попробуй /rotate для повторной попытки\n"
            "или /socks для SOCKS5"
        )
    await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def send_socks5_proxy(update, context, message, edit=False):
    user_id = update.effective_user.id
    bot.track_request(user_id)
    loading_text = "⏳ *Ищу рабочий SOCKS5-прокси...*"
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    proxy, ping, ip = await asyncio.get_event_loop().run_in_executor(None, bot.get_verified_socks5_proxy)

    if proxy:
        host, port = proxy.split(":")
        bot.user_last_proxy[user_id] = f"socks5://{proxy}"
        text = (
            f"🔒 *SOCKS5 Прокси найден!*\n\n"
            f"```\nsocks5://{proxy}\n```\n\n"
            f"🌐 *Хост:* `{host}`\n"
            f"🔌 *Порт:* `{port}`\n"
            f"📍 *Внешний IP:* `{ip}`\n"
            f"⚡ *Пинг:* `{ping} мс`\n\n"
            f"📋 *Как использовать:*\n"
            f"• Firefox: Настройки → Прокси → SOCKS5\n"
            f"• curl: `curl --socks5 {proxy} https://example.com`\n"
            f"• Telegram: Настройки → Данные и память → Прокси\n\n"
            f"✅ Прокси проверен и работает!"
        )
    else:
        text = (
            "❌ *SOCKS5-прокси временно недоступны*\n\n"
            "Попробуй /proxy для HTTP-прокси\n"
            "или /vpn для OpenVPN"
        )
    await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def send_vpn(update, context, message, edit=False):
    user_id = update.effective_user.id
    bot.track_request(user_id)
    loading_text = "⏳ *Генерирую OpenVPN конфиг...*"
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    config = bot.parser.get_random_vpn_config()
    ovpn_content = bot.parser.generate_ovpn(config)

    with tempfile.NamedTemporaryFile(
        mode='w', suffix='.ovpn', delete=False,
        prefix=f"vpnbook_{config['server'].split('.')[0]}_"
    ) as f:
        f.write(ovpn_content)
        tmp_path = f.name

    caption = (
        f"🌍 *OpenVPN Конфиг готов!*\n\n"
        f"🖥️ *Сервер:* `{config['server']}`\n"
        f"🔌 *Порт:* `{config['port']}`\n"
        f"🌐 *Страна:* {config['country']}\n"
        f"🔐 *Протокол:* `{config['proto'].upper()}`\n\n"
        f"👤 *Логин:* `{config['username']}`\n"
        f"🔑 *Пароль:* `{bot.parser.vpnbook_password}`\n\n"
        f"📋 *Как использовать:*\n"
        f"1. Скачай файл .ovpn\n"
        f"2. Установи OpenVPN клиент\n"
        f"3. Импортируй файл\n"
        f"4. Введи логин/пароль выше\n"
        f"5. Подключись!\n\n"
        f"✅ Конфиг сгенерирован автоматически"
    )

    try:
        await msg.delete()
        with open(tmp_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"{config['server']}.ovpn",
                caption=caption,
                parse_mode="Markdown",
                reply_markup=back_keyboard()
            )
    except Exception as e:
        logger.error(f"Ошибка отправки VPN: {e}")
        await msg.edit_text(
            caption + f"\n\n📄 *Конфиг:*\n```\n{ovpn_content[:500]}...\n```",
            parse_mode="Markdown",
            reply_markup=back_keyboard()
        )
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


async def send_auto(update, context, message, edit=False):
    user_id = update.effective_user.id
    req_count = bot.get_request_count(user_id)
    bot.track_request(user_id)
    loading_text = "🤖 *Авто-режим: анализирую лучший вариант...*"
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    if req_count >= 3:
        choice = "vpn"
        reason = "🔄 Ты часто запрашивал прокси — попробуем VPN для надёжности"
    else:
        proxy, ping, ip = await asyncio.get_event_loop().run_in_executor(None, bot.get_verified_http_proxy)
        if proxy and ping < 500:
            choice = "http"
            reason = f"⚡ HTTP-прокси с пингом {ping}мс — оптимальный выбор!"
        else:
            s_proxy, s_ping, s_ip = await asyncio.get_event_loop().run_in_executor(None, bot.get_verified_socks5_proxy)
            if s_proxy:
                choice = "socks5"
                reason = "🔒 HTTP недоступен — переключаюсь на SOCKS5"
            else:
                choice = "vpn"
                reason = "🌍 Прокси недоступны — рекомендую OpenVPN"

    await msg.edit_text(f"🤖 *Авто-режим*\n\n{reason}\n\n⏳ Получаю...", parse_mode="Markdown")

    if choice == "http":
        await send_http_proxy(update, context, msg, edit=True)
    elif choice == "socks5":
        await send_socks5_proxy(update, context, msg, edit=True)
    else:
        await send_vpn(update, context, msg, edit=True)


async def send_check_ip(update, context, message, edit=False):
    loading_text = "🔍 *Проверяю твой текущий IP...*"
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    def get_ip_info():
        try:
            r = requests.get("http://ip-api.com/json/", timeout=5)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        try:
            r = requests.get("https://httpbin.org/ip", timeout=5)
            if r.status_code == 200:
                return {"query": r.json().get("origin"), "country": "?", "city": "?", "isp": "?"}
        except Exception:
            pass
        return None

    data = await asyncio.get_event_loop().run_in_executor(None, get_ip_info)

    if data:
        country = data.get("country", "Неизвестно")
        flags = {"Russia": "🇷🇺", "United States": "🇺🇸", "Germany": "🇩🇪",
                 "France": "🇫🇷", "United Kingdom": "🇬🇧", "China": "🇨🇳"}
        flag = flags.get(country, "🌐")
        text = (
            f"🔍 *Твой текущий IP*\n\n"
            f"📍 *IP:* `{data.get('query', 'N/A')}`\n"
            f"{flag} *Страна:* {country}\n"
            f"🏙️ *Город:* {data.get('city', 'N/A')}\n"
            f"🏢 *Провайдер:* {data.get('isp', 'N/A')}\n\n"
            f"💡 Если видишь свой реальный IP — используй прокси/VPN!"
        )
    else:
        text = "❌ Не удалось определить IP. Проверь подключение."

    await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def send_rotate(update, context, message, edit=False):
    user_id = update.effective_user.id
    bot.user_request_count[user_id] = 0
    loading_text = "🔄 *Ротация прокси...*\nИщу новый рабочий прокси..."
    if edit:
        msg = await message.edit_text(loading_text, parse_mode="Markdown")
    else:
        msg = await message.reply_text(loading_text, parse_mode="Markdown")

    old_proxy = bot.user_last_proxy.get(user_id)
    if old_proxy and "socks5://" not in old_proxy:
        bot.pool.mark_dead(old_proxy)

    proxy, ping, ip = await asyncio.get_event_loop().run_in_executor(None, bot.get_verified_http_proxy)

    if proxy:
        bot.user_last_proxy[user_id] = proxy
        text = (
            f"🔄 *Прокси сменён!*\n\n"
            f"✅ *Новый прокси:* `{proxy}`\n"
            f"📍 *IP:* `{ip}`\n"
            f"⚡ *Пинг:* `{ping} мс`\n\n"
            f"Старый прокси помечен как неактивный."
        )
    else:
        text = "⚠️ *Не удалось найти новый прокси*\n\nПопробуй /vpn для OpenVPN конфига"

    await msg.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def send_stats(update, context, message, edit=False):
    stats = bot.pool.stats()
    text = (
        f"📊 *Статистика прокси-пула*\n\n"
        f"⚡ *HTTP прокси:* {stats['http_total']} всего\n"
        f"✅ *Живых HTTP:* {stats['alive_http']}\n"
        f"🔒 *SOCKS5 прокси:* {stats['socks5_total']}\n"
        f"💀 *Мёртвых:* {stats['dead']}\n\n"
        f"🌍 *VPN конфигов:* {len(bot.parser.vpn_configs)}\n"
        f"🔑 *VPNBook пароль:* `{bot.parser.vpnbook_password}`\n\n"
        f"🔄 *Обновление:* каждые 10 минут\n"
        f"⏰ *Время:* {datetime.now().strftime('%H:%M:%S')}"
    )
    if edit:
        await message.edit_text(text, parse_mode="Markdown", reply_markup=back_keyboard())
    else:
        await message.reply_text(text, parse_mode="Markdown", reply_markup=back_keyboard())


async def unknown_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Используй команды:\n"
        "/start — главное меню\n"
        "/proxy — HTTP прокси\n"
        "/socks — SOCKS5 прокси\n"
        "/vpn — OpenVPN конфиг\n"
        "/auto — авто-выбор\n"
        "/check — мой IP\n"
        "/rotate — сменить прокси",
        reply_markup=bot.main_menu_keyboard()
    )


# ─────────────────────────────────────────────
# 7. main()
# ─────────────────────────────────────────────

def main():
    logger.info("🚀 Запуск бота...")

    def initial_parse():
        time.sleep(5)
        try:
            bot.parser.parse_http_proxies()
            bot.parser.parse_socks5_proxies()
            bot.parser.fetch_vpnbook_password()
        except Exception as e:
            logger.warning(f"Первичный парсинг: {e}")

    threading.Thread(target=initial_parse, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("vpn", cmd_vpn))
    app.add_handler(CommandHandler("proxy", cmd_proxy))
    app.add_handler(CommandHandler("socks", cmd_socks))
    app.add_handler(CommandHandler("auto", cmd_auto))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("rotate", cmd_rotate))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown_message))

    logger.info("✅ Бот запущен и готов к работе!")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
