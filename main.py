import json
import os
import requests
import signal
import sys
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, MessageEntity, ChatPermissions, ChatMember
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters, ChatMemberHandler
from telegram.error import BadRequest
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import re # Imported for emoji detection
import asyncio # NEW: For gcmessage delay

# === CONFIG ===
# Make sure this BOT_TOKEN is correct and active.
BOT_TOKEN = '8350357234:AAG4hN-sXdxw5YU4Ggd9Yz_xcHy1TK5pUtE'
API_KEY = 'cfccc875ea6d4t8fyf8f86fff58b0f380941b7f49c'

# !!! IMPORTANT !!!
# This is the ID of the group where the bot sends success messages.
# The "Chat not found" error can occur here if the bot is NOT a member of this group.
# Make sure your bot is a member of the group with this ID.
GROUP_CHAT_ID = -1003270164289

# --- NEW ---: Daily limit for free users
DAILY_LIMIT_FREE = 3

LIKE_API_URL = 'https://dpx-army-ff-ghost-apis.vercel.app/like?uid={uid}&server_name={region}&key=@ghost_x_like'
USAGE_FILE = 'daily_usage.json'
LIKE_LOG_FILE = 'like_log.json'
VIP_FILE = 'vip_users.json'
CHANNELS_FILE = 'channels.json'
ALLOWED_GROUPS_FILE = 'allowed_groups.json'
AUTOLIKE_FILE = 'autolike_users.json'
ADMINS_FILE = 'admins.json'
PROMO_FILE = 'promotion.json' # NEW: File for promotion
OWNER_ID = 8100642714
MAX_LIKES = 25870

# --- NEW FILES FOR MODERATION ---
WARNINGS_FILE = 'warnings.json'
MODERATION_SETTINGS_FILE = 'moderation_settings.json'
WELCOME_IMAGE_URL = 'https://i.postimg.cc/ZRqFZCZd/file-00000000778461f997af8e55556a1331.png' # You can change this URL to your preferred image

# Valid regions
VALID_REGIONS = ['ind', 'bd', 'sg', 'id', 'me', 'br', 'vn', 'eu', 'th', 'na', 'us', 'uk', 'tw', 'mx', 'pk', 'np', 'latam', 'gl']

# Dictionary of permissions for administrators
PERMISSIONS = {
    'add_vip': "➕ Add/Edit VIP",
    'remove_vip': "➖ Remove VIP",
    'list_vip': "📋 List VIPs",
    'add_channel': "➕ Add Channel",
    'remove_channel': "➖ Remove Channel",
    'list_channels': "📋 List Channels",
    'add_group': "➕ Add Group",
    'remove_group': "➖ Remove Group",
    'list_groups': "📋 List Groups",
    'reset_daily': "🔄 Reset Daily Usage",
    'manage_autolike': "🤖 Manage Auto-Like",
    'manage_moderation': "🔧 Manage Moderation",
    'manage_promo': "📢 Manage Promotion", # NEW PERMISSION
}

# !!! VERY IMPORTANT - LIKELY CAUSE OF YOUR ERROR !!!
JOIN_CHANNEL_LINK = "https://t.me/CODER_LEGEND_LIKE"
JOIN_GROUP_LINK = "https://t.me/CODER_LEGEND_LIKE"
BUY_VIP_LINK = "https://t.me/CODER_LEGEND"


# === File Helpers ===
def load_json(path, default_value=None):
    if default_value is None:
        default_value = {} # Changed default to dict for promo
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return default_value
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default_value

def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)

# === NEW: Moderation Helpers ===
def load_warnings():
    return load_json(WARNINGS_FILE, default_value={})

def save_warnings(data):
    save_json(WARNINGS_FILE, data)

def load_moderation_settings():
    defaults = {"warning_limit": 3, "mute_duration_minutes": 30}
    settings = load_json(MODERATION_SETTINGS_FILE, default_value=defaults)
    # Ensure default keys exist
    settings.setdefault("warning_limit", 3)
    settings.setdefault("mute_duration_minutes", 30)
    return settings

def save_moderation_settings(data):
    save_json(MODERATION_SETTINGS_FILE, data)

# === NEW: Helper to detect standard emojis ===
def contains_emoji(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.search(text) is not None

# === Helper for stats logging ===
def log_like_for_stats(user_id: int, chat_id: int):
    log_data = load_json(LIKE_LOG_FILE, default_value=[])
    log_data.append({
        "user_id": user_id,
        "chat_id": chat_id,
        "timestamp": datetime.now().isoformat()
    })
    save_json(LIKE_LOG_FILE, log_data)

# === Admin and Authorization Helpers ===
def load_admins():
    return load_json(ADMINS_FILE, default_value=[])

def save_admins(data):
    save_json(ADMINS_FILE, data)

def is_authorized(user_id: int, permission_key: str) -> bool:
    if user_id == OWNER_ID:
        return True

    admins = load_admins()
    for admin in admins:
        if admin.get("id") == user_id:
            return permission_key in admin.get("permissions", [])
    return False

# === Allowed Groups Helpers ===
def load_allowed_groups():
    return load_json(ALLOWED_GROUPS_FILE, default_value=[])

def save_allowed_groups(data):
    save_json(ALLOWED_GROUPS_FILE, data)

# === Channel Management Helpers ===
def load_channels():
    return load_json(CHANNELS_FILE, default_value=[])

def save_channels(data):
    save_json(CHANNELS_FILE, data)

# === Daily Usage ===
def load_daily_usage():
    return load_json(USAGE_FILE, default_value=[])

def save_daily_usage(data):
    save_json(USAGE_FILE, data)

def get_usage_count(user_id):
    usage_data = load_daily_usage()
    today = datetime.now().strftime("%Y-%m-%d")
    for user in usage_data:
        if user.get("id") == user_id and user.get("date") == today:
            return user.get("count", 0)
    return 0

def increment_usage(user_id):
    usage_data = load_daily_usage()
    today = datetime.now().strftime("%Y-%m-%d")
    user_found = False
    for user in usage_data:
        if user.get("id") == user_id:
            user_found = True
            if user.get("date") == today:
                user["count"] = user.get("count", 0) + 1
            else:
                user["date"] = today
                user["count"] = 1
            break

    if not user_found:
        usage_data.append({"id": user_id, "date": today, "count": 1})

    save_daily_usage(usage_data)

def has_exceeded_limit(user_id):
    return get_usage_count(user_id) >= DAILY_LIMIT_FREE

# === VIP Logic ===
def load_vip_users():
    return load_json(VIP_FILE, default_value=[])

def save_vip_user(user_id, days, like_limit):
    vip_users = load_vip_users()
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
    for user in vip_users:
        if user["id"] == user_id:
            user["expiry"] = expiry_date
            user["like_limit"] = like_limit
            break
    else:
        vip_users.append({
            "id": user_id,
            "expiry": expiry_date,
            "like_limit": like_limit
        })
    save_json(VIP_FILE, vip_users)

def remove_vip_user(user_id):
    vip_users = load_vip_users()
    vip_users = [u for u in vip_users if u["id"] != user_id]
    save_json(VIP_FILE, vip_users)

def is_vip_user(user_id):
    vip_users = load_vip_users()
    for user in vip_users:
        if user["id"] == user_id:
            try:
                expiry_date = datetime.strptime(user['expiry'], "%Y-%m-%d")
                return datetime.now() < expiry_date
            except (ValueError, KeyError):
                continue
    return False

def get_vip_like_limit(user_id):
    vip_users = load_vip_users()
    for user in vip_users:
        if user["id"] == user_id:
            return user.get("like_limit", 1)
    return 1

# === Auto-Like Service Helpers ===
def load_autolike_users():
    return load_json(AUTOLIKE_FILE, default_value=[])

def save_autolike_users(data):
    save_json(AUTOLIKE_FILE, data)

# === API CALL ===
async def call_like_api(region, uid):
    try:
        url = LIKE_API_URL.format(region=region, uid=uid)
        response = requests.get(url)

        if response.status_code != 200 or not response.text:
            return {"error": "API request failed or returned an empty response. Please try again later."}

        try:
            data = response.json()
        except json.JSONDecodeError:
            return {"error": "The API returned an invalid response. Please contact the owner."}

        if data.get("LikesafterCommand", 0) >= MAX_LIKES:
            return {
                "status": 2,
                "message": "Player already has maximum likes",
                "LikesafterCommand": data.get("LikesafterCommand", 0),
                "LikesbeforeCommand": data.get("LikesbeforeCommand", 0),
                "PlayerNickname": data.get("PlayerNickname", "N/A"),
                "UID": uid,
                "LikesGivenByAPI": data.get("LikesGivenByAPI", 0)
            }

        return data
    except requests.exceptions.RequestException as e:
        return {"error": f"Could not connect to the API. Details: {e}"}
    except Exception as e:
        return {"error": str(e)}

# === Helper Functions ===
def reset_daily_data():
    for file in [USAGE_FILE]:
        if os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)
    print("*🧹 Daily usage data cleared.*")

