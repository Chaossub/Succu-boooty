def _root_kb(is_admin: bool) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton("📍 Check My Status", callback_data="reqpanel:self")],
    ]

    if is_admin:
        rows.append(
            [InlineKeyboardButton("🧾 Look Up Member", callback_data="reqpanel:lookup")]
        )
        rows.append(
            [InlineKeyboardButton("🛠 Owner / Models Tools", callback_data="reqpanel:admin")]
        )

    # ⬇️ CHANGE THIS PART ⬇️
    # OLD:
    # rows.append(
    #     [InlineKeyboardButton("⬅ Back to Sanctuary Menu", callback_data="portal:home")]
    # )

    # NEW: go back to the Help screen instead of the main menu
    rows.append(
        [InlineKeyboardButton("⬅ Back to Help Menu", callback_data="portal:help")]
    )
    # ⬆️ CHANGE THIS PART ⬆️

    return InlineKeyboardMarkup(rows)
