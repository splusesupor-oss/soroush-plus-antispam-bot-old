
import asyncio

async def delete_messages_batch(bot, chat_id, ids, batch_size=100):
    """
    حذف پیام‌ها به صورت دسته‌ای 100 تایی
    مخصوص Splus
    """

    if not ids:
        return

    print(f"🗑️ HISTORY CLEANER START: {len(ids)} messages")

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i+batch_size]

        try:
            await bot.client.delete_messages(
                chat_id,
                batch
            )

            print(
                f"✅ deleted batch {i//batch_size + 1} "
                f"({len(batch)} messages)"
            )

        except Exception as e:
            print("❌ batch delete error:", e)

        await asyncio.sleep(0.2)


async def clean_user_history(bot, chat_id, user_id, get_ids, clear_func):
    try:
        ids = get_ids(chat_id, user_id)

        if ids:
            await delete_messages_batch(
                bot,
                chat_id,
                ids
            )

        clear_func(
            chat_id,
            user_id
        )

        print("✅ history cleared")

    except Exception as e:
        print("❌ history cleaner error:", e)
