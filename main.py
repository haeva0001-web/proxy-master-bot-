#!/usr/bin/env python3
"""
Telegram Proxy/VPN Bot - Railway Optimized
Uses WEBHOOK (required for Railway) instead of polling
"""

import os
import sys
import random
import asyncio
import logging
import tempfile
import requests
import time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    TypeHandler
)

# =============================================================================
# CONFIGURATION
# =============================================================================

TOKEN = os.environ.get("TOKEN", "8640337686:AAGGetelvbiaIKz1AIIm6mi0QC-r4yOJtRM")
PORT = int(os.environ.get("PORT", 8080))
WEBHOOK_HOST = os.environ.get("RAILWAY_STATIC_URL", "")  # Railway даёт автоматически
if not WEBHOOK_HOST:
    WEBHOOK_HOST = os.environ.get("WEBHOOK_URL", "")

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# =============================================================================
# BUILT-IN RESERVES
# =============================================================================

BUILTIN_HTTP_PROXIES = [
    "103.152.112.120:8080", "104.248.63.17:8080", "134.209.29.120:3128",
    "138.68.60.8:8080", "139.59.1.14:8080", "140.82.35.242:8080",
    "142.93.202.130:8080", "142.93.229.155:3128", "143.110.151.242:8080",
    "144.126.216.57:8080", "146.59.14.186:80", "146.59.14.186:8080",
    "147.182.180.10:8080", "149.56.96.252:9300", "157.245.97.60:8080",
    "159.89.49.172:3128", "161.35.70.249:8080", "162.243.184.21:8080",
    "164.90.210.13:8080", "165.227.215.193:8080", "167.172.158.85:8080",
    "167.71.5.83:8080", "167.99.124.118:8080", "172.104.128.149:8080",
    "172.105.58.60:8080", "172.105.117.25:3128", "172.105.197.49:8080",
    "173.212.219.227:8080", "174.138.54.49:8080", "176.31.200.104:3128",
    "178.62.86.166:8080", "178.128.82.105:8080", "178.128.200.47:8080",
    "178.128.248.26:8080", "178.238.11.165:8080", "185.132.42.201:8080",
    "188.166.56.246:8080", "188.166.162.1:8080", "188.166.204.85:8080",
    "192.99.160.45:3128", "192.241.146.214:8080", "193.70.73.66:3128",
    "194.195.123.125:8080", "195.201.42.36:8080", "198.199.86.11:8080",
    "198.199.120.102:8080", "198.211.100.124:8080", "198.211.110.185:8080",
    "206.189.35.79:8080", "207.154.231.211:8080", "209.97.150.167:8080"
]

BUILTIN_SOCKS_PROXIES = [
    "144.126.216.57:1080", "162.243.184.21:1080", "167.71.5.83:1080",
    "172.104.128.149:1080", "178.62.86.166:1080", "188.166.56.246:1080",
    "192.241.146.214:1080", "198.199.86.11:1080", "206.189.35.79:1080",
    "209.97.150.167:1080"
]

BUILTIN_VPN_CONFIGS = [
    {
        "name": "VPNBook-US1",
        "country": "🇺🇸 USA",
        "config": """client
dev tun
proto udp
remote us1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-128-CBC
fast-io""",
        "username": "vpnbook",
        "password": "d9c7f8m"
    },
    {
        "name": "VPNBook-US2",
        "country": "🇺🇸 USA",
        "config": """client
dev tun
proto udp
remote us2.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-128-CBC
fast-io""",
        "username": "vpnbook",
        "password": "d9c7f8m"
    },
    {
        "name": "VPNBook-CA1",
        "country": "🇨🇦 Canada",
        "config": """client
dev tun
proto udp
remote ca1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-128-CBC
fast-io""",
        "username": "vpnbook",
        "password": "c4b3r9x"
    },
    {
        "name": "VPNBook-DE1",
        "country": "🇩🇪 Germany",
        "config": """client
dev tun
proto udp
remote de1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-128-CBC
fast-io""",
        "username": "vpnbook",
        "password": "g5t8h2k"
    },
    {
        "name": "VPNBook-FR1",
        "country": "🇫🇷 France",
        "config": """client
dev tun
proto udp
remote fr1.vpnbook.com 80
resolv-retry infinite
nobind
persist-key
persist-tun
auth-user-pass
comp-lzo
verb 3
cipher AES-128-CBC
fast-io""",
        "username": "vpnbook",
        "password": "f2n6m9p"
    }
]

user_sessions: Dict[int, Dict] = {}

# =============================================================================
# PROXY POOL
# =============================================================================

@dataclass
class Proxy:
    address: str
    type: str
    is_alive: bool = True
    last_checked: Optional[datetime] = None
    response_time: float = 999.0
    fail_count: int = 0
    source: str = "builtin"

