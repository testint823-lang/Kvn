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
from dotenv import load_dotenv

load_dotenv()

# ==================== CONFIGURATION ====================
# Bot Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
LOGGER_GROUP_ID = int(os.getenv("LOGGER_GROUP_ID", "0"))

# API Credentials (for string sessions)
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Load all session strings from environment
def load_session_strings():
    """Load all STRING_1, STRING_2, etc. from .env"""
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

# Report reasons mapping
REPORT_REASONS = {
    "spam": ("🚫 Spam", InputReportReasonSpam()),
    "violence": ("⚔️ Violence", InputReportReasonViolence()),
    "pornography": ("🔞 Pornography/Nudity", InputReportReasonPornography()),
    "child_abuse": ("👶 Child Abuse", InputReportReasonChildAbuse()),
    "copyright": ("©️ Copyright", InputReportReasonCopyright()),
    "fake": ("🎭 Fake Account", InputReportReasonFake()),
    "illegal_drugs": ("💊 Illegal Drugs", InputReportReasonIllegalDrugs())
}

# ==================== STORAGE ====================
user_clients = {}  # {account_num: Client instance}
report_data = {}   # Temporary report data for owner

# ==================== BOT INSTANCE ====================
bot = Client("report_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ==================== OWNER CHECK DECORATOR ====================
def owner_only(func):
    """Decorator to restrict commands to owner only"""
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

# ==================== STARTUP - CONNECT ALL ACCOUNTS ====================
async def connect_all_accounts():
    """Connect all accounts from session strings"""
    print("=" * 60)
    print(f"🔗 Connecting {TOTAL_ACCOUNTS} accounts...")
    print("=" * 60)
    
    for acc_num, session_string in SESSION_STRINGS.items():
        try:
            print(f"📱 Connecting Account #{acc_num}...")
            
            # Create client from session string
            client = Client(
                name=f"account_{acc_num}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True
            )
            
            await client.start()
            
            # Get account info
            me = await client.get_me()
            print(f"✅ Account #{acc_num} connected: {me.first_name} (@{me.username or 'No username'})")
            
            # Store client
            user_clients[acc_num] = client
            
        except Exception as e:
            print(f"❌ Account #{acc_num} failed: {e}")
    
    print("=" * 60)
    print(f"✅ {len(user_clients)}/{TOTAL_ACCOUNTS} accounts connected successfully!")
    print("=" * 60)
    
    # Send startup messages to logger group
    if LOGGER_GROUP_ID and user_clients:
        await send_startup_messages()

# ==================== SEND STARTUP MESSAGES ====================
async def send_startup_messages():
    """Send 'Assistant Started' message from all connected accounts"""
    print("\n📢 Sending startup messages to logger group...")
    
    for acc_num, client in user_clients.items():
        try:
            await client.send_message(
                LOGGER_GROUP_ID,
                f"✅ **Assistant Started**\n\n"
                f"Account #{acc_num} is ready!"
            )
            print(f"✅ Account #{acc_num} sent startup message")
        except Exception as e:
            print(f"❌ Account #{acc_num} failed to send: {e}")
    
    print("=" * 60)

# ==================== START COMMAND ====================
@bot.on_message(filters.command("start") & filters.private)
@owner_only
async def start_command(client, message):
    """Main menu for owner"""
    active = len(user_clients)
    
    await message.reply_text(
        f"🔐 **Multi-Account Report Bot**\n\n"
        f"👑 Owner: {message.from_user.first_name}\n"
        f"📊 Total Accounts: {TOTAL_ACCOUNTS}\n"
        f"✅ Active Sessions: {active}\n\n"
        f"**Available Commands:**\n"
        f"• `/stats` - View session statistics\n"
        f"• `/check` - Test all accounts (in logger group)\n"
        f"• `/report` - Report chat/channel/message\n\n"
        f"⚡️ All accounts loaded from STRING sessions!"
    )

# ==================== STATS COMMAND ====================
@bot.on_message(filters.command("stats") & filters.private)
@owner_only
async def stats_command(client, message):
    """Show detailed statistics"""
    active = len(user_clients)
    inactive = TOTAL_ACCOUNTS - active
    
    text = "📊 **Session Statistics**\n\n"
    text += f"📦 Total Accounts: {TOTAL_ACCOUNTS}\n"
    text += f"✅ Active Sessions: {active}\n"
    text += f"⚪️ Inactive Sessions: {inactive}\n\n"
    
    if user_clients:
        text += "**Active Accounts:**\n"
        for acc_num, client_instance in user_clients.items():
            try:
                me = await client_instance.get_me()
                text += f"• Account #{acc_num} - {me.first_name}\n"
            except:
                text += f"• Account #{acc_num} - Unknown\n"
    
    if inactive > 0:
        text += f"\n**Note:** {inactive} account(s) failed to connect.\n"
        text += "Check your STRING values in .env file."
    
    await message.reply_text(text)

# ==================== CHECK COMMAND ====================
@bot.on_message(filters.command("check"))
@owner_only
async def check_command(client, message):
    """Test all accounts by sending messages to logger group"""
    # Must be used in logger group
    if message.chat.id != LOGGER_GROUP_ID:
        await message.reply_text(
            "❌ This command only works in the logger group!\n\n"
            f"Logger Group ID: `{LOGGER_GROUP_ID}`"
        )
        return
    
    if not user_clients:
        await message.reply_text("❌ No active sessions to test!")
        return
    
    status_msg = await message.reply_text(
        f"🔍 **Testing {len(user_clients)} accounts...**\n"
        f"Please wait..."
    )
    
    success = 0
    failed = 0
    
    for acc_num, client_instance in user_clients.items():
        try:
            await client_instance.send_message(
                LOGGER_GROUP_ID,
                f"✅ **Account #{acc_num} - Done**"
            )
            success += 1
            await asyncio.sleep(0.5)  # Small delay
        except Exception as e:
            await message.reply_text(f"❌ Account #{acc_num} failed: {str(e)[:50]}")
            failed += 1
    
    await status_msg.edit_text(
        f"✅ **Check Complete!**\n\n"
        f"✅ Working: {success}\n"
        f"❌ Failed: {failed}\n"
        f"📊 Total: {len(user_clients)}"
    )

# ==================== REPORT COMMAND ====================
@bot.on_message(filters.command("report") & filters.private)
@owner_only
async def report_command(client, message):
    """Start report process"""
    if not user_clients:
        await message.reply_text("❌ No active sessions!\n\nCheck your STRING configurations.")
        return
    
    report_data[OWNER_ID] = {"step": "ask_type"}
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Public Chat/Channel", callback_data="type_public")],
        [InlineKeyboardButton("🔒 Private Chat/Channel", callback_data="type_private")]
    ])
    
    await message.reply_text(
        "📝 **Report System**\n\n"
        f"Ready to report with {len(user_clients)} accounts.\n\n"
        "Is the target public or private?",
        reply_markup=keyboard
    )

