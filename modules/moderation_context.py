"""Context shared between moderation queue jobs and routed worker clients."""
import contextvars

CURRENT_ACTION = contextvars.ContextVar("current_moderation_action", default="")
