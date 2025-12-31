from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, BadRequest, UserAlreadyParticipant, PeerIdInvalid
from pyrogram.raw.functions.account import ReportPeer
from pyrogram.raw.types import (
    InputReportReasonSpam, InputReportReasonViolence, 
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake, InputReportReasonIllegalDrugs
)
import os
import asyncio
from dotenv import load_dotenv

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
LOGGER_GROUP_LINK = os.getenv("LOGGER_GROUP_LINK")  # Invite link instead of ID
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
logger_chat_id = None  # Will be set after joining

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

# ==================== CONNECT ACCOUNTS ====================
async def connect_all_accounts():
    global logger_chat_id
    
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
    
    # Join logger group and send startup messages
    if LOGGER_GROUP_LINK and user_clients:
        await join_logger_and_send_messages()

# ==================== JOIN LOGGER GROUP ====================
async def join_logger_and_send_messages():
    global logger_chat_id
    
    print("\n📥 Joining logger group...")
    
    # First check if bot is in the group
    try:
        chat = await bot.get_chat(LOGGER_GROUP_LINK)
        logger_chat_id = chat.id
        print(f"✅ Bot already in group: {chat.title}")
    except:
        print("❌ Bot is not in logger group!")
        print("⚠️  Please add bot to logger group and make it admin!")
        return
    
    # Join with all accounts
    for acc_num, client in user_clients.items():
        try:
            await client.join_chat(LOGGER_GROUP_LINK)
            print(f"✅ Account #{acc_num} joined logger group")
        except UserAlreadyParticipant:
            print(f"✅ Account #{acc_num} already in group")
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to join: {e}")
        
        await asyncio.sleep(0.5)
    
    # Send startup messages
    print("\n📢 Sending startup messages...")
    
    for acc_num, client in user_clients.items():
        try:
            await client.send_message(
                logger_chat_id,
                f"✅ **Assistant Started**\n\nAccount #{acc_num} is ready!"
            )
            print(f"✅ Account #{acc_num} sent startup message")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to send: {e}")
    
    print("=" * 60)

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
        f"• `/check` - Test all accounts\n"
        f"• `/report` - Report chat/channel\n\n"
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
    # Check if used in logger group
    if logger_chat_id and message.chat.id != logger_chat_id:
        await message.reply_text(
            "❌ This command only works in logger group!\n\n"
            "Use this command in the logger group where bot is admin."
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
                f"✅ **Account #{acc_num} - Done**"
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
    
    if data["type"] == "public":
        # Public - direct report
        chat_link = data["chat_link"]
        
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
                results.append(f"❌ Account #{acc_num}: {str(e)[:30]}")
                failed += 1
            
            await asyncio.sleep(0.3)
    
    else:
        # Private - join first
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
                results.append(f"❌ Account #{acc_num}: {str(e)[:30]}")
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
    print(f"📢 Logger Link: {LOGGER_GROUP_LINK or 'Not set'}")
    print(f"📊 Total Accounts: {TOTAL_ACCOUNTS}")
    print("=" * 60 + "\n")
    
    if not all([BOT_TOKEN, OWNER_ID, API_ID, API_HASH]):
        print("❌ Missing configuration in .env!")
        return
    
    if TOTAL_ACCOUNTS == 0:
        print("❌ No STRING sessions found in .env!")
        return
    
    # Start bot first
    await bot.start()
    bot_info = await bot.get_me()
    print(f"✅ Bot started: @{bot_info.username}\n")
    
    # Connect all accounts
    await connect_all_accounts()
    
    print("\n🎉 Bot is ready! Press Ctrl+C to stop.\n" + "=" * 60 + "\n")
    
    # Keep running
    await asyncio.Event().wait()

async def cleanup():
    print("\n🛑 Stopping all clients...")
    for acc_num, cl in user_clients.items():
        try:
            await cl.stop()
            print(f"✅ Account #{acc_num} stopped")
        except:
            pass
    await bot.stop()
    print("👋 Goodbye!")

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user (Ctrl+C)")
        asyncio.run(cleanup())
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
