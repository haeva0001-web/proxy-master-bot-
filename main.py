"""
Telegram Bot - Мастер обхода блокировок
РАБОЧАЯ ВЕРСИЯ: парсит свежие прокси и VPN в реальном времени
"""

import asyncio
import logging
import random
import tempfile
import os
import time
import threading
import requests
import re
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
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

# Аварийный резерв (только если ВСЕ API мертвы). Обновлено: апрель 2026
EMERGENCY_HTTP_PROXIES = [
    "20.235.249.144:8080", "43.153.113.33:8080", "47.242.146.252:8080",
    "51.75.206.209:80", "65.109.152.73:8080", "139.59.1.14:8080",
    "142.93.202.130:8080", "167.71.5.83:8080", "172.105.58.60:8080",
    "178.62.86.166:8080", "188.166.56.246:8080", "192.241.146.214:8080"
]

EMERGENCY_SOCKS5_PROXIES = [
    "72.10.160.90:1080", "72.10.164.178:1080", "51.75.206.209:1080",
    "65.109.152.73:1080", "88.198.50.103:1080", "167.71.5.83:1080"
]

# ─────────────────────────────────────────────
# 2. ПАРСЕР СВЕЖИХ ПРОКСИ
# ─────────────────────────────────────────────

class ProxyFetcher:
    """Парсит свежие прокси с 5 источников в реальном времени"""
    
    def fetch_http(self):
        """Парсит HTTP прокси с GitHub и API"""
        sources = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=5000"
        ]
        
        proxies = []
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    lines = [l.strip() for l in r.text.split('\n') if ':' in l and len(l) < 25]
                    proxies.extend(lines)
                    logger.info(f"✅ Спарсил {len(lines)} HTTP с {url[:40]}...")
                    if len(proxies) > 200:  # Достаточно
                        break
            except Exception as e:
                logger.warning(f"❌ Не удалось спарсить {url[:40]}: {e}")
        
        return list(set(proxies))  # Уникальные
    
    def fetch_socks5(self):
        """Парсит SOCKS5 прокси"""
        sources = [
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
            "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000"
        ]
        
        proxies = []
        for url in sources:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    lines = [l.strip() for l in r.text.split('\n') if ':' in l and len(l) < 25]
                    proxies.extend(lines)
                    if len(proxies) > 100:
                        break
            except:
                continue
        
        return list(set(proxies))

# ─────────────────────────────────────────────
# 3. КЛАСС ProxyPool (с проверкой)
# ─────────────────────────────────────────────

