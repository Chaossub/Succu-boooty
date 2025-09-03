    @app.on_callback_query(filters.regex(r"^menu:(.+)$"))
    async def _show_menu(c: Client, cq: CallbackQuery):
        model = cq.data.split(":", 1)[1]
        item = MENUS.get_menu(model)
        if not item:
            await cq.answer("No menu saved for this model.", show_alert=True)
            return

        kb = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu:close")]])

        # We intentionally SEND a new message with a Back button.
        # The model-list message above remains visible.
        if item.photo_file_id:
            await cq.message.reply_photo(item.photo_file_id,
                                         caption=item.caption or f"{model}'s Menu",
                                         reply_markup=kb)
        else:
            await cq.message.reply_text(item.caption or f"{model}'s Menu",
                                        reply_markup=kb)

        await cq.answer()

    @app.on_callback_query(filters.regex(r"^menu:close$"))
    async def _close_menu(c: Client, cq: CallbackQuery):
        # Delete the current menu message so the list above is now the visible state.
        try:
            await cq.message.delete()
        except Exception:
            pass
        # No need to edit anything else; the list above is still there.
        await cq.answer("Back")
