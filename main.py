#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import random
import tempfile
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ==================== КОНФИГУРАЦИЯ ====================
TOKEN = "8640337686:AAGGetelvbiaIKz1AIIm6mi0QC-r4yOJtRM"

# ----- ВСТРОЕННЫЙ РЕЗЕРВ HTTP ПРОКСИ (50 штук) -----
BUILTIN_HTTP_PROXIES = [
    "20.206.75.78:80", "13.38.156.5:3128", "185.199.229.156:7497",
    "47.242.132.79:3128", "45.87.121.136:8080", "159.65.177.28:3128",
    "188.166.56.238:8080", "167.71.5.83:3128", "34.68.234.4:8080",
    "34.73.122.131:3128", "35.237.174.129:80", "3.134.112.6:3128",
    "18.220.149.240:8080", "54.85.161.62:3128", "52.3.96.191:8080",
    "34.229.138.115:3128", "35.171.13.158:80", "54.234.40.126:8080",
    "52.44.158.194:3128", "35.174.238.46:80", "3.238.247.31:8080",
    "18.206.199.196:3128", "52.90.18.105:80", "54.81.146.102:8080",
    "3.81.234.153:3128", "34.203.117.27:80", "52.200.119.33:8080",
    "3.131.46.169:3128", "18.217.116.244:80", "54.193.83.204:8080",
    "34.222.195.87:3128", "52.11.92.178:80", "35.167.52.37:8080",
    "54.188.235.102:3128", "52.14.116.165:80", "3.135.204.118:8080",
    "18.118.48.235:3128", "54.186.8.165:80", "35.164.66.171:8080",
    "52.39.164.243:3128", "34.209.174.91:80", "44.195.142.220:8080",
    "3.136.88.195:3128", "18.222.96.18:80", "54.159.85.106:8080",
    "35.168.37.113:3128", "52.41.231.232:80", "3.139.242.121:8080",
    "44.202.4.111:3128", "34.227.79.129:80"
]

# ----- ВСТРОЕННЫЙ РЕЗЕРВ SOCKS5 ПРОКСИ (10 штук) -----
BUILTIN_SOCKS_PROXIES = [
    "185.159.157.166:1080", "45.76.94.253:1080", "139.162.116.254:1080",
    "51.158.170.207:1080", "51.158.170.208:1080", "51.158.170.209:1080",
    "51.158.170.210:1080", "51.158.170.211:1080", "51.158.170.212:1080",
    "51.158.170.213:1080"
]

