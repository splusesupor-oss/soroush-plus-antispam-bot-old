from modules.moderation_context import CURRENT_ACTION
from modules.routed_admin_actions import RoutedAdminActions

class Target:
    def __init__(self, name): self.name = name
    def which(self): return self.name

primary, management, background = Target('primary'), Target('management'), Target('background')
router = RoutedAdminActions(management, background, primary)
assert router.which() == 'background'
token = CURRENT_ACTION.set('mute')
try: assert router.which() == 'management'
finally: CURRENT_ACTION.reset(token)
token = CURRENT_ACTION.set('ban')
try: assert router.which() == 'background'
finally: CURRENT_ACTION.reset(token)
print('routed admin actions OK')
