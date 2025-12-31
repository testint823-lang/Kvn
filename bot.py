from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, BadRequest, UserAlreadyParticipant, PeerIdInvalid, PhoneNumberUnoccupied
from pyrogram.raw.functions.account import ReportPeer
from pyrogram.raw.functions.messages import Report
from pyrogram.raw.types import (
    InputReportReasonSpam, InputReportReasonViolence, 
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake, InputReportReasonIllegalDrugs,
    InputPeerUser
)
import os
import asyncio
from dotenv import load_dotenv
import signal
import re

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

# Report reasons
REPORT_REASONS = {
    "spam": ("🚫 Spam", InputReportReasonSpam()),
    "violence": ("⚔️ Violence", InputReportReasonViolence()),
    "pornography": ("🔞 Pornography/Nudity", InputReportReasonPornography()),
    "child_abuse": ("👶 Child Abuse", InputReportReasonChildAbuse()),
    "copyright": ("©️ Copyright", InputReportReasonCopyright()),
    "fake": ("🎭 Fake Account", InputReportReasonFake()),
    "illegal_drugs": ("💊 Illegal Drugs", InputReportReasonIllegalDrugs())
}

# Storage
user_clients = {}
report_data = {}
logger_group_invite_link = None

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
    """Parse Telegram message link"""
    # https://t.me/channel_name/123
    # https://t.me/c/1234567890/123
    patterns = [
        r't\.me/([^/]+)/(\d+)',  # Public: t.me/channel/msgid
        r't\.me/c/(\d+)/(\d+)'   # Private: t.me/c/chatid/msgid
    ]
    
    for pattern in patterns:
        match = re.search(pattern, link)
        if match:
            return match.groups()
    return None

# ==================== CHECK IF BOT IS ADMIN ====================
async def check_bot_admin_status():
    """Check if bot is admin and can create invite links"""
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
    """Wait up to 1 minute for bot to be made admin"""
    
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
    """Generate invite link for logger group"""
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
    
    print("=" * 60)
    print(f"🔗 Connecting {TOTAL_ACCOUNTS} accounts...")
    print("=" * 60)
    
    for acc_num, session_string in SESSION_STRINGS.items():
        try:
            print(f"📱 Connecting Account #{acc_num}...")
            
            client = Client(
                name=f":memory:",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                no_updates=True
            )
            
            await client.start()
            me = await client.get_me()
            print(f"✅ Account #{acc_num}: {me.first_name} (@{me.username or 'No username'})")
            
            user_clients[acc_num] = client
            
        except Exception as e:
            print(f"❌ Account #{acc_num} failed: {e}")
    
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
        
        await asyncio.sleep(0.5)
    
    print("=" * 60)
    print(f"✅ {joined_count}/{len(user_clients)} accounts joined successfully!")
    print("=" * 60)
    
    print("\n📢 Sending startup messages...")
    
    for acc_num, client in user_clients.items():
        try:
            await client.send_message(
                LOGGER_GROUP_ID,
                f"✅ **Assistant Started**\n\nAccount #{acc_num} is ready!"
            )
            print(f"✅ Account #{acc_num} sent startup message")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to send: {e}")
    
    print("=" * 60)
    print("✅ Logger group setup complete!")
    print("=" * 60 + "\n")