def format_next_available_time():
    now = datetime.now()
    next_time = now + timedelta(hours=24)
    return next_time.strftime("%Y-%m-%d %H:%M:%S")

async def send_like_success_message(update: Update, context: ContextTypes.DEFAULT_TYPE, api_response: dict, region: str, is_vip: bool = False, remaining_likes: int = 0):
    user_first_name = update.effective_user.first_name or "User"

    if update.callback_query and update.callback_query.message.reply_to_message:
        target_message = update.callback_query.message.reply_to_message
    else:
        target_message = update.effective_message

    if not target_message:
        print("Error: Could not find a target message to reply to in send_like_success_message.")
        return

    if api_response.get("status") == 2:
        text = (
            f"📌 <b>Notice</b>\n\n"
            f"Maximum likes reached for this player.\n"
            f"Please try again with a different UID.\n\n"
            f"🔍 <b>Player:</b> <code>{api_response.get('PlayerNickname', 'N/A')}</code>\n"
            f"🔍 <b>UID:</b> <code>{api_response.get('UID', 'N/A')}</code>\n"
            f"🔍 <b>Current Likes:</b> <code>{api_response.get('LikesafterCommand', 0)}</code>\n\n"
            f"<b>Bot Owner:</b> @CODER_LEGEND"
        )
    else:
        vip_text = f"💎 <b>VIP User:</b> {user_first_name}\n" if is_vip else f"👤 <b>User:</b> {user_first_name}\n"

        if is_vip:
            limit_text = f"💎 <b>Daily Limit:</b> Unlimited"
        elif remaining_likes > 0:
            limit_text = f"❗ <b>Likes Remaining Today:</b> {remaining_likes}/{DAILY_LIMIT_FREE}"
        else:
            limit_text = f"❗ <b>Next Likes Available:</b> {format_next_available_time()}"

        text = (
            f"<b>✅ Like Sent Successfully!</b>\n\n"
            f"{vip_text}"
            f"🔸 <b>Player:</b> <code>{api_response.get('PlayerNickname', 'N/A')}</code>\n"
            f"🔸 <b>UID:</b> <code>{api_response.get('UID', 'N/A')}</code>\n"
            f"🔸 <b>Region:</b> <code>{region.upper()}</code>\n"
            f"🔸 <b>Likes Before:</b> <code>{api_response.get('LikesbeforeCommand', 0)}</code>\n"
            f"🔸 <b>Likes After:</b> <code>{api_response.get('LikesafterCommand', 0)}</code>\n"
            f"🔸 <b>Likes Given:</b> <code>{api_response.get('LikesGivenByAPI', 0)}</code>\n\n"
            f"{limit_text}\n\n"
            f"<b>Bot Owner:</b> @CODER_LEGEND"
        )

    buttons = [
        [InlineKeyboardButton("🌟 JOIN CHANNEL", url=JOIN_CHANNEL_LINK),
         InlineKeyboardButton("🤝 JOIN GROUP", url=JOIN_GROUP_LINK)],
        [InlineKeyboardButton("💎 BUY VIP", url=BUY_VIP_LINK)]
    ]
    
    # NEW: Add promo button if it exists
    promo_data = load_json(PROMO_FILE)
    if promo_data and 'url' in promo_data and 'text' in promo_data:
        buttons.append([InlineKeyboardButton(promo_data['text'], url=promo_data['url'])])
        
    keyboard = InlineKeyboardMarkup(buttons)

    await target_message.reply_text(
        text=text,
        reply_markup=keyboard,
        parse_mode='HTML'
    )

    try:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
    except BadRequest as e:
        if "Chat not found" in str(e):
            print(f"Info: Could not send to GROUP_CHAT_ID ({GROUP_CHAT_ID}) because the bot is not a member.")
        else:
            print(f"Error: Could not send message to GROUP_CHAT_ID ({GROUP_CHAT_ID}). Reason: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while trying to send to GROUP_CHAT_ID: {e}")

