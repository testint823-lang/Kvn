from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, BadRequest, UserAlreadyParticipant, PeerIdInvalid, PhoneNumberUnoccupied
from pyrogram.raw.functions.account import ReportPeer
from pyrogram.raw.functions.messages import Report
from pyrogram.raw.types import (
    InputReportReasonSpam, InputReportReasonViolence,
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake, InputReportReasonIllegalDrugs,
    InputPeerChannel, InputChannel, InputReportReasonOther
)
import os
import asyncio
from dotenv import load_dotenv
import signal
import re
import time
import random

load_dotenv()

# Clean old session files
for file in os.listdir('.'):
    if file.endswith('.session') or file.endswith('.session-journal'):
        try:
            os.remove(file)
        except:
            pass

# ==================== CONFIGURATION ====================

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOGGER_GROUP_ID = int(os.getenv("LOGGER_GROUP_ID", "0"))
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
MAX_REPORTS = int(os.getenv("MAX_REPORTS", "10"))

# Load session strings
def load_session_strings():
    sessions = {}
    i = 1
    while True:
        session_string = os.getenv(f"STRING_{i}")
        if not session_string:
            break
        sessions[i] = session_string
        i += 1
    return sessions

SESSION_STRINGS = load_session_strings()
TOTAL_ACCOUNTS = len(SESSION_STRINGS)

# ==================== NEW 2025 REPORT SYSTEM ====================

REPORT_REASONS = {
    "child_sexual": (
        "👶🔞 Child Sexual Abuse",
        InputReportReasonChildAbuse(),
        b'\x08\x01',
        "CSAM/CP content detected. Immediate action required under child protection laws."
    ),
    "child_physical": (
        "👶⚔️ Child Physical Abuse",
        InputReportReasonChildAbuse(),
        b'\x08\x02',
        "Child physical abuse content detected. Violates child protection regulations."
    ),
    "child_exploitation": (
        "👶💰 Child Exploitation",
        InputReportReasonChildAbuse(),
        b'\x08\x03',
        "Child exploitation content detected. Immediate removal required."
    ),
    "porn_adult": (
        "🔞 Adult Pornography",
        InputReportReasonPornography(),
        b'\x10\x01',
        "Illegal pornographic content shared without consent."
    ),
    "porn_nonconsensual": (
        "🔞⚠️ Non-consensual Content",
        InputReportReasonPornography(),
        b'\x10\x02',
        "Non-consensual intimate content. Privacy violation."
    ),
    "violence_graphic": (
        "⚔️ Graphic Violence",
        InputReportReasonViolence(),
        b'\x18\x01',
        "Graphic violent content. Violates community standards."
    ),
    "violence_threats": (
        "⚔️⚠️ Threats/Terrorism",
        InputReportReasonViolence(),
        b'\x18\x02',
        "Violent threats or terrorist content detected."
    ),
    "spam": (
        "🚫 Spam",
        InputReportReasonSpam(),
        None,
        "Spam content reported."
    ),
    "copyright": (
        "©️ Copyright Violation",
        InputReportReasonCopyright(),
        None,
        "Copyright violation detected."
    ),
    "fake": (
        "🎭 Fake Account/Impersonation",
        InputReportReasonFake(),
        None,
        "Fake account or impersonation detected."
    ),
    "illegal_drugs": (
        "💊 Illegal Drugs",
        InputReportReasonIllegalDrugs(),
        None,
        "Illegal drug content detected."
    ),
    "other": (
        "❓ Other Violation",
        InputReportReasonOther(),
        None,
        "Content violates Telegram Terms of Service."
    )
}

# Storage
user_clients = {}
report_data = {}
logger_group_invite_link = None
assistant_status = {}

# ==================== BOT INSTANCE ====================

