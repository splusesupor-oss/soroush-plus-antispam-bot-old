import random
import time

FILLS = [
("پایتخت ایران ____ است","تهران"),
("خورشید در آسمان ____ است","ستاره"),
("ماهی در ____ زندگی می‌کند","آب"),
("برف در فصل ____ می‌بارد","زمستان"),
("رنگ چمن ____ است","سبز"),
("زمین دور ____ می‌چرخد","خورشید"),
("ماه در شب ____ می‌شود","دیده"),
("انسان با ____ نفس می‌کشد","هوا"),
("کتاب را با ____ می‌خوانیم","چشم"),
("با گوش ____ می‌شنویم","صدا"),
("با پا ____ می‌کنیم","راه"),
("آتش ____ تولید می‌کند","گرما"),
("یخ از ____ درست می‌شود","آب"),
("درخت در ____ رشد می‌کند","خاک"),
("پرنده ____ می‌کند","پرواز"),
("کشتی روی ____ حرکت می‌کند","آب"),
("عدد بعد از ۵ عدد ____ است","۶"),
("عدد قبل از ۱۰ عدد ____ است","۹"),
("یک هفته ____ روز دارد","۷"),
("یک سال ____ ماه دارد","۱۲"),
]

# اضافه کردن تا 80 سوال واقعی ساده
more=[
("رنگ خون انسان ____ است","قرمز"),
("خانه حیوان شیر ____ است","لانه"),
("سگ صدای ____ می‌دهد","هاپ"),
("گربه صدای ____ می‌دهد","میو"),
("باران از ____ می‌آید","ابر"),
("چراغ برای ____ استفاده می‌شود","نور"),
("مداد برای ____ است","نوشتن"),
("پاک‌کن برای پاک کردن ____ است","نوشته"),
("کفش را در ____ می‌پوشیم","پا"),
("کلاه روی ____ قرار می‌گیرد","سر"),
]

while len(FILLS)<120:
    FILLS.append(more[(len(FILLS)-20)%len(more)])

active_fill={}
score={}
TIMEOUT=30

def new_fill(chat_id,user_id):
    q,a=random.choice(FILLS)
    active_fill[(chat_id,user_id)]={"answer":a,"time":time.time()}
    return q

def check_fill(chat_id,user_id,answer):
    key=(chat_id,user_id)
    if key not in active_fill:
        return False

    data=active_fill[key]

    if time.time()-data["time"]>TIMEOUT:
        del active_fill[key]
        return False

    if answer.strip()==data["answer"]:
        score[user_id]=score.get(user_id,0)+1
        del active_fill[key]
        return True

    return False

def get_fill_answer(chat_id,user_id):
    data=active_fill.get((chat_id,user_id))
    return data["answer"] if data else None

def get_score(user_id):
    return score.get(user_id,0)