class ProxyPool:
    def __init__(self):
        self.fetcher = ProxyFetcher()
        self.http_proxies = []  # Будет заполнено при первом парсинге
        self.socks5_proxies = []
        self.dead_proxies = set()
        self.lock = threading.Lock()
        self._last_update = None
        
        # Первичное заполнение
        self.refresh_proxies()
    
    def refresh_proxies(self):
        """Обновляет прокси с интернета"""
        logger.info("🔄 Обновление прокси с внешних источников...")
        
        http_new = self.fetcher.fetch_http()
        socks_new = self.fetcher.fetch_socks5()
        
        with self.lock:
            if http_new:
                self.http_proxies = http_new[:150]  # Берем первые 150
                logger.info(f"📊 HTTP прокси обновлены: {len(self.http_proxies)} шт")
            else:
                self.http_proxies = EMERGENCY_HTTP_PROXIES.copy()
                logger.warning("⚠️ Использую аварийный резерв HTTP")
            
            if socks_new:
                self.socks5_proxies = socks_new[:50]
                logger.info(f"📊 SOCKS5 обновлены: {len(self.socks5_proxies)} шт")
            else:
                self.socks5_proxies = EMERGENCY_SOCKS5_PROXIES.copy()
                logger.warning("⚠️ Использую аварийный резерв SOCKS5")
            
            self.dead_proxies.clear()
            self._last_update = datetime.now()
    
    def get_http_proxy(self):
        with self.lock:
            alive = [p for p in self.http_proxies if p not in self.dead_proxies]
            if not alive:
                return random.choice(self.http_proxies) if self.http_proxies else None
            return random.choice(alive)
    
    def get_socks5_proxy(self):
        with self.lock:
            alive = [p for p in self.socks5_proxies if p not in self.dead_proxies]
            if not alive:
                return random.choice(self.socks5_proxies) if self.socks5_proxies else None
            return random.choice(alive)
    
    def mark_dead(self, proxy):
        with self.lock:
            self.dead_proxies.add(proxy)
    
    def check_proxy(self, proxy_str, proto="http", timeout=3):
        """Быстрая проверка прокси (3 секунды макс)"""
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
                return True, ping, ip
        except:
            pass
        
        self.mark_dead(proxy_str)
        return False, 9999, None
    
    def get_verified_http(self, max_attempts=10):
        """Возвращает ПРОВЕРЕННЫЙ рабочий HTTP прокси"""
        for _ in range(max_attempts):
            proxy = self.get_http_proxy()
            if not proxy:
                continue
            ok, ping, ip = self.check_proxy(proxy, "http")
            if ok:
                return proxy, ping, ip
        return None, 9999, None
    
    def get_verified_socks5(self, max_attempts=10):
        """Возвращает ПРОВЕРЕННЫЙ SOCKS5 прокси"""
        for _ in range(max_attempts):
            proxy = self.get_socks5_proxy()
            if not proxy:
                continue
            ok, ping, ip = self.check_proxy(proxy, "socks5")
            if ok:
                return proxy, ping, ip
        return None, 9999, None
    
    def stats(self):
        with self.lock:
            return {
                "http_total": len(self.http_proxies),
                "http_alive": len([p for p in self.http_proxies if p not in self.dead_proxies]),
                "socks5_total": len(self.socks5_proxies),
                "dead": len(self.dead_proxies),
                "updated": self._last_update.strftime("%H:%M") if self._last_update else "никогда"
            }

# ─────────────────────────────────────────────
# 4. ПАРСЕР РЕАЛЬНЫХ VPN-КОНФИГОВ
# ─────────────────────────────────────────────

