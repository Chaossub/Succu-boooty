# handlers/menu.py
import json, os
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

MENU_FILE = "menus.json"

# Load menus from file
def load_menus():
    if os.path.exists(MENU_FILE):
        with open(MENU_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# Save menus to file
def save_menus(menus):
    with open(MENU_FILE, "w", encoding="utf-8") as f:
        json.dump(menus, f, indent=2)

menus = load_menus()

def register(app):

    # Command to create/replace a menu for a model
    @app.on_message(filters.command("createmenu"))
    async def create_menu(_, msg):
        parts = msg.text.split(maxsplit=2)
        if len(parts) < 3:
            return await msg.reply("Usage: /createmenu <model> <menu text>")
        model, menu_text = parts[1].strip(), parts[2].strip()
        menus[model.lower()] = menu_text
        save_menus(menus)
        await msg.reply(f"✅ Saved *{model}* menu (text-only).", quote=True)

    # Show model selection
    @app.on_callback_query(filters.regex("^menu$"))
    async def show_menu_selection(_, cq):
        kb = [
            [InlineKeyboardButton("💘 Roni", callback_data="show:roni"),
             InlineKeyboardButton("💘 Ruby", callback_data="show:ruby")],
            [InlineKeyboardButton("💘 Rin", callback_data="show:rin"),
             InlineKeyboardButton("💘 Savy", callback_data="show:savy")],
            [InlineKeyboardButton("⬅️ Back to Main", callback_data="back_main")]
        ]
        await cq.message.edit_text("💕 *Menus*\nPick a model whose menu is saved.",
                                   reply_markup=InlineKeyboardMarkup(kb))

    # Show a specific model menu
    @app.on_callback_query(filters.regex("^show:(.+)$"))
    async def show_model_menu(_, cq):
        model = cq.data.split(":", 1)[1].lower()
        if model not in menus:
            return await cq.answer("❌ No menu saved for this model.", show_alert=True)

        text = menus[model]
        kb = [[InlineKeyboardButton("⬅️ Back", callback_data="menu")]]
        await cq.message.edit_text(text, reply_markup=InlineKeyboardMarkup(kb))

    # Handle going back to main panel
    @app.on_callback_query(filters.regex("^back_main$"))
    async def back_to_main(_, cq):
        # Re-import panels so you don’t duplicate
        from handlers.panels import main_menu
        await main_menu(cq.message)