# ==================== TYPE SELECTION ====================
@bot.on_callback_query(filters.regex("^type_"))
@owner_only
async def select_type(client, callback):
    """Handle public/private selection"""
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
async def show_reason_keyboard(message_to_edit):
    """Show report reason selection keyboard"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Spam", callback_data="reason_spam")],
        [InlineKeyboardButton("⚔️ Violence", callback_data="reason_violence")],
        [InlineKeyboardButton("🔞 Pornography/Nudity", callback_data="reason_pornography")],
        [InlineKeyboardButton("👶 Child Abuse", callback_data="reason_child_abuse")],
        [InlineKeyboardButton("©️ Copyright", callback_data="reason_copyright")],
        [InlineKeyboardButton("🎭 Fake Account", callback_data="reason_fake")],
        [InlineKeyboardButton("💊 Illegal Drugs", callback_data="reason_illegal_drugs")]
    ])
    
    await message_to_edit.edit_text(
        "⚠️ **Select Report Reason**\n\n"
        "Choose the appropriate reason for reporting:",
        reply_markup=keyboard
    )

@bot.on_callback_query(filters.regex("^reason_"))
@owner_only
async def select_reason(client, callback):
    """Handle reason selection and execute report"""
    reason_key = callback.data.split("_", 1)[1]
    
    if OWNER_ID not in report_data:
        await callback.answer("Session expired! Use /report again", show_alert=True)
        return
    
    report_data[OWNER_ID]["reason"] = reason_key
    reason_name, _ = REPORT_REASONS[reason_key]
    
    await callback.message.edit_text(
        f"✅ Reason: {reason_name}\n\n"
        f"⏳ **Processing report from {len(user_clients)} accounts...**\n"
        f"Please wait..."
    )
    
    await callback.answer()
    
    # Execute the actual report
    await execute_report(client, callback.message)

# ==================== EXECUTE REPORT ====================
async def execute_report(client, message):
    """Execute the report on all accounts"""
    data = report_data[OWNER_ID]
    reason_key = data["reason"]
    reason_name, reason_obj = REPORT_REASONS[reason_key]
    
    success = 0
    failed = 0
    results = []
    
    if data["type"] == "public":
        # PUBLIC CHAT - Direct report without joining
        chat_link = data["chat_link"]
        
        for acc_num, user_client in user_clients.items():
            try:
                # Get chat
                chat = await user_client.get_chat(chat_link)
                
                # Report
                await user_client.invoke(
                    ReportPeer(
                        peer=await user_client.resolve_peer(chat.id),
                        reason=reason_obj,
                        message="Reported via bot"
                    )
                )
                
                results.append(f"✅ Account #{acc_num}")
                success += 1
                
            except Exception as e:
                results.append(f"❌ Account #{acc_num}: {str(e)[:30]}")
                failed += 1
            
            await asyncio.sleep(0.3)  # Small delay
    
    else:
        # PRIVATE CHAT - Join first, then report
        invite_link = data["invite_link"]
        
        # Step 1: Join all accounts
        await message.edit_text(
            f"📥 **Joining with {len(user_clients)} accounts...**\n"
            f"Please wait..."
        )
        
        joined_accounts = []
        
        for acc_num, user_client in user_clients.items():
            try:
                await user_client.join_chat(invite_link)
                joined_accounts.append(acc_num)
            except UserAlreadyParticipant:
                joined_accounts.append(acc_num)
            except Exception as e:
                results.append(f"❌ Account #{acc_num} join failed")
                failed += 1
            
            await asyncio.sleep(0.5)
        
        if not joined_accounts:
            await message.edit_text(
                "❌ **Join Failed!**\n\n"
                "Could not join with any account.\n"
                "Check the invite link."
            )
            del report_data[OWNER_ID]
            return
        
        # Step 2: Report
        await message.edit_text(
            f"✅ Joined with {len(joined_accounts)} accounts\n\n"
            f"⚠️ **Reporting...**\n"
            f"Please wait..."
        )
        
        # Check if specific message needs to be reported
        if "message_link" in data and data["message_link"]:
            # Report specific message
            msg_link = data["message_link"]
            
            for acc_num in joined_accounts:
                user_client = user_clients[acc_num]
                try:
                    # Get chat
                    chat = await user_client.get_chat(invite_link)
                    
                    # Report (Pyrogram doesn't have direct message report, so reporting chat)
                    await user_client.invoke(
                        ReportPeer(
                            peer=await user_client.resolve_peer(chat.id),
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
            # Report entire chat
            for acc_num in joined_accounts:
                user_client = user_clients[acc_num]
                try:
                    chat = await user_client.get_chat(invite_link)
                    
                    await user_client.invoke(
                        ReportPeer(
                            peer=await user_client.resolve_peer(chat.id),
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
    )
    
    # Show first 15 results
    if results:
        result_text += "**Results:**\n"
        for result in results[:15]:
            result_text += f"{result}\n"
        
        if len(results) > 15:
            result_text += f"\n_... and {len(results) - 15} more_"
    
    await message.edit_text(result_text)
    
    # Clear report data
    del report_data[OWNER_ID]

# ==================== MESSAGE HANDLER FOR REPORT FLOW ====================
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "stats", "check", "report"]))
@owner_only
async def handle_report_messages(client, message):
    """Handle text messages during report flow"""
    if OWNER_ID not in report_data:
        return
    
    data = report_data[OWNER_ID]
    step = data["step"]
    
    if step == "ask_link":
        # Public chat link received
        chat_link = message.text.strip()
        
        # Extract username
        if 't.me/' in chat_link:
            username = chat_link.split('/')[-1].replace('@', '')
        else:
            username = chat_link.replace('@', '')
        
        report_data[OWNER_ID]["chat_link"] = username
        report_data[OWNER_ID]["step"] = "done"
        
        # Show reason selection
        await show_reason_keyboard(await message.reply_text("Processing..."))
    
    elif step == "ask_invite":
        # Private invite link received
        invite_link = message.text.strip()
        
        if 't.me/+' not in invite_link and 't.me/joinchat/' not in invite_link:
            await message.reply_text(
                "❌ Invalid invite link format!\n\n"
                "Expected format:\n"
                "• `https://t.me/+AbCdEfGh`\n"
                "• `https://t.me/joinchat/AbCdEfGh`"
            )
            return
        
        report_data[OWNER_ID]["invite_link"] = invite_link
        report_data[OWNER_ID]["step"] = "ask_message"
        
        await message.reply_text(
            "🔗 **Invite link saved!**\n\n"
            "Do you want to report a specific message?\n\n"
            "• Send message link to report specific message\n"
            "• Type `skip` to report the entire chat"
        )
    
    elif step == "ask_message":
        # Optional message link
        text = message.text.strip()
        
        if text.lower() == "skip":
            report_data[OWNER_ID]["message_link"] = None
        else:
            report_data[OWNER_ID]["message_link"] = text
        
        report_data[OWNER_ID]["step"] = "done"
        
        # Show reason selection
        await show_reason_keyboard(await message.reply_text("Processing..."))

# ==================== MAIN FUNCTION ====================
async def main():
    """Main function to start the bot"""
    print("\n" + "=" * 60)
    print("🤖 MULTI-ACCOUNT REPORT BOT")
    print("=" * 60)
    print(f"👑 Owner ID: {OWNER_ID}")
    print(f"📢 Logger Group: {LOGGER_GROUP_ID}")
    print(f"📊 Total Accounts: {TOTAL_ACCOUNTS}")
    print("=" * 60 + "\n")
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in .env!")
        return
    
    if not OWNER_ID:
        print("❌ OWNER_ID not found in .env!")
        return
    
    if TOTAL_ACCOUNTS == 0:
        print("❌ No STRING sessions found in .env!")
        print("Add STRING_1, STRING_2, etc. to your .env file")
        return
    
    # Start bot
    await bot.start()
    bot_info = await bot.get_me()
    print(f"✅ Bot started: @{bot_info.username}\n")
    
    # Connect all user accounts
    await connect_all_accounts()
    
    print("\n🎉 Bot is ready! Press Ctrl+C to stop.\n")
    print("=" * 60 + "\n")
    
    # Keep running
    await asyncio.Event().wait()

# ==================== CLEANUP ON EXIT ====================
async def cleanup():
    """Stop all clients gracefully"""
    print("\n🛑 Stopping all clients...")
    for acc_num, client_instance in user_clients.items():
        try:
            await client_instance.stop()
            print(f"✅ Account #{acc_num} stopped")
        except:
            pass
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