# === Main Like Processing Logic ===
async def process_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE, region: str, uid: str):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id

    if update.callback_query and update.callback_query.message.reply_to_message:
        target_message = update.callback_query.message.reply_to_message
    else:
        target_message = update.effective_message

    if not target_message:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="*⚠️ Could not find the original message. Please try the command again.*",
            parse_mode='Markdown'
        )
        return

    loading_msg = await target_message.reply_text(
        text=f"*⏳ Processing your like request...*",
        parse_mode='Markdown'
    )

    is_user_vip = is_vip_user(user_id)

    if user_id == OWNER_ID or is_user_vip:
        api_response = await call_like_api(region, uid)
        await loading_msg.delete()
        if "error" in api_response:
            await target_message.reply_text(f"*⚠️ API Error:*\n`{api_response['error']}`", parse_mode='Markdown')
            return
        log_like_for_stats(user_id, chat_id)
        await send_like_success_message(update, context, api_response, region, is_vip=True)
        return

    if has_exceeded_limit(user_id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💎 BUY VIP FOR UNLIMITED LIKES", url=BUY_VIP_LINK)]
        ])
        await loading_msg.edit_text(
            f"*🚫 You have used all your {DAILY_LIMIT_FREE} free likes for today.*\n\n"
            "*Come back tomorrow or purchase VIP for unlimited access.*",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return

    api_response = await call_like_api(region, uid)
    if "error" in api_response:
        await loading_msg.edit_text(f"*⚠️ API Error:*\n`{api_response['error']}`", parse_mode='Markdown')
        return

    increment_usage(user_id)
    log_like_for_stats(user_id, chat_id)
    remaining_likes = DAILY_LIMIT_FREE - get_usage_count(user_id)

    await loading_msg.delete()
    await send_like_success_message(update, context, api_response, region, is_vip=False, remaining_likes=remaining_likes)


# === Daily Auto-Like Scheduler ===
async def run_daily_autolikes(app: Application):
    bot = app.bot
    autolike_users = load_autolike_users()
    active_users = []
    today = datetime.now()

    if not autolike_users:
        print("Auto-Like Task: No users to process.")
        return

    for user in autolike_users:
        try:
            expiry_date = datetime.strptime(user['expiry'], "%Y-%m-%d")
            if today < expiry_date:
                active_users.append(user)
                region = user['region']
                uid = user['uid']

                api_response = await call_like_api(region, uid)

                report_message = ""
                if "error" in api_response:
                    report_message = (
                        f"🔴 *Auto-Like Failed*\n\n"
                        f"• *UID:* `{uid}`\n"
                        f"• *Region:* `{region.upper()}`\n"
                        f"• *Error:* `{api_response['error']}`"
                    )
                elif api_response.get("status") == 2:
                     report_message = (
                        f"🟡 *Auto-Like Notice*\n\n"
                        f"• *Player:* `{api_response.get('PlayerNickname', 'N/A')}`\n"
                        f"• *UID:* `{uid}`\n"
                        f"• *Current Likes:* `{api_response.get('LikesafterCommand', 0)}`\n"
                        f"• *Reason:* Maximum likes reached."
                    )
                else:
                    report_message = (
                        f"🟢 *Auto-Like Successful*\n\n"
                        f"• *Player:* `{api_response.get('PlayerNickname', 'N/A')}`\n"
                        f"• *UID:* `{uid}`\n"
                        f"• *Region:* `{region.upper()}`\n"
                        f"• *Likes Before:* `{api_response.get('LikesbeforeCommand', 0)}`\n"
                        f"• *Likes After:* `{api_response.get('LikesafterCommand', 0)}`\n"
                        f"• *Likes Given:* `{api_response.get('LikesGivenByAPI', 0)}`"
                    )

                await bot.send_message(chat_id=OWNER_ID, text=report_message, parse_mode='Markdown')

                try:
                    await bot.send_message(chat_id=GROUP_CHAT_ID, text=report_message, parse_mode='Markdown')
                except Exception as e:
                    print(f"Could not send auto-like report to group {GROUP_CHAT_ID}: {e}")

        except (ValueError, KeyError) as e:
            print(f"Error processing auto-like user {user.get('uid')}: {e}")
            continue

    save_autolike_users(active_users)
    summary_message = f"✅ *Daily auto-like task finished. Processed {len(autolike_users)} users.*"
    await bot.send_message(chat_id=OWNER_ID, text=summary_message, parse_mode='Markdown')
    try:
        await bot.send_message(chat_id=GROUP_CHAT_ID, text=summary_message, parse_mode='Markdown')
    except Exception as e:
        print(f"Could not send auto-like summary to group {GROUP_CHAT_ID}: {e}")


# === Commands ===
async def like_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat = update.message.chat
    chat_id = chat.id
    chat_type = chat.type

    if user_id != OWNER_ID:
        if chat_type == "private":
            if not is_vip_user(user_id):
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🌟 JOIN CHANNEL", url=JOIN_CHANNEL_LINK),
                     InlineKeyboardButton("🤝 JOIN GROUP", url=JOIN_GROUP_LINK)],
                    [InlineKeyboardButton("💎 DM FOR VIP", url=BUY_VIP_LINK)]
                ])
                await update.message.reply_text(
                    "*❌ Private use is for VIP members only.*\n\n"
                    "To use this command in a private message, you need a VIP subscription. Please contact the owner to get VIP access.",
                    reply_markup=keyboard,
                    parse_mode='Markdown'
                )
                return
        elif chat_type in ["group", "supergroup"]:
            allowed_groups = load_allowed_groups()
            if chat_id not in allowed_groups:
                await update.message.reply_text(
                    "*❌ This bot is not authorized to work in this group.*\n\n"
                    "*An admin must contact the bot owner to get this group approved.*",
                    parse_mode='Markdown'
                )
                return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "*❌ Invalid Format*\n\n"
            "*Usage:* `/like [region] [uid]`\n\n"
            f"*Valid Regions:* {', '.join(VALID_REGIONS)}\n\n"
            "*Example:* `/like ind 8431487083`",
            parse_mode='Markdown'
        )
        return

    region = context.args[0].lower()
    uid = context.args[1]

    if region not in VALID_REGIONS:
        await update.message.reply_text(
            "*❌ Invalid Region*\n\n"
            f"*You entered:* `{region}`\n"
            f"*Valid Regions:* {', '.join(VALID_REGIONS)}\n\n"
            "*Example:* `/like ind 8431487083`",
            parse_mode='Markdown'
        )
        return

    is_main_group_member = False
    try:
        member = await context.bot.get_chat_member(chat_id=GROUP_CHAT_ID, user_id=user_id)
        if member.status in ['creator', 'administrator', 'member']:
            is_main_group_member = True
    except BadRequest as e:
        if "Chat not found" in str(e):
            print(f"Info: Could not check main group membership. The bot might not be in the group {GROUP_CHAT_ID}.")
        else:
            print(f"An unexpected BadRequest occurred while checking main group membership for user {user_id}: {e}")
    except Exception as e:
        print(f"An unexpected error occurred while checking main group membership for user {user_id}: {e}")

    if user_id == OWNER_ID or is_vip_user(user_id) or is_main_group_member:
        await process_like_request(update, context, region, uid)
        return

    channels = load_channels()
    if not channels:
        await process_like_request(update, context, region, uid)
        return

    unjoined_channels = []
    for channel in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel['id'], user_id=user_id)
            if member.status in ['left', 'kicked']:
                unjoined_channels.append(channel)
        except BadRequest as e:
            if "Chat not found" in str(e):
                print(f"!!! CRITICAL ERROR: Bot cannot find channel with ID {channel['id']}. Please check the ID or add the bot to the channel as an admin.")
            unjoined_channels.append(channel)
        except Exception:
            unjoined_channels.append(channel)

    if unjoined_channels:
        buttons = [[InlineKeyboardButton(f"🔗 Join {channel['name']}", url=channel['link'])] for channel in unjoined_channels]

        callback_data = f"verify_join:{user_id}:{region}:{uid}"
        buttons.append([InlineKeyboardButton("✅ Verify Membership", callback_data=callback_data)])

        keyboard = InlineKeyboardMarkup(buttons)
        await update.message.reply_text(
            "**🚨 Please join our channels to use this command.**\n\n"
            "After joining, click the 'Verify Membership' button below.",
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        return

    await process_like_request(update, context, region, uid)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 JOIN CHANNEL", url=JOIN_CHANNEL_LINK),
         InlineKeyboardButton("🤝 JOIN GROUP", url=JOIN_GROUP_LINK)],
        [InlineKeyboardButton("💎 BUY VIP", url=BUY_VIP_LINK)]
    ])
    await update.message.reply_text(
        "*Welcome to the Free Fire VIP Like Bot!*\n\n"
        "To get likes, use:\n`/like [region] [uid]`\n\n"
        "*Example:* `/like ind 5437366288`\n\n"
        f"*Valid Regions:* {', '.join(VALID_REGIONS)}\n\n"
        "👇 Join our communities below! 👇",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat.type not in ["group", "supergroup"]:
        await update.message.reply_text("*This command can only be used in a group.*", parse_mode='Markdown')
        return

    chat_id = chat.id

    try:
        total_members = await context.bot.get_chat_member_count(chat_id)
    except Exception as e:
        await update.message.reply_text(f"*Could not get member count. Error: {e}*", parse_mode='Markdown')
        return

    like_log = load_json(LIKE_LOG_FILE, default_value=[])

    total_unique_users = len(set(entry['user_id'] for entry in like_log))
    group_like_users = len(set(entry['user_id'] for entry in like_log if entry['chat_id'] == chat_id))

    stats_message = (
        f"📊 *Bot and Group Statistics*\n\n"
        f"👥 *Total Group Members:* `{total_members}`\n"
        f"👍 *Users who took likes in this group:* `{group_like_users}`\n"
        f"🌍 *Total unique users of the bot:* `{total_unique_users}`\n\n"
        f"ℹ️ *Note: Bot member count is unavailable due to Telegram's privacy restrictions.*"
    )

    await update.message.reply_text(stats_message, parse_mode='Markdown')


async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    user_id = user.id
    first_name = user.first_name
    last_name = user.last_name or ""
    username = f"@{user.username}" if user.username else "N/A"
    
    # Note: Bio/about text is not available through the standard Telegram Bot API for privacy reasons.
    # We can get the user's profile pictures, however.

    info_text = (
        f"👤 <b>User Info</b>\n\n"
        f"<b>First Name:</b> {first_name}\n"
        f"<b>Last Name:</b> {last_name}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>User ID:</b> <code>{user_id}</code>\n"
        f"<b>Is a Bot:</b> {'Yes' if user.is_bot else 'No'}\n\n"
        f"ℹ️ <i>User bio is not accessible via bots.</i>"
    )

    try:
        profile_photos = await context.bot.get_user_profile_photos(user_id, limit=1)
        if profile_photos and profile_photos.photos:
            # The photos are returned in a nested list, with the first list containing different sizes
            # We'll take the largest one, which is usually the last in the list.
            photo_file = await context.bot.get_file(profile_photos.photos[0][-1].file_id)
            await update.message.reply_photo(
                photo=photo_file.file_path,
                caption=info_text,
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(info_text, parse_mode='HTML')
    except Exception as e:
        print(f"Error fetching profile photo for myinfo: {e}")
        await update.message.reply_text(info_text, parse_mode='HTML')


async def id_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    text = (
        f"🔹 **Your User ID:** `{user_id}`\n"
        f"🔸 **Current Chat ID:** `{chat_id}`"
    )
    
    await update.message.reply_text(text, parse_mode='Markdown')

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    feedback_message = " ".join(context.args)

    if not feedback_message:
        await update.message.reply_text(
            "*Please provide a message to send as feedback.*\n\n"
            "*Usage:* `/feedback [your message]`",
            parse_mode='Markdown'
        )
        return

    try:
        forwarded_text = (
            f"📝 **New Feedback Received**\n\n"
            f"**From User:** {user.mention_markdown_v2()}\n"
            f"**User ID:** `{user.id}`\n\n"
            f"**Message:**\n"
            f"{feedback_message}"
        )
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=forwarded_text,
            parse_mode='Markdown'
        )
        await update.message.reply_text(
            "✅ *Thank you! Your feedback has been sent to the owner.*",
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Failed to send feedback: {e}")
        await update.message.reply_text(
            "❌ *Sorry, there was an error sending your feedback. Please try again later.*",
            parse_mode='Markdown'
        )

# === NEW & IMPROVED: Help Command ===
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    user_help_text = (
        "📘 *Here are the commands you can use:*\n\n"
        "*/start* - Welcome message and basic instructions.\n"
        "*/like* `[region] [uid]` - Get likes for a Free Fire account.\n"
        "   - *Example:* `/like ind 123456789`\n"
        "*/help* - Shows this help message.\n"
        "*/myinfo* - Displays your Telegram user information.\n"
        "*/id* - Shows your User ID and the current Chat ID.\n"
        "*/feedback* `[message]` - Send a message to the bot owner.\n"
        "*/stats* - View statistics for this group.\n"
    )

    # Check if the user is the owner or an admin
    is_admin = (user_id == OWNER_ID) or any(is_authorized(user_id, p) for p in PERMISSIONS)

    if is_admin:
        admin_help_text = (
            "\n\n👑 *Admin & Owner Command List*\n\n"
            "*/ownerhelp* - Shows a detailed list of all admin commands.\n"
            "*/gcmessage* `[text]` - (Owner Only) Sends a message to all groups.\n"
            "*/add* `[user_id] [days] [limit]` - Add/update a VIP.\n"
            "*/remove* `[user_id]` - Remove a VIP.\n"
            "*/viplist* - List all VIP users.\n"
            "*/addgroup* `[id]` - Allow the bot in a new group.\n"
        )
        help_text = user_help_text + admin_help_text
    else:
        help_text = user_help_text

    await update.message.reply_text(help_text, parse_mode='Markdown')

async def owner_help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    # Check if the user is the owner or any kind of admin
    if user_id != OWNER_ID and not any(is_authorized(user_id, p) for p in PERMISSIONS):
        await update.message.reply_text("*❌ This command is for the bot owner and authorized admins only.*", parse_mode='Markdown')
        return

    # FIXED: The entire string is now a "raw" string (r"...") to prevent SyntaxWarning
    owner_help_text = (
        r"👑 *Owner & Admin Command List*"
        "\n\n"
        r"📚 *User Commands:*"
        "\n"
        r"`/start`, `/like`, `/help`, `/myinfo`, `/id`, `/feedback`, `/stats`"
        "\n\n"
        r"💎 *VIP Management (add_vip, remove_vip, list_vip):*"
        "\n"
        r"`/add [user_id] [days] [limit]` - Add or update a VIP."
        "\n"
        r"`/remove [user_id]` - Remove a VIP."
        "\n"
        r"`/viplist` - List all VIP users."
        "\n\n"
        r"📢 *Channel Management (add_channel, remove_channel, list_channels):*"
        "\n"
        r"`/addchannel [id] [name] [link]` - Add a required channel."
        "\n"
        r"`/removechannel [id]` - Remove a channel."
        "\n"
        r"`/channellist` - List all required channels."
        "\n\n"
        r"🏢 *Group Management (add_group, remove_group, list_groups):*"
        "\n"
        r"`/addgroup [id]` - Allow the bot in a group."
        "\n"
        r"`/removegroup [id]` - Disallow the bot in a group."
        "\n"
        r"`/listgroups` - List allowed groups."
        "\n\n"
        r"🤖 *Auto-Like Service (manage_autolike):*"
        "\n"
        r"`/autolike [region] [uid] [days]` - Set up auto-likes."
        "\n"
        r"`/removeauto [uid]` - Remove from auto-like."
        "\n"
        r"`/listauto` - List all auto-like users."
        "\n\n"
        r"🔧 *Moderation (manage_moderation):*"
        "\n"
        r"`/setwarnlimit [number]` - Set warning limit before mute."
        "\n"
        r"`/setmutetime [minutes]` - Set mute duration."
        "\n\n"
        r"🎁 *Promotion (manage_promo):*"
        "\n"
        r"`/setpromo [url] [text]` - Set a promotional button."
        "\n"
        r"`/removepromo` - Remove the promotion."
        "\n\n"
        r"👑 *Owner-Only Commands:*"
        "\n"
        r"`/gcmessage [text]` - Send a message to all allowed groups."
        "\n"
        r"`/addadmin [user_id]` - Start adding/editing an admin."
        "\n"
        r"`/removeadmin [user_id]` - Remove an admin."
        "\n"
        r"`/listadmins` - List all admins and permissions."
        "\n"
        r"`/resetdaily` - (Permission: reset_daily) Reset daily limits for all users."
        "\n"
        r"`/ownerhelp` - Shows this message."
    )
    await update.message.reply_text(owner_help_text, parse_mode='Markdown')


# === NEW FEATURE: Global Message Command ===
async def gcmessage_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        await update.message.reply_text("*❌ This command can only be used by the bot owner.*", parse_mode='Markdown')
        return

    message_text = " ".join(context.args)
    if not message_text:
        await update.message.reply_text(
            "*❌ Please provide a message to send.*\n\n"
            "*Usage:* `/gcmessage [your message]`",
            parse_mode='Markdown'
        )
        return

    allowed_groups = load_allowed_groups()
    if not allowed_groups:
        await update.message.reply_text("*⚠️ There are no groups in the allowed list to send a message to.*", parse_mode='Markdown')
        return
        
    # Get bot's username for the signature
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username
    
    # Message design
    formatted_message = (
        f"📢  <b>Announcement from the Owner</b> 📢\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"{message_text}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>This is an official message from the admin of @{bot_username}.</i>"
    )

    success_count = 0
    fail_count = 0
    
    progress_message = await update.message.reply_text(f"*📢 Sending message to {len(allowed_groups)} groups...*", parse_mode='Markdown')

    for group_id in allowed_groups:
        try:
            await context.bot.send_message(
                chat_id=group_id,
                text=formatted_message,
                parse_mode='HTML',
                disable_web_page_preview=True
            )
            success_count += 1
        except Exception as e:
            print(f"Failed to send message to group {group_id}: {e}")
            fail_count += 1
        await asyncio.sleep(0.5) # Add a small delay to avoid rate limiting

    report_text = (
        f"✅ *Broadcast Complete*\n\n"
        f"• *Successfully sent to:* `{success_count}` groups\n"
        f"• *Failed to send to:* `{fail_count}` groups"
    )
    await progress_message.edit_text(report_text, parse_mode='Markdown')

# --- Admin Management Commands ---
async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/addadmin [user_id]`", parse_mode='Markdown')
        return

    try:
        target_user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("*❌ Invalid User ID. It must be a number.*", parse_mode='Markdown')
        return

    setup_key = f'admin_setup_{target_user_id}'
    context.user_data[setup_key] = set()

    buttons = []
    for key, desc in PERMISSIONS.items():
        buttons.append([InlineKeyboardButton(f"🔲 {desc}", callback_data=f"admin_perm:{target_user_id}:{key}")])
    buttons.append([InlineKeyboardButton("💾 Save Permissions", callback_data=f"admin_save:{target_user_id}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel:{target_user_id}")])

    keyboard = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"Configuring permissions for admin `{target_user_id}`.\n\nSelect the permissions they should have:",
        reply_markup=keyboard,
        parse_mode='Markdown'
    )

async def remove_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/removeadmin [user_id]`", parse_mode='Markdown')
        return

    try:
        admin_id_to_remove = int(context.args[0])
        admins = load_admins()
        initial_len = len(admins)
        admins = [a for a in admins if a.get("id") != admin_id_to_remove]

        if len(admins) < initial_len:
            save_admins(admins)
            await update.message.reply_text(f"*✅ Admin `{admin_id_to_remove}` has been removed.*", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"*⚠️ Admin `{admin_id_to_remove}` not found.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid User ID.*", parse_mode='Markdown')

async def list_admins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("*❌ Only the owner can use this command.*", parse_mode='Markdown')
        return

    admins = load_admins()
    if not admins:
        await update.message.reply_text("*ℹ️ No administrators have been set up.*", parse_mode='Markdown')
        return

    text = "*👑 List of Admins and Permissions:*\n\n"
    for admin in admins:
        admin_id = admin.get("id")
        perms = admin.get("permissions", [])
        text += f"• *Admin ID:* `{admin_id}`\n"
        if perms:
            for perm_key in perms:
                perm_desc = PERMISSIONS.get(perm_key, perm_key)
                text += f"  - `{perm_desc}`\n"
        else:
            text += "  - *No permissions assigned.*\n"
        text += "\n"

    await update.message.reply_text(text, parse_mode='Markdown')

# --- Group Management Commands ---
async def add_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'add_group'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text(
            "*❌ Usage:* `/addgroup [group_id]`\n\n"
            "*Tip:* Use the `/id` command in your group to find its ID. It's usually a negative number.",
            parse_mode='Markdown'
        )
        return

    try:
        group_id = int(context.args[0])
        allowed_groups = load_allowed_groups()
        if group_id in allowed_groups:
            await update.message.reply_text(f"*⚠️ Group `{group_id}` is already on the allowed list.*", parse_mode='Markdown')
            return

        allowed_groups.append(group_id)
        save_allowed_groups(allowed_groups)
        await update.message.reply_text(f"*✅ Group `{group_id}` has been added to the allowed list.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid Group ID. It must be a number.*", parse_mode='Markdown')

async def remove_group_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'remove_group'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/removegroup [group_id]`", parse_mode='Markdown')
        return

    try:
        group_id_to_remove = int(context.args[0])
        allowed_groups = load_allowed_groups()
        if group_id_to_remove not in allowed_groups:
            await update.message.reply_text(f"*⚠️ Group `{group_id_to_remove}` not found on the allowed list.*", parse_mode='Markdown')
            return

        allowed_groups.remove(group_id_to_remove)
        save_allowed_groups(allowed_groups)
        await update.message.reply_text(f"*✅ Group `{group_id_to_remove}` has been removed from the allowed list.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid Group ID.*", parse_mode='Markdown')

async def list_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'list_groups'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    allowed_groups = load_allowed_groups()
    if not allowed_groups:
        await update.message.reply_text("*ℹ️ There are currently no allowed groups.*", parse_mode='Markdown')
        return

    text = "*🔑 Allowed Groups:*\n\n"
    for group_id in allowed_groups:
        text += f"• `{group_id}`\n"

    await update.message.reply_text(text, parse_mode='Markdown')

# --- Auto-Like Commands ---
async def autolike_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_autolike'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if len(context.args) < 3:
        await update.message.reply_text(
            "*❌ Invalid Format*\n\n"
            "*Usage:* `/autolike [region] [uid] [days]`\n\n"
            "*Example:* `/autolike ind 8431487083 30`",
            parse_mode='Markdown'
        )
        return

    region = context.args[0].lower()
    uid = context.args[1]

    try:
        days = int(context.args[2])
    except ValueError:
        await update.message.reply_text("*❌ Invalid number of days. It must be a number.*", parse_mode='Markdown')
        return

    if region not in VALID_REGIONS:
        await update.message.reply_text(f"*❌ Invalid Region: `{region}`*", parse_mode='Markdown')
        return

    autolike_users = load_autolike_users()
    expiry_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    user_found = False
    for user in autolike_users:
        if user["uid"] == uid:
            user["expiry"] = expiry_date
            user["region"] = region
            user_found = True
            break

    if not user_found:
        autolike_users.append({
            "uid": uid,
            "region": region,
            "expiry": expiry_date
        })

    save_autolike_users(autolike_users)
    await update.message.reply_text(
        f"*✅ Auto-Like service has been configured for UID `{uid}` in region `{region.upper()}` for {days} days.*",
        parse_mode='Markdown'
    )

async def remove_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_autolike'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/removeauto [uid]`", parse_mode='Markdown')
        return

    uid_to_remove = context.args[0]
    autolike_users = load_autolike_users()
    initial_len = len(autolike_users)

    autolike_users = [u for u in autolike_users if u["uid"] != uid_to_remove]

    if len(autolike_users) < initial_len:
        save_autolike_users(autolike_users)
        await update.message.reply_text(f"*✅ UID `{uid_to_remove}` has been removed from the auto-like service.*", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"*⚠️ UID `{uid_to_remove}` not found in the auto-like list.*", parse_mode='Markdown')

async def list_auto_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_autolike'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    autolike_users = load_autolike_users()
    if not autolike_users:
        await update.message.reply_text("*ℹ️ There are no users currently in the auto-like service.*", parse_mode='Markdown')
        return

    text = "*🔄 Auto-Like Service Users:*\n\n"
    for user in autolike_users:
        text += f"• *UID:* `{user['uid']}` | *Region:* `{user['region'].upper()}` | *Expires:* `{user['expiry']}`\n"

    await update.message.reply_text(text, parse_mode='Markdown')

# --- Existing Owner/Admin Commands ---
async def add_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'add_vip'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if len(context.args) < 3:
        await update.message.reply_text("*❌ Usage:* `/add [user_id] [days] [like_limit]`", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])
        days = int(context.args[1])
        like_limit = int(context.args[2])
        save_vip_user(user_id, days, like_limit)
        await update.message.reply_text(
            f"*✅ User {user_id} added/updated as VIP for {days} days with {like_limit} likes per day.*",
            parse_mode='Markdown'
        )
    except ValueError:
        await update.message.reply_text("*❌ Invalid user ID, days, or like limit.*", parse_mode='Markdown')

async def remove_vip_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'remove_vip'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*❌ Usage:* `/remove [user_id]`", parse_mode='Markdown')
        return

    try:
        user_id = int(context.args[0])
        remove_vip_user(user_id)
        await update.message.reply_text(f"*✅ User {user_id} removed from VIP.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid user ID.*", parse_mode='Markdown')

async def vip_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'list_vip'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    vip_users = load_vip_users()
    if not vip_users:
        await update.message.reply_text("*ℹ️ No VIP users found.*", parse_mode='Markdown')
        return

    text = "*🌟 VIP User List:*\n\n"
    for user in vip_users:
        expiry_status = f"Expires: `{user['expiry']}`"
        limit = user.get('like_limit', 1)
        text += f"• *ID:* `{user['id']}` - {expiry_status} - *Limit:* `{limit}` likes/day\n"

    await update.message.reply_text(text, parse_mode='Markdown')

async def reset_daily_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'reset_daily'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    reset_daily_data()
    await update.message.reply_text("*✅ Daily data has been reset.*", parse_mode='Markdown')

# === Channel Management Commands ===
async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'add_channel'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if len(context.args) < 3:
        await update.message.reply_text("*Usage:* `/addchannel <ID> <Name> <Link>`\n*Example:* `/addchannel -10012345 MyChannel https://t.me/mychannel`")
        return

    try:
        channel_id = int(context.args[0])
        channel_name = context.args[1]
        channel_link = context.args[2]

        channels = load_channels()
        if any(c['id'] == channel_id for c in channels):
            await update.message.reply_text("*⚠️ This channel is already on the list.*")
            return

        channels.append({"id": channel_id, "name": channel_name, "link": channel_link})
        save_channels(channels)
        await update.message.reply_text(f"*✅ Channel '{channel_name}' added successfully.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid Channel ID. It must be a number.*")
    except Exception as e:
        await update.message.reply_text(f"*🔥 An error occurred: {e}*")

async def remove_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'remove_channel'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*Usage:* `/removechannel <channel_id>`")
        return

    try:
        channel_id_to_remove = int(context.args[0])
        channels = load_channels()
        initial_len = len(channels)
        channels = [c for c in channels if c['id'] != channel_id_to_remove]

        if len(channels) < initial_len:
            save_channels(channels)
            await update.message.reply_text(f"*✅ Channel with ID `{channel_id_to_remove}` removed.*", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"*⚠️ No channel found with ID `{channel_id_to_remove}`.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Invalid Channel ID.*")

async def channel_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'list_channels'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    channels = load_channels()
    if not channels:
        await update.message.reply_text("*ℹ️ No channels are configured.*", parse_mode='Markdown')
        return

    text = "*📢 Mandatory Join Channels:*\n\n"
    for idx, ch in enumerate(channels, 1):
        text += f"*{idx}. Name:* `{ch['name']}`\n   *ID:* `{ch['id']}`\n   *Link:* {ch['link']}\n\n"
    await update.message.reply_text(text, parse_mode='Markdown', disable_web_page_preview=True)


# === NEW: Promotion Commands ===
async def set_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_promo'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "*❌ Invalid Format*\n\n"
            "*Usage:* `/setpromo [url] [button_text]`\n\n"
            "*Example:* `/setpromo https://youtube.com/watch?v=... Watch Our New Video!`",
            parse_mode='Markdown'
        )
        return

    url = context.args[0]
    text = " ".join(context.args[1:])

    # Basic URL validation
    if not (url.startswith('http://') or url.startswith('https://')):
        await update.message.reply_text("*❌ Invalid URL. It must start with `http://` or `https://`.*", parse_mode='Markdown')
        return

    promo_data = {"url": url, "text": text}
    save_json(PROMO_FILE, promo_data)
    await update.message.reply_text(f"*✅ Promotion has been set successfully!*\n\n*URL:* {url}\n*Text:* {text}", parse_mode='Markdown')

