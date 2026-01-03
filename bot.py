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
MAX_REPORTS = int(os.getenv("MAX_REPORTS", "10"))  # Default 10 reports per account

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
    "illegal_drugs": ("💊 Illegal Drugs", InputReportReasonIllegalDrugs()),
    "other": ("❓ Other", InputReportReasonOther())
}

# Storage
user_clients = {}
report_data = {}
logger_group_invite_link = None
assistant_status = {}  # Track assistant status

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
    patterns = [
        r't\.me/([^/]+)/(\d+)',  # Public: t.me/channel/msgid
        r't\.me/c/(-?\d+)/(\d+)'   # Private: t.me/c/chatid/msgid
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
        f"🔐 **Multi-Account Report Bot**\n\n"  
        f"👑 Owner: {message.from_user.first_name}\n"  
        f"📊 Total Accounts: {TOTAL_ACCOUNTS}\n"  
        f"✅ Active Sessions: {active}\n"  
        f"🔁 Reports per Account: {MAX_REPORTS}\n\n"  
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
    
    status = await message.reply_text(f"🔍 Testing {len(user_clients)} accounts...\nPlease wait...")  
    
    success = 0  
    failed = 0
    results = []
    
    # Send test messages from all accounts
    for acc_num, cl in user_clients.items():  
        try:  
            sent_msg = await cl.send_message(  
                message.chat.id,  
                f"✅ **Account #{acc_num} - Working**\n\nUser ID: `{assistant_status.get(acc_num, {}).get('id', 'N/A')}`"  
            )
            
            # Try to delete the test message after 5 seconds
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
        
        await asyncio.sleep(2)  # Increased delay between checks
    
    result_text = f"✅ **Check Complete!**\n\n"  
    result_text += f"✅ Working: {success}\n"  
    result_text += f"❌ Failed: {failed}\n"  
    result_text += f"📊 Total: {len(user_clients)}\n\n"
    
    if results:
        result_text += "\n".join(results[:15])
        if len(results) > 15:
            result_text += f"\n\n... and {len(results) - 15} more"
    
    await status.edit_text(result_text)

# ==================== REPORT COMMAND (PRIVATE CHAT) ====================

@bot.on_message(filters.command("report") & filters.private)
@owner_only
async def report_command(client, message):
    if not user_clients:
        await message.reply_text("❌ No active sessions!")
        return

    # Check if replying to a message  
    if message.reply_to_message and message.reply_to_message.text:  
        target = message.reply_to_message.text.strip()  
        
        # Clean the target (remove any whitespace, newlines)
        target = target.strip()
        
        print(f"DEBUG: Target received: {target}")
        
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
                print(f"DEBUG: Detected as message link")
                await show_reason_keyboard(await message.reply_text("📨 Detected: Message Link"))  
                return  
        
        # Check if channel/group link
        if 't.me/' in target:
            # Try to extract username from link
            if 't.me/joinchat/' in target or 't.me/+' in target:
                # It's an invite link
                report_data[OWNER_ID] = {  
                    "step": "ask_reason",  
                    "type": "private_chat",  
                    "target": target  
                }  
                print(f"DEBUG: Detected as private chat invite")
                await show_reason_keyboard(await message.reply_text("🔒 Detected: Private Chat/Channel"))  
                return
            else:
                # Public channel/group
                # Extract username from t.me/username
                parts = target.split('t.me/')
                if len(parts) > 1:
                    username = parts[-1].split('/')[0].replace('@', '').strip()
                    report_data[OWNER_ID] = {  
                        "step": "ask_reason",  
                        "type": "public_chat",  
                        "target": username  
                    }  
                    print(f"DEBUG: Detected as public chat: @{username}")
                    await show_reason_keyboard(await message.reply_text(f"📢 Detected: @{username}"))  
                    return
        
        # Check if bot username (starts with @ or just text)
        if target.startswith('@') or (not target.startswith('http') and not '/' in target and not 't.me' in target):
            username = target.replace('@', '').strip()
            report_data[OWNER_ID] = {  
                "step": "ask_reason",  
                "type": "public_chat",  # Changed from bot_or_channel to public_chat
                "target": username  
            }  
            print(f"DEBUG: Detected as username: @{username}")
            await show_reason_keyboard(await message.reply_text(f"🤖 Detected: @{username}"))  
            return  
    
    # Normal flow - no reply, ask for type
    report_data[OWNER_ID] = {"step": "ask_type"}  
    
    keyboard = InlineKeyboardMarkup([  
        [InlineKeyboardButton("📢 Public Chat/Channel", callback_data="type_public")],  
        [InlineKeyboardButton("🔒 Private Chat/Channel", callback_data="type_private")]  
    ])  
    
    await message.reply_text(  
        f"📝 **Report System**\n\n"  
        f"Ready to report with {len(user_clients)} accounts.\n"  
        f"Each account will send {MAX_REPORTS} report(s).\n\n"  
        "Is the target public or private?",  
        reply_markup=keyboard  
    )

# ==================== REPORT IN LOGGER GROUP (WITH VERIFICATION) ====================

@bot.on_message(filters.command("report") & filters.group)
@owner_only
async def report_in_logger_group(client, message):
    """Handle /report command in logger group with verification step"""
    
    # Check if this is the logger group
    if message.chat.id != LOGGER_GROUP_ID:
        return
    
    # Check if replying to a message with a link
    if not message.reply_to_message or not message.reply_to_message.text:
        await message.reply_text(
            "❌ Please reply to a message link with /report command!\n\n"
            "Example: Reply to a message like `t.me/channelname/123`"
        )
        return
    
    target = message.reply_to_message.text.strip()
    print(f"DEBUG: Target in logger group: {target}")
    
    # Parse the message link
    parsed = parse_message_link(target)
    if not parsed:
        await message.reply_text(
            "❌ Invalid message link format!\n\n"
            "Please provide a valid Telegram message link like:\n"
            "• `t.me/channelname/123`\n"
            "• `t.me/c/chatid/123`"
        )
        return
    
    chat_identifier, msg_id = parsed
    print(f"DEBUG: Parsed - Chat: {chat_identifier}, Msg ID: {msg_id}")
    
    # Store report data with verification flag
    report_data[OWNER_ID] = {
        "step": "verification",
        "type": "message",
        "target": target,
        "parsed": parsed,
        "message_id": message.id,  # Store the command message ID for later
        "chat_id": message.chat.id
    }
    
    # Step 1: Pick one assistant account to test access
    if not user_clients:
        await message.reply_text("❌ No active assistant accounts!")
        return
    
    # Pick the first working assistant
    test_acc_num = list(user_clients.keys())[0]
    test_client = user_clients[test_acc_num]
    
    status_msg = await message.reply_text(
        f"🔍 **Verification Step 1/2**\n\n"
        f"Testing access with Assistant #{test_acc_num}...\n"
        f"Target: `{target}`"
    )
    
    try:
        # Resolve chat identifier to numeric ID
        if not chat_identifier.startswith('-100') and not chat_identifier.startswith('-'):
            # It's a username, get the chat info
            chat = await test_client.get_chat(chat_identifier)
            chat_id = chat.id
            chat_title = chat.title
        else:
            # Already a numeric ID
            chat_id = int(chat_identifier)
            chat = await test_client.get_chat(chat_id)
            chat_title = chat.title
            
        print(f"DEBUG: Resolved to Chat ID: {chat_id}, Title: {chat_title}")
        
        # Try to get the specific message
        try:
            msg = await test_client.get_messages(chat_id, int(msg_id))
            
            # Forward the message to logger group for verification
            forwarded_msg = await test_client.forward_messages(
                LOGGER_GROUP_ID,
                chat_id,
                int(msg_id)
            )
            
            # Update status
            await status_msg.edit_text(
                f"✅ **Verification Step 1/2 - SUCCESS**\n\n"
                f"Assistant #{test_acc_num} successfully accessed the message!\n"
                f"**Channel:** {chat_title}\n"
                f"**Message ID:** {msg_id}\n\n"
                f"📨 Message forwarded above for verification."
            )
            
            # Store the forwarded message ID for context
            report_data[OWNER_ID]["forwarded_msg_id"] = forwarded_msg.id
            report_data[OWNER_ID]["chat_id_resolved"] = chat_id
            report_data[OWNER_ID]["chat_title"] = chat_title
            report_data[OWNER_ID]["test_acc_num"] = test_acc_num
            
            # Step 2: Ask for confirmation with buttons
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ CONFIRM - Send Reports", callback_data=f"confirm_report_{chat_id}_{msg_id}")],
                [InlineKeyboardButton("❌ CANCEL", callback_data="cancel_report")]
            ])
            
            await message.reply_text(
                f"⚠️ **Verification Step 2/2 - CONFIRMATION REQUIRED**\n\n"
                f"**Target Confirmed:**\n"
                f"• Channel: {chat_title}\n"
                f"• Message ID: {msg_id}\n"
                f"• Link: `{target}`\n\n"
                f"**Will Report As:** Child Abuse\n"
                f"**Accounts Ready:** {len(user_clients)}\n"
                f"**Reports per Account:** {MAX_REPORTS}\n"
                f"**Total Reports:** {len(user_clients) * MAX_REPORTS}\n\n"
                f"Click CONFIRM to proceed with mass reporting:",
                reply_markup=keyboard
            )
            
        except Exception as e:
            await status_msg.edit_text(
                f"❌ **Verification FAILED - Cannot Access Message**\n\n"
                f"Assistant #{test_acc_num} could not access the specific message.\n\n"
                f"**Error:** `{str(e)[:100]}`\n\n"
                f"Possible reasons:\n"
                f"• Message doesn't exist\n"
                f"• Assistant is blocked from channel\n"
                f"• Message was deleted\n"
                f"• Private channel access needed"
            )
            
    except Exception as e:
        await status_msg.edit_text(
            f"❌ **Verification FAILED - Cannot Access Channel**\n\n"
            f"Assistant #{test_acc_num} could not access the channel.\n\n"
            f"**Error:** `{str(e)[:100]}`\n\n"
            f"Possible reasons:\n"
            f"• Channel is private (need invite)\n"
            f"• Channel doesn't exist\n"
            f"• Assistant is blocked"
        )