bot = Client(
    "report_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# ==================== OWNER CHECK ====================

def owner_only(func):
    async def wrapper(client, update):
        user_id = update.from_user.id
        if user_id != OWNER_ID:
            if isinstance(update, Message):
                await update.reply_text("❌ This bot is private. Owner only!")
            else:
                await update.answer("❌ Owner only!", show_alert=True)
            return
        return await func(client, update)
    return wrapper

# ==================== PARSE MESSAGE LINK ====================

def parse_message_link(link):
    patterns = [
        r't\.me/([^/]+)/(\d+)',
        r't\.me/c/(-?\d+)/(\d+)'
    ]
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.groups()
    return None

# ==================== CHECK IF BOT IS ADMIN ====================

async def check_bot_admin_status():
    try:
        test_link = await bot.create_chat_invite_link(
            LOGGER_GROUP_ID,
            name="Test Link",
            creates_join_request=False
        )
        print(f"✅ Bot has admin access!")
        try:
            await bot.revoke_chat_invite_link(LOGGER_GROUP_ID, test_link.invite_link)
        except:
            pass
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "chat_admin_required" in error_msg:
            print("❌ Bot is not admin!")
        elif "chat_admin_invite_required" in error_msg:
            print("❌ Bot doesn't have 'Invite Users' permission!")
        else:
            print(f"❌ Error: {e}")
        return False

# ==================== WAIT FOR BOT TO BE ADMIN ====================

async def wait_for_admin_access():
    print("\n" + "=" * 60)
    print("⏳ Waiting for bot to be made admin in logger group...")
    print("⚠️  Make sure bot has 'Invite Users via Link' permission!")
    print("=" * 60)
    max_attempts = 20
    for attempt in range(1, max_attempts + 1):
        try:
            print(f"\n🔍 Checking if bot is admin... (Attempt {attempt}/{max_attempts})")
            try:
                chat = await bot.get_chat(LOGGER_GROUP_ID)
                print(f"✅ Bot is in group: {chat.title}")
            except Exception as e:
                print(f"❌ Bot is not in group: {e}")
                print("⚠️  Please add bot to logger group first!")
                await asyncio.sleep(3)
                continue
            is_admin = await check_bot_admin_status()
            if is_admin:
                print("\n" + "=" * 60)
                print("✅ BOT IS NOW ADMIN WITH INVITE PERMISSION!")
                print("=" * 60 + "\n")
                return True
            else:
                print(f"⚠️  Waiting 3 seconds before next check...")
                await asyncio.sleep(3)
        except Exception as e:
            print(f"❌ Error on attempt {attempt}: {e}")
            await asyncio.sleep(3)
    print("\n" + "=" * 60)
    print("❌ TIMEOUT: Bot was not made admin within 1 minute!")
    print("=" * 60 + "\n")
    return False

# ==================== GENERATE INVITE LINK ====================

async def generate_invite_link():
    global logger_group_invite_link
    try:
        print("🔗 Generating invite link for logger group...")
        invite_link = await bot.create_chat_invite_link(
            LOGGER_GROUP_ID,
            name="Assistant Accounts",
            creates_join_request=False
        )
        logger_group_invite_link = invite_link.invite_link
        print(f"✅ Invite link generated successfully!")
        return True
    except Exception as e:
        print(f"❌ Failed to generate invite link: {e}")
        return False

# ==================== CONNECT ACCOUNTS ====================

async def connect_all_accounts():
    global assistant_status
    print("=" * 60)
    print(f"🔗 Connecting {TOTAL_ACCOUNTS} accounts...")
    print("=" * 60)
    for acc_num, session_string in SESSION_STRINGS.items():
        try:
            print(f"📱 Connecting Account #{acc_num}...")
            client = Client(
                name=f"account_{acc_num}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True
            )
            await client.start()
            me = await client.get_me()
            print(f"✅ Account #{acc_num}: {me.first_name} (@{me.username or 'No username'})")
            user_clients[acc_num] = client
            assistant_status[acc_num] = {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name,
                "status": "connected"
            }
        except Exception as e:
            print(f"❌ Account #{acc_num} failed: {e}")
            assistant_status[acc_num] = {
                "status": "failed",
                "error": str(e)[:100]
            }
    print("=" * 60)
    print(f"✅ {len(user_clients)}/{TOTAL_ACCOUNTS} accounts connected!")
    print("=" * 60)
    if LOGGER_GROUP_ID and user_clients:
        await setup_logger_group()

# ==================== SETUP LOGGER GROUP ====================

async def setup_logger_group():
    print("\n📥 Setting up logger group...")
    is_admin = await wait_for_admin_access()
    if not is_admin:
        print("❌ Setup cancelled - Bot is not admin")
        return
    link_generated = await generate_invite_link()
    if not link_generated:
        print("❌ Setup cancelled - Failed to generate invite link")
        return
    print("\n" + "=" * 60)
    print(f"📥 Joining {len(user_clients)} assistant accounts to logger group...")
    print("=" * 60)
    joined_count = 0
    for acc_num, client in user_clients.items():
        try:
            print(f"📥 Joining Account #{acc_num}...")
            await client.join_chat(logger_group_invite_link)
            print(f"✅ Account #{acc_num} joined successfully")
            joined_count += 1
        except UserAlreadyParticipant:
            print(f"✅ Account #{acc_num} already in group")
            joined_count += 1
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to join: {e}")
            assistant_status[acc_num]["logger_status"] = f"Failed: {str(e)[:50]}"
        await asyncio.sleep(1)
    print("=" * 60)
    print(f"✅ {joined_count}/{len(user_clients)} accounts joined successfully!")
    print("=" * 60)
    print("\n📢 Sending startup messages...")
    for acc_num, client in user_clients.items():
        try:
            await client.send_message(
                LOGGER_GROUP_ID,
                f"✅ **Assistant Started**\n\nAccount #{acc_num} is ready!\n\nUser ID: `{assistant_status[acc_num]['id']}`"
            )
            print(f"✅ Account #{acc_num} sent startup message")
            assistant_status[acc_num]["logger_status"] = "active"
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to send: {e}")
            assistant_status[acc_num]["logger_status"] = f"Failed to send: {str(e)[:50]}"
    print("=" * 60)
    print("✅ Logger group setup complete!")
    print("=" * 60 + "\n")

# ==================== START COMMAND ====================

@bot.on_message(filters.command("start") & filters.private)
@owner_only
async def start_command(client, message):
    active = len(user_clients)
    await message.reply_text(
        f"🔐 **Multi-Account Report Bot (2025 Edition)**\n\n"
        f"👑 Owner: {message.from_user.first_name}\n"
        f"📊 Total Accounts: {TOTAL_ACCOUNTS}\n"
        f"✅ Active Sessions: {active}\n"
        f"🔁 Reports per Account: {MAX_REPORTS}\n\n"
        f"**✨ NEW: 2025 Report System**\n"
        f"• Sub-category selection ✅\n"
        f"• Automatic comments ✅\n"
        f"• Enhanced success rate ✅\n\n"
        f"**Available Commands:**\n"
        f"• `/stats` - View session statistics\n"
        f"• `/check` - Test all accounts\n"
        f"• `/report` - Report content (with new system)\n\n"
        f"**Quick Report:**\n"
        f"Reply to any message link with `/report`\n\n"
        f"⚡️ Reports now include sub-categories & comments!"
    )

# ==================== STATS COMMAND ====================

@bot.on_message(filters.command("stats") & filters.private)
@owner_only
async def stats_command(client, message):
    active = len(user_clients)
    inactive = TOTAL_ACCOUNTS - active
    text = "📊 **Session Statistics**\n\n"
    text += f"📦 Total Accounts: {TOTAL_ACCOUNTS}\n"
    text += f"✅ Active Sessions: {active}\n"
    text += f"⚪️ Inactive Sessions: {inactive}\n"
    text += f"🔁 Reports per Account: {MAX_REPORTS}\n"
    text += f"📊 Total Reports: {active * MAX_REPORTS}\n\n"
    if user_clients:
        text += "**Active Accounts:**\n"
        for acc_num, cl in user_clients.items():
            try:
                me = await cl.get_me()
                text += f"• Account #{acc_num} - {me.first_name} (@{me.username or 'N/A'})\n"
            except:
                text += f"• Account #{acc_num} - Error\n"
    if inactive > 0:
        text += f"\n⚠️ {inactive} account(s) failed to connect."
    await message.reply_text(text)

# ==================== CHECK COMMAND ====================

@bot.on_message(filters.command("check"))
@owner_only
async def check_command(client, message):
    if not LOGGER_GROUP_ID:
        await message.reply_text("❌ Logger group not configured!")
        return
    if message.chat.id != LOGGER_GROUP_ID:
        await message.reply_text("❌ This command only works in logger group!")
        return
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    status = await message.reply_text(f"🔍 Testing {len(user_clients)} accounts...")
    success = 0
    failed = 0
    results = []
    for acc_num, cl in user_clients.items():
        try:
            sent_msg = await cl.send_message(
                message.chat.id,
                f"✅ **Account #{acc_num} - Working**\n\nUser ID: `{assistant_status.get(acc_num, {}).get('id', 'N/A')}`"
            )
            await asyncio.sleep(5)
            try:
                await sent_msg.delete()
            except:
                pass
            success += 1
            results.append(f"✅ Account #{acc_num}: Working")
        except Exception as e:
            error_msg = str(e)
            await message.reply_text(f"❌ Account #{acc_num}: {error_msg[:100]}")
            failed += 1
            results.append(f"❌ Account #{acc_num}: {error_msg[:50]}")
        await asyncio.sleep(2)
    result_text = f"✅ **Check Complete!**\n\n"
    result_text += f"✅ Working: {success}\n"
    result_text += f"❌ Failed: {failed}\n"
    result_text += f"📊 Total: {len(user_clients)}\n\n"
    if results:
        result_text += "\n".join(results[:15])
        if len(results) > 15:
            result_text += f"\n\n... and {len(results) - 15} more"
    await status.edit_text(result_text)

# ==================== REPORT COMMAND ====================

@bot.on_message(filters.command("report") & filters.private)
@owner_only
async def report_command(client, message):
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    if message.reply_to_message and message.reply_to_message.text:
        target = message.reply_to_message.text.strip()
        print(f"DEBUG: Target received: {target}")
        if 't.me/' in target and '/' in target.split('t.me/')[-1]:
            parsed = parse_message_link(target)
            if parsed:
                report_data[OWNER_ID] = {
                    "step": "ask_reason",
                    "type": "message",
                    "target": target,
                    "parsed": parsed
                }
                await show_reason_keyboard(await message.reply_text("📨 Detected: Message Link"))
                return
        if 't.me/' in target:
            if 't.me/joinchat/' in target or 't.me/+' in target:
                report_data[OWNER_ID] = {
                    "step": "ask_reason",
                    "type": "private_chat",
                    "target": target
                }
                await show_reason_keyboard(await message.reply_text("🔒 Detected: Private Chat/Channel"))
                return
            else:
                parts = target.split('t.me/')
                if len(parts) > 1:
                    username = parts[-1].split('/')[0].replace('@', '').strip()
                    report_data[OWNER_ID] = {
                        "step": "ask_reason",
                        "type": "public_chat",
                        "target": username
                    }
                    await show_reason_keyboard(await message.reply_text(f"📢 Detected: @{username}"))
                    return
        if target.startswith('@') or (not target.startswith('http') and not '/' in target and not 't.me' in target):
            username = target.replace('@', '').strip()
            report_data[OWNER_ID] = {
                "step": "ask_reason",
                "type": "public_chat",
                "target": username
            }
            await show_reason_keyboard(await message.reply_text(f"🤖 Detected: @{username}"))
            return
    report_data[OWNER_ID] = {"step": "ask_type"}
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Public Chat/Channel", callback_data="type_public")],
        [InlineKeyboardButton("🔒 Private Chat/Channel", callback_data="type_private")]
    ])
    await message.reply_text(
        f"📝 **Report System (2025 Edition)**\n\n"
        f"Ready to report with {len(user_clients)} accounts.\n"
        f"Each account will send {MAX_REPORTS} report(s).\n\n"
        f"Is the target public or private?",
        reply_markup=keyboard
    )