class ProxyPool:
    def __init__(self):
        self.http_proxies: List[Proxy] = []
        self.socks_proxies: List[Proxy] = []
        self.vpn_configs: List[Dict] = []
        self._init_builtin()
    
    def _init_builtin(self):
        for addr in BUILTIN_HTTP_PROXIES:
            self.http_proxies.append(Proxy(addr, "http", source="builtin"))
        for addr in BUILTIN_SOCKS_PROXIES:
            self.socks_proxies.append(Proxy(addr, "socks5", source="builtin"))
        self.vpn_configs = BUILTIN_VPN_CONFIGS.copy()
        logger.info(f"Initialized: {len(self.http_proxies)} HTTP, {len(self.socks_proxies)} SOCKS5, {len(self.vpn_configs)} VPN")
    
    def get_random_proxy(self, proxy_type: str = "http") -> Optional[Proxy]:
        pool = self.http_proxies if proxy_type == "http" else self.socks_proxies
        alive = [p for p in pool if p.is_alive]
        if not alive:
            dead = [p for p in pool if not p.is_alive and p.fail_count < 3]
            if dead:
                return random.choice(dead)
            return None
        return random.choice(alive)
    
    def get_random_vpn(self) -> Optional[Dict]:
        if self.vpn_configs:
            return random.choice(self.vpn_configs)
        return None
    
    def mark_dead(self, proxy: Proxy):
        proxy.is_alive = False
        proxy.fail_count += 1
    
    def mark_alive(self, proxy: Proxy, response_time: float):
        proxy.is_alive = True
        proxy.response_time = response_time
        proxy.last_checked = datetime.now()
        proxy.fail_count = 0
    
    def check_proxy(self, proxy: Proxy) -> Tuple[bool, float]:
        try:
            proxy_dict = {
                "http": f"{proxy.type}://{proxy.address}",
                "https": f"{proxy.type}://{proxy.address}"
            }
            start = time.time()
            response = requests.get(
                "http://httpbin.org/ip",
                proxies=proxy_dict,
                timeout=5
            )
            elapsed = time.time() - start
            if response.status_code == 200:
                self.mark_alive(proxy, elapsed)
                return True, elapsed
            return False, 999.0
        except Exception as e:
            self.mark_dead(proxy)
            return False, 999.0

# =============================================================================
# BOT LOGIC
# =============================================================================