async def remove_promo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_promo'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if os.path.exists(PROMO_FILE):
        os.remove(PROMO_FILE)
    
    await update.message.reply_text("*✅ Promotion has been removed successfully.*", parse_mode='Markdown')


# === NEW: Moderation Commands ===
async def set_warn_limit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_moderation'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*Usage:* `/setwarnlimit <number>`\n*Example:* `/setwarnlimit 3`", parse_mode='Markdown')
        return

    try:
        limit = int(context.args[0])
        if limit <= 0:
            await update.message.reply_text("*❌ The limit must be a positive number.*", parse_mode='Markdown')
            return

        settings = load_moderation_settings()
        settings['warning_limit'] = limit
        save_moderation_settings(settings)
        await update.message.reply_text(f"*✅ Warning limit set to {limit}.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Please provide a valid number.*", parse_mode='Markdown')

async def set_mute_time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id, 'manage_moderation'):
        await update.message.reply_text("*❌ You are not authorized to use this command.*", parse_mode='Markdown')
        return

    if not context.args:
        await update.message.reply_text("*Usage:* `/setmutetime <minutes>`\n*Example:* `/setmutetime 30`", parse_mode='Markdown')
        return

    try:
        minutes = int(context.args[0])
        if minutes <= 0:
            await update.message.reply_text("*❌ The duration must be positive.*", parse_mode='Markdown')
            return

        settings = load_moderation_settings()
        settings['mute_duration_minutes'] = minutes
        save_moderation_settings(settings)
        await update.message.reply_text(f"*✅ Mute duration set to {minutes} minutes.*", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("*❌ Please provide a valid number of minutes.*", parse_mode='Markdown')


# === Button Handler ===
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    clicker_user_id = query.from_user.id
    data = query.data

    if data.startswith("verify_join:"):
        await query.answer()
        try:
            _, original_user_id_str, region, uid = data.split(":", 3)
            original_user_id = int(original_user_id_str)
        except (ValueError, IndexError):
            await query.answer("❗️ Error: Invalid verification data.", show_alert=True)
            return

        if clicker_user_id != original_user_id:
            await query.answer("⚠️ This verification request is not for you.", show_alert=True)
            return

        all_joined = True
        channels = load_channels()
        if channels:
            for channel in channels:
                try:
                    member = await context.bot.get_chat_member(chat_id=channel['id'], user_id=clicker_user_id)
                    if member.status in ['left', 'kicked']:
                        all_joined = False
                        break
                except Exception:
                    all_joined = False
                    break

        if all_joined:
            await query.message.delete()

            mock_update = type('MockUpdate', (object,), {
                'effective_user': query.from_user,
                'effective_message': query.message.reply_to_message,
                'effective_chat': query.message.chat,
                'callback_query': query
            })()

            await process_like_request(mock_update, context, region, uid)
        else:
            await query.answer("❌ You haven't joined all the required channels. Please join them and click verify again.", show_alert=True)

    elif data.startswith("admin_"):
        if clicker_user_id != OWNER_ID:
            await query.answer("This is for the bot owner only.", show_alert=True)
            return

        parts = data.split(':')
        action = parts[0]
        target_user_id = int(parts[1])
        setup_key = f'admin_setup_{target_user_id}'

        if action == "admin_perm":
            perm_key = parts[2]

            if setup_key not in context.user_data:
                 await query.edit_message_text("This action has expired or is invalid. Please start again with `/addadmin`.")
                 await query.answer()
                 return

            if perm_key in context.user_data[setup_key]:
                context.user_data[setup_key].remove(perm_key)
            else:
                context.user_data[setup_key].add(perm_key)

            selected_perms = context.user_data[setup_key]
            buttons = []
            for key, desc in PERMISSIONS.items():
                status = "✅" if key in selected_perms else "🔲"
                buttons.append([InlineKeyboardButton(f"{status} {desc}", callback_data=f"admin_perm:{target_user_id}:{key}")])
            buttons.append([InlineKeyboardButton("💾 Save Permissions", callback_data=f"admin_save:{target_user_id}")])
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"admin_cancel:{target_user_id}")])

            keyboard = InlineKeyboardMarkup(buttons)
            try:
                await query.edit_message_reply_markup(reply_markup=keyboard)
            except BadRequest as e:
                if "message is not modified" not in str(e):
                    raise
            await query.answer(f"Toggled: {PERMISSIONS.get(perm_key, 'Unknown')}")

        elif action == "admin_save":
            if setup_key not in context.user_data:
                 await query.edit_message_text("This action has expired or is invalid. Please start again with `/addadmin`.")
                 await query.answer()
                 return

            selected_perms = list(context.user_data[setup_key])
            admins = load_admins()

            admin_found = False
            for admin in admins:
                if admin['id'] == target_user_id:
                    admin['permissions'] = selected_perms
                    admin_found = True
                    break
            if not admin_found:
                admins.append({"id": target_user_id, "permissions": selected_perms})

            save_admins(admins)
            del context.user_data[setup_key]

            await query.edit_message_text(f"✅ Permissions saved for admin `{target_user_id}`.", parse_mode='Markdown')
            await query.answer("Saved!")

        elif action == "admin_cancel":
            if setup_key in context.user_data:
                del context.user_data[setup_key]
            await query.edit_message_text("❌ Admin creation canceled.")
            await query.answer()

    # --- NEW: Unmute button logic ---
    elif data.startswith("unmute:"):
        await query.answer()
        try:
            _, user_to_unmute_id_str, chat_id_str = data.split(":")
            user_to_unmute_id = int(user_to_unmute_id_str)
            chat_id = int(chat_id_str)
        except (ValueError, IndexError):
            await query.answer("❗️ Error: Invalid unmute data.", show_alert=True)
            return

        clicker_user_id = query.from_user.id
        is_authorized_to_unmute = False

        if clicker_user_id == OWNER_ID:
            is_authorized_to_unmute = True
        else:
            try:
                member = await context.bot.get_chat_member(chat_id, clicker_user_id)
                if member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
                    is_authorized_to_unmute = True
            except Exception as e:
                print(f"Could not verify unmute permission for {clicker_user_id} in {chat_id}: {e}")

        if is_authorized_to_unmute:
            try:
                # Restore default permissions to unmute the user
                await context.bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=user_to_unmute_id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True,
                    )
                )
                await query.edit_message_text(f"✅ User has been unmuted by {query.from_user.mention_markdown()}.", parse_mode='Markdown')
            except Exception as e:
                print(f"Failed to unmute user {user_to_unmute_id}: {e}")
                await query.answer("Failed to unmute the user.", show_alert=True)
        else:
            await query.answer("❌ You are not authorized to unmute users in this group.", show_alert=True)


