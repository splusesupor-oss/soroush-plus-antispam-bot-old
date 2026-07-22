from pathlib import Path

p = Path("handlers/message_handler.py")

text = p.read_text(encoding="utf-8")

old = """                              except Exception as err:
                                  print("DELETE BATCH ERROR:", err)

                      except Exception as err:"""

new = """                              except Exception as err:
                                  print("DELETE BATCH ERROR:", err)

                          clear_user(chat_id, user_id)

                      except Exception as err:"""

if old in text:
    backup = Path("handlers/message_handler.py.before_add_clear_history")
    backup.write_text(text, encoding="utf-8")

    text = text.replace(old, new, 1)
    p.write_text(text, encoding="utf-8")

    print("✅ clear_user added")
    print("backup:", backup)
else:
    print("❌ target block not found")