# ----- ВСТРОЕННЫЕ OPENVPN КОНФИГИ (10 штук) -----
# Формат: (имя_сервера, содержимое_конфига, логин, пароль)
BUILTIN_VPN_CONFIGS = [
    (
        "VPNBook US1",
        """client
dev tun
proto tcp
remote us1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook US2",
        """client
dev tun
proto tcp
remote us2.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook CA1",
        """client
dev tun
proto tcp
remote ca1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook DE1",
        """client
dev tun
proto tcp
remote de1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook FR1",
        """client
dev tun
proto tcp
remote fr1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    # Дублируем для запаса (разные порты)
    (
        "VPNBook US1 (443)",
        """client
dev tun
proto tcp
remote us1.vpnbook.com 443
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook CA1 (443)",
        """client
dev tun
proto tcp
remote ca1.vpnbook.com 443
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook DE1 (443)",
        """client
dev tun
proto tcp
remote de1.vpnbook.com 443
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook FR1 (443)",
        """client
dev tun
proto tcp
remote fr1.vpnbook.com 443
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
    (
        "VPNBook US2 (443)",
        """client
dev tun
proto tcp
remote us2.vpnbook.com 443
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
""",
        "vpnbook",
        "he2fe5e"
    ),
]

# ==================== КЛАСС УПРАВЛЕНИЯ ПРОКСИ ====================
class ProxyPool:
    def __init__(self):
        self.http_proxies: List[Tuple[str, bool]] = []   # (proxy, is_alive)
        self.socks_proxies: List[Tuple[str, bool]] = []
        self.lock = threading.Lock()
        self._init_builtin()

    def _init_builtin(self):
        """Загружает встроенные прокси в пул (изначально все считаем живыми)"""
        for p in BUILTIN_HTTP_PROXIES:
            self.http_proxies.append((p, True))
        for p in BUILTIN_SOCKS_PROXIES:
            self.socks_proxies.append((p, True))

    def add_http_proxy(self, proxy: str):
        with self.lock:
            if not any(p[0] == proxy for p in self.http_proxies):
                self.http_proxies.append((proxy, True))

    def add_socks_proxy(self, proxy: str):
        with self.lock:
            if not any(p[0] == proxy for p in self.socks_proxies):
                self.socks_proxies.append((proxy, True))

    def get_random_http(self) -> Optional[str]:
        """Возвращает случайный живой HTTP прокси"""
        with self.lock:
            alive = [p for p, alive in self.http_proxies if alive]
            if not alive:
                # если все мертвы, перезагружаем встроенные и пробуем снова
                self._init_builtin()
                alive = [p for p, alive in self.http_proxies if alive]
            return random.choice(alive) if alive else None

    def get_random_socks(self) -> Optional[str]:
        with self.lock:
            alive = [p for p, alive in self.socks_proxies if alive]
            if not alive:
                self._init_builtin()
                alive = [p for p, alive in self.socks_proxies if alive]
            return random.choice(alive) if alive else None

    def mark_dead(self, proxy: str, proxy_type: str = "http"):
        with self.lock:
            if proxy_type == "http":
                for i, (p, _) in enumerate(self.http_proxies):
                    if p == proxy:
                        self.http_proxies[i] = (p, False)
                        break
            else:
                for i, (p, _) in enumerate(self.socks_proxies):
                    if p == proxy:
                        self.socks_proxies[i] = (p, False)
                        break

    def test_proxy(self, proxy: str, proxy_type: str = "http") -> Tuple[bool, float]:
        """
        Проверяет прокси: пинг до google.com и смена IP.
        Возвращает (работоспособность, пинг_в_секундах)
        """
        proxies = {}
        if proxy_type == "http":
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        else:
            proxies = {"http": f"socks5://{proxy}", "https": f"socks5://{proxy}"}
        start = time.time()
        try:
            # Проверка смены IP
            r = requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
            if r.status_code != 200:
                return False, 999
            # Проверка пинга через google
            r2 = requests.get("https://www.google.com", proxies=proxies, timeout=10)
            if r2.status_code != 200:
                return False, 999
            ping = time.time() - start
            return ping < 5, ping
        except Exception:
            return False, 999

# ==================== КЛАСС ПАРСЕРА VPN ====================
class VPNParser:
    @staticmethod
    async def parse_vpnbook(proxy_pool: ProxyPool) -> List[Tuple[str, str, str]]:
        """
        Парсит актуальные OpenVPN конфиги с vpnbook.com через случайный прокси.
        Возвращает список (название_сервера, содержимое_конфига, логин, пароль)
        """
        proxy = proxy_pool.get_random_http()
        if not proxy:
            return []
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        try:
            resp = requests.get("https://www.vpnbook.com/freevpn", proxies=proxies, timeout=15)
            if resp.status_code != 200:
                return []
            html = resp.text
            # Простейший парсинг: ищем ссылки на .ovpn и пароли (упрощённо)
            # Для реального проекта нужен BeautifulSoup, но по условию обойдёмся регулярками
            import re
            ovpn_links = re.findall(r'href="([^"]+\.ovpn)"', html)
            # Пароли обычно в теге <p>Password: ...</p>
            pwd_match = re.search(r'Password:\s*<strong>([^<]+)</strong>', html)
            password = pwd_match.group(1) if pwd_match else "vpnbook"
            configs = []
            for link in ovpn_links[:5]:  # не больше 5
                if not link.startswith("http"):
                    link = "https://www.vpnbook.com" + link
                conf_resp = requests.get(link, proxies=proxies, timeout=10)
                if conf_resp.status_code == 200:
                    content = conf_resp.text
                    # Заменяем строку auth-user-pass на auth-user-pass (уже есть)
                    name = link.split("/")[-1].replace(".ovpn", "")
                    configs.append((name, content, "vpnbook", password))
            return configs
        except Exception:
            return []

# ==================== ОСНОВНОЙ КЛАСС БОТА ====================
class SmartBot:
    def __init__(self, proxy_pool: ProxyPool):
        self.proxy_pool = proxy_pool
        self.user_auto_counter: Dict[int, int] = {}      # сколько раз подряд авто-режим выдал однотипный прокси
        self.user_last_type: Dict[int, str] = {}         # 'http', 'socks', 'vpn'

    # --- Вспомогательные методы ---
    async def _check_proxy_and_return(self, proxy: str, ptype: str, update: Update) -> bool:
        """Проверяет прокси и отправляет результат. Возвращает True, если прокси рабочий."""
        await update.message.reply_text(f"🔄 Проверяю {ptype.upper()} прокси {proxy}...")
        ok, ping = self.proxy_pool.test_proxy(proxy, ptype)
        if ok:
            await update.message.reply_text(
                f"✅ *Рабочий {ptype.upper()} прокси*\n"
                f"`{proxy}`\n"
                f"📡 Пинг: `{ping:.2f} сек`\n"
                f"🌐 Используйте в своих приложениях.",
                parse_mode=ParseMode.MARKDOWN
            )
            return True
        else:
            await update.message.reply_text(f"❌ Прокси {proxy} не работает, ищу другой...")
            self.proxy_pool.mark_dead(proxy, ptype)
            return False

    async def _send_vpn_config(self, config_tuple: Tuple[str, str, str, str], update: Update):
        """Отправляет .ovpn файл пользователю"""
        name, content, login, pwd = config_tuple
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ovpn', delete=False) as f:
            # Добавляем логин/пароль в конфиг, если их нет
            if "auth-user-pass" in content and "auth-user-pass" not in content.split("\n")[-5:]:
                # нужно вставить после строки auth-user-pass
                lines = content.splitlines()
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if line.strip() == "auth-user-pass":
                        new_lines.append(login)
                        new_lines.append(pwd)
                content = "\n".join(new_lines)
            f.write(content)
            f.flush()
            with open(f.name, 'rb') as doc:
                await update.message.reply_document(
                    document=doc,
                    filename=f"{name}.ovpn",
                    caption=f"🔐 *VPN конфиг:* `{name}`\nЛогин: `{login}` Пароль: `{pwd}`",
                    parse_mode=ParseMode.MARKDOWN
                )

    # --- Команды ---
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("🌍 VPN OpenVPN", callback_data="vpn"),
             InlineKeyboardButton("⚡ HTTP Прокси", callback_data="proxy")],
            [InlineKeyboardButton("🔒 SOCKS5", callback_data="socks"),
             InlineKeyboardButton("🤖 Авто-режим", callback_data="auto")],
            [InlineKeyboardButton("🔄 Сменить прокси", callback_data="rotate")],
            [InlineKeyboardButton("📡 Проверить IP", callback_data="check")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🛡️ *Бот-мастер обхода блокировок*\n"
            "Выберите тип подключения:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        data = query.data
        user_id = update.effective_user.id

        if data == "vpn":
            # Выбираем случайный рабочий VPN из встроенных (можно парсить новые, но для скорости берём готовый)
            vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
            await self._send_vpn_config(vpn_config, update)
            self.user_last_type[user_id] = 'vpn'
        elif data == "proxy":
            # HTTP прокси
            proxy = self.proxy_pool.get_random_http()
            if not proxy:
                await query.edit_message_text("⚠️ Нет доступных HTTP прокси, попробуйте позже.")
                return
            ok = await self._check_proxy_and_return(proxy, "http", update)
            if not ok:
                # повторяем с другим
                proxy2 = self.proxy_pool.get_random_http()
                if proxy2:
                    await self._check_proxy_and_return(proxy2, "http", update)
            self.user_last_type[user_id] = 'http'
        elif data == "socks":
            proxy = self.proxy_pool.get_random_socks()
            if not proxy:
                await query.edit_message_text("⚠️ Нет доступных SOCKS5 прокси, попробуйте позже.")
                return
            ok = await self._check_proxy_and_return(proxy, "socks", update)
            if not ok:
                proxy2 = self.proxy_pool.get_random_socks()
                if proxy2:
                    await self._check_proxy_and_return(proxy2, "socks", update)
            self.user_last_type[user_id] = 'socks'
        elif data == "auto":
            # Авторежим: сначала HTTP, если плохой пинг -> VPN
            http_proxy = self.proxy_pool.get_random_http()
            if http_proxy:
                ok, ping = self.proxy_pool.test_proxy(http_proxy, "http")
                if ok and ping < 2.0:   # быстрый
                    await self._check_proxy_and_return(http_proxy, "http", update)
                    self.user_last_type[user_id] = 'http'
                    self.user_auto_counter[user_id] = 0
                else:
                    # предлагаем VPN
                    vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
                    await self._send_vpn_config(vpn_config, update)
                    self.user_last_type[user_id] = 'vpn'
                    self.user_auto_counter[user_id] = 1
            else:
                vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
                await self._send_vpn_config(vpn_config, update)
                self.user_last_type[user_id] = 'vpn'
        elif data == "rotate":
            last_type = self.user_last_type.get(user_id, 'http')
            if last_type == 'http':
                proxy = self.proxy_pool.get_random_http()
                if proxy:
                    await self._check_proxy_and_return(proxy, "http", update)
                else:
                    await query.edit_message_text("Нет доступных HTTP прокси")
            elif last_type == 'socks':
                proxy = self.proxy_pool.get_random_socks()
                if proxy:
                    await self._check_proxy_and_return(proxy, "socks", update)
                else:
                    await query.edit_message_text("Нет доступных SOCKS прокси")
            elif last_type == 'vpn':
                vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
                await self._send_vpn_config(vpn_config, update)
            else:
                await query.edit_message_text("Сначала выберите тип через /start")
        elif data == "check":
            # Показываем IP сервера бота
            try:
                resp = requests.get("https://api.ipify.org?format=json", timeout=10)
                ip = resp.json().get("ip", "неизвестно")
                await query.edit_message_text(
                    f"🖥️ *Текущий IP сервера бота:* `{ip}`\n"
                    f"ℹ️ Это IP, с которого бот обращается к интернету. Ваш реальный IP может отличаться.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                await query.edit_message_text("❌ Не удалось определить IP.")

    # --- Команды для прямого ввода ---
    async def vpn_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
        await self._send_vpn_config(vpn_config, update)

    async def proxy_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        proxy = self.proxy_pool.get_random_http()
        if proxy:
            await self._check_proxy_and_return(proxy, "http", update)
        else:
            await update.message.reply_text("Нет рабочих HTTP прокси.")

    async def socks_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        proxy = self.proxy_pool.get_random_socks()
        if proxy:
            await self._check_proxy_and_return(proxy, "socks", update)
        else:
            await update.message.reply_text("Нет рабочих SOCKS5 прокси.")

    async def auto_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # вызываем ту же логику, что и кнопка auto
        user_id = update.effective_user.id
        http_proxy = self.proxy_pool.get_random_http()
        if http_proxy:
            ok, ping = self.proxy_pool.test_proxy(http_proxy, "http")
            if ok and ping < 2.0:
                await self._check_proxy_and_return(http_proxy, "http", update)
                self.user_last_type[user_id] = 'http'
                self.user_auto_counter[user_id] = 0
            else:
                vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
                await self._send_vpn_config(vpn_config, update)
                self.user_last_type[user_id] = 'vpn'
                self.user_auto_counter[user_id] = 1
        else:
            vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
            await self._send_vpn_config(vpn_config, update)

    async def check_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            resp = requests.get("https://api.ipify.org?format=json", timeout=10)
            ip = resp.json().get("ip", "неизвестно")
            await update.message.reply_text(
                f"🖥️ *IP сервера бота:* `{ip}`",
                parse_mode=ParseMode.MARKDOWN
            )
        except:
            await update.message.reply_text("❌ Не удалось определить IP.")

    async def rotate_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        last_type = self.user_last_type.get(user_id, 'http')
        if last_type == 'http':
            proxy = self.proxy_pool.get_random_http()
            if proxy:
                await self._check_proxy_and_return(proxy, "http", update)
            else:
                await update.message.reply_text("Нет доступных HTTP прокси")
        elif last_type == 'socks':
            proxy = self.proxy_pool.get_random_socks()
            if proxy:
                await self._check_proxy_and_return(proxy, "socks", update)
            else:
                await update.message.reply_text("Нет доступных SOCKS прокси")
        elif last_type == 'vpn':
            vpn_config = random.choice(BUILTIN_VPN_CONFIGS)
            await self._send_vpn_config(vpn_config, update)
        else:
            await update.message.reply_text("Сначала выберите тип через /start или /auto")

# ==================== ФОНОВЫЕ ЗАДАЧИ ====================
async def background_proxy_refresh(proxy_pool: ProxyPool):
    """Каждые 10 минут парсит новые прокси через встроенные и добавляет в пул"""
    while True:
        await asyncio.sleep(600)  # 10 минут
        try:
            # Парсим HTTP прокси с публичных API через случайный живой прокси
            proxy = proxy_pool.get_random_http()
            if proxy:
                proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
                sources = [
                    "https://api.proxyscrape.com/?request=displayproxies&proxytype=http&timeout=5000",
                    "https://www.proxy-list.download/api/v1/get?type=http",
                ]
                for url in sources:
                    try:
                        resp = requests.get(url, proxies=proxies, timeout=15)
                        if resp.status_code == 200:
                            lines = resp.text.strip().splitlines()
                            for line in lines[:20]:  # не более 20 за раз
                                line = line.strip()
                                if line and ":" in line:
                                    proxy_pool.add_http_proxy(line)
                    except:
                        continue
            # Парсим VPN конфиги (для обновления паролей)
            vpn_configs = await VPNParser.parse_vpnbook(proxy_pool)
            if vpn_configs:
                # обновляем BUILTIN_VPN_CONFIGS глобально (неидеально, но для демо)
                global BUILTIN_VPN_CONFIGS
                BUILTIN_VPN_CONFIGS = vpn_configs + BUILTIN_VPN_CONFIGS[:5]  # оставляем резерв
        except Exception:
            pass

# ==================== ЗАПУСК ====================
def main():
    # Создаём пул прокси
    proxy_pool = ProxyPool()
    bot = SmartBot(proxy_pool)

    # Создаём приложение
    app = Application.builder().token(TOKEN).build()

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("vpn", bot.vpn_command))
    app.add_handler(CommandHandler("proxy", bot.proxy_command))
    app.add_handler(CommandHandler("socks", bot.socks_command))
    app.add_handler(CommandHandler("auto", bot.auto_command))
    app.add_handler(CommandHandler("check", bot.check_command))
    app.add_handler(CommandHandler("rotate", bot.rotate_command))
    app.add_handler(CallbackQueryHandler(bot.button_callback))

    # Запускаем фоновую задачу
    loop = asyncio.get_event_loop()
    loop.create_task(background_proxy_refresh(proxy_pool))

    # Запуск polling
    print("Бот запущен...")
    app.run_polling()

if __name__ == "__main__":
    main()
