from splusthon import SoroushClient

client = SoroushClient

print("METHODS:")

for x in dir(client):
    if "admin" in x.lower() or "participant" in x.lower() or "member" in x.lower() or "chat" in x.lower():
        print(x)
