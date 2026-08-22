"""Route admin actions to management or background Soroush clients."""
from modules.moderation_context import CURRENT_ACTION


class RoutedAdminActions:
    """Compatibility facade; callers keep using ``bot.admin_actions``."""
    _MANAGEMENT_ACTIONS = frozenset({"mute", "unmute", "unban", "lock", "unlock"})

    def __init__(self, management, background, fallback):
        object.__setattr__(self, "_management", management)
        object.__setattr__(self, "_background", background)
        object.__setattr__(self, "_fallback", fallback)

    def _target(self):
        action = CURRENT_ACTION.get() or ""
        if action in self._MANAGEMENT_ACTIONS:
            return self._management or self._fallback
        if action in {"ban", "punish", "kick", "auto_mute"}:
            return self._background or self._fallback
        # Non-queue helpers such as warning notices are background work.
        return self._background or self._fallback

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        # Shared runtime attributes must be available on all delegates.
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        for target in (self._management, self._background, self._fallback):
            if target is not None:
                setattr(target, name, value)
