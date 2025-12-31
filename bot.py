

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, BadRequest, UserAlreadyParticipant
from pyrogram.raw.functions.account import ReportPeer
from pyrogram.raw.types import (
    InputReportReasonSpam, InputReportReasonViolence, 
    InputReportReasonPornography, InputReportReasonChildAbuse,
    InputReportReasonCopyright, InputReportReasonFake, InputReportReasonIllegalDrugs
)
import os
import asyncio
import shutil
from dotenv import load_dotenv

load_dotenv()

# ==================== CLEAN OLD SESSIONS ====================
# Remove any old session files that might cause conflicts
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

# Load all session strings
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

user_clients = {}
report_data = {}

# Bot instance
bot = Client(
    "report_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True  # Important: Don't save bot session
)

# Owner check
def owner_only(func):
    async def wrapper(client, update):
        user_id = update.from_user.id
        if user_id != OWNER_ID:
            if isinstance(update, Message):
                await update.reply_text("❌ Owner only!")
            else:
                await update.answer("❌ Owner only!", show_alert=True)
            return
        return await func(client, update)
    return wrapper

# Connect all accounts
async def connect_all_accounts():
    print("=" * 60)
    print(f"🔗 Connecting {TOTAL_ACCOUNTS} accounts...")
    print("=" * 60)
    
    for acc_num, session_string in SESSION_STRINGS.items():
        try:
            print(f"📱 Connecting Account #{acc_num}...")
            
            # Create client with in_memory to avoid database issues
            client = Client(
                name=f":memory:",  # Use memory instead of file
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                no_updates=True  # Disable updates for faster connection
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
        await send_startup_messages()

async def send_startup_messages():
    print("\n📢 Sending startup messages...")
    
    for acc_num, client in user_clients.items():
        try:
            await client.send_message(
                LOGGER_GROUP_ID,
                f"✅ **Assistant Started**\n\nAccount #{acc_num} is ready!"
            )
            print(f"✅ Account #{acc_num} sent message")
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"❌ Account #{acc_num} failed: {e}")
    
    print("=" * 60)

@bot.on_message(filters.command("start") & filters.private)
@owner_only
async def start_command(client, message):
    active = len(user_clients)
    
    await message.reply_text(
        f"🔐 **Multi-Account Report Bot**\n\n"
        f"👑 Owner: {message.from_user.first_name}\n"
        f"📊 Total: {TOTAL_ACCOUNTS}\n"
        f"✅ Active: {active}\n\n"
        f"**Commands:**\n"
        f"• `/stats` - Statistics\n"
        f"• `/check` - Test accounts\n"
        f"• `/report` - Report system"
    )

@bot.on_message(filters.command("stats") & filters.private)
@owner_only
async def stats_command(client, message):
    active = len(user_clients)
    inactive = TOTAL_ACCOUNTS - active
    
    text = f"📊 **Statistics**\n\n"
    text += f"📦 Total: {TOTAL_ACCOUNTS}\n"
    text += f"✅ Active: {active}\n"
    text += f"⚪️ Inactive: {inactive}\n\n"
    
    if user_clients:
        text += "**Active Accounts:**\n"
        for acc_num, cl in user_clients.items():
            try:
                me = await cl.get_me()
                text += f"• #{acc_num} - {me.first_name}\n"
            except:
                text += f"• #{acc_num} - Error\n"
    
    await message.reply_text(text)

@bot.on_message(filters.command("check"))
@owner_only
async def check_command(client, message):
    if message.chat.id != LOGGER_GROUP_ID:
        await message.reply_text(f"❌ Use in logger group!\nID: `{LOGGER_GROUP_ID}`")
        return
    
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    
    status = await message.reply_text(f"🔍 Testing {len(user_clients)} accounts...")
    
    success = 0
    failed = 0
    
    for acc_num, cl in user_clients.items():
        try:
            await cl.send_message(LOGGER_GROUP_ID, f"✅ Account #{acc_num} - Done")
            success += 1
            await asyncio.sleep(0.5)
        except Exception as e:
            await message.reply_text(f"❌ #{acc_num}: {str(e)[:40]}")
            failed += 1
    
    await status.edit_text(
        f"✅ **Complete!**\n\n"
        f"✅ Working: {success}\n"
        f"❌ Failed: {failed}"
    )

@bot.on_message(filters.command("report") & filters.private)
@owner_only
async def report_command(client, message):
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return
    
    report_data[OWNER_ID] = {"step": "ask_type"}
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Public", callback_data="type_public")],
        [InlineKeyboardButton("🔒 Private", callback_data="type_private")]
    ])
    
    await message.reply_text(
        f"📝 **Report System**\n\n"
        f"Ready with {len(user_clients)} accounts.\n\n"
        "Public or Private?",
        reply_markup=keyboard
    )

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
            "📢 **Public Chat**\n\n"
            "Send link or username:\n"
            "• `@channel`\n"
            "• `https://t.me/channel`"
        )
    else:
        await callback.message.edit_text(
            "🔒 **Private Chat**\n\n"
            "Send invite link:\n"
            "• `https://t.me/+AbCdEfGh`"
        )
    
    await callback.answer()

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
    
    await msg.edit_text("⚠️ **Select Reason:**", reply_markup=keyboard)