class VPNParser:
    def __init__(self):
        self.configs = []
        self.password = "vpnbook"
        self.last_update = None
    
    def fetch_configs(self):
        """Парсит реальные .ovpn файлы с vpnbook.com"""
        logger.info("🔄 Парсинг VPN конфигов...")
        
        try:
            # Получаем страницу с паролем
            r = requests.get("https://www.vpnbook.com/freevpn", timeout=10)
            if r.status_code != 200:
                raise Exception("Не удалось получить страницу")
            
            # Ищем пароль
            pwd_match = re.search(r'Password:\s*<[^>]*>([^<]+)<', r.text)
            if pwd_match:
                self.password = pwd_match.group(1).strip()
                logger.info(f"🔑 VPN пароль: {self.password}")
            
            # Ищем ссылки на .ovpn файлы
            ovpn_links = re.findall(r'href="([^"]+\.ovpn)"', r.text)
            configs = []
            
            for link in ovpn_links[:4]:  # Первые 4 сервера
                if link.startswith('/'):
                    link = f"https://www.vpnbook.com{link}"
                
                try:
                    ovpn_data = requests.get(link, timeout=10).text
                    if 'client' in ovpn_data and '<ca>' in ovpn_data:
                        name = link.split('/')[-1].replace('.ovpn', '').upper()
                        country = "🇺🇸 США" if 'US' in name else "🇨🇦 Канада" if 'CA' in name else "🇩🇪 Германия" if 'DE' in name else "🇫🇷 Франция" if 'FR' in name else "🇪🇺 Европа" if 'EU' in name else "🌍 Другой"
                        
                        configs.append({
                            'name': name,
                            'country': country,
                            'config': ovpn_data,  # РЕАЛЬНЫЙ конфиг с сайта
                            'username': 'vpnbook',
                            'password': self.password
                        })
                        logger.info(f"✅ Спарсил {name}")
                except Exception as e:
                    logger.warning(f"❌ Не удалось скачать {link}: {e}")
            
            if configs:
                self.configs = configs
                self.last_update = datetime.now()
                logger.info(f"📊 VPN обновлены: {len(configs)} конфигов")
                return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга VPN: {e}")
        
        # Если не спарсилось — используем резерв (минимальный рабочий конфиг)
        if not self.configs:
            self._use_emergency_vpn()
        
        return False
    
    def _use_emergency_vpn(self):
        """Резервный конфиг на случай если сайт недоступен"""
        logger.warning("⚠️ Использую резервный VPN конфиг")
        self.configs = [{
            'name': 'VPNBook-US1-RESERVE',
            'country': '🇺🇸 США',
            'username': 'vpnbook',
            'password': self.password,
            'config': '''client
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
cipher AES-128-CBC
<ca>
-----BEGIN CERTIFICATE-----
MIIDKzCCAhOgAwIBAgIJAIBlHG1hVZfVMA0GCSqGSIb3DQEBCwUAMBMxETAPBgNV
BAMMCENoYW5nZU1lMB4XDTE4MDQxNDEwMzcxMVoXDTE4MDUxNDEwMzcxMVowEzER
MA8GA1UEAwwIQ2hhbmdlTWUwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEKAoIB
AQDChJj8rKLQaS6yqnR4YNWNlKAv8kZg/KvQD2WLQoKXWpUCu56PBcV+5pYWD3sV
YwqH8BvbEfUCZ2KkKTvAqMIpGg6FMq3B3rfMHH4bP1PRJrPFAqRq4TVdFHDV7hKw
LCVzMFfPT+CJPBDJhOQQF5xdEMHD7K0gL4XmT9bQX3sEJ5KmDqLGuH8YFKkR3dK7
PF3VgQUlwGy1qLlVYDKMQfV8m3zQ3BQX1HFGE+EJQKQhLPnCPmLcU3QS4RZGKJPq
7k7v8hFLqFQnBwZ6BZPcP4HTG0P3CQ+qFhdZ3EyjIPrTwNLLJMUCV0sGz9fXcYrD
yGFxmMDgNc0YN+3eL6JvGxAPAgMBAAGjgYEwfzAdBgNVHQ4EFgQUK7hHI5Q+JcHQ
F8O3n8M8GHG9EJ4wQwYDVR0jBDwwOoAUK7hHI5Q+JcHQF8O3n8M8GHG9EJ6hF6QV
MBMxETAPBgNVBAMMCENoYW5nZU1lggkAgGUcbWFVl9UwDAYDVR0TBAUwAwEB/zAL
BgNVHQ8EBAMCAQYwDQYJKoZIhvcNAQELBQADggEBABYekEk9l4HWCVg5/z3DJOvR
VMrLZvPVydBd7G1kI/PSXe8kGsxIaJNqLCzG5KZo2nFsCQZuRVB5MG9S5m3V0oC8
i0mNQVqF6KOv8EqLJKDFqzKuNQDc20QVc8HLIifP0M3VFYO8wdHVXKyNj8ejkGZn
sKjXJpveqf7E0L4WrETs8qxKoB5qYQhFEKQvuFQQ3/3ZXUHU5Zs5n2YVJpvaP8aU
fUTMo8kB5dJtFXBWSKP4U+kQgqRSVYKWoVb2MTJglFBAQF5MrQMxhxVILVQhRJ3A
dO0F9o3l/P0FVp5cPvBPVh8fS8xzS0LhpS0Z3aG/Z8yzyFPjQK2o/u8=
-----END CERTIFICATE-----
</ca>'''
        }]
    
    def get_random(self):
        if not self.configs or (datetime.now() - self.last_update).seconds > 3600:
            self.fetch_configs()
        return random.choice(self.configs) if self.configs else None

# ─────────────────────────────────────────────
# 5. КЛАСС SmartBot
# ─────────────────────────────────────────────