# ==================== HANDLE USER INPUT (for links/usernames) ====================

@bot.on_message(filters.private & ~filters.command(["start", "stats", "report", "check"]))
@owner_only
async def handle_user_input(client, message):
    if OWNER_ID not in report_data:
        return
    
    data = report_data[OWNER_ID]
    
    if data.get("step") == "ask_link":
        # User sent a public chat link/username
        target = message.text.strip()
        
        # Clean the target
        if target.startswith('@'):
            username = target[1:]
        elif 't.me/' in target:
            # Extract username from link
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
        # User sent a private chat invite link
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
            "• `@channel_name`\n"  
            "• `channel_name`\n\n"  
            "**Note:** Assistant accounts must be able to see the chat/channel."  
        )  
    else:  
        await callback.message.edit_text(  
            "🔒 **Private Chat/Channel**\n\n"  
            "Send the invite link:\n\n"  
            "**Examples:**\n"  
            "• `https://t.me/+AbCdEfGhIjKl`\n"  
            "• `https://t.me/joinchat/AbCdEfGhIjKl`\n\n"  
            "**Note:** Assistant accounts will join via the invite link first."  
        )  
    
    await callback.answer()

# ==================== REASON SELECTION ====================

async def show_reason_keyboard(msg):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚫 Spam", callback_data="reason_spam")],
        [InlineKeyboardButton("⚔️ Violence", callback_data="reason_violence")],
        [InlineKeyboardButton("🔞 Pornography/Nudity", callback_data="reason_pornography")],
        [InlineKeyboardButton("👶 Child Abuse", callback_data="reason_child_abuse")],
        [InlineKeyboardButton("©️ Copyright", callback_data="reason_copyright")],
        [InlineKeyboardButton("🎭 Fake", callback_data="reason_fake")],
        [InlineKeyboardButton("💊 Illegal Drugs", callback_data="reason_illegal_drugs")],
        [InlineKeyboardButton("❓ Other", callback_data="reason_other")]
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
    
    total_reports = len(user_clients) * MAX_REPORTS  
    
    await callback.message.edit_text(  
        f"✅ Reason: {reason_name}\n\n"  
        f"⏳ Sending {total_reports} reports from {len(user_clients)} accounts...\n"  
        f"Please wait..."  
    )  
    
    await callback.answer()  
    await execute_report(client, callback.message)

