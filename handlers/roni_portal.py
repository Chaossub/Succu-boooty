# Updated sections with NSFW availability controls and booking handler

# Add to the existing imports section
from handlers.nsfw_text_session_availability import nsfw_availability_handler
from handlers.nsfw_text_session_booking import nsfw_booking_handler

# Modify the _roni_main_keyboard() method to include new NSFW buttons:
def _roni_main_keyboard(user_id: int | None = None) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    rows.append([InlineKeyboardButton("📖 Roni’s Menu", callback_data="roni_portal:menu")])
    rows.append([InlineKeyboardButton("💌 Book Roni", url=f"https://t.me/{RONI_USERNAME}")])
    
    # NEW: NSFW booking flow (for DM-only via Roni assistant menu)
    rows.append([InlineKeyboardButton("💞 Book a private NSFW texting session", callback_data="nsfw_book:open")])
    
    # Rest of your buttons...
    return InlineKeyboardMarkup(rows)

# Register new handlers for booking and availability management (added to register() function)
def register(app: Client) -> None:
    # Existing registration for other handlers
    # Register the new NSFW session handlers:
    nsfw_availability_handler.register(app)
    nsfw_booking_handler.register(app)

    # Rest of your code remains unchanged...

