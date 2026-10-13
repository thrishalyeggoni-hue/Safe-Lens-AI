"""Real ClamAV, private temporary socket, one scan at a time, idle shutdown."""
import asyncio
from contextlib import suppress
import os
from pathlib import Path
import re
import shutil
import struct
import tempfile
import time

SCAN_LOCK=asyncio.Lock()
_process=None
_folder=None
_socket=None
_idle=None


def daemon_binary():
    binary=shutil.which('clamd')
    if binary:return binary
    scanner=shutil.which('clamscan')
    candidate=Path(scanner).resolve().parent.parent/'sbin/clamd' if scanner else None
    return str(candidate) if candidate and candidate.is_file() else None


async def _stop_unlocked():
    global _process,_folder,_socket
    if _process and _process.returncode is None:
        _process.terminate()
        try:await asyncio.wait_for(_process.wait(),3)
        except TimeoutError:_process.kill();await _process.wait()
    _process=None;_socket=None
    if _folder:_folder.cleanup();_folder=None


async def stop_scanner():
    global _idle
    if _idle:
        _idle.cancel()
        with suppress(asyncio.CancelledError):await _idle
        _idle=None
    async with SCAN_LOCK:await _stop_unlocked()


async def retire_idle():
    await asyncio.sleep(30)
    async with SCAN_LOCK:await _stop_unlocked()


async def command(value):
    reader,writer=await asyncio.open_unix_connection(str(_socket))
    try:
        writer.write(b'z'+value+b'\0');await writer.drain()
        return (await reader.readuntil(b'\0')).decode('utf-8',errors='replace').strip('\0\n')
    finally:writer.close();await writer.wait_closed()


async def start_daemon():
    global _process,_folder,_socket
    if _process and _process.returncode is None:return None
    binary=daemon_binary()
    if not binary:return 'ClamAV daemon is unavailable'
    database=Path(os.environ.get('CLAMAV_DATABASE_DIR','/opt/homebrew/var/lib/clamav' if Path('/opt/homebrew/var/lib/clamav').is_dir() else '/var/lib/clamav'))
    daily=[p for p in database.glob('daily.*') if p.suffix in ('.cvd','.cld')]
    if not daily or time.time()-max(p.stat().st_mtime for p in daily)>7*86400:return 'ClamAV daily signatures are missing or older than seven days; run freshclam'
    _folder=tempfile.TemporaryDirectory(prefix='safelens-clam-');root=Path(_folder.name);_socket=root/'scanner.sock';config=root/'clamd.conf'
    config.write_text(f'Foreground yes\nLocalSocket {_socket}\nLocalSocketMode 600\nDatabaseDirectory {database}\nMaxThreads 1\nMaxQueue 2\nStreamMaxLength 20M\nMaxFileSize 20M\nMaxScanSize 50M\nMaxScanTime 10000\nMaxRecursion 8\nMaxFiles 128\nAlertExceedsMax yes\nLogClean no\n')
    _process=await asyncio.create_subprocess_exec(binary,'--config-file',str(config),stdout=asyncio.subprocess.DEVNULL,stderr=asyncio.subprocess.DEVNULL)
    try:
        async with asyncio.timeout(30):
            while True:
                if _process.returncode is not None:raise RuntimeError('Scanner startup failed')
                if _socket.exists():
                    try:
                        if await command(b'PING')=='PONG':return None
                    except (OSError,asyncio.IncompleteReadError):pass
                await asyncio.sleep(.1)
    except (TimeoutError,RuntimeError):await _stop_unlocked();return 'ClamAV daemon failed to load its signatures within 30 seconds'
    except asyncio.CancelledError:await _stop_unlocked();raise


def scan_result(reply,engine_version=None):
    if reply.endswith(': OK'):return {'status':'clean','engine':'ClamAV','version':engine_version,'signature_match':None,'detail':'No configured known malware signature was detected. This is not a safety guarantee.'}
    match=re.search(r': ([^\r\n]{1,200}) FOUND',reply)
    if match:
        signature=match.group(1);limited='Heuristics.Limits.' in signature
        return {'status':'limited' if limited else 'infected','engine':'ClamAV','version':engine_version,'signature_match':signature,'detail':'Scanner limits prevented full inspection' if limited else 'Actual ClamAV signature matched the upload'}
    return {'status':'failed','engine':'ClamAV','version':engine_version,'signature_match':None,'detail':'ClamAV scan failed; no clean result inferred'}


async def scan_document(path):
    global _idle
    if not daemon_binary():return {'status':'unavailable','engine':'ClamAV','detail':'ClamAV daemon is not installed; install the full ClamAV package','signature_match':None}
    async with SCAN_LOCK:
        if _idle:
            _idle.cancel()
            with suppress(asyncio.CancelledError):await _idle
            _idle=None
        error=await start_daemon()
        if error:return {'status':'unavailable','engine':'ClamAV','signature_match':None,'detail':error}
        writer=None
        try:
            async with asyncio.timeout(30):
                engine_version=await command(b'VERSION')
                reader,writer=await asyncio.open_unix_connection(str(_socket));writer.write(b'zINSTREAM\0')
                with open(path,'rb') as file:
                    while chunk:=file.read(65536):
                        writer.write(struct.pack('!I',len(chunk))+chunk);await writer.drain()
                writer.write(struct.pack('!I',0));await writer.drain()
                reply=(await reader.readuntil(b'\0')).decode('utf-8',errors='replace').strip('\0\n')
                return {**scan_result(reply,engine_version),'transport':'Private temporary Unix socket, INSTREAM; original upload bytes','idle_shutdown_seconds':30}
        except (TimeoutError,OSError,asyncio.IncompleteReadError,asyncio.LimitOverrunError):return {'status':'failed','engine':'ClamAV','signature_match':None,'detail':'ClamAV scan failed or exceeded 30 seconds'}
        finally:
            if writer:writer.close();await writer.wait_closed()
            _idle=asyncio.create_task(retire_idle())