# ==================== START COMMAND ====================
@bot.on_message(filters.command("start") & filters.private)
@owner_only
async def start_command(client, message):
    active = len(user_clients)
    
    await message.reply_text(
        f"🔐 **Multi-Account Report Bot**\n\n"
        f"👑 Owner: {message.from_user.first_name}\n"
        f"📊 Total Accounts: {TOTAL_ACCOUNTS}\n"
        f"✅ Active Sessions: {active}\n\n"
        f"**Available Commands:**\n"
        f"• `/stats` - View session statistics\n"
        f"• `/check` - Test all accounts (use in logger group)\n"
        f"• `/report` - Report chat/channel/bot/message\n\n"
        f"**Quick Report:**\n"
        f"Reply to any message link, bot username, channel link with `/report`\n\n"
        f"⚡️ All accounts loaded from STRING sessions!"
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
    text += f"⚪️ Inactive Sessions: {inactive}\n\n"
    
    if user_clients:
        text += "**Active Accounts:**\n"
        for acc_num, cl in user_clients.items():
            try:
                me = await cl.get_me()
                text += f"• Account #{acc_num} - {me.first_name}\n"
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
        await message.reply_text(
            "❌ Logger group not configured!\n\n"
            "Please set LOGGER_GROUP_ID in .env file."
        )
        return
    
    if message.chat.id != LOGGER_GROUP_ID:
        await message.reply_text(
            "❌ This command only works in logger group!\n\n"
            f"Use this command in the logger group (Chat ID: `{LOGGER_GROUP_ID}`)."
        )
        return
    
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    
    status = await message.reply_text(f"🔍 Testing {len(user_clients)} accounts...")
    
    success = 0
    failed = 0
    
    for acc_num, cl in user_clients.items():
        try:
            await cl.send_message(
                message.chat.id,
                f"✅ **Account #{acc_num} - Working**"
            )
            success += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            await message.reply_text(f"❌ Account #{acc_num}: {str(e)[:40]}")
            failed += 1
    
    await status.edit_text(
        f"✅ **Check Complete!**\n\n"
        f"✅ Working: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(user_clients)}"
    )

# ==================== REPORT COMMAND ====================
@bot.on_message(filters.command("report") & filters.private)
@owner_only
async def report_command(client, message):
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    
    # Check if replying to a message
    if message.reply_to_message and message.reply_to_message.text:
        target = message.reply_to_message.text.strip()
        
        # Detect type
        if 't.me/' in target and '/' in target.split('t.me/')[-1]:
            # Message link
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
        
        # Check if bot username
        if target.startswith('@') or (not target.startswith('http') and not '/' in target):
            username = target.replace('@', '').strip()
            report_data[OWNER_ID] = {
                "step": "ask_reason",
                "type": "bot_or_channel",
                "target": username
            }
            await show_reason_keyboard(await message.reply_text(f"🤖 Detected: @{username}"))
            return
        
        # Channel/group link
        if 't.me/' in target:
            username = target.split('/')[-1].replace('@', '')
            report_data[OWNER_ID] = {
                "step": "ask_reason",
                "type": "channel",
                "target": username
            }
            await show_reason_keyboard(await message.reply_text(f"📢 Detected: Channel/Group"))
            return
    
    # Normal flow
    report_data[OWNER_ID] = {"step": "ask_type"}
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Public Chat/Channel", callback_data="type_public")],
        [InlineKeyboardButton("🔒 Private Chat/Channel", callback_data="type_private")]
    ])
    
    await message.reply_text(
        f"📝 **Report System**\n\n"
        f"Ready to report with {len(user_clients)} accounts.\n\n"
        "Is the target public or private?",
        reply_markup=keyboard
    )

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
            "• `@channel_name`\n"
            "• `channel_name`"
        )
    else:
        await callback.message.edit_text(
            "🔒 **Private Chat/Channel**\n\n"
            "Send the invite link:\n\n"
            "**Examples:**\n"
            "• `https://t.me/+AbCdEfGhIjKl`\n"
            "• `https://t.me/joinchat/AbCdEfGhIjKl`"
        )
    
    await callback.answer()

