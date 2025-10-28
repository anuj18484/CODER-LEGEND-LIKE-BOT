import telebot
import requests
import time
import json
import os
import random
import string
import logging
import re
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Logging setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = "8350357234:AAG4hN-sXdxw5YU4Ggd9Yz_xcHy1TK5pUtE"
OWNER_ID = 8100642714
CHANNELS = ["https://t.me/+NQ9U36WfvdlkZjM9", "https://t.me/+NQ9U36WfvdlkZjM9"]
GROUP_LINK = "https://t.me/CODER_LEGEND_LIKE"
VIDEO_URL = "video?raw=true"
LIKE_API_URL = "https://dpx-army-ff-ghost-apis.vercel.app/like?uid={uid}&server_name={region}&key=@ghost_x_like"
VISIT_API_URL = "xxxx"
SHORTENER_API = "dc51b152a241efbfe306fdcf20bb5b2345e9e855"
VISIT_COOLDOWN = 120
ALLOWED_GROUP_ID = --1003270164289

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

class DataStorage:
    def __init__(self):
        self.approved_groups = set()
        self.vip_users = set()
        self.verification_credits = {}
        self.used_tokens = set()
        self.user_last_verification = {}
        self.pending_requests = {}
        self.token_to_user = {}
        self.vip_expiry = {}
        self.visit_cooldowns = {}
        self.user_coins = {}
        self.all_users = set()
        self.bot_active = True  # New field for bot on/off status
        self.load_data()

    def save_data(self):
        data = {
            'approved_groups': list(self.approved_groups),
            'vip_users': list(self.vip_users),
            'verification_credits': self.verification_credits,
            'used_tokens': list(self.used_tokens),
            'user_last_verification': self.user_last_verification,
            'pending_requests': {k: {'region': v['region'], 'uid': v['uid'], 'type': v['type']} 
                               for k, v in self.pending_requests.items()},  # Save only necessary data
            'token_to_user': self.token_to_user,
            'vip_expiry': self.vip_expiry,
            'visit_cooldowns': self.visit_cooldowns,
            'user_coins': self.user_coins,
            'all_users': list(self.all_users),
            'bot_active': self.bot_active  # Save bot status
        }
        with open('bot_data.json', 'w') as f:
            json.dump(data, f, indent=4)

    def load_data(self):
        if os.path.exists('bot_data.json'):
            with open('bot_data.json', 'r') as f:
                data = json.load(f)
                self.approved_groups = set(data.get('approved_groups', []))
                self.vip_users = set(data.get('vip_users', []))
                self.verification_credits = data.get('verification_credits', {})
                self.used_tokens = set(data.get('used_tokens', []))
                self.user_last_verification = data.get('user_last_verification', {})
                self.token_to_user = data.get('token_to_user', {})
                self.vip_expiry = data.get('vip_expiry', {})
                self.visit_cooldowns = data.get('visit_cooldowns', {})
                self.user_coins = data.get('user_coins', {})
                self.all_users = set(data.get('all_users', []))
                self.bot_active = data.get('bot_active', True)  # Load bot status
                
                # Reconstruct pending_requests with message objects
                self.pending_requests = {}
                for user_id, req_data in data.get('pending_requests', {}).items():
                    self.pending_requests[int(user_id)] = {
                        'message': None,  # Will be replaced when needed
                        'region': req_data['region'],
                        'uid': req_data['uid'],
                        'type': req_data['type']
                    }

db = DataStorage()

def shorten_url(url):
    try:
        response = requests.get(f"https://earnlinks.in/api?api={SHORTENER_API}&url={requests.utils.quote(url)}&format=text", timeout=10)
        return response.text if response.text.startswith('http') else url
    except:
        return url

def is_subscribed(user_id):
    not_joined = []
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ['member', 'creator', 'administrator']:
                not_joined.append(channel)
        except:
            not_joined.append(channel)
    return not_joined

def call_like_api(region, uid):
    try:
        response = requests.get(f"{LIKE_API_URL}?server_name={region}&uid={uid}", timeout=15)
        return response.json() if response.status_code == 200 else {"status": 0, "error": "API_ERROR"}
    except Exception as e:
        print(f"Like API Error: {e}")
        return {"status": 0, "error": "CONNECTION_ERROR"}

def call_visit_api(region, uid):
    try:
        response = requests.get(f"{VISIT_API_URL}/{region}/{uid}", timeout=15)
        return response.json() if response.status_code == 200 else {"error": "API_ERROR"}
    except Exception as e:
        print(f"Visit API Error: {e}")
        return {"error": "CONNECTION_ERROR"}

def generate_verification_token(user_id):
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    db.token_to_user[token] = user_id
    db.save_data()
    return token

def is_vip(user_id):
    if user_id in db.vip_users or user_id == OWNER_ID:
        if user_id in db.vip_expiry:
            if time.time() < db.vip_expiry[user_id]:
                return True
            else:
                db.vip_users.remove(user_id)
                del db.vip_expiry[user_id]
                db.save_data()
                return False
        return True
    return False

def get_profile_info(uid, region):
    url = f"https://aditya-info-v9op.onrender.com/player-info?uid={uid}&region={region}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        logger.error(f"Error fetching profile info: {e}")
        return None

def format_timestamp(ts):
    try:
        if isinstance(ts, str) and ts.isdigit():
            ts = int(ts)
        return datetime.fromtimestamp(ts).strftime('%d %B %Y %H:%M:%S')
    except:
        return "Not Available"

def get_user_info(user_id):
    try:
        user = bot.get_chat(user_id)
        username = f"@{user.username}" if user.username else f"ID: {user_id}"
        name = user.first_name or ""
        if user.last_name:
            name += f" {user.last_name}"
        return username, name.strip()
    except:
        return f"ID: {user_id}", f"User {user_id}"

def is_admin(user_id):
    return user_id == OWNER_ID