@bot.on_callback_query(filters.regex("^reason_"))
@owner_only
async def select_reason(client, callback):
    reason_key = callback.data.split("_", 1)[1]
    
    if OWNER_ID not in report_data:
        await callback.answer("Expired! Use /report", show_alert=True)
        return
    
    report_data[OWNER_ID]["reason"] = reason_key
    reason_name, _ = REPORT_REASONS[reason_key]
    
    await callback.message.edit_text(
        f"✅ {reason_name}\n\n⏳ Processing {len(user_clients)} accounts..."
    )
    
    await callback.answer()
    await execute_report(client, callback.message)

async def execute_report(client, message):
    data = report_data[OWNER_ID]
    reason_key = data["reason"]
    reason_name, reason_obj = REPORT_REASONS[reason_key]
    
    success = 0
    failed = 0
    results = []
    
    if data["type"] == "public":
        chat_link = data["chat_link"]
        
        for acc_num, ucl in user_clients.items():
            try:
                chat = await ucl.get_chat(chat_link)
                await ucl.invoke(
                    ReportPeer(
                        peer=await ucl.resolve_peer(chat.id),
                        reason=reason_obj,
                        message="Report"
                    )
                )
                results.append(f"✅ #{acc_num}")
                success += 1
            except Exception as e:
                results.append(f"❌ #{acc_num}")
                failed += 1
            
            await asyncio.sleep(0.3)
    
    else:
        invite_link = data["invite_link"]
        
        await message.edit_text(f"📥 Joining {len(user_clients)} accounts...")
        
        joined = []
        for acc_num, ucl in user_clients.items():
            try:
                await ucl.join_chat(invite_link)
                joined.append(acc_num)
            except UserAlreadyParticipant:
                joined.append(acc_num)
            except:
                failed += 1
            await asyncio.sleep(0.5)
        
        if not joined:
            await message.edit_text("❌ Join failed!")
            del report_data[OWNER_ID]
            return
        
        await message.edit_text(f"✅ Joined! Reporting...")
        
        for acc_num in joined:
            ucl = user_clients[acc_num]
            try:
                chat = await ucl.get_chat(invite_link)
                await ucl.invoke(
                    ReportPeer(
                        peer=await ucl.resolve_peer(chat.id),
                        reason=reason_obj,
                        message="Report"
                    )
                )
                results.append(f"✅ #{acc_num}")
                success += 1
            except:
                results.append(f"❌ #{acc_num}")
                failed += 1
            await asyncio.sleep(0.3)
    
    result_text = (
        f"📊 **Complete!**\n\n"
        f"📝 {reason_name}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}\n\n"
    )
    
    for r in results[:15]:
        result_text += f"{r}\n"
    
    if len(results) > 15:
        result_text += f"\n... +{len(results)-15} more"
    
    await message.edit_text(result_text)
    del report_data[OWNER_ID]

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
        await show_reason_keyboard(await message.reply_text("..."))
    
    elif step == "ask_invite":
        invite = message.text.strip()
        if 't.me/+' not in invite and 't.me/joinchat/' not in invite:
            await message.reply_text("❌ Invalid invite link!")
            return
        
        report_data[OWNER_ID]["invite_link"] = invite
        await show_reason_keyboard(await message.reply_text("..."))

async def main():
    print("\n" + "=" * 60)
    print("🤖 MULTI-ACCOUNT REPORT BOT")
    print("=" * 60)
    print(f"👑 Owner: {OWNER_ID}")
    print(f"📢 Logger: {LOGGER_GROUP_ID}")
    print(f"📊 Accounts: {TOTAL_ACCOUNTS}")
    print("=" * 60 + "\n")
    
    if not all([BOT_TOKEN, OWNER_ID, API_ID, API_HASH]):
        print("❌ Missing config in .env!")
        return
    
    if TOTAL_ACCOUNTS == 0:
        print("❌ No STRING sessions!")
        return
    
    await bot.start()
    bot_info = await bot.get_me()
    print(f"✅ Bot: @{bot_info.username}\n")
    
    await connect_all_accounts()
    
    print("\n🎉 Ready! Ctrl+C to stop\n" + "=" * 60 + "\n")
    
    await asyncio.Event().wait()

async def cleanup():
    print("\n🛑 Stopping...")
    for acc_num, cl in user_clients.items():
        try:
            await cl.stop()
        except:
            pass
    print("👋 Bye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        asyncio.run(cleanup())
    except Exception as e:
        print(f"\n❌ Error: {e}")