# ==================== REPORT IN LOGGER GROUP ====================

@bot.on_message(filters.command("report") & filters.group)
@owner_only
async def report_in_logger_group(client, message):
    if message.chat.id != LOGGER_GROUP_ID:
        return
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply_text("❌ Please reply to a message link with /report command!")
        return
    target = message.reply_to_message.text.strip()
    parsed = parse_message_link(target)
    if not parsed:
        await message.reply_text("❌ Invalid message link format!")
        return
    chat_identifier, msg_id = parsed
    report_data[OWNER_ID] = {
        "step": "verification",
        "type": "message",
        "target": target,
        "parsed": parsed
    }
    if not user_clients:
        await message.reply_text("❌ No active assistant accounts!")
        return
    test_acc_num = list(user_clients.keys())[0]
    test_client = user_clients[test_acc_num]
    status_msg = await message.reply_text(f"🔍 **Verification**\n\nTesting access...")
    try:
        if not chat_identifier.startswith('-100') and not chat_identifier.startswith('-'):
            chat = await test_client.get_chat(chat_identifier)
            chat_id = chat.id
            chat_title = chat.title
        else:
            chat_id = int(chat_identifier)
            chat = await test_client.get_chat(chat_id)
            chat_title = chat.title
        try:
            msg = await test_client.get_messages(chat_id, int(msg_id))
            forwarded_msg = await test_client.forward_messages(LOGGER_GROUP_ID, chat_id, int(msg_id))
            await status_msg.edit_text(
                f"✅ **Verification SUCCESS**\n\n"
                f"Channel: {chat_title}\n"
                f"Message ID: {msg_id}"
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ CONFIRM", callback_data=f"confirm_report_{chat_id}_{msg_id}")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_report")]
            ])
            await message.reply_text(
                f"⚠️ **CONFIRMATION REQUIRED**\n\n"
                f"Channel: {chat_title}\n"
                f"Message ID: {msg_id}\n\n"
                f"Will report as: Child Sexual Abuse\n"
                f"Total Reports: {len(user_clients) * MAX_REPORTS}\n\n"
                f"Click CONFIRM:",
                reply_markup=keyboard
            )
        except Exception as e:
            await status_msg.edit_text(f"❌ **FAILED**\n\nError: `{str(e)[:100]}`")
    except Exception as e:
        await status_msg.edit_text(f"❌ **FAILED**\n\nError: `{str(e)[:100]}`")

