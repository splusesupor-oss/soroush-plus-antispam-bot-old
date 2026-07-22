
def bold(text):
    a="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b="𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭"
    return text.translate(str.maketrans(a,b))


def mono(text):
    a="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b="𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉"
    return text.translate(str.maketrans(a,b))


def italic(text):
    a="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    b="𝘢𝘣𝘤𝘥𝘦𝘧𝘨𝘩𝘪𝘫𝘬𝘭𝘮𝘯𝘰𝘱𝘲𝘳𝘴𝘵𝘶𝘷𝘸𝘹𝘺𝘻𝘈𝘉𝘊𝘋𝘌𝘍𝘎𝘏𝘐𝘑𝘒𝘓𝘔𝘕𝘖𝘗𝘘𝘙𝘚𝘛𝘜𝘝𝘞𝘟𝘠𝘡"
    return text.translate(str.maketrans(a,b))


def bubble(text):
    return "".join(chr(ord(c)+0x24D0) if c.isalpha() else c for c in text.lower())


def square(text):
    return "".join("🅰️" if c.lower()=="a" else c for c in text)


def wide(text):
    return "".join(chr(ord(c)+0xFEE0) if '!' <= c <= '~' else c for c in text)


def upside(text):
    table=str.maketrans("abcdefghijklmnopqrstuvwxyz",
    "ɐqɔpǝɟƃɥᴉɾʞןɯuodbɹsʇnʌʍxʎz")
    return text.lower().translate(table)


def small(text):
    table=str.maketrans("abcdefghijklmnopqrstuvwxyz",
    "ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀsᴛᴜᴠᴡxʏᴢ")
    return text.lower().translate(table)


def gothic(text):
    return "𝕲𝖔𝖙𝖍𝖎𝖈: "+text


def double(text):
    table=str.maketrans("abcdefghijklmnopqrstuvwxyz",
    "𝕒𝕓𝕔𝕕𝕖𝕗𝕘𝕙𝕚𝕛𝕜𝕝𝕞𝕟𝕠𝕡𝕢𝕣𝕤𝕥𝕦𝕧𝕨𝕩𝕪𝕫")
    return text.translate(table)


def make_fonts(text):
    return [
        bold(text),
        mono(text),
        italic(text),
        bubble(text),
        wide(text),
        upside(text),
        small(text),
        double(text),
        "『"+text+"』",
        "★彡 "+text+" 彡★",
        "꧁༺ "+text+" ༻꧂",
        "『🔥』"+text+"『🔥』",
        "⚡ "+text+" ⚡"
    ]