# === NEW: Welcome Handler (FIXED & IMPROVED) ===
async def welcome_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return

    chat = update.message.chat
    new_members = update.message.new_chat_members

    for member in new_members:
        if member.is_bot:
            continue
            
        try:
            total_members = await context.bot.get_chat_member_count(chat.id)
            user_name = member.full_name
            user_id = member.id
            username = f"@{member.username}" if member.username else "N/A"

            welcome_text = (
                f"🎉 <b>WELCOME TO THE GROUP</b> 🎉\n\n"
                f"Hello {user_name}, thanks for joining!\n\n"
                f"This bot lets you get likes in Free Fire for free. "
                f"Just use the command:\n"
                f"<code>/like [region] [uid]</code>\n\n"
                f"<b>─── Member Details ───</b>\n"
                f"› <b>NAME:</b> {user_name}\n"
                f"› <b>ID:</b> <code>{user_id}</code>\n"
                f"› <b>USERNAME:</b> {username}\n"
                f"› <b>TOTAL MEMBERS:</b> {total_members}\n"
                f"<b>────────────────────</b>"
            )

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🤖 Use the Bot", url=f"https://t.me/{context.bot.username}?start=help")],
                [InlineKeyboardButton("🌟 Main Channel", url=JOIN_CHANNEL_LINK)]
            ])

            await context.bot.send_photo(
                chat_id=chat.id,
                photo=WELCOME_IMAGE_URL,
                caption=welcome_text,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Failed to send welcome message in chat {chat.id} for user {member.id}: {e}")

# === NEW: Moderation Handler (FIXED & UPDATED) ===
async def moderation_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.from_user:
        return
        
    user = message.from_user
    chat = message.chat

    if chat.type == 'private':
        return

    try:
        member = await chat.get_member(user.id)
        if member.status in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            return
    except Exception as e:
        print(f"Could not check member status for moderation: {e}")
        return

    try:
        await message.delete()
    except Exception as e:
        print(f"Failed to delete message: {e}")
        return

    warnings = load_warnings()
    settings = load_moderation_settings()
    user_id_str = str(user.id)

    if user_id_str not in warnings:
        warnings[user_id_str] = 0

    warnings[user_id_str] += 1
    current_warnings = warnings[user_id_str]

    if current_warnings >= settings['warning_limit']:
        mute_duration = timedelta(minutes=settings['mute_duration_minutes'])
        try:
            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=user.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + mute_duration
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔓 Unmute User", callback_data=f"unmute:{user.id}:{chat.id}")]
            ])
            await context.bot.send_message(
                chat_id=chat.id,
                text=f"🔇 {user.mention_markdown()} has been muted for {settings['mute_duration_minutes']} minutes for reaching the limit of {settings['warning_limit']} warnings.",
                parse_mode='Markdown',
                reply_markup=keyboard
            )
            warnings[user_id_str] = 0
        except Exception as e:
            print(f"Failed to mute user {user.id}: {e}")
    else:
        await context.bot.send_message(
            chat_id=chat.id,
            text=f"⚠️ {user.mention_markdown()}, please do not send emojis, links, mentions, or forwarded messages.\n\n"
                    f"Warning {current_warnings}/{settings['warning_limit']}.",
            parse_mode='Markdown'
        )

    save_warnings(warnings)

