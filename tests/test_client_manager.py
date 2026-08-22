import asyncio
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.client_manager import ClientManager, ClientRouteError
from modules.reply_router import ReplyRouter
from modules.delete_router import DeleteRouter
from modules.moderation_router import ModerationRouter

class Log:
    def __init__(self): self.rows=[]; self.errors=[]
    def log_info(self, value): self.rows.append(value)
    def log_error(self, value): self.errors.append(value)

class Client:
    def __init__(self, name, fail=False): self.name=name; self.fail=fail; self.calls=[]; self.connected=False
    async def connect(self):
        if self.fail: raise RuntimeError(self.name)
        self.connected=True
    async def disconnect(self): self.connected=False
    async def send_message(self, *a, **k): self.calls.append(("send", a, k)); return self.name
    async def delete_messages(self, *a, **k): self.calls.append(("delete", a, k)); return self.name
    async def __call__(self, request): self.calls.append(("moderation", request)); return self.name

async def main():
    primary, management, background = Client("primary"), Client("management"), Client("background")
    log = Log()
    m = ClientManager(primary, management_factory=lambda: management, background_factory=lambda: background, logger=log, enabled=True)
    assert await m.connect_workers()
    assert primary.connected is False and management.connected and background.connected
    assert await ReplyRouter(m).send_public(type("E", (), {"chat_id": 1, "message": type("M", (), {"id": 2})()})(), "x") == "background"
    assert await DeleteRouter(m).delete_background(1, [2]) == "background"
    assert any("ROUTE background -> delete real" in row for row in log.rows)
    assert await ModerationRouter(m).execute("ban") == "management"
    assert any("ROUTE background -> send_message" in row for row in log.rows)
    assert any("ROUTE management -> __call__" in row for row in log.rows)
    m.observe_routes()
    assert any("ROUTE primary -> receive dry_run=True" in row for row in log.rows)
    # A failed management client cannot use primary as a fallback.
    broken = ClientManager(primary, management_factory=lambda: Client("bad", True), background_factory=lambda: background, enabled=True)
    await broken.connect_workers()
    try:
        await broken.send_management(1, "x")
        raise AssertionError("fallback occurred")
    except ClientRouteError:
        pass
    # Background backlog is isolated from management route.
    background.calls.extend([("busy",)] * 100)
    assert await m.moderation_management("mute") == "management"

asyncio.run(main())
print("client manager tests OK")

# Preparation interfaces do not alter legacy client selection.
from modules.message_delete_queue import MessageDeleteQueue
legacy_manager = ClientManager(Client('legacy'), enabled=False)
queue = MessageDeleteQueue(Client('legacy'), Log(), delete_router=DeleteRouter(legacy_manager))
assert queue.delete_router.manager is legacy_manager

from modules.watchdog_reporting import deliver_pending_reports
import tempfile
from pathlib import Path
async def watchdog_busy_test():
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / 'watchdog.json'
        state.write_text('{"version":1,"pending":[{"id":"x"}],"sent":{},"suppressed":{}}', encoding='utf-8')
        log = Log()
        assert await deliver_pending_reports(Client('background'), background_client=Client('background'), background_ready=lambda: False, logger=log, state_path=state) == 0
        assert "WATCHDOG REPORT DEFERRED reason=background_busy" in log.rows
asyncio.run(watchdog_busy_test())
