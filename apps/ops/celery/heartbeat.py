from pathlib import Path

from celery.signals import heartbeat_sent, worker_ready, worker_shutdown

# 产品改造：心跳目录支持 MAXKB_TMP_DIR 覆盖；容器外回落 apps/.runtime/tmp（绝对路径）
_TMP_ROOT = Path(
    __import__('os').environ.get('MAXKB_TMP_DIR')
    or (Path('/opt/maxkb-app/tmp') if Path('/opt/maxkb-app').is_dir()
        else Path(__file__).resolve().parents[2] / '.runtime' / 'tmp')
)
_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def _worker_path(kind: str, worker_name: str) -> Path:
    return _TMP_ROOT / 'worker_{}_{}'.format(kind, worker_name)


@heartbeat_sent.connect
def heartbeat(sender, **kwargs):
    worker_name = sender.eventer.hostname.split('@')[0]
    _worker_path('heartbeat', worker_name).touch()


@worker_ready.connect
def worker_ready(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    _worker_path('ready', worker_name).touch()


@worker_shutdown.connect
def worker_shutdown(sender, **kwargs):
    worker_name = sender.hostname.split('@')[0]
    for signal in ['ready', 'heartbeat']:
        _worker_path(signal, worker_name).unlink(missing_ok=True)