# === Cleanup on Shutdown ===
def clear_data_on_shutdown():
    for file in [USAGE_FILE]:
        if os.path.exists(file):
            with open(file, 'w') as f:
                json.dump([], f)
    print("*🧹 Daily usage data cleared.*")

def handle_shutdown(signum, frame):
    print("*🚫 Stopping the bot...*")
    clear_data_on_shutdown()
    sys.exit(0)

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

# === Function to start the scheduler after bot initialization ===
async def post_init(application: Application):
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Kolkata'))
    scheduler.add_job(run_daily_autolikes, 'cron', hour=4, minute=5, args=[application])
    scheduler.start()
    print("*⏰ Auto-Like service has been scheduled.*")

# === Start Bot ===
if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(post_init).build()

    # User Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("like", like_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("myinfo", myinfo_command))
    app.add_handler(CommandHandler("id", id_command))
    app.add_handler(CommandHandler("feedback", feedback_command))
    app.add_handler(CommandHandler("help", help_command)) # IMPROVED user/admin help
    app.add_handler(CommandHandler("ownerhelp", owner_help_command)) # Detailed owner/admin help


    # Admin/Owner Commands
    app.add_handler(CommandHandler("add", add_vip_command))
    app.add_handler(CommandHandler("remove", remove_vip_command))
    app.add_handler(CommandHandler("viplist", vip_list_command))
    app.add_handler(CommandHandler("resetdaily", reset_daily_command))
    app.add_handler(CommandHandler("addchannel", add_channel_command))
    app.add_handler(CommandHandler("removechannel", remove_channel_command))
    app.add_handler(CommandHandler("channellist", channel_list_command))
    app.add_handler(CommandHandler("addgroup", add_group_command))
    app.add_handler(CommandHandler("removegroup", remove_group_command))
    app.add_handler(CommandHandler("listgroups", list_groups_command))
    app.add_handler(CommandHandler("autolike", autolike_command))
    app.add_handler(CommandHandler("removeauto", remove_auto_command))
    app.add_handler(CommandHandler("listauto", list_auto_command))

    # New Promotion Commands
    app.add_handler(CommandHandler("setpromo", set_promo_command))
    app.add_handler(CommandHandler("removepromo", remove_promo_command))
    
    # New Moderation Commands
    app.add_handler(CommandHandler("setwarnlimit", set_warn_limit_command))
    app.add_handler(CommandHandler("setmutetime", set_mute_time_command))
    
    # NEW Owner-only Broadcast Command
    app.add_handler(CommandHandler("gcmessage", gcmessage_command))

    # Admin Management Commands (Owner Only)
    app.add_handler(CommandHandler("addadmin", add_admin_command))
    app.add_handler(CommandHandler("removeadmin", remove_admin_command))
    app.add_handler(CommandHandler("listadmins", list_admins_command))

    # Handlers
    # Using MessageHandler for new members is more reliable
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_members))
    
    forbidden_content_filters = (
        filters.FORWARDED |
        filters.Entity(MessageEntity.URL) |
        filters.Entity(MessageEntity.TEXT_LINK) |
        filters.Entity(MessageEntity.MENTION) |
        filters.Entity(MessageEntity.CUSTOM_EMOJI) |
        filters.Regex(re.compile(
            "["
            "\U0001F600-\U0001F64F"
            "\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF"
            "\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+"
        ))
    )
    app.add_handler(MessageHandler(forbidden_content_filters & (~filters.COMMAND), moderation_handler))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("*🤖 The Free Fire VIP Like Bot is running...*")
    app.run_polling()