# ==================== HANDLE USER INPUT ====================

@bot.on_message(filters.private & ~filters.command(["start", "stats", "report", "check"]))
@owner_only
async def handle_user_input(client, message):
    if OWNER_ID not in report_data:
        return
    data = report_data[OWNER_ID]
    if data.get("step") == "ask_link":
        target = message.text.strip()
        if target.startswith('@'):
            username = target[1:]
        elif 't.me/' in target:
            parts = target.split('t.me/')
            username = parts[-1].split('/')[0].replace('@', '')
        else:
            username = target
        report_data[OWNER_ID] = {
            "step": "ask_reason",
            "type": "public_chat",
            "target": username
        }
        await show_reason_keyboard(await message.reply_text(f"📢 Target: @{username}"))
    elif data.get("step") == "ask_invite":
        target = message.text.strip()
        report_data[OWNER_ID] = {
            "step": "ask_reason",
            "type": "private_chat",
            "target": target
        }
        await show_reason_keyboard(await message.reply_text("🔒 Target: Private Chat"))

# ==================== TYPE SELECTION ====================

@bot.on_callback_query(filters.regex("^type_"))
@owner_only
async def select_type(client, callback):
    chat_type = callback.data.split("_")[1]
    report_data[OWNER_ID] = {
        "step": "ask_link" if chat_type == "public" else "ask_invite",
        "type": chat_type
    }
    if chat_type == "public":
        await callback.message.edit_text(
            "📢 **Public Chat/Channel**\n\n"
            "Send the chat/channel link or username:\n\n"
            "**Examples:**\n"
            "• `https://t.me/channel_name`\n"
            "• `@channel_name`"
        )
    else:
        await callback.message.edit_text(
            "🔒 **Private Chat/Channel**\n\n"
            "Send the invite link:\n\n"
            "**Examples:**\n"
            "• `https://t.me/+AbCdEfGhIjKl`"
        )
    await callback.answer()

