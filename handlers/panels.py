async def render_contact(msg: Message, me_username: Optional[str]):
    def _contact_url(username: Optional[str], numeric_id: Optional[str]) -> Optional[str]:
        if username and username.strip():
            return f"https://t.me/{username.strip().lstrip('@')}"
        if numeric_id and str(numeric_id).strip():
            # works even if user has no public @username
            return f"https://t.me/user?id={int(str(numeric_id).strip())}"
        return None

    rows = []

    # RONI
    roni_url = _contact_url(os.getenv("RONI_USERNAME"), RONI_ID)
    if roni_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RONI_NAME or 'Roni'}", url=roni_url)])

    # RUBY
    ruby_url = _contact_url(os.getenv("RUBY_USERNAME"), RUBY_ID)
    if ruby_url:
        rows.append([InlineKeyboardButton(f"👑 Contact {RUBY_NAME or 'Ruby'}", url=ruby_url)])

    # Suggestions + Anonymous
    rows.append([_btn("💡 Suggestions (type in chat)", "contact:suggest")])
    rows.append([_btn("🕵️ Anonymous Message", "contact:anon")])
    rows += _back_main()

    kb = InlineKeyboardMarkup(rows)
    await msg.edit_text(
        "👑 <b>Contact Admins</b>\n\n"
        "• Tag an admin in chat\n"
        "• Or send an anonymous message via the bot.\n",
        reply_markup=kb
    )