def get_help_message(user_id):
    is_vip_user = is_vip(user_id)
    
    help_message = """
✨ <b>CODER LEGEND VIP BOT HELP CENTER</b> ✨

🎮 <b>MAIN COMMANDS:</b>
╰┈➤ <code>/start</code> - Start the bot
╰┈➤ <code>/help</code> - Show this help
╰┈➤ <code>/coins</code> - Check your coins

💎 <b>VIP SERVICES:</b>
╰┈➤ <code>/like &lt;region&gt; &lt;uid&gt;</code> - Send likes
╰┈➤ <code>/visit &lt;region&gt; &lt;uid&gt;</code> - Send visits

🌐 <b>REGION CODES:</b>
╰┈➤ <code>bd</code> - Bangladesh
╰┈➤ <code>ind</code> - Indonesia
╰┈➤ <code>ind</code> - India
╰┈➤ <code>br</code> - Brazil
╰┈➤ <code>pk</code> - Pakistan

🔐 <b>VERIFICATION SYSTEM:</b>
1. Join required channels
2. Use /like or /visit
3. Complete verification
4. Earn 1 free credit

💰 <b>COIN SYSTEM:</b>
╰┈➤ Earn coins via verification
╰┈➤ Spend coins for services
╰┈➤ Check with /coins
""" + (f"""

🌟 <b>VIP MEMBER PERKS:</b>
╰┈➤ Unlimited services
╰┈➤ No cooldowns
╰┈➤ Priority support
""" if is_vip_user else """

🔮 <b>BECOME VIP:</b>
╰┈➤ Contact @CODER_LEGEND
╰┈➤ Get unlimited access
""") + """

📢 <b>SUPPORT:</b>
╰┈➤ Channel: @CODER_LEGEND_LIKE
╰┈➤ Group: @CODER_LEGEND_LIKE
╰┈➤ Owner: @CODER_LEGEND
"""
    return help_message

def check_bot_active(message):
    if not db.bot_active:
        bot.reply_to(message, "🔴 <b>BOT IS CURRENTLY OFFLINE</b>\n\nPlease wait until the bot is back online.")
        return False
    return True