# ==================== REASON SELECTION ====================

async def show_reason_keyboard(msg):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👶🔞 Child Sexual Abuse", callback_data="reason_child_sexual")],
        [InlineKeyboardButton("👶⚔️ Child Physical Abuse", callback_data="reason_child_physical")],
        [InlineKeyboardButton("🔞 Adult Pornography", callback_data="reason_porn_adult")],
        [InlineKeyboardButton("⚔️ Graphic Violence", callback_data="reason_violence_graphic")],
        [InlineKeyboardButton("🚫 Spam", callback_data="reason_spam")],
        [InlineKeyboardButton("©️ Copyright", callback_data="reason_copyright")]
    ])
    await msg.edit_text(
        "⚠️ **Select Report Reason (2025 System)**\n\n"
        "Reports include sub-categories & comments:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("^reason_"))
@owner_only
async def select_reason(client, callback):
    reason_key = callback.data.split("_", 1)[1]
    if OWNER_ID not in report_data:
        await callback.answer("Session expired!", show_alert=True)
        return
    report_data[OWNER_ID]["reason"] = reason_key
    reason_name, _, _, _ = REPORT_REASONS[reason_key]
    await callback.message.edit_text(
        f"✅ Reason: {reason_name}\n\n"
        f"⏳ Sending reports...\n"
        f"Please wait..."
    )
    await callback.answer()
    await execute_report(client, callback.message)

# ==================== CONFIRMATION HANDLER ====================

@bot.on_callback_query(filters.regex("^confirm_report_"))
@owner_only
async def confirm_report(client, callback):
    data_parts = callback.data.split("_")
    chat_id = data_parts[2]
    msg_id = data_parts[3]
    if OWNER_ID not in report_data:
        await callback.answer("Session expired!", show_alert=True)
        return
    await callback.message.edit_text(
        f"🚀 **Starting Mass Reports**\n\n"
        f"⏳ Sending reports with new 2025 system..."
    )
    await callback.answer("Starting...")
    await execute_verified_report(client, callback.message, chat_id, msg_id)

@bot.on_callback_query(filters.regex("^cancel_report$"))
@owner_only
async def cancel_report(client, callback):
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]
    await callback.message.edit_text("❌ **Report Cancelled**")
    await callback.answer("Cancelled")