# ==================== CONFIRMATION HANDLER ====================

@bot.on_callback_query(filters.regex("^confirm_report_"))
@owner_only
async def confirm_report(client, callback):
    """Handle confirmation for mass reporting"""
    
    # Extract data from callback
    data_parts = callback.data.split("_")
    chat_id = data_parts[2]
    msg_id = data_parts[3]
    
    if OWNER_ID not in report_data:
        await callback.answer("Session expired! Start over.", show_alert=True)
        return
    
    # Update the message to show "Starting reports..."
    await callback.message.edit_text(
        f"🚀 **Starting Mass Reports**\n\n"
        f"Confirmed target:\n"
        f"• Chat ID: `{chat_id}`\n"
        f"• Message ID: `{msg_id}`\n\n"
        f"⏳ Sending {len(user_clients) * MAX_REPORTS} reports from {len(user_clients)} accounts...\n"
        f"This may take several minutes..."
    )
    
    await callback.answer("Starting mass reports...")
    
    # Execute the actual reporting
    await execute_verified_report(client, callback.message, chat_id, msg_id)

@bot.on_callback_query(filters.regex("^cancel_report$"))
@owner_only
async def cancel_report(client, callback):
    """Handle report cancellation"""
    
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]
    
    await callback.message.edit_text(
        "❌ **Report Cancelled**\n\n"
        "No reports were sent. Use /report again to start over."
    )
    await callback.answer("Report cancelled")

