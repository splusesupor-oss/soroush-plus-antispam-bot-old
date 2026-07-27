"""Responsible, non-diagnostic name information for the شخصیت command."""
import re

_NAME_INFO = {
    "علی": ("عربی", "بلندمرتبه و والا"),
    "محمد": ("عربی", "ستوده‌شده"),
    "رضا": ("عربی", "خشنودی و رضایت"),
    "حسین": ("عربی", "نیک و زیبا"),
    "مریم": ("عبری/آرامی", "نامی کهن با کاربرد گسترده در فرهنگ‌های گوناگون"),
    "سارا": ("عبری", "بانوی والا"),
    "ملیکا": ("یونانی/لاتین", "ملکه‌مانند"),
    "عماد": ("عربی", "تکیه‌گاه"),
    "همایون": ("فارسی", "خجسته و فرخنده"),
}


def _norm(value):
    return " ".join(str(value or "").strip().lower().replace("ي", "ی").replace("ك", "ک").split())


def report(name):
    value = " ".join(str(name or "").strip().split())
    if not value or len(value) > 40 or not re.fullmatch(r"[A-Za-zآ-یءئؤة -]+", value):
        return None
    key = _norm(value.split()[0])
    origin, meaning = _NAME_INFO.get(key, ("نامشخص", "برای این نام اطلاعات ریشه‌شناختی کافی در دادهٔ داخلی ندارم"))
    detail = (
        "این تحلیل کلی است؛ از روی اسم نمی‌توان شخصیت واقعی یا توانایی‌های یک فرد را تشخیص داد."
    )
    return (
        f"🧩 تحلیل کلی نام «{value}»\n\n"
        f"• خاستگاه احتمالی: {origin}\n"
        f"• معنای رایج: {meaning}\n"
        "• برداشت منطقی: اسم بیشتر بخشی از هویت فرهنگی و خانوادگی است، نه پیش‌بینی‌کنندهٔ شخصیت.\n"
        f"• نکته: {detail}"
    )
