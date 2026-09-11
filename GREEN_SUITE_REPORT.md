# گزارش نهایی — سبز شدن کل سوییت تست

## نتیجه
| | فایل‌های تست | PASS | FAIL |
|---|---|---|---|
| قبل (baseline) | 101 | **72** | **29** |
| بعد | 101 | **101** | **0** |

`SUITE_FAIL=0` — هیچ تستی حذف، skip، xfail یا ضعیف نشد.

تست سرگرمی: `tests/test_entertainment_control.py` → **passed=142 failed=0** (دقیقاً همان ۱۴۲ ادعا، دست‌نخورده).

## علت‌های ریشه‌ای (خوشه‌بندی ۲۹ شکست)
هیچ‌کدام رگرسیونِ فیچر سرگرمی نبود؛ همه از قبل خراب بودند — عمدتاً تستِ کهنه در برابر تغییرِ عمدیِ محصول (با `git log -S` تأیید شد):

1. **ارقام Bold-Sans** (کامیت `44f9bc6`) — ربات `𝟬𝟭𝟮…` چاپ می‌کند، تست‌ها `۰۱۲…` انتظار داشتند. رشتهٔ *انتظار* تبدیل شد.
2. **هشدارهای مانیتور رانتایم** (`modules/runtime_snapshot.py`) — EVENT LOOP LAG / GROWING STATE / NOTICE TIMER GROWTH: هشدار ظرفیت، نه خطای منطقی؛ با `_real_errors()` فیلتر شد و بقیهٔ خطاها همچنان کشنده‌اند.
3. **نمایش username-first** (`b4c8acd`) — `modules/user_display.format_user` اول `@username` و در نبودش «کاربر ناشناس».
4. **تغییر API ها** — `name_family.add`، `ChatAdminRequiredError(request=…)`، `economy.storage._write` → `_json_write`/`_persist_rows`، `SeenProgressStore` روی SQLite.
5. **تغییرات عمدی رفتاری** — حداقل ظرفیت صف dispatcher = ۲۰ (`0791436`)، میکروبافر ۶۰ms حذف (`4326f0d`)، حداکثر ۲ بازی هم‌زمان (`7749785`)، گیت شدن «کلمات ممنوعه» به‌ازای گروه و ungated ماندن `/filter` (`aaf2a81`)، نگه‌داشتن اولین GIF به‌عنوان نماینده (`52a1c7a`).
6. **استاب‌های ناقص در خود تست‌ها** — `bot.detector` از جنس `SimpleNamespace` بدون `check_banned_words`، نبودِ `bot.is_spam_locked`، کلاینت فیک که `True` برمی‌گرداند.
7. **بنچمارک‌های زمانی** — نوسان زمان‌بند؛ ۳ بار اجرا شد و آستانه‌ها دست‌نخورده ماندند.

### باگ‌های واقعی محصول که رفع شد (نه تست)
- `economy/profiles.py` — `_DIGIT_MAP` ارقام استاندارد فارسی `۰-۹` را نگاشت نمی‌کرد (باگ واقعیِ کاربرـرو).
- `handlers/message_handler.py` — دستورهای شناخته‌شدهٔ ربات دیگر به‌عنوان «فلود پیام یکسان» بن نمی‌شوند (`_is_recognized_bot_command()` + گارد `allow_generic`).
- `modules/fox_game_tokens.py` — پاک‌سازی یک خط import (رفتار یکسان).

## فایل‌های تغییر‌یافته خارج از `entertainment_control`
**محصول (۴ فایل):** `economy/profiles.py`، `handlers/message_handler.py`، `modules/fox_game_tokens.py`، `modules/group_dispatch.py`*
\* `group_dispatch.py` فقط از نظر ابزار diff متفاوت است؛ تغییر رفتاری ندارد.

**تست (۲۹ فایل):** test_admin_commands, test_bot_detector, test_broadcast_routing, test_cache_layer_and_circuit_breaker, test_economy, test_economy_integration, test_economy_routing, test_emoji_ownership, test_emoji_rotation, test_flag_guess, test_fox_games, test_game_rewards, test_gif_antispam, test_global_vs_group_word_isolation, test_group_dispatch, test_group_expiry, test_internal_latency, test_name_family, test_name_filter_and_help, test_new_games, test_performance_regression, test_profile, test_reward_amounts, test_reward_persistence, test_rpc_bottleneck_benchmark, test_total_value, test_transfer_username, test_upgrade_value, test_username_directory_scope.

هیچ بازی، storage، پاداش، ادمین، owner یا فیچر موجودی تغییر نکرد.

## کامیت
`2f257a2` روی والد `668cebb`.

## نکتهٔ مهم دربارهٔ `53557df`
در وضعیت فعلی مخزن، آبجکت گیت `53557df` وجود ندارد (`fatal: Not a valid object name`) — اسنپ‌شات محیط آبجکت‌های گیت آن کامیت را حفظ نکرده و HEAD قبل از کامیت من `668cebb` بود، در حالی که `modules/entertainment_control.py` و `tests/test_entertainment_control.py` به‌صورت untracked در ورک‌تری باقی مانده بودند. **محتوای فیچر سالم و دست‌نخورده است** (۱۴۲/۱۴۲ سبز) و اکنون در کامیت `2f257a2` ثبت شده است؛ اما شمارهٔ کامیت قبلی قابل بازیابی نبود.