# ==================== REASON SELECTION ====================
async def show_reason_keyboard(msg):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Spam", callback_data="reason_spam")],
        [InlineKeyboardButton("⚔️ Violence", callback_data="reason_violence")],
        [InlineKeyboardButton("🔞 Pornography", callback_data="reason_pornography")],
        [InlineKeyboardButton("👶 Child Abuse", callback_data="reason_child_abuse")],
        [InlineKeyboardButton("©️ Copyright", callback_data="reason_copyright")],
        [InlineKeyboardButton("🎭 Fake", callback_data="reason_fake")],
        [InlineKeyboardButton("💊 Drugs", callback_data="reason_illegal_drugs")]
    ])
    
    await msg.edit_text(
        "⚠️ **Select Report Reason**\n\n"
        "Choose the appropriate reason:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("^reason_"))
@owner_only
async def select_reason(client, callback):
    reason_key = callback.data.split("_", 1)[1]
    
    if OWNER_ID not in report_data:
        await callback.answer("Session expired! Use /report", show_alert=True)
        return
    
    report_data[OWNER_ID]["reason"] = reason_key
    reason_name, _ = REPORT_REASONS[reason_key]
    
    await callback.message.edit_text(
        f"✅ Reason: {reason_name}\n\n"
        f"⏳ Processing report from {len(user_clients)} accounts...\n"
        f"Please wait..."
    )
    
    await callback.answer()
    await execute_report(client, callback.message)

# ==================== EXECUTE REPORT ====================
async def execute_report(client, message):
    data = report_data[OWNER_ID]
    reason_key = data["reason"]
    reason_name, reason_obj = REPORT_REASONS[reason_key]
    
    success = 0
    failed = 0
    results = []
    
    report_type = data.get("type")
    
    # Message report
    if report_type == "message":
        parsed = data["parsed"]
        chat_id, msg_id = parsed
        
        if chat_id.isdigit():  # Private chat
            chat_id = int(f"-100{chat_id}")
        
        for acc_num, ucl in user_clients.items():
            try:
                await ucl.invoke(
                    Report(
                        peer=await ucl.resolve_peer(chat_id),
                        id=[int(msg_id)],
                        reason=reason_obj,
                        message="Reported via bot"
                    )
                )
                results.append(f"✅ Account #{acc_num}")
                success += 1
            except Exception as e:
                results.append(f"❌ Account #{acc_num}: {str(e)[:30]}")
                failed += 1
            
            await asyncio.sleep(0.3)
    
    # Bot/Channel username report
    elif report_type == "bot_or_channel":
        username = data["target"]
        
        for acc_num, ucl in user_clients.items():
            try:
                target_entity = await ucl.get_users(username)
                
                await ucl.invoke(
                    ReportPeer(
                        peer=await ucl.resolve_peer(username),
                        reason=reason_obj,
                        message="Reported via bot"
                    )
                )
                results.append(f"✅ Account #{acc_num}")
                success += 1
            except Exception as e:
                error = str(e)
                if "PHONE_NOT" not in error:
                    results.append(f"❌ Account #{acc_num}: {error[:30]}")
                    failed += 1
            
            await asyncio.sleep(0.3)
    
    # Public channel/group
    elif report_type in ["public", "channel"]:
        chat_link = data.get("chat_link") or data.get("target")
        
        for acc_num, ucl in user_clients.items():
            try:
                chat = await ucl.get_chat(chat_link)
                await ucl.invoke(
                    ReportPeer(
                        peer=await ucl.resolve_peer(chat.id),
                        reason=reason_obj,
                        message="Reported via bot"
                    )
                )
                results.append(f"✅ Account #{acc_num}")
                success += 1
            except Exception as e:
                error = str(e)
                if "PHONE_NOT" not in error:
                    results.append(f"❌ Account #{acc_num}: {error[:30]}")
                    failed += 1
            
            await asyncio.sleep(0.3)
    
    # Private channel/group
    else:
        invite_link = data["invite_link"]
        
        await message.edit_text(f"📥 Joining with {len(user_clients)} accounts...")
        
        joined = []
        for acc_num, ucl in user_clients.items():
            try:
                await ucl.join_chat(invite_link)
                joined.append(acc_num)
            except UserAlreadyParticipant:
                joined.append(acc_num)
            except Exception as e:
                results.append(f"❌ Account #{acc_num} join failed")
                failed += 1
            
            await asyncio.sleep(0.5)
        
        if not joined:
            await message.edit_text("❌ All accounts failed to join!")
            del report_data[OWNER_ID]
            return
        
        await message.edit_text(
            f"✅ {len(joined)} accounts joined!\n\n"
            f"⚠️ Reporting..."
        )
        
        for acc_num in joined:
            ucl = user_clients[acc_num]
            try:
                chat = await ucl.get_chat(invite_link)
                await ucl.invoke(
                    ReportPeer(
                        peer=await ucl.resolve_peer(chat.id),
                        reason=reason_obj,
                        message="Reported via bot"
                    )
                )
                results.append(f"✅ Account #{acc_num}")
                success += 1
            except Exception as e:
                error = str(e)
                if "PHONE_NOT" not in error:
                    results.append(f"❌ Account #{acc_num}: {error[:30]}")
                    failed += 1
            
            await asyncio.sleep(0.3)
    
    # Show results
    result_text = (
        f"📊 **Report Complete!**\n\n"
        f"📝 Reason: {reason_name}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(user_clients)}\n\n"
        f"**Results:**\n"
    )
    
    for r in results[:15]:
        result_text += f"{r}\n"
    
    if len(results) > 15:
        result_text += f"\n... and {len(results)-15} more"
    
    await message.edit_text(result_text)
    del report_data[OWNER_ID]

# ==================== MESSAGE HANDLER ====================
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "stats", "check", "report"]))
@owner_only
async def handle_messages(client, message):
    if OWNER_ID not in report_data:
        return
    
    data = report_data[OWNER_ID]
    step = data["step"]
    
    if step == "ask_link":
        link = message.text.strip()
        
        if 't.me/' in link:
            username = link.split('/')[-1].replace('@', '')
        else:
            username = link.replace('@', '')
        
        report_data[OWNER_ID]["chat_link"] = username
        await show_reason_keyboard(await message.reply_text("Processing..."))
    
    elif step == "ask_invite":
        invite = message.text.strip()
        
        if 't.me/+' not in invite and 't.me/joinchat/' not in invite:
            await message.reply_text("❌ Invalid invite link format!")
            return
        
        report_data[OWNER_ID]["invite_link"] = invite
        await show_reason_keyboard(await message.reply_text("Processing..."))

# ==================== MAIN ====================
async def main():
    print("\n" + "=" * 60)
    print("🤖 MULTI-ACCOUNT REPORT BOT")
    print("=" * 60)
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"📢 Logger Group ID: {LOGGER_GROUP_ID or 'Not set'}")
    print(f"📊 Total Accounts: {TOTAL_ACCOUNTS}")
    print("=" * 60 + "\n")
    
    if not all([BOT_TOKEN, OWNER_ID, API_ID, API_HASH]):
        print("❌ Missing configuration in .env!")
        return
    
    if not LOGGER_GROUP_ID:
        print("❌ LOGGER_GROUP_ID not set in .env!")
        return
    
    if TOTAL_ACCOUNTS == 0:
        print("❌ No STRING sessions found in .env!")
        return
    
    await bot.start()
    bot.me = await bot.get_me()
    print(f"✅ Bot started: @{bot.me.username}\n")
    
    await connect_all_accounts()
    
    print("\n🎉 Bot is ready! Press Ctrl+C to stop.\n" + "=" * 60 + "\n")
    
    await idle()

async def stop_all():
    """Stop all clients gracefully"""
    print("\n🛑 Stopping all clients...")
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

async def idle():
    """Keep the bot running until interrupted"""
    stop_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await stop_event.wait()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user (Ctrl+C)")
    finally:
        loop.run_until_complete(stop_all())
        loop.close()