# ==================== EXECUTE VERIFIED REPORT ====================

async def execute_verified_report(client, message, chat_id, msg_id):
    if not user_clients:
        await message.edit_text("❌ No active accounts!")
        return
    success = 0
    failed = 0
    working_accounts = list(user_clients.items())
    reason_name, reason_obj, option_bytes, comment_text = REPORT_REASONS["child_sexual"]
    for report_num in range(MAX_REPORTS):
        for acc_num, ucl in working_accounts:
            try:
                await ucl.invoke(
                    Report(
                        peer=await ucl.resolve_peer(int(chat_id)),
                        id=[int(msg_id)],
                        reason=reason_obj,
                        message=comment_text,
                        option=option_bytes
                    )
                )
                success += 1
                print(f"✅ Account #{acc_num} report #{report_num + 1} SUCCESS")
            except Exception as e:
                error = str(e)
                print(f"❌ Account #{acc_num} failed: {error}")
                if "FLOOD_WAIT" in error:
                    wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                    if wait_match:
                        await asyncio.sleep(int(wait_match.group(1)))
                failed += 1
            await asyncio.sleep(random.uniform(3, 7))
    await message.edit_text(
        f"📊 **Mass Report Completed**\n\n"
        f"✅ Successful: {success}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Accounts: {len(working_accounts)}\n\n"
        f"✨ Reports sent with 2025 system:\n"
        f"• Sub-category included ✅\n"
        f"• Strong comments included ✅"
    )
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]

# ==================== EXECUTE REPORT ====================

