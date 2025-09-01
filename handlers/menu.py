# Main Menus UI using persistent store
import os
from typing import List
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from utils.menu_store import store

BTN_BACK = os.getenv("BTN_BACK", "⬅️ Back to Main")

WELCOME_TEXT = (
    "🔥 <b>Welcome to SuccuBot</b> 🔥\n"
    "Your naughty little helper inside the Sanctuary — ready to keep things fun, flirty, and flowing.\n\n"
    "✨ <i>Use the menu below to navigate!</i>"
)

def _hub_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("💕 Menus", callback_data="open_menus")],
        [InlineKeyboardButton("👑 Contact Admins", callback_data="open_contact_admins")],
        [InlineKeyboardButton("🔥 Find Our Models Elsewhere", callback_data="open_models_links")],
        [InlineKeyboardButton("❓ Help", callback_data="open_help")],
    ]
    return InlineKeyboardMarkup(rows)

def _chunk_buttons(labels: List[str], cols: int = 2) -> List[List[InlineKeyboardButton]]:
    rows = []
    for i in range(0, len(labels), cols):
        chunk = labels[i:i+cols]
        rows.append([InlineKeyboardButton(f"💘 {name}", callback_data=f"menu_open::{name}") for name in chunk])
    return rows

def _menus_panel_kb() -> InlineKeyboardMarkup:
    models = store.all_models()
    if not models:
        # fall back to ENV names (for first boot with no menus yet)
        defaults = [x for x in [
            os.getenv("RONI_NAME", "Roni"),
            os.getenv("RUBY_NAME", "Ruby"),
            os.getenv("RIN_NAME", "Rin"),
            os.getenv("SAVY_NAME", os.getenv("SAVY_NAME", "Savy")),
        ] if x]
        models = sorted(set(defaults))
    rows = _chunk_buttons(models, cols=2)
    rows.append([InlineKeyboardButton("💞 Contact Models", callback_data="open_contact_admins")])
    rows.append([InlineKeyboardButton(BTN_BACK, callback_data="panel_back_main")])
    return InlineKeyboardMarkup(rows)

def register(app: Client):
    # from hub → Menus
    @app.on_callback_query(filters.regex(r"^open_menus$"))
    async def open_menus(_, cq: CallbackQuery):
        await cq.message.edit_text("💕 <b>Menus</b>\nPick a model or contact the team.", reply_markup=_menus_panel_kb(), disable_web_page_preview=True)
        await cq.answer()

    # open a specific model menu
    @app.on_callback_query(filters.regex(r"^menu_open::(.+)$"))
    async def open_model(_, cq: CallbackQuery):
        model = cq.matches[0].group(1)
        text = store.get_menu(model)
        if not text:
            await cq.answer("No menu saved for this model (use /createmenu).", show_alert=True)
            return
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back to Menus", callback_data="open_menus")]])
        await cq.message.edit_text(f"💘 <b>{model}</b>\n\n{text}", reply_markup=kb, disable_web_page_preview=True)

    # allow hub “Back” actions from other panels
    @app.on_callback_query(filters.regex(r"^panel_back_main$"))
    async def back_main(_, cq: CallbackQuery):
        await cq.message.edit_text(WELCOME_TEXT, reply_markup=_hub_kb(), disable_web_page_preview=True)
        await cq.answer()
