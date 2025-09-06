from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# --- Contact Admin Panel ---

@Client.on_message(filters.command("contact") & filters.private)
async def contact_panel(client, message):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📩 Contact Roni", url="https://t.me/RoniJane"),
                InlineKeyboardButton("📩 Contact Ruby", url="https://t.me/RubyRansoms")
            ],
            [
                InlineKeyboardButton("🙈 Anonymous Message to Admin", callback_data="anon_message")
            ]
        ]
    )

    await message.reply_text(
        "Who would you like to contact?",
        reply_markup=keyboard
    )


@Client.on_callback_query(filters.regex("anon_message"))
async def anon_message_handler(client: Client, query: CallbackQuery):
    await query.message.reply_text(
        "Send me your message and I will forward it anonymously to the admin."
    )

    # Save state for this user (simple example; you may want to track it in MongoDB)
    client._anon_waiting = getattr(client, "_anon_waiting", set())
    client._anon_waiting.add(query.from_user.id)
    await query.answer("Okay, send me your anonymous message!")


@Client.on_message(filters.private & ~filters.command("contact"))
async def forward_anon(client, message):
    # Only forward if user is in anon_waiting
    if hasattr(client, "_anon_waiting") and message.from_user.id in client._anon_waiting:
        # Forward anonymously to you (Roni)
        await client.send_message(
            6964994611,  # your Telegram ID
            f"📩 Anonymous message:\n\n{message.text}"
        )
        await message.reply_text("✅ Your message has been sent anonymously.")
        client._anon_waiting.remove(message.from_user.id)


# --- Main menu button injection (if needed elsewhere) ---
def get_contact_buttons():
    """Return contact buttons for use in other menus."""
    return [
        [
            InlineKeyboardButton("📩 Contact Roni", url="https://t.me/RoniJane"),
            InlineKeyboardButton("📩 Contact Ruby", url="https://t.me/RubyRansoms")
        ],
        [
            InlineKeyboardButton("🙈 Anonymous Message to Admin", callback_data="anon_message")
        ]
    ]


# --- Fix for main.py wiring ---
def register(app):
    """
    No-op for main.py wiring. All handlers here are already registered
    via decorators; this just prevents AttributeError in main.py.
    """
    return