# ==================== EXECUTE VERIFIED REPORT ====================

async def execute_verified_report(client, message, chat_id, msg_id):
    """Execute mass reporting after verification"""
    
    if not user_clients:
        await message.edit_text("❌ No active accounts!")
        return
    
    success = 0
    failed = 0
    results = []
    working_accounts = list(user_clients.items())
    
    reason_name, reason_obj = REPORT_REASONS["child_abuse"]
    
    # Round robin reporting
    for report_num in range(MAX_REPORTS):
        for acc_num, ucl in working_accounts:
            try:
                print(f"DEBUG: Account #{acc_num} reporting message {msg_id} (Report #{report_num + 1})")
                
                # FIXED: Using messages.Report for specific message reporting
                await ucl.invoke(
                    Report(
                        peer=await ucl.resolve_peer(int(chat_id)),
                        id=[int(msg_id)],
                        reason=reason_obj
                    )
                )
                
                success += 1
                print(f"✅ Account #{acc_num} report #{report_num + 1} successful")
                results.append(f"✅ Acc #{acc_num}: Report {report_num + 1}")
                
            except Exception as e:
                error = str(e)
                print(f"DEBUG: Account #{acc_num} failed: {error}")
                
                # Handle flood waits
                if "FLOOD_WAIT" in error:
                    wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                    if wait_match:
                        wait_time = int(wait_match.group(1))
                        print(f"DEBUG: Flood wait for {wait_time} seconds")
                        await asyncio.sleep(wait_time)
                
                if "USER_BOT" not in error and "PHONE_NOT" not in error:
                    failed += 1
                    results.append(f"❌ Acc #{acc_num}: Failed")
            
            # Random delay
            delay = random.uniform(3, 7)
            await asyncio.sleep(delay)
    
    # Final results
    result_text = f"📊 **Mass Report Completed**\n\n"
    result_text += f"🎯 Target Message ID: `{msg_id}`\n"
    result_text += f"📨 Reason: {reason_name}\n"
    result_text += f"✅ Successful Reports: {success}\n"
    result_text += f"❌ Failed Reports: {failed}\n"
    result_text += f"👥 Accounts Used: {len(working_accounts)}\n"
    result_text += f"🔄 Reports per Account: {MAX_REPORTS}\n\n"
    
    if results:
        result_text += "**Report Summary:**\n"
        # Group by account
        account_results = {}
        for r in results:
            if "Acc #" in r:
                acc_num = r.split("Acc #")[1].split(":")[0]
                if acc_num not in account_results:
                    account_results[acc_num] = {"success": 0, "failed": 0}
                if "✅" in r:
                    account_results[acc_num]["success"] += 1
                elif "❌" in r:
                    account_results[acc_num]["failed"] += 1
        
        for acc_num, stats in account_results.items():
            result_text += f"• Acc #{acc_num}: ✅{stats['success']} ❌{stats['failed']}\n"
    
    await message.edit_text(result_text)
    
    # Clear report data
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]

# ==================== EXECUTE REPORT ====================

