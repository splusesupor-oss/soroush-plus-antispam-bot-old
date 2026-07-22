from pathlib import Path
import shutil

p=Path("handlers/message_handler.py")
backup=p.with_name("message_handler.py.before_history_delete_auto2")
shutil.copy(p,backup)

lines=p.read_text(encoding="utf-8").splitlines()

out=[]
i=0
fixed=False

while i < len(lines):
    line=lines[i]
    
    if "ids = get_message_ids(chat_id, user_id)" in line:
        fixed=True
        
        # تا انتهای بلاک if ids قدیمی رد شود
        out.append(line)
        i+=1
        
        while i < len(lines) and not (
            "print(f\"🚨 BAN FROM HISTORY" in lines[i]
            or "print(\"🚨 BAN FROM HISTORY" in lines[i]
        ):
            i+=1
        
        out.extend([
"                if ids:",
"                    try:",
"                        print('🗑️ DELETE ALL HISTORY:', len(ids))",
"",
"                        for x in range(0, len(ids), 100):",
"                            batch = ids[x:x+100]",
"                            try:",
"                                await bot.client.delete_messages(",
"                                    chat_id,",
"                                    batch",
"                                )",
"                            except Exception as err:",
"                                print('DELETE ERROR:', err)",
"",
"                    except Exception as err:",
"                        print('HISTORY DELETE ERROR:', err)",
""
        ])
        continue

    out.append(line)
    i+=1

if fixed:
    p.write_text("\n".join(out)+"\n",encoding="utf-8")
    print("✅ auto history delete replaced")
    print("backup:",backup)
else:
    print("❌ get_message_ids not found")