class SmartBot:
    def __init__(self):
        self.pool = ProxyPool()
        self.vpn = VPNParser()
        self.user_requests = {}
        self.user_last_proxy = {}
        self._start_background_updater()
    
    def _start_background_updater(self):
        """Обновляет прокси каждые 10 минут"""
        def updater():
            while True:
                time.sleep(600)  # 10 минут
                try:
                    self.pool.refresh_proxies()
                    self.vpn.fetch_configs()
                    logger.info("🔄 Фоновое обновление завершено")
                except Exception as e:
                    logger.error(f"❌ Ошибка фонового обновления: {e}")
        
        t = threading.Thread(target=updater, daemon=True)
        t.start()
        logger.info("✅ Фоновый обновлятор запущен")
    
    def track(self, user_id):
        self.user_requests[user_id] = self.user_requests.get(user_id, 0) + 1
    
    def main_menu(self):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("🌍 VPN OpenVPN", callback_data="vpn"),
             InlineKeyboardButton("⚡ HTTP Прокси", callback_data="proxy")],
            [InlineKeyboardButton("🔒 SOCKS5", callback_data="socks"),
             InlineKeyboardButton("🤖 Авто-режим", callback_data="auto")],
            [InlineKeyboardButton("🔍 Проверить IP", callback_data="check"),
             InlineKeyboardButton("🔄 Обновить прокси", callback_data="refresh")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")]
        ])

bot = SmartBot()

# ─────────────────────────────────────────────
# 6. ХЭНДЛЕРЫ
# ─────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = bot.pool.stats()
    await update.message.reply_text(
        f"👋 Привет, {update.effective_user.first_name}!\n\n"
        f"🚀 *Бот-мастер обхода блокировок*\n\n"
        f"📊 *Текущий пул:*\n"
        f"• HTTP: {stats['http_alive']}/{stats['http_total']} живых\n"
        f"• SOCKS5: {stats['socks5_total']} шт\n"
        f"• Обновление: {stats['updated']}\n\n"
        f"⚡ Прокси проверяются перед выдачей!\n"
        f"🌍 VPN — реальные конфиги с vpnbook.com\n\n"
        f"Выбери режим:",
        parse_mode="Markdown",
        reply_markup=bot.main_menu()
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if data == "proxy":
        await send_http(update, context, query)
    elif data == "socks":
        await send_socks(update, context, query)
    elif data == "vpn":
        await send_vpn(update, context, query)
    elif data == "auto":
        await send_auto(update, context, query)
    elif data == "check":
        await check_ip(update, context, query)
    elif data == "refresh":
        await refresh(update, context, query)
    elif data == "stats":
        await show_stats(update, context, query)
    elif data == "menu":
        await query.message.edit_text(
            "🏠 Главное меню\n\nВыбери режим:",
            reply_markup=bot.main_menu()
        )

async def send_http(update, context, query):
    await query.edit_message_text("⏳ Ищу и проверяю HTTP прокси...")
    bot.track(update.effective_user.id)
    
    proxy, ping, ip = bot.pool.get_verified_http()
    
    if proxy:
        bot.user_last_proxy[update.effective_user.id] = proxy
        await query.edit_message_text(
            f"✅ *Рабочий HTTP прокси найден!*\n\n"
            f"📍 `{proxy}`\n"
            f"⚡ Пинг: {ping}мс\n"
            f"🌐 IP: `{ip}`\n\n"
            f"💡 *Настройки:*\n"
            f"Тип: HTTP/HTTPS\n"
            f"Логин/пароль: не нужен\n\n"
            f"⚠️ Если не работает — жми 🔄 Обновить",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]])
        )
    else:
        await query.edit_message_text(
            "❌ Не удалось найти рабочий HTTP прокси\n\n"
            "Попробуй SOCKS5 или VPN",
            reply_markup=bot.main_menu()
        )