@bot.message_handler(commands=['ghost-off'])
def ghost_off(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ You are not authorized to use this command!")
        return
    
    db.bot_active = False
    db.save_data()
    bot.reply_to(message, "🔴 <b>BOT HAS BEEN TURNED OFF</b>\n\nNo commands will work until the bot is turned back on.")

@bot.message_handler(commands=['ghost-on'])
def ghost_on(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ You are not authorized to use this command!")
        return
    
    db.bot_active = True
    db.save_data()
    bot.reply_to(message, "🟢 <b>BOT HAS BEEN TURNED ON</b>\n\nAll commands are now working normally.")

@bot.message_handler(commands=['start'])
def handle_start(message):
    if not check_bot_active(message):
        return
    
    args = message.text.split()
    if len(args) > 1 and args[1].startswith('verify_'):
        handle_verification(message)
        return
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🌟 JOIN VIP GROUP", url=GROUP_LINK))
    for channel in CHANNELS:
        kb.add(InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
    
    bot.reply_to(message,
        "✨ <b>🔥 WELCOME TO CODER LEGEND VIP BOT 🔥</b> ✨\n\n"
        "💎 <b>Premium FF ID Services</b>\n"
        "⚡ Instant Like/Visit Delivery\n"
        "🔒 Secure VIP Network\n\n"
        "<b>🔗 JOIN OUR CHANNELS:</b>",
        reply_markup=kb,
        disable_web_page_preview=True
    )

@bot.message_handler(commands=['help'])
def handle_help(message):
    if not check_bot_active(message):
        return
    
    help_msg = get_help_message(message.from_user.id)
    bot.reply_to(message, help_msg, parse_mode='HTML', disable_web_page_preview=True)

@bot.message_handler(commands=['addvip'])
def add_vip(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    try:
        args = message.text.split()
        
        if len(args) < 3:
            bot.reply_to(message,
                "✨ <b>VIP ADDITION COMMAND</b> ✨\n\n"
                "<code>/addvip &lt;duration&gt; &lt;user_id/@username&gt;</code>\n\n"
                "⏳ <b>Duration Examples:</b>\n"
                "<code>30min</code>, <code>2hours</code>, <code>15days</code>, <code>perm</code>\n\n"
                "💎 <b>Examples:</b>\n"
                "<code>/addvip 30min @username</code>\n"
                "<code>/addvip 2hours 123456789</code>\n"
                "<code>/addvip perm @user</code>",
                parse_mode='HTML'
            )
            return
        
        duration_input = args[1].lower()
        target_input = args[2]
        
        try:
            if target_input.startswith('@'):
                user_info = bot.get_chat(target_input)
                target = user_info.id
            else:
                target = int(target_input)
        except:
            bot.reply_to(message, "❌ Invalid user specified")
            return
        
        if target in db.vip_users:
            bot.reply_to(message, "⚠️ User is already VIP")
            return
        
        if duration_input == 'perm':
            expiry = 'Permanent'
            db.vip_users.add(target)
            expiry_time = None
        else:
            match = re.match(r'^(\d+)(min|mins|minute|minutes|hour|hours|day|days)$', duration_input)
            if not match:
                bot.reply_to(message, "❌ Invalid duration format. Examples: 30min, 2hours, 15days")
                return
            
            amount = int(match.group(1))
            unit = match.group(2).lower()
            
            if unit.startswith('min'):
                expiry_time = time.time() + (amount * 60)
                expiry = f"{amount} minute(s)"
            elif unit.startswith('hour'):
                expiry_time = time.time() + (amount * 3600)
                expiry = f"{amount} hour(s)"
            elif unit.startswith('day'):
                expiry_time = time.time() + (amount * 86400)
                expiry = f"{amount} day(s)"
            
            db.vip_users.add(target)
            db.vip_expiry[target] = expiry_time
        
        db.save_data()
        
        try:
            user = bot.get_chat(target)
            username = f"@{user.username}" if user.username else str(target)
        except:
            username = str(target)
        
        bot.reply_to(message,
            f"🎉 <b>VIP STATUS GRANTED</b> 🎉\n\n"
            f"👤 <b>User:</b> {username}\n"
            f"🆔 <b>ID:</b> <code>{target}</code>\n"
            f"⏳ <b>Duration:</b> {expiry}\n"
            f"🔑 <b>Added by:</b> @{message.from_user.username}",
            parse_mode='HTML'
        )
        
        try:
            bot.send_message(
                target,
                f"✨ <b>🌟 VIP MEMBERSHIP ACTIVATED 🌟</b> ✨\n\n"
                f"⏳ <b>Duration:</b> {expiry}\n"
                f"📅 <b>Activated at:</b> {datetime.now().strftime('%d %B %Y %H:%M:%S')}\n\n"
                f"Thank you for being part of our VIP community!",
                parse_mode='HTML'
            )
        except:
            pass
            
    except Exception as e:
        logger.error(f"Add VIP error: {e}")
        bot.reply_to(message, "⚠️ Error processing command")

@bot.message_handler(commands=['dvip'])
def remove_vip(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    try:
        if message.reply_to_message:
            target = message.reply_to_message.from_user.id
        else:
            target = int(message.text.split()[1])

        if target in db.vip_users:
            db.vip_users.remove(target)
            if target in db.vip_expiry:
                del db.vip_expiry[target]
            db.save_data()
            bot.reply_to(message, f"🚫 REMOVED {target} FROM VIP LIST")
        else:
            bot.reply_to(message, "⚠️ This user is not in VIP list")
    except:
        bot.reply_to(message, "⚠️ Usage: Reply to user or provide user ID")

@bot.message_handler(commands=['vips'])
def list_vips(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if not db.vip_users:
        bot.reply_to(message, "No VIP users yet.")
        return
    
    text = "👑 VIP Users:\n"
    for user_id in db.vip_users:
        expiry = db.vip_expiry.get(user_id, "Permanent")
        if expiry != "Permanent":
            expiry = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(expiry))
        try:
            user = bot.get_chat(user_id)
            username = f"@{user.username}" if user.username else str(user_id)
        except:
            username = str(user_id)
        text += f"{username} - Expires: {expiry}\n"
    
    bot.reply_to(message, text)

@bot.message_handler(commands=['addc'])
def add_coins(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    try:
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, 
                "💎 <b>Add Coins Command</b> 💎\n\n"
                "<code>/addc &lt;amount&gt; &lt;user_id/@username&gt;</code>\n\n"
                "<b>Example:</b>\n"
                "<code>/addc 100 123456789</code>\n"
                "<code>/addc 50 @username</code>",
                parse_mode='HTML')
            return
        
        amount = int(args[1])
        target_input = args[2]
        
        try:
            if target_input.startswith('@'):
                user_info = bot.get_chat(target_input)
                target = user_info.id
            else:
                target = int(target_input)
        except:
            bot.reply_to(message, "❌ Invalid user specified")
            return
        
        db.user_coins[target] = db.user_coins.get(target, 0) + amount
        db.all_users.add(target)
        db.save_data()
        
        username, name = get_user_info(target)
        
        bot.reply_to(message,
            f"💰 <b>COINS ADDED SUCCESSFULLY!</b>\n\n"
            f"👤 <b>User:</b> {username}\n"
            f"📛 <b>Name:</b> {name}\n"
            f"🆔 <b>ID:</b> {target}\n"
            f"🪙 <b>Added:</b> {amount} coins\n"
            f"💎 <b>New Balance:</b> {db.user_coins.get(target, 0)} coins",
            parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error in add_coins: {e}")
        bot.reply_to(message, "❌ Error processing command")

@bot.message_handler(commands=['dcn'])
def deduct_coins(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    try:
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, 
                "💎 <b>Deduct Coins Command</b> 💎\n\n"
                "<code>/dcn &lt;amount/all&gt; &lt;user_id/@username&gt;</code>\n\n"
                "<b>Examples:</b>\n"
                "<code>/dcn 50 123456789</code>\n"
                "<code>/dcn all @username</code>",
                parse_mode='HTML')
            return
        
        amount_input = args[1].lower()
        target_input = args[2]
        
        try:
            if target_input.startswith('@'):
                user_info = bot.get_chat(target_input)
                target = user_info.id
            else:
                target = int(target_input)
        except:
            bot.reply_to(message, "❌ Invalid user specified")
            return
        
        if amount_input == 'all':
            amount = db.user_coins.get(target, 0)
        else:
            amount = int(amount_input)
            
        current = db.user_coins.get(target, 0)
        
        if current < amount:
            bot.reply_to(message, f"❌ User only has {current} coins")
            return
            
        db.user_coins[target] = current - amount
        db.save_data()
        
        username, name = get_user_info(target)
        
        bot.reply_to(message,
            f"💰 <b>COINS DEDUCTED SUCCESSFULLY!</b>\n\n"
            f"👤 <b>User:</b> {username}\n"
            f"📛 <b>Name:</b> {name}\n"
            f"🆔 <b>ID:</b> {target}\n"
            f"🪙 <b>Deducted:</b> {amount} coins\n"
            f"💎 <b>New Balance:</b> {db.user_coins.get(target, 0)} coins",
            parse_mode='HTML')
            
    except Exception as e:
        logger.error(f"Error in deduct_coins: {e}")
        bot.reply_to(message, "❌ Error processing command")

@bot.message_handler(commands=['coins'])
def check_coins(message):
    if not check_bot_active(message):
        return
    
    try:
        args = message.text.split()
        target = message.from_user.id
        
        if len(args) > 1 and is_admin(message.from_user.id):
            target_input = args[1]
            try:
                if target_input.startswith('@'):
                    user_info = bot.get_chat(target_input)
                    target = user_info.id
                else:
                    target = int(target_input)
            except:
                bot.reply_to(message, "❌ Invalid user specified")
                return
        
        coins = db.user_coins.get(target, 0)
        username, name = get_user_info(target)
        
        response = (
            f"✨ <b>GHOST X COIN BALANCE</b> ✨\n\n"
            f"👤 <b>User:</b> {username}\n"
            f"📛 <b>Name:</b> {name}\n"
            f"🆔 <b>ID:</b> <code>{target}</code>\n\n"
            f"💰 <b>Coin Balance:</b>\n"
            f"╰┈➤ <b>{coins} Coins</b>\n\n"
            f"🌟 <b>Status:</b> {'VIP Member' if is_vip(target) else 'Regular User'}\n"
            f"📅 <b>Last Active:</b> {format_timestamp(db.user_last_verification.get(target, 0))}"
        )
        
        bot.reply_to(message, response, parse_mode='HTML')
        
    except Exception as e:
        logger.error(f"Error in check_coins: {e}")
        bot.reply_to(message, "❌ Error checking coin balance")

@bot.message_handler(commands=['approve'])
def approve_group(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if message.chat.id != message.from_user.id:
        db.approved_groups.add(message.chat.id)
        db.save_data()
        bot.reply_to(message, "💎 GROUP APPROVED FOR VIP SERVICE")

@bot.message_handler(commands=['dapprove'])
def disapprove_group(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    try:
        if message.reply_to_message and message.reply_to_message.forward_from_chat:
            group_id = message.reply_to_message.forward_from_chat.id
        else:
            group_id = int(message.text.split()[1])

        if group_id in db.approved_groups:
            db.approved_groups.remove(group_id)
            db.save_data()
            bot.reply_to(message, f"🚫 GROUP {group_id} REMOVED FROM APPROVED LIST")
        else:
            bot.reply_to(message, "⚠️ This group is not in the approved list")
    except:
        bot.reply_to(message, "⚠️ Usage: Reply to a forwarded group message or provide group ID")

@bot.message_handler(commands=['groups'])
def list_groups(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if not db.approved_groups:
        bot.reply_to(message, "No approved groups yet.")
        return
    
    text = "📢 Approved Groups:\n"
    for group_id in db.approved_groups:
        try:
            chat = bot.get_chat(group_id)
            text += f"{chat.title} ({group_id})\n"
        except:
            text += f"{group_id}\n"
    
    bot.reply_to(message, text)

@bot.message_handler(commands=['broadcast'])
def broadcast_message(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ Please reply to a message to broadcast it")
        return
    
    confirm_kb = InlineKeyboardMarkup()
    confirm_kb.add(
        InlineKeyboardButton("✅ Confirm Broadcast", callback_data="broadcast_confirm"),
        InlineKeyboardButton("❌ Cancel", callback_data="broadcast_cancel")
    )
    
    bot.reply_to(message,
        "⚠️ <b>BROADCAST CONFIRMATION</b>\n\n"
        f"This message will be sent to:\n"
        f"• {len(db.approved_groups)} approved groups\n"
        f"• {len(db.all_users)} individual users\n\n"
        "Are you sure you want to proceed?",
        reply_markup=confirm_kb,
        reply_to_message_id=message.reply_to_message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('broadcast_'))
def handle_broadcast_confirmation(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "⚠️ You are not authorized!", show_alert=True)
        return
    
    if call.data == "broadcast_cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Broadcast cancelled")
        return
    
    bot.answer_callback_query(call.id, "Starting broadcast...")
    
    original_message = call.message.reply_to_message
    total_users = len(db.all_users)
    total_groups = len(db.approved_groups)
    success_users = 0
    success_groups = 0
    failed_users = 0
    failed_groups = 0
    
    status_msg = bot.edit_message_text(
        "📢 <b>BROADCAST IN PROGRESS</b>\n\n"
        f"• Users: 0/{total_users}\n"
        f"• Groups: 0/{total_groups}",
        call.message.chat.id,
        call.message.message_id
    )
    
    for user_id in db.all_users:
        try:
            bot.copy_message(
                user_id,
                original_message.chat.id,
                original_message.message_id
            )
            success_users += 1
        except Exception as e:
            failed_users += 1
            logger.error(f"Failed to send to user {user_id}: {e}")
        
        if success_users % 10 == 0 or user_id == list(db.all_users)[-1]:
            bot.edit_message_text(
                "📢 <b>BROADCAST IN PROGRESS</b>\n\n"
                f"• Users: {success_users}/{total_users}\n"
                f"• Groups: 0/{total_groups}",
                call.message.chat.id,
                status_msg.message_id
            )
    
    for group_id in db.approved_groups:
        try:
            bot.copy_message(
                group_id,
                original_message.chat.id,
                original_message.message_id
            )
            success_groups += 1
        except Exception as e:
            failed_groups += 1
            logger.error(f"Failed to send to group {group_id}: {e}")
        
        if success_groups % 5 == 0 or group_id == list(db.approved_groups)[-1]:
            bot.edit_message_text(
                "📢 <b>BROADCAST IN PROGRESS</b>\n\n"
                f"• Users: {success_users}/{total_users}\n"
                f"• Groups: {success_groups}/{total_groups}",
                call.message.chat.id,
                status_msg.message_id
            )
    
    bot.edit_message_text(
        "✅ <b>BROADCAST COMPLETED</b>\n\n"
        f"👤 <b>Users:</b> {success_users} success, {failed_users} failed\n"
        f"👥 <b>Groups:</b> {success_groups} success, {failed_groups} failed\n\n"
        f"📅 <b>Completed at:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        call.message.chat.id,
        status_msg.message_id
    )

@bot.message_handler(commands=['modhu'])
def broadcast_to_groups(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        return
    
    if not message.reply_to_message:
        bot.reply_to(message, "Reply to a message to broadcast it.")
        return
    
    success = 0
    failed = 0
    for group_id in db.approved_groups:
        try:
            bot.forward_message(group_id, message.chat.id, message.reply_to_message.message_id)
            success += 1
        except:
            failed += 1
    
    bot.reply_to(message, f"Broadcast complete!\nSuccess: {success}\nFailed: {failed}")

@bot.message_handler(commands=['like'])
def handle_like(message):
    if not check_bot_active(message):
        return
    
    db.all_users.add(message.from_user.id)
    
    if message.chat.type == "private":
        bot.reply_to(message, f"⚠️ VIP COMMAND ONLY WORKS IN OUR GROUP:\n{GROUP_LINK}", disable_web_page_preview=True)
        return
    
    if message.chat.id not in db.approved_groups:
        bot.reply_to(message, "🚫 VIP GROUP ACCESS REQUIRED\nContact @CODER_LEGEND for approval")
        return
    
    if message.from_user.id in db.pending_requests:
        try:
            old_msg = db.pending_requests[message.from_user.id]['message']
            if old_msg.message_id != message.message_id:
                bot.delete_message(old_msg.chat.id, old_msg.message_id)
        except:
            pass
    
    not_joined = is_subscribed(message.from_user.id)
    if not_joined:
        kb = InlineKeyboardMarkup()
        for channel in not_joined:
            kb.add(InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
        kb.add(InlineKeyboardButton("🔓 VERIFY JOINING", callback_data=f"verify_join:{message.from_user.id}:like"))
        
        sent_msg = bot.reply_to(message, "<b>🔒 VIP CHANNEL ACCESS REQUIRED</b>", reply_markup=kb, disable_web_page_preview=True)
        
        db.pending_requests[message.from_user.id] = {
            'message': sent_msg,
            'type': 'like',
            'region': None,
            'uid': None
        }
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message,
            "<b>💎 VIP LIKE COMMAND USAGE</b>\n\n"
            "<code>/like &lt;region&gt; &lt;uid&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "<code>/like bd 123456789</code>\n"
            "<code>/like id 987654321</code>",
            disable_web_page_preview=True
        )
        return
    
    region, uid = args[1], args[2]
    
    # Check if user is VIP or has credits
    user_id = message.from_user.id
    if is_vip(user_id):
        process_like(message, region, uid)
    elif db.verification_credits.get(user_id, 0) > 0:
        original_credits = db.verification_credits.get(user_id, 0)
        db.verification_credits[user_id] -= 1
        db.save_data()
        process_like(message, region, uid, original_credits)
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔓 GET VERIFICATION CREDIT", callback_data=f"credit:{user_id}:{region}:{uid}:like"))
        
        bot.reply_to(message,
            "<b>💎 VIP LIKE REQUEST</b>\n\n"
            f"🆔 <b>UID:</b> {uid}\n"
            f"🌍 <b>Region:</b> {region.upper()}\n\n"
            "<b>🔒 VERIFICATION REQUIRED</b>\n"
            "You have 0 credits left. Click below to get 1 FREE credit:",
            reply_markup=kb,
            disable_web_page_preview=True
        )

@bot.message_handler(commands=['visit'])
def handle_visit(message):
    if not check_bot_active(message):
        return
    
    db.all_users.add(message.from_user.id)
    
    if message.chat.type == "private":
        bot.reply_to(message, f"⚠️ VIP COMMAND ONLY WORKS IN OUR GROUP:\n{GROUP_LINK}", disable_web_page_preview=True)
        return
    
    if message.chat.id not in db.approved_groups:
        bot.reply_to(message, "🚫 VIP GROUP ACCESS REQUIRED\nContact @CODER_LEGEND for approval")
        return
    
    if message.from_user.id in db.pending_requests:
        try:
            old_msg = db.pending_requests[message.from_user.id]['message']
            if old_msg.message_id != message.message_id:
                bot.delete_message(old_msg.chat.id, old_msg.message_id)
        except:
            pass
    
    not_joined = is_subscribed(message.from_user.id)
    if not_joined:
        kb = InlineKeyboardMarkup()
        for channel in not_joined:
            kb.add(InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
        kb.add(InlineKeyboardButton("🔓 VERIFY JOINING", callback_data=f"verify_join:{message.from_user.id}:visit"))
        
        sent_msg = bot.reply_to(message, "<b>🔒 VIP CHANNEL ACCESS REQUIRED</b>", reply_markup=kb, disable_web_page_preview=True)
        
        db.pending_requests[message.from_user.id] = {
            'message': sent_msg,
            'type': 'visit',
            'region': None,
            'uid': None
        }
        return
    
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message,
            "<b>👑 VIP VISIT COMMAND USAGE</b>\n\n"
            "<code>/visit &lt;region&gt; &lt;uid&gt;</code>\n\n"
            "<b>Examples:</b>\n"
            "<code>/visit bd 123456789</code>\n"
            "<code>/visit id 987654321</code>",
            disable_web_page_preview=True
        )
        return
    
    region, uid = args[1], args[2]
    
    # Check if user is VIP or has credits
    user_id = message.from_user.id
    
    # Check cooldown for non-VIP users
    if not is_vip(user_id):
        last_visit = db.visit_cooldowns.get(user_id, 0)
        elapsed = time.time() - last_visit
        if elapsed < VISIT_COOLDOWN:
            remaining = int(VISIT_COOLDOWN - elapsed)
            bot.reply_to(message, f"⏳ Please wait {remaining} seconds before sending another visit.\n💎 Become VIP for no cooldown!")
            return
    
    if is_vip(user_id):
        process_visit(message, region, uid)
    elif db.verification_credits.get(user_id, 0) > 0:
        original_credits = db.verification_credits.get(user_id, 0)
        db.verification_credits[user_id] -= 1
        db.save_data()
        process_visit(message, region, uid, original_credits)
    else:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("🔓 GET VERIFICATION CREDIT", callback_data=f"credit:{user_id}:{region}:{uid}:visit"))
        
        bot.reply_to(message,
            "<b>👑 VIP VISIT REQUEST</b>\n\n"
            f"🆔 <b>UID:</b> {uid}\n"
            f"🌍 <b>Region:</b> {region.upper()}\n\n"
            "<b>🔒 VERIFICATION REQUIRED</b>\n"
            "You have 0 credits left. Click below to get 1 FREE credit:",
            reply_markup=kb,
            disable_web_page_preview=True
        )

def process_like(message, region, uid, original_credits=None):
    msg = bot.reply_to(message, "⚡ PROCESSING VIP REQUEST...")
    
    steps = [
        "🔐 VERIFYING VIP ACCESS...",
        "🌐 CONNECTING TO SERVER...",
        "💎 PROCESSING REQUEST...",
        "✅ FINALIZING TRANSACTION..."
    ]
    
    for step in steps:
        time.sleep(1.2)
        bot.edit_message_text(step, message.chat.id, msg.message_id)
    
    api_result = call_like_api(region, uid)
    user_id = message.from_user.id
    
    if api_result.get('error') or api_result.get('status') == 2:
        if original_credits is not None and user_id not in db.vip_users:
            db.verification_credits[user_id] = original_credits
            db.save_data()
    
    try:
        status = api_result.get('status', 0)
        
        if status == 1:
            likes_given = int(api_result.get('LikesGivenByAPI', 0))
            likes_before = int(api_result.get('LikesbeforeCommand', 0))
            likes_after = int(api_result.get('LikesafterCommand', 0))
            
            bot.send_video(
                chat_id=message.chat.id,
                video=VIDEO_URL,
                caption=(
                    "<b>💎 VIP LIKE SUCCESSFUL!</b>\n\n"
                    f"👑 <b>Player:</b> {api_result.get('PlayerNickname', 'VIP USER')}\n"
                    f"🆔 <b>UID:</b> {api_result.get('UID', uid)}\n"
                    f"🌍 <b>Region:</b> {region.upper()}\n\n"
                    f"💖 <b>Likes Sent:</b> {likes_given}\n"
                    f"📊 <b>Before:</b> {likes_before} | <b>After:</b> {likes_after}\n"
                    f"🔥 <b>Total Likes Now:</b> {likes_after}\n\n"
                    f"🌟 <b>Status:</b> {'VIP MEMBER' if is_vip(user_id) else f'CREDITS LEFT: {db.verification_credits.get(user_id, 0)}'}\n\n"
                    f"Join @CODER_LEGEND_LIKE for updates"
                ),
                reply_to_message_id=message.message_id
            )
            
        elif status == 2:
            bot.send_video(
                chat_id=message.chat.id,
                video=VIDEO_URL,
                caption=(
                    "<b>⚠️ ACCOUNT ALREADY LIKED</b>\n\n"
                    f"👑 <b>Player:</b> {api_result.get('PlayerNickname', 'VIP USER')}\n"
                    f"🆔 <b>UID:</b> {api_result.get('UID', uid)}\n"
                    f"🌍 <b>Region:</b> {region.upper()}\n\n"
                    f"💖 <b>Current Likes:</b> {api_result.get('LikesafterCommand')}\n\n"
                    "Your credit has been restored.\n\n"
                    f"Join @CODER_LEGEND_LIKE for support"
                ),
                reply_to_message_id=message.message_id
            )
            
        else:
            bot.send_video(
                chat_id=message.chat.id,
                video=VIDEO_URL,
                caption=(
                    "<b>❌ LIKE REQUEST FAILED</b>\n\n"
                    f"🆔 <b>UID:</b> {uid}\n"
                    f"🌍 <b>Region:</b> {region.upper()}\n\n"
                    "Please check the UID and region and try again.\n\n"
                    f"Join @CODER_LEGEND_LIKE for support"
                ),
                reply_to_message_id=message.message_id
            )
            
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        print(f"Like response error: {e}")
        bot.edit_message_text(
            f"<b>💎 VIP LIKE PROCESSED</b>\n"
            f"🆔 <b>UID:</b> {uid}\n"
            f"🌍 <b>Region:</b> {region.upper()}\n"
            f"💖 <b>Status:</b> {'SUCCESS' if status == 1 else 'ALREADY LIKED' if status == 2 else 'FAILED'}",
            message.chat.id,
            msg.message_id
        )

def process_visit(message, region, uid, original_credits=None):
    msg = bot.reply_to(message, "⚡ PROCESSING VISIT REQUEST...")
    
    steps = [
        "🔐 VERIFYING VIP ACCESS...",
        "🌐 CONNECTING TO SERVER...",
        "👀 SENDING VISITS...",
        "✅ FINALIZING TRANSACTION..."
    ]
    
    for step in steps:
        time.sleep(1.2)
        bot.edit_message_text(step, message.chat.id, msg.message_id)
    
    api_result = call_visit_api(region, uid)
    user_id = message.from_user.id
    
    if not is_vip(user_id):
        db.visit_cooldowns[user_id] = time.time()
        db.save_data()
    
    try:
        if "nickname" in api_result:
            bot.send_video(
                chat_id=message.chat.id,
                video=VIDEO_URL,
                caption=(
                    "<b>👑 VIP VISIT SUCCESSFUL!</b>\n\n"
                    f"🔰 <b>FF NAME:</b> {api_result.get('nickname', 'VIP USER')}\n"
                    f"🆔 <b>UID:</b> {api_result.get('uid', uid)}\n"
                    f"📊 <b>LEVEL:</b> {api_result.get('level', 'N/A')}\n"
                    f"🌍 <b>REGION:</b> {region.upper()}\n"
                    f"✅ <b>SUCCESS:</b> {api_result.get('success', 0)}\n"
                    f"❌ <b>FAILED:</b> {api_result.get('fail', 0)}\n\n"
                    f"🌟 <b>Status:</b> {'VIP MEMBER' if is_vip(user_id) else f'CREDITS LEFT: {db.verification_credits.get(user_id, 0)}'}\n\n"
                    f"Join @CODER_LEGEND_LIKE for updates"
                ),
                reply_to_message_id=message.message_id
            )
        else:
            if original_credits is not None and user_id not in db.vip_users:
                db.verification_credits[user_id] = original_credits
                db.save_data()
            
            bot.send_video(
                chat_id=message.chat.id,
                video=VIDEO_URL,
                caption=(
                    "<b>❌ VISIT REQUEST FAILED</b>\n\n"
                    f"🆔 <b>UID:</b> {uid}\n"
                    f"🌍 <b>Region:</b> {region.upper()}\n\n"
                    "Please check the UID and region and try again.\n\n"
                    f"Join @CODER_LEGEND_LIKE for support"
                ),
                reply_to_message_id=message.message_id
            )
            
        bot.delete_message(message.chat.id, msg.message_id)
        
    except Exception as e:
        print(f"Visit response error: {e}")
        bot.edit_message_text(
            f"<b>👑 VIP VISIT PROCESSED</b>\n"
            f"🆔 <b>UID:</b> {uid}\n"
            f"🌍 <b>Region:</b> {region.upper()}\n"
            f"👀 <b>Status:</b> {'SUCCESS' if 'nickname' in api_result else 'FAILED'}",
            message.chat.id,
            msg.message_id
        )

def handle_verification(message):
    try:
        token = message.text.split()[1][7:]
        user_id = message.from_user.id
        
        if token in db.used_tokens:
            if db.token_to_user.get(token) == user_id:
                if user_id in db.pending_requests:
                    req = db.pending_requests[user_id]
                    try:
                        bot.delete_message(req['message'].chat.id, req['message'].message_id)
                    except:
                        pass
                    
                    if req['type'] == 'like':
                        process_like(req['message'], req['region'], req['uid'])
                    elif req['type'] == 'visit':
                        process_visit(req['message'], req['region'], req['uid'])
                    del db.pending_requests[user_id]
                    return
                
                bot.reply_to(message, 
                    "<b>✅ VERIFICATION ALREADY COMPLETED</b>\n\n"
                    "You've already claimed credit from this link!\n\n"
                    f"💎 <b>Current Credits:</b> {db.verification_credits.get(user_id, 0)}")
            else:
                bot.reply_to(message, 
                    "<b>⚠️ LINK ALREADY USED</b>\n\n"
                    "This verification link was already used by another user!")
            return
        
        # Verify the token belongs to this user
        if db.token_to_user.get(token) != user_id:
            bot.reply_to(message, 
                "⚠️ <b>INVALID VERIFICATION LINK</b>\n\n"
                "This verification link doesn't belong to you!")
            return
        
        db.used_tokens.add(token)
        db.verification_credits[user_id] = db.verification_credits.get(user_id, 0) + 1
        db.user_coins[user_id] = db.user_coins.get(user_id, 0) + 1
        db.user_last_verification[user_id] = time.time()
        db.all_users.add(user_id)
        db.save_data()
        
        if user_id in db.pending_requests:
            req = db.pending_requests[user_id]
            try:
                bot.delete_message(req['message'].chat.id, req['message'].message_id)
            except:
                pass
            
            if req['type'] == 'like':
                process_like(req['message'], req['region'], req['uid'])
            elif req['type'] == 'visit':
                process_visit(req['message'], req['region'], req['uid'])
            del db.pending_requests[user_id]
            return
        
        bot.reply_to(message,
            "✨ <b>✅ VERIFICATION SUCCESSFUL!</b> ✨\n\n"
            f"💎 <b>Credit Received:</b> 1 VIP credit\n"
            f"🪙 <b>Coin Bonus:</b> 1 Ghost Coin\n\n"
            f"📊 <b>Current Balance:</b>\n"
            f"╰┈➤ <b>VIP Credits:</b> {db.verification_credits.get(user_id, 0)}\n"
            f"╰┈➤ <b>Ghost Coins:</b> {db.user_coins.get(user_id, 0)}\n\n"
            f"Use /like or /visit in {GROUP_LINK} to send likes/visits\n\n"
            f"🌟 Check your balance with /coins",
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Verification error: {e}")
        bot.reply_to(message, 
            "⚠️ <b>VERIFICATION SUCCESS</b>\n\n"
            "PLEASE SEND COMMAND ON @CODER_LEGEND_LIKE GROUP 💥")

@bot.callback_query_handler(func=lambda call: call.data.startswith('verify_join'))
def handle_verify_join(call):
    data_parts = call.data.split(':')
    user_id = int(data_parts[1])
    command_type = data_parts[2] if len(data_parts) > 2 else 'like'
    
    not_joined = is_subscribed(user_id)
    
    if not_joined:
        kb = InlineKeyboardMarkup()
        for channel in not_joined:
            kb.add(InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
        kb.add(InlineKeyboardButton("🔓 VERIFY JOINING", callback_data=f"verify_join:{user_id}:{command_type}"))
        
        bot.answer_callback_query(call.id, "⚠️ Please join all channels first!", show_alert=True)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text="<b>🔒 VIP CHANNEL ACCESS REQUIRED</b>",
            reply_markup=kb
        )
    else:
        bot.answer_callback_query(call.id, f"✅ Verification successful! You can now use /{command_type}", show_alert=True)
        bot.delete_message(call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('credit'))
def handle_credit(call):
    try:
        _, user_id, region, uid, command_type = call.data.split(':')
        user_id = int(user_id)
        
        not_joined = is_subscribed(user_id)    
        if not_joined:
            kb = InlineKeyboardMarkup()
            for channel in not_joined:
                kb.add(InlineKeyboardButton(f"📢 JOIN {channel}", url=f"https://t.me/{channel.replace('@', '')}"))
            kb.add(InlineKeyboardButton("🔓 VERIFY JOINING", callback_data=f"verify_join:{user_id}:{command_type}"))
            
            bot.answer_callback_query(call.id, "⚠️ Please join all channels first!", show_alert=True)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="<b>🔒 VIP CHANNEL ACCESS REQUIRED</b>",
                reply_markup=kb
            )
            return
        
        cooldown = 20 * 60
        elapsed = time.time() - db.user_last_verification.get(user_id, 0)
        
        if elapsed < cooldown:
            remaining = int((cooldown - elapsed) / 60)
            bot.answer_callback_query(call.id, f"⏳ Please wait {remaining} minutes before verifying again", show_alert=True)
            return
        
        token = generate_verification_token(user_id)
        verify_url = f"https://t.me/{bot.get_me().username}?start=verify_{token}"
        short_url = shorten_url(verify_url)
        
        db.pending_requests[user_id] = {
            'message': call.message,
            'region': region,
            'uid': uid,
            'type': command_type
        }
        db.save_data()
        
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🔓 CLICK TO VERIFY NOW", url=short_url))
        kb.add(InlineKeyboardButton("📘 VERIFICATION GUIDE", url="https://t.me/CODER_LEGEND"))
        kb.add(InlineKeyboardButton("💎 BUY VIP MEMBERSHIP", url="https://t.me/CODER_LEGEND"))
        
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=(
                "<b>💎 GET VERIFICATION CREDIT</b>\n\n"
                "1️⃣ <b>Click the VERIFY button below</b>\n"
                "2️⃣ <b>Complete the verification process</b>\n"
                "3️⃣ <b>Return to group to use your credit</b>\n\n"
                "⚠️ <i>Each link can only be used once</i>"
            ),
            reply_markup=kb
        )
        bot.answer_callback_query(call.id, "Verification link generated!")
        
    except Exception as e:
        print(f"Credit error: {e}")
        bot.answer_callback_query(call.id, "⚠️ Error generating link. Please try again.", show_alert=True)

@bot.message_handler(func=lambda message: message.text.startswith('Get ') and message.chat.id == ALLOWED_GROUP_ID)
def handle_freefire_info(message):
    if not check_bot_active(message):
        return
    
    text = message.text
    parts = text.split()
    if len(parts) != 3:
        bot.reply_to(message, "Use: Get <region> <uid>")
        return

    region, uid = parts[1], parts[2]
    msg = bot.reply_to(message, f"Fetching info for UID `{uid}`...")

    data = get_profile_info(uid, region)
    if not data:
        bot.edit_message_text("❌ Failed to fetch data. Try again.", chat_id=message.chat.id, message_id=msg.message_id)
        return

    pinfo = data.get("player_info", {})
    basic = pinfo.get("basicInfo", {})
    social = pinfo.get("socialInfo", {})
    pet = pinfo.get("petInfo", {})
    credit = pinfo.get("creditScoreInfo", {})
    profile = pinfo.get("profileInfo", {})

    created_at = format_timestamp(basic.get("createAt", 0))
    last_login = format_timestamp(basic.get("lastLoginAt", 0))
    signature = social.get("signature", "No Signature")
    elite_pass = "Yes" if basic.get("hasElitePass", False) else "No"
    equipped_skills = profile.get("equipedSkills", [])
    equipped_skills_str = ", ".join(str(s) for s in equipped_skills) if equipped_skills else "N/A"
    clothes = profile.get("clothes", [])
    clothes_str = ", ".join(str(c) for c in clothes) if clothes else "N/A"

    msg_text = (
        f"┌🧑‍💻 ACCOUNT BASIC INFO\n"
        f"├─ Name: {basic.get('nickname', 'Unknown')}\n"
        f"├─ UID: {basic.get('accountId', uid)}\n"
        f"├─ Level: {basic.get('level', 'N/A')} (Exp: {basic.get('exp', 'N/A')})\n"
        f"├─ Region: {basic.get('region', region)}\n"
        f"├─ Likes: {basic.get('liked', 'N/A')}\n"
        f"├─ Honor Score: {credit.get('creditScore', 'N/A')}\n"
        f"├─ Title: {basic.get('badgeId', 'N/A')}\n"
        f"└─ Signature: {signature}\n\n"

        f"┌🎮 ACCOUNT ACTIVITY\n"
        f"├─ Most Recent OB: {basic.get('releaseVersion', 'N/A')}\n"
        f"├─ Booyah Pass: {elite_pass}\n"
        f"├─ Current BP Badges: {basic.get('badgeCnt', 'N/A')}\n"
        f"├─ BR Rank: {basic.get('rank', 'N/A')}\n"
        f"├─ CS Points: {basic.get('csRankingPoints', 'N/A')}\n"
        f"├─ Created At: {created_at}\n"
        f"└─ Last Login: {last_login}\n\n"

        f"┌👕 ACCOUNT OVERVIEW\n"
        f"├─ Avatar ID: {basic.get('headPic', 'Default')}\n"
        f"├─ Banner ID: {basic.get('bannerId', 'Default')}\n"
        f"├─ Equipped Skills: {equipped_skills_str}\n"
        f"├─ Outfits: {clothes_str}\n\n"

        f"┌🐾 PET DETAILS\n"
        f"├─ Equipped?: {'Yes' if pet.get('isSelected', False) else 'No'}\n"
        f"├─ Pet ID: {pet.get('id', 'N/A')}\n"
        f"├─ Pet Exp: {pet.get('exp', 'N/A')}\n"
        f"└─ Pet Level: {pet.get('level', 'N/A')}\n"
    )

    bot.edit_message_text(msg_text, chat_id=message.chat.id, message_id=msg.message_id)

    banner_url = f"https://aditya-banner-v9op.onrender.com/banner-image?uid={uid}&region={region}"
    outfit_url = f"https://aditya-outfit-v9op.onrender.com/outfit-image?uid={uid}&region={region}&key=99day"

    try:
        bot.send_photo(message.chat.id, banner_url, caption="🖼️ BANNER IMAGE")
    except Exception as e:
        logger.error(f"Failed to send banner image: {e}")

    try:
        bot.send_photo(message.chat.id, outfit_url, caption="🧥 OUTFIT IMAGE")
    except Exception as e:
        logger.error(f"Failed to send outfit image: {e}")

@bot.message_handler(commands=['admin'])
def admin_commands(message):
    if not check_bot_active(message):
        return
    
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⚠️ You are not authorized to use this command!")
        return
    
    admin_help = """
🔐 <b>CODER LEGEND ADMIN COMMANDS</b> 🔐

💰 <b>Coin Management:</b>
<code>/addc &lt;amount&gt; &lt;user_id/username&gt;</code> - Add coins
<code>/dcn &lt;amount/all&gt; &lt;user_id/username&gt;</code> - Deduct coins
<code>/coins &lt;user_id/username&gt;</code> - Check balance

👑 <b>VIP Management:</b>
<code>/addvip &lt;duration&gt; &lt;user_id/username&gt;</code> - Add VIP
<code>/dvip &lt;user_id/username&gt;</code> - Remove VIP
<code>/vips</code> - List VIP users

📢 <b>Group Management:</b>
<code>/approve</code> - Approve current group
<code>/dapprove &lt;group_id&gt;</code> - Remove approval
<code>/groups</code> - List approved groups

📡 <b>Broadcasting:</b>
<code>/broadcast</code> - Broadcast to all
<code>/modhu</code> - Broadcast to groups

🔌 <b>Bot Control:</b>
<code>/ghost-on</code> - Turn bot on
<code>/ghost-off</code> - Turn bot off

⚙️ <b>Other Commands:</b>
<code>/admin</code> - Show this menu
"""
    bot.reply_to(message, admin_help, parse_mode='HTML')

if __name__ == "__main__":
    print("✨ CODER LEGEND VIP BOT IS RUNNING... ✨")
    bot.infinity_polling()