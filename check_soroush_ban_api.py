import inspect
import splusthon.client.chats as chats
from splusthon import types, functions

print("=== classes ===")
for x in dir(chats):
    obj = getattr(chats, x)
    if inspect.isclass(obj):
        print(x)

print("\n=== edit_permissions source ===")
for x in dir(chats):
    obj = getattr(chats, x)
    if hasattr(obj, "edit_permissions"):
        print("CLASS:", x)
        print(inspect.getsource(obj.edit_permissions))

print("\n=== EditBannedRequest ===")
print(inspect.signature(functions.channels.EditBannedRequest))

print("\n=== ChatBannedRights ===")
print(inspect.signature(types.ChatBannedRights))