async def execute_report(client, message):
    if OWNER_ID not in report_data:
        await message.edit_text("❌ Report session expired! Use /report again.")
        return
        
    data = report_data[OWNER_ID]
    reason_key = data["reason"]
    reason_name, reason_obj = REPORT_REASONS[reason_key]
    
    success = 0  
    failed = 0  
    results = []  
    
    report_type = data.get("type")  
    target = data.get("target", "")
    
    print(f"DEBUG: Starting report. Type: {report_type}, Target: {target}, Reason: {reason_key}")
    
    # Get list of working accounts
    working_accounts = list(user_clients.items())
    
    if not working_accounts:
        await message.edit_text("❌ No working accounts!")
        return
    
    # Public chat/channel report (username based)
    if report_type in ["public_chat", "bot_or_channel", "channel"]:
        username = target
        
        # ROUND ROBIN REPORTING: Each account sends one report at a time
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in working_accounts:
                try:
                    print(f"DEBUG: Account #{acc_num} attempting report #{report_num + 1} for @{username}")
                    
                    # Try to get chat info first
                    try:
                        chat = await ucl.get_chat(username)
                        print(f"DEBUG: Account #{acc_num} can see chat: {chat.title}")
                    except Exception as e:
                        print(f"DEBUG: Account #{acc_num} cannot access chat @{username}: {e}")
                    
                    # Report the peer
                    await ucl.invoke(
                        ReportPeer(
                            peer=await ucl.resolve_peer(username),
                            reason=reason_obj
                        )
                    )
                    
                    success += 1
                    print(f"✅ Account #{acc_num} report #{report_num + 1} successful")
                    
                    # Add to results
                    results.append(f"✅ Acc #{acc_num}: Report {report_num + 1}")
                    
                except Exception as e:
                    error = str(e)
                    print(f"DEBUG: Account #{acc_num} report #{report_num + 1} failed: {error}")
                    
                    if "FLOOD_WAIT" in error:
                        # Extract wait time
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            wait_time = int(wait_match.group(1))
                            print(f"DEBUG: Flood wait for {wait_time} seconds")
                            await asyncio.sleep(wait_time)
                    
                    # Don't count certain errors as failures
                    if "USER_BOT" not in error and "PHONE_NOT" not in error and "USERNAME_NOT_OCCUPIED" not in error:
                        failed += 1
                        results.append(f"❌ Acc #{acc_num}: Failed")
                    else:
                        print(f"DEBUG: Skipping error for account #{acc_num}: {error[:50]}")
                
                # Random delay between 3-7 seconds to avoid detection
                delay = random.uniform(3, 7)
                await asyncio.sleep(delay)
    
    # Private chat report (invite link based)
    elif report_type == "private_chat":
        invite_link = target
        
        # First join all accounts to the private chat
        joined_accounts = []
        for acc_num, ucl in working_accounts:
            try:
                await ucl.join_chat(invite_link)
                print(f"DEBUG: Account #{acc_num} joined private chat")
                joined_accounts.append((acc_num, ucl))
            except UserAlreadyParticipant:
                print(f"DEBUG: Account #{acc_num} already in chat")
                joined_accounts.append((acc_num, ucl))
            except Exception as e:
                print(f"DEBUG: Account #{acc_num} failed to join: {e}")
        
        if not joined_accounts:
            await message.edit_text("❌ No accounts could join the private chat!")
            return
        
        # Get chat ID for reporting
        chat_id = None
        try:
            temp_client = joined_accounts[0][1]
            chat = await temp_client.get_chat(invite_link)
            chat_id = chat.id
            print(f"DEBUG: Chat ID: {chat_id}")
        except Exception as e:
            print(f"DEBUG: Failed to get chat ID: {e}")
        
        # ROUND ROBIN REPORTING for private chats
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in joined_accounts:
                try:
                    print(f"DEBUG: Account #{acc_num} attempting private chat report #{report_num + 1}")
                    
                    await ucl.invoke(
                        ReportPeer(
                            peer=await ucl.resolve_peer(chat_id) if chat_id else await ucl.resolve_peer(invite_link),
                            reason=reason_obj
                        )
                    )
                    
                    success += 1
                    print(f"✅ Account #{acc_num} private report #{report_num + 1} successful")
                    results.append(f"✅ Acc #{acc_num}: Private Report {report_num + 1}")
                    
                except Exception as e:
                    error = str(e)
                    print(f"DEBUG: Account #{acc_num} private report failed: {error}")
                    
                    if "FLOOD_WAIT" in error:
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            wait_time = int(wait_match.group(1))
                            await asyncio.sleep(wait_time)
                    
                    if "USER_BOT" not in error and "PHONE_NOT" not in error:
                        failed += 1
                        results.append(f"❌ Acc #{acc_num}: Failed")
                
                # Random delay
                delay = random.uniform(3, 7)
                await asyncio.sleep(delay)
    
    # Message report
    elif report_type == "message":
        parsed = data["parsed"]
        chat_id, msg_id = parsed
        
        # Convert to proper chat ID format
        if not chat_id.startswith('-'):
            chat_id = f"-100{chat_id}"
            
        # ROUND ROBIN REPORTING for messages
        for report_num in range(MAX_REPORTS):
            for acc_num, ucl in working_accounts:
                try:
                    # Get chat first to ensure we can access it
                    chat = await ucl.get_chat(int(chat_id))
                    
                    # FIXED: Report the message using messages.Report
                    await ucl.invoke(
                        Report(
                            peer=await ucl.resolve_peer(int(chat_id)),
                            id=[int(msg_id)],
                            reason=reason_obj
                        )
                    )
                    
                    success += 1
                    print(f"✅ Account #{acc_num} message report #{report_num + 1} successful")
                    results.append(f"✅ Acc #{acc_num}: Msg Report {report_num + 1}")
                    
                except Exception as e:
                    error = str(e)
                    print(f"DEBUG: Account #{acc_num} message report failed: {error}")
                    
                    if "FLOOD_WAIT" in error:
                        wait_match = re.search(r'FLOOD_WAIT_(\d+)', error)
                        if wait_match:
                            wait_time = int(wait_match.group(1))
                            await asyncio.sleep(wait_time)
                    
                    if "PHONE_NOT" not in error and "USER_BOT" not in error:
                        failed += 1
                        results.append(f"❌ Acc #{acc_num}: Failed")
                
                # Random delay
                delay = random.uniform(3, 7)
                await asyncio.sleep(delay)
    
    # Send results
    result_text = f"📊 **Report Results**\n\n"
    result_text += f"🎯 Target: {target}\n"
    result_text += f"📨 Reason: {reason_name}\n"
    result_text += f"✅ Success: {success}\n"
    result_text += f"❌ Failed: {failed}\n"
    result_text += f"📊 Total: {success + failed}\n"
    result_text += f"👥 Accounts: {len(working_accounts)}\n\n"
    
    if results:
        # Show last 10 results
        result_text += "**Last Reports:**\n"
        result_text += "\n".join(results[-10:])
        if len(results) > 10:
            result_text += f"\n\n... and {len(results) - 10} more"
    
    await message.edit_text(result_text)
    
    # Also send a copy to logger group if available
    if LOGGER_GROUP_ID:
        try:
            await bot.send_message(
                LOGGER_GROUP_ID,
                f"📊 **Report Completed**\n\n"
                f"🎯 Target: {target}\n"
                f"📨 Reason: {reason_name}\n"
                f"✅ Success: {success}\n"
                f"❌ Failed: {failed}\n"
                f"👥 Accounts: {len(working_accounts)}"
            )
        except Exception as e:
            print(f"DEBUG: Failed to send to logger: {e}")
    
    # Clear report data
    if OWNER_ID in report_data:
        del report_data[OWNER_ID]

# ==================== STOP ALL CLIENTS ====================

async def stop_all():
    """Stop all clients and bot"""
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
    """Keep the bot running until interrupted"""
    stop_event = asyncio.Event()
    
    def signal_handler(signum, frame):
        stop_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await stop_event.wait()

# ==================== MAIN FUNCTION ====================

async def main():
    await bot.start()
    print("✅ Bot started!")
    
    me = await bot.get_me()
    print(f"🤖 Bot: {me.first_name} (@{me.username})")
    
    await connect_all_accounts()
    await idle()

# ==================== ENTRY POINT ====================

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n⚠️ Stopped by user (Ctrl+C)")
    finally:
        loop.run_until_complete(stop_all())
        loop.close()
