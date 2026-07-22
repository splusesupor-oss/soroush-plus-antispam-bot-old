from modules.admin_storage import add_admin, is_admin, load_admins

group = 9429374
user = 65309684

add_admin(group, user)

print("DATA:")
print(load_admins())

print("CHECK:")
print(is_admin(group, user))