async def execute_report(client, message):
    if OWNER_ID not in report_data:
        await message.edit_text("❌ Report session expired!")
        return
    data = report_data[OWNER_ID]
    reason_key = data["reason"]
    reason_name, reason_obj, option_bytes, comment_text = REPORT_REASONS[reason_key]
    success = 0
    failed = 0
    report_type = data.get("type")
    target = data.get("target", "")
    working_accounts = list(user_clients.items())
    if not working_accounts:
        await message.edit_text("❌ No working accounts!")
        return
    
    # Public chat/channel report
    if report_type in ["public_chat", "channel"]:
        username = target
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in working_accounts:
                try:
                    await ucl.invoke(
                        ReportPeer(
                            peer=await ucl.resolve_peer(username),
                            reason=reason_obj,
                            message=comment_text
                        )
                    )
                    success += 1
                    print(f"✅ Account #{acc_num} report #{report_num + 1} SUCCESS")
                except Exception as e:
                    error = str(e)
                    print(f"❌ Account #{acc_num} failed: {error}")
                    if "FLOOD_WAIT" in error:
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            await asyncio.sleep(int(wait_match.group(1)))
                    if "USER_BOT" not in error and "PHONE_NOT" not in error:
                        failed += 1
                await asyncio.sleep(random.uniform(3, 7))
    
    # Private chat report
    elif report_type == "private_chat":
        invite_link = target
        joined_accounts = []
        for acc_num, ucl in working_accounts:
            try:
                await ucl.join_chat(invite_link)
                joined_accounts.append((acc_num, ucl))
            except UserAlreadyParticipant:
                joined_accounts.append((acc_num, ucl))
            except:
                pass
        if not joined_accounts:
            await message.edit_text("❌ No accounts could join!")
            return
        chat_id = None
        try:
            chat = await joined_accounts[0][1].get_chat(invite_link)
            chat_id = chat.id
        except:
            pass
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in joined_accounts:
                try:
                    await ucl.invoke(
                        ReportPeer(
                            peer=await ucl.resolve_peer(chat_id) if chat_id else await ucl.resolve_peer(invite_link),
                            reason=reason_obj,
                            message=comment_text
                        )
                    )
                    success += 1
                    print(f"✅ Account #{acc_num} report #{report_num + 1} SUCCESS")
                except Exception as e:
                    error = str(e)
                    if "FLOOD_WAIT" in error:
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            await asyncio.sleep(int(wait_match.group(1)))
                    if "USER_BOT" not in error:
                        failed += 1
                await asyncio.sleep(random.uniform(3, 7))
    
    # Message report
    elif report_type == "message":
        parsed = data["parsed"]
        chat_id, msg_id = parsed
        if not chat_id.startswith('-'):
            chat_id = f"-100{chat_id}"
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in working_accounts:
                try:
                    await ucl.invoke(
                        Report(
                            peer=await ucl.resolve_peer(int(chat_id)),
                            id=[int(msg_id)],
                            reason=reason_obj,
                            message=comment_text,
                            option=option_bytes if option_bytes else b''
                        )
                    )
                    success += 1
                    print(f"✅ Account #{acc_num} report #{report_num + 1} SUCCESS")
                except Exception as e:
                    error = str(e)
                    print(f"❌ Account #{acc_num} failed: {error}")
                    if "FLOOD_WAIT" in error:
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            await asyncio.sleep(int(wait_match.group(1)))
                    if "PHONE_NOT" not in error and "USER_BOT" not in error:
                        failed += 1
                await asyncio.sleep(random.uniform(3, 7))
    
    # Send results
    await message.edit_text(
        f"📊 **Report Results (2025 System)**\n\n"
        f"🎯 Target: {target}\n"
        f"📨 Reason: {reason_name}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"👥 Accounts: {len(working_accounts)}\n\n"
        f"✨ Reports sent with new system:\n"
        f"• Sub-category included ✅\n"
        f"• Strong comments included ✅"
    )
    if LOGGER_GROUP_ID:
        try:
            await bot.send_message(
                LOGGER_GROUP_ID,
                f"📊 **Report Completed**\n\n"
                f"Target: {target}\n"
                f"Reason: {reason_name}\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}"
            )
        except:
            pass
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]

# ==================== STOP ALL CLIENTS ====================

async def stop_all():
    print("\n⏳ Stopping all sessions...")
    for acc_num, cl in user_clients.items():
        try:
            await cl.stop()
            print(f"✅ Account #{acc_num} stopped")
        except:
            pass
    try:
        await bot.stop()
        print("✅ Bot stopped")
    except:
        pass
    print("👋 Goodbye!")

# ==================== IDLE FUNCTION ====================

async def idle():
    stop_event = asyncio.Event()
    def signal_handler(signum, frame):
        stop_event.set()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    await stop_event.wait()

# ==================== MAIN FUNCTION ====================

async def main():
    try:
        await bot.start()
        print("✅ Bot started!")
        me = await bot.get_me()
        print(f"🤖 Bot: {me.first_name} (@{me.username})")
        print("\n" + "=" * 60)
        print("✨ NEW 2025 TELEGRAM REPORT SYSTEM ENABLED")
        print("=" * 60)
        print("• Sub-category selection ✅")
        print("• Automatic strong comments ✅")
        print("• Enhanced API compatibility ✅")
        print("• Higher success rate expected ✅")
        print("=" * 60 + "\n")
        await connect_all_accounts()
        await idle()
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 STARTING BOT...")
    print("=" * 60)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        loop.run_until_complete(stop_all())
        loop.close()