class SmartBot:
    def __init__(self):
        self.pool = ProxyPool()
        self.user_history: Dict[int, List[str]] = {}
        self.application = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        
        keyboard = [
            [
                InlineKeyboardButton("🌍 VPN OpenVPN", callback_data='vpn'),
                InlineKeyboardButton("⚡ HTTP Прокси", callback_data='proxy')
            ],
            [
                InlineKeyboardButton("🔒 SOCKS5", callback_data='socks'),
                InlineKeyboardButton("🤖 Авто-режим", callback_data='auto')
            ],
            [
                InlineKeyboardButton("🔄 Сменить", callback_data='rotate'),
                InlineKeyboardButton("📍 Мой IP", callback_data='check')
            ]
        ]
        
        welcome_text = (
            "🚀 *ProxyMaster Bot* - Обход блокировок 24/7\n\n"
            f"📊 Резерв: {len(BUILTIN_HTTP_PROXIES)} HTTP | {len(BUILTIN_SOCKS_PROXIES)} SOCKS5 | {len(BUILTIN_VPN_CONFIGS)} VPN\n"
            "✅ Автономный режим (работает без внешних API)\n\n"
            "Выбери режим:"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data
        user_id = update.effective_user.id
        
        if user_id not in self.user_history:
            self.user_history[user_id] = []
        self.user_history[user_id].append(data)
        if len(self.user_history[user_id]) > 5:
            self.user_history[user_id].pop(0)
        
        if data == 'vpn':
            await self.send_vpn(update, context)
        elif data == 'proxy':
            await self.send_proxy(update, context, "http")
        elif data == 'socks':
            await self.send_proxy(update, context, "socks5")
        elif data == 'auto':
            await self.smart_select(update, context)
        elif data == 'check':
            await self.check_ip(update, context)
        elif data == 'rotate':
            await self.rotate_proxy(update, context)
    
    async def send_vpn(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.edit_message_text("🔍 Ищу VPN конфиг...")
        
        vpn = self.pool.get_random_vpn()
        if not vpn:
            await query.edit_message_text("❌ Нет доступных VPN")
            return
        
        config_content = vpn["config"]
        filename = f"{vpn['name']}.ovpn"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ovpn', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            caption = (
                f"🌍 *{vpn['name']}* {vpn['country']}\n"
                f"👤 Логин: `{vpn['username']}`\n"
                f"🔑 Пароль: `{vpn['password']}`\n\n"
                f"Импортируй в OpenVPN Connect"
            )
            
            with open(temp_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=f,
                    filename=filename,
                    caption=caption,
                    parse_mode='Markdown'
                )
            
            await query.edit_message_text("✅ Конфиг отправлен!")
        finally:
            os.unlink(temp_path)
    
    async def send_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE, proxy_type: str):
        query = update.callback_query
        proxy_type_name = "HTTP" if proxy_type == "http" else "SOCKS5"
        await query.edit_message_text(f"🔍 Проверяю {proxy_type_name}...")
        
        for attempt in range(5):
            proxy = self.pool.get_random_proxy(proxy_type)
            if not proxy:
                continue
            
            is_working, response_time = self.pool.check_proxy(proxy)
            
            if is_working:
                speed_emoji = "🟢" if response_time < 0.5 else "🟡" if response_time < 1.0 else "🔴"
                
                message = (
                    f"⚡ *{proxy_type_name} Прокси*\n\n"
                    f"📍 `{proxy.address}`\n"
                    f"⏱ {speed_emoji} {response_time:.2f}s\n\n"
                    f"Настройки:\n"
                    f"• Тип: {proxy_type.upper()}\n"
                    f"• Логин/пароль: нет\n\n"
                    f"🔄 Не работает? Жми /rotate"
                )
                
                keyboard = [[InlineKeyboardButton("🔄 Сменить", callback_data='rotate')]]
                
                await query.edit_message_text(
                    message,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
                if update.effective_user.id not in user_sessions:
                    user_sessions[update.effective_user.id] = {}
                user_sessions[update.effective_user.id]['current_proxy'] = proxy
                return
        
        await query.edit_message_text(
            "❌ Не удалось найти рабочий прокси\nПопробуй VPN",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🌍 VPN", callback_data='vpn')]])
        )
    
    async def smart_select(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        
        history = self.user_history.get(user_id, [])
        
        if len(history) >= 3 and len(set(history)) == 1:
            current = history[-1]
            if current in ['proxy', 'http']:
                await query.edit_message_text("🤖 Проблемы с HTTP. Переключаю на SOCKS5...")
                await asyncio.sleep(1)
                await self.send_proxy(update, context, "socks5")
            elif current == 'socks':
                await query.edit_message_text("🤖 Переключаю на VPN...")
                await asyncio.sleep(1)
                await self.send_vpn(update, context)
            else:
                await self.send_proxy(update, context, "http")
        else:
            await query.edit_message_text("🤖 Ищу быстрый прокси...")
            await self.send_proxy(update, context, "http")
    
    async def check_ip(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.edit_message_text("📍 Проверяю IP...")
        
        try:
            response = requests.get("http://httpbin.org/ip", timeout=10)
            ip = response.json().get('origin', 'Unknown')
            await query.edit_message_text(f"📍 *Твой IP:*\n`{ip}`", parse_mode='Markdown')
        except Exception as e:
            await query.edit_message_text(f"❌ Ошибка: {str(e)[:100]}")
    
    async def rotate_proxy(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        user_id = update.effective_user.id
        session = user_sessions.get(user_id, {})
        current = session.get('current_proxy')
        
        if current:
            self.pool.mark_dead(current)
        
        await query.edit_message_text("🔄 Ищу новый...")
        await self.send_proxy(update, context, "http")

# =============================================================================
# FLASK WEB SERVER + WEBHOOK
# =============================================================================

flask_app = Flask(__name__)
bot_instance = SmartBot()

@flask_app.route('/')
def health():
    return "✅ Bot is running!", 200

@flask_app.route(f'/webhook/{TOKEN}', methods=['POST'])
def webhook():
    """Receive updates from Telegram"""
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot_instance.application.bot)
        asyncio.create_task(bot_instance.application.process_update(update))
        return "OK", 200
    return "Forbidden", 403

def main():
    if not TOKEN:
        logger.error("No TOKEN!")
        sys.exit(1)
    
    # Create application
    bot_instance.application = Application.builder().token(TOKEN).build()
    
    # Add handlers
    bot_instance.application.add_handler(CommandHandler("start", bot_instance.start))
    bot_instance.application.add_handler(CallbackQueryHandler(bot_instance.button_handler))
    
    # Set webhook if URL provided, else start polling (local dev)
    if WEBHOOK_HOST:
        logger.info(f"Setting webhook: {WEBHOOK_URL}")
        
        # Initialize and set webhook
        bot_instance.application.initialize()
        bot_instance.application.bot.set_webhook(url=WEBHOOK_URL)
        
        # Start flask
        flask_app.run(host='0.0.0.0', port=PORT)
    else:
        logger.info("No WEBHOOK_URL, starting polling...")
        bot_instance.application.run_polling()

if __name__ == "__main__":
    main()

