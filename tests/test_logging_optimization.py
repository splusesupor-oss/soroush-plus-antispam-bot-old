"""Offline logging regression tests. Each runtime uses a disposable subprocess."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def run_case(tmp_path, body, **settings):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT), SOROUSH_BOT_DATA_DIR=str(tmp_path), BOT_VERBOSE_LOGS="0")
    env.update({k: str(v) for k, v in settings.items()})
    r = subprocess.run([sys.executable, "-c", textwrap.dedent(body)], cwd=ROOT,
        env=env, capture_output=True, text=True, timeout=40)
    assert r.returncode == 0, r.stdout + r.stderr
    return r


def test_quiet_defaults_preserve_important_events_and_audit(tmp_path):
    run_case(tmp_path, '''
        import json
        from modules.logger_module import BotLogger, _runtime
        from modules.runtime_paths import LOG_DIR
        log = BotLogger()
        for line in ['MODERATION RPC START id=1', 'RPC TRACE result=success',
                     'CONN TRACE SOCKET SEND id=1', 'KEEPALIVE PONG RECEIVED',
                     'HEALTH_HEARTBEAT_REPORT routine', 'NAME FILTER CHECK routine',
                     'RPC GOVERNOR WAIT normal', 'GOVERNOR ACQUIRE routine']:
            log.log_info(line)
        for line in ['GROUP DISPATCH OVERFLOW chat_id=7', 'OUTGOING SEND DROP chat_id=8',
                     'KEEPALIVE PONG TIMEOUT', 'SPLUS RECONNECT SUCCESS',
                     'ENTERTAINMENT DISABLED', 'RPC TRACE result=failed:ServerError']:
            log.log_info(line)
        log.log_error('DB WRITE FAILED disk full')
        log.log_deleted_message(12, 'sample', -7, 'test', 'x'*10000, 'spam', 25)
        log.log_action('BAN', 12, -7, 'spam')
        _runtime().stop()
        text = (LOG_DIR/'bot.log').read_text()
        assert 'routine' not in text and 'result=success' not in text
        assert 'MODERATION RPC START' not in text and 'SOCKET SEND' not in text
        for expected in ['OVERFLOW', 'SEND DROP', 'PONG TIMEOUT', 'RECONNECT SUCCESS',
                         'ENTERTAINMENT DISABLED', 'failed:ServerError', 'disk full']:
            assert expected in text, expected
        row = json.loads((LOG_DIR/'deleted_messages.log').read_text())
        assert row['user_id']==12 and row['group_id']==-7 and row['message_id']==25
        assert row['reason']=='spam' and row['timestamp']
        assert len(row['original_text'])==160
        assert json.loads((LOG_DIR/'actions.log').read_text())['action']=='BAN'
    ''')


def test_verbose_and_console_option(tmp_path):
    r = run_case(tmp_path, '''
        from modules.logger_module import BotLogger, _runtime
        from modules.runtime_paths import LOG_DIR
        a = BotLogger(console_log=False)
        a.log_info('RPC TRACE secret-console-test')
        a.log_error('disk-error-file-only')
        b = BotLogger()
        b.log_info('RPC TRACE visible-debug')
        _runtime().stop()
        text=(LOG_DIR/'bot.log').read_text()
        assert 'secret-console-test' in text and 'visible-debug' in text
    ''', BOT_VERBOSE_LOGS=1)
    assert 'secret-console-test' not in r.stderr and 'disk-error-file-only' not in r.stderr
    assert 'visible-debug' in r.stderr


def test_disk_io_and_json_are_not_on_producer_thread(tmp_path):
    run_case(tmp_path, '''
        import json, logging.handlers, threading
        from modules.logger_module import BotLogger, _runtime
        log = BotLogger(console_log=False)
        producer = threading.get_ident()
        dumps = json.dumps
        emit = logging.handlers.RotatingFileHandler.emit
        counts = {'json':0, 'disk':0}
        def guarded_json(*a, **kw):
            assert threading.get_ident()!=producer, 'producer encoded JSON'
            counts['json']+=1
            return dumps(*a, **kw)
        def guarded_emit(*a, **kw):
            assert threading.get_ident()!=producer, 'producer wrote disk'
            counts['disk']+=1
            return emit(*a, **kw)
        json.dumps=guarded_json
        logging.handlers.RotatingFileHandler.emit=guarded_emit
        for i in range(100):
            log.log_deleted_message(1, 'u', -2, 'g', 'sample', 'filter', i)
            log.log_action('WARN', 1, -2, 'test')
        _runtime().stop()
        assert counts['json']==200 and counts['disk']>=400, counts
    ''')


def test_full_queue_does_not_wait_and_loss_is_visible(tmp_path):
    run_case(tmp_path, '''
        import logging, queue, time
        from modules.logger_module import _DroppingQueueHandler, _ReportingQueueListener
        q = queue.Queue(maxsize=1)
        h = _DroppingQueueHandler(q)
        rec = logging.LogRecord('test', 20, '', 0, 'test', (), None)
        h.handle(rec)
        t=time.perf_counter()
        for _ in range(10000): h.handle(rec)
        assert time.perf_counter()-t < 1.0
        assert h.dropped>=10000
        seen=[]
        class Capture(logging.Handler):
            def emit(self, rec): seen.append(rec.msg)
        listener=_ReportingQueueListener(q, Capture())
        listener.start(); listener.stop(); listener.stop()
        assert any(isinstance(x,dict) and x.get('event')=='LOG_QUEUE_OVERFLOW' for x in seen)
    ''')


def test_optional_debug_does_not_build_rpc_strings_or_snapshots(tmp_path):
    run_case(tmp_path, '''
        from modules.logger_module import BotLogger, _runtime
        from modules import outgoing_profiler as op
        from modules.connection_guard import log_ping_lifecycle
        log=BotLogger(console_log=False)
        def forbidden(*a, **k): raise AssertionError('disabled diagnostic formatted')
        op._format_trace=forbidden
        op.pending_rpc_snapshot=forbidden
        op._log_trace(log, {'result':'success'})
        op._log_rpc_budget(log, None, 'send', {'rpc_await_ms':800})
        class BadString:
            def __str__(self): return forbidden()
            def __repr__(self): return forbidden()
        op._log_conn_trace(log, 'SOCKET SEND', huge=BadString())
        log_ping_lifecycle(log, 1, 'SENT', huge=BadString())
        _runtime().stop()
    ''')


def test_configuration_is_validated(tmp_path):
    run_case(tmp_path, '''
        from modules.logger_module import _MAX_LOG_BYTES, _LOG_BACKUPS, BotLogger, _runtime
        assert _MAX_LOG_BYTES==3*1024*1024 and _LOG_BACKUPS==2
        BotLogger(console_log=False)
        _runtime().stop()
    ''', BOT_LOG_MAX_BYTES='invalid', BOT_LOG_BACKUPS='invalid')


def test_append_and_rotation_are_bounded(tmp_path):
    run_case(tmp_path, '''
        from modules.logger_module import BotLogger, _runtime
        from modules.runtime_paths import LOG_DIR
        from pathlib import Path
        LOG_DIR.mkdir(parents=True,exist_ok=True)
        (LOG_DIR/'bot.log').write_text('PREEXISTING\\n')
        log=BotLogger(console_log=False)
        log.log_error('kept')
        _runtime().queue.join()
        assert (LOG_DIR/'bot.log').read_text().startswith('PREEXISTING')
        # Pace only the TEST generator so the audit-volume/rotation assertion
        # measures actual writing rather than intentionally dropped overload.
        for base in range(0,24000,500):
            for i in range(base,base+500):
                log.log_deleted_message(1,'u',-2,'g','x'*500,'spam',i)
                log.log_action('WARN',1,-2,'y'*400)
            _runtime().queue.join(); _runtime().deleted_queue.join()
        _runtime().stop()
        for name in ['bot.log','deleted_messages.log','actions.log']:
            files=list(LOG_DIR.glob(name+'*'))
            assert 2 <= len(files) <= 2, (name, files)
            assert all(f.stat().st_size <= 1024*1024 for f in files)
        assert log.dropped_records()==0
    ''', BOT_LOG_MAX_BYTES=1024*1024, BOT_LOG_BACKUPS=1)
