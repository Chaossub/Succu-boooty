# handlers/welcome.py
# Group welcomes with portal button. NO /start here.

import os, time, random, contextlib
from typing import Optional, Dict, Tuple
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ChatMemberUpdated, User
from pyrogram.enums import ChatType, ChatMemberStatus

WELCOME_ENABLE = os.getenv("WELCOME_ENABLE", "1") == "1"
GOODBYE_ENABLE = os.getenv("GOODBYE_ENABLE", "1") == "1"
WELCOME_DELETE_SERVICE = os.getenv("WELCOME_DELETE_SERVICE", "0") == "1"
GOODBYE_DELETE_SERVICE = os.getenv("GOODBYE_DELETE_SERVICE", "0") == "1"
WELCOME_PHOTO = os.getenv("WELCOME_PHOTO")
GOODBYE_PHOTO = os.getenv("GOODBYE_PHOTO")

BTN_MENU   = os.getenv("BTN_MENU",  "💕 Menu")
BTN_DM     = os.getenv("BTN_DM",    "💌 DM Now")
BTN_RULES  = os.getenv("BTN_RULES", "‼️ Rules")
BTN_BUYER  = os.getenv("BTN_BUYER", "✨ Buyer Requirements")

WELCOME_LINES = [
    "🔥 <b>Welcome to the Succubus Sanctuary</b>, {mention}! Tap <b>💌 DM Now</b> to open your portal.",
    "Hey {first} — hit <b>💌 DM Now</b> to pop open your hub.",
    "{mention} slipped in like a midnight secret… Tap <b>💌 DM Now</b> for the full portal.",
]

GOODBYE_LEFT = ["Bye {mention} 💋"]
GOODBYE_KICKED = ["Removed: {mention}."]
GOODBYE_BANNED = ["Banished: {mention}."]

_recent: Dict[Tuple[int,int,str], float] = {}
DEDUP = 90.0
def _seen(chat_id:int, user_id:int, kind:str)->bool:
    now=time.time(); k=(chat_id,user_id,kind); last=_recent.get(k,0.0)
    if now-last<DEDUP: return True
    _recent[k]=now
    for kk,ts in list(_recent.items()):
        if now-ts>5*DEDUP: _recent.pop(kk,None)
    return False

def _mention(u: Optional[User])->str:
    if not u: return "there"
    safe=(u.first_name or "there").replace("<","&lt;").replace(">","&gt;")
    return f"<a href='tg://user?id={u.id}'>{safe}</a>"

def _kb(dm_username: Optional[str])->InlineKeyboardMarkup:
    rows=[]
    if dm_username:
        rows.append([InlineKeyboardButton(BTN_DM, url=f"https://t.me/{dm_username}?start=ready")])
    rows.append([InlineKeyboardButton(BTN_MENU, callback_data="dmf_open_menu")])
    rows.append([InlineKeyboardButton(BTN_RULES, callback_data="dmf_rules"),
                 InlineKeyboardButton(BTN_BUYER, callback_data="dmf_buyer")])
    return InlineKeyboardMarkup(rows)

async def _send_welcome(client: Client, chat_id:int, user: Optional[User], reply_to: Optional[int]=None):
    if not WELCOME_ENABLE or (user and user.is_bot): return
    me=await client.get_me()
    text=random.choice(WELCOME_LINES).format(mention=_mention(user), first=(user.first_name if user else "there"))
    kb=_kb(me.username)
    try:
        if WELCOME_PHOTO:
            await client.send_photo(chat_id, WELCOME_PHOTO, caption=text, reply_markup=kb)
        else:
            await client.send_message(chat_id, text, reply_markup=kb, reply_to_message_id=reply_to or 0)
    except Exception:
        await client.send_message(chat_id, text, reply_markup=kb)

async def _send_goodbye(client: Client, chat_id:int, user: Optional[User], reason:str):
    if not GOODBYE_ENABLE or (user and user.is_bot): return
    pool = GOODBYE_LEFT if reason=="left" else GOODBYE_KICKED if reason=="kicked" else GOODBYE_BANNED
    text=random.choice(pool).format(mention=_mention(user), first=(user.first_name if user else "They"))
    try:
        if GOODBYE_PHOTO: await client.send_photo(chat_id, GOODBYE_PHOTO, caption=text)
        else: await client.send_message(chat_id, text)
    except Exception: pass

def register(app: Client):
    @app.on_message(filters.group & filters.new_chat_members)
    async def on_service_join(client: Client, m: Message):
        for u in m.new_chat_members:
            if _seen(m.chat.id, u.id, "join"): continue
            await _send_welcome(client, m.chat.id, u, reply_to=m.id)
        if WELCOME_DELETE_SERVICE:
            with contextlib.suppress(Exception): await m.delete()

    @app.on_message(filters.group & filters.left_chat_member)
    async def on_service_left(client: Client, m: Message):
        u=m.left_chat_member
        if not u or _seen(m.chat.id, u.id, "leave"): return
        await _send_goodbye(client, m.chat.id, u, reason="left")
        if GOODBYE_DELETE_SERVICE:
            with contextlib.suppress(Exception): await m.delete()

    @app.on_chat_member_updated()
    async def on_member_updated(client: Client, upd: ChatMemberUpdated):
        chat=upd.chat
        if not chat or chat.type==ChatType.PRIVATE: return
        old=upd.old_chat_member; new=upd.new_chat_member
        user=(new.user or (old.user if old else None))
        if not user: return
        if new.status==ChatMemberStatus.MEMBER and (not old or old.status!=ChatMemberStatus.MEMBER):
            if not _seen(chat.id, user.id, "join"): await _send_welcome(client, chat.id, user); return
        if new.status in (ChatMemberStatus.LEFT, ChatMemberStatus.BANNED):
            if _seen(chat.id, user.id, "leave"): return
            reason = "banned" if new.status==ChatMemberStatus.BANNED else ("kicked" if getattr(upd,"from_user",None) and upd.from_user.id!=user.id else "left")
            await _send_goodbye(client, chat.id, user, reason=reason)