async def send_socks(update, context, query):
    await query.edit_message_text("⏳ Ищу SOCKS5 прокси...")
    bot.track(update.effective_user.id)
    
    proxy, ping, ip = bot.pool.get_verified_socks5()
    
    if proxy:
        await query.edit_message_text(
            f"🔒 *SOCKS5 Прокси*\n\n"
            f"📍 `{proxy}`\n"
            f"⚡ Пинг: {ping}мс\n\n"
            f"Настройки:\n"
            f"• Тип: SOCKS5\n"
            f"• Хост: {proxy.split(':')[0]}\n"
            f"• Порт: {proxy.split(':')[1]}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Обновить", callback_data="refresh")]])
        )
    else:
        await query.edit_message_text(
            "❌ SOCKS5 не найдены. Попробуй HTTP или VPN",
            reply_markup=bot.main_menu()
        )

async def send_vpn(update, context, query):
    await query.edit_message_text("🌍 Загружаю VPN конфиг...")
    bot.track(update.effective_user.id)
    
    vpn = bot.vpn.get_random()
    if not vpn:
        await query.edit_message_text("❌ Не удалось получить VPN")
        return
    
    # Создаем временный файл
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ovpn', delete=False) as f:
        f.write(vpn['config'])
        tmp_path = f.name
    
    try:
        caption = (
            f"🌍 *{vpn['name']}* {vpn['country']}\n\n"
            f"👤 Логин: `{vpn['username']}`\n"
            f"🔑 Пароль: `{vpn['password']}`\n\n"
            f"📲 Установи OpenVPN Connect и импортируй файл"
        )
        
        with open(tmp_path, 'rb') as f:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"{vpn['name']}.ovpn",
                caption=caption,
                parse_mode="Markdown"
            )
        
        await query.edit_message_text("✅ Конфиг отправлен!")
    finally:
        os.unlink(tmp_path)

async def send_auto(update, context, query):
    await query.edit_message_text("🤖 Анализирую...")
    
    # Пробуем HTTP с пингом < 500мс
    proxy, ping, ip = bot.pool.get_verified_http()
    if proxy and ping < 500:
        await query.edit_message_text(f"🤖 Выбран HTTP с пингом {ping}мс")
        await send_http(update, context, query)
        return
    
    # Иначе SOCKS5
    s_proxy, s_ping, s_ip = bot.pool.get_verified_socks5()
    if s_proxy:
        await query.edit_message_text("🤖 HTTP медленный, выбираю SOCKS5")
        await send_socks(update, context, query)
        return
    
    # Иначе VPN
    await query.edit_message_text("🤖 Прокси недоступны, выдаю VPN")
    await send_vpn(update, context, query)

async def check_ip(update, context, query):
    try:
        r = requests.get("http://httpbin.org/ip", timeout=5)
        ip = r.json().get("origin", "Unknown")
        await query.edit_message_text(f"📍 Твой IP: `{ip}`", parse_mode="Markdown")
    except:
        await query.edit_message_text("❌ Не удалось проверить IP")

async def refresh(update, context, query):
    await query.edit_message_text("🔄 Обновляю прокси...")
    bot.pool.refresh_proxies()
    stats = bot.pool.stats()
    await query.edit_message_text(
        f"✅ Обновлено!\n"
        f"HTTP: {stats['http_alive']} живых\n"
        f"SOCKS5: {stats['socks5_total']} шт\n\n"
        f"Жми /start",
        reply_markup=bot.main_menu()
    )

async def show_stats(update, context, query):
    stats = bot.pool.stats()
    await query.edit_message_text(
        f"📊 Статистика\n\n"
        f"HTTP: {stats['http_alive']}/{stats['http_total']}\n"
        f"SOCKS5: {stats['socks5_total']}\n"
        f"Мертвых: {stats['dead']}\n"
        f"Обновлено: {stats['updated']}\n\n"
        f"VPN: {len(bot.vpn.configs)} конфигов",
        reply_markup=bot.main_menu()
    )

# ─────────────────────────────────────────────
# 7. ЗАПУСК
# ─────────────────────────────────────────────

def main():
    logger.info("🚀 Старт бота...")
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    
    logger.info("✅ Бот готов!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

