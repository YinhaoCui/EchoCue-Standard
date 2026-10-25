"""Keep-alive HTTP(S) connections for streaming model requests.

urllib opens a new TCP + TLS connection for every request and sends
``Connection: close``.  For overseas APIs that handshake alone costs a few
hundred milliseconds before the first token.  This module keeps finished
connections open and lets the UI pre-open one while the user is speaking.

Requests fall back to ``urllib.request.urlopen`` when a proxy applies (so
system/env proxy settings keep working) or when urlopen has been replaced
(tests patch it).
"""
from contextlib import contextmanager
import http.client
import io
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

def _urlopen_replaced():
    current = urllib.request.urlopen
    return current is not _URLOPEN or getattr(current, '__module__', None) != 'urllib.request'


_URLOPEN = urllib.request.urlopen
_lock = threading.Lock()
_idle = {}          # (scheme, host, port) -> [(connection, idle_since)]
_warming = set()
_context = ssl.create_default_context()
MAX_IDLE = 4
# Errors raised when a reused keep-alive socket was already closed by the server
# before it received our request; retrying once on a fresh connection is safe.
STALE_ERRORS = (http.client.RemoteDisconnected, http.client.BadStatusLine,
                ConnectionResetError, ConnectionAbortedError, BrokenPipeError)


def _target(url):
    parts = urllib.parse.urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname:
        return None
    proxies = urllib.request.getproxies()
    if (proxies.get(parts.scheme) or proxies.get('all')) and not urllib.request.proxy_bypass(parts.hostname):
        return None
    port = parts.port or (443 if parts.scheme == 'https' else 80)
    path = (parts.path or '/') + ('?' + parts.query if parts.query else '')
    return (parts.scheme, parts.hostname, port), path


def _new(key, timeout):
    scheme, host, port = key
    if scheme == 'https':
        return http.client.HTTPSConnection(host, port, timeout=timeout, context=_context)
    return http.client.HTTPConnection(host, port, timeout=timeout)


def _take(key):
    with _lock:
        pool = _idle.get(key) or []
        while pool:
            conn, _ = pool.pop()          # newest first
            if conn.sock is not None:
                return conn
            conn.close()
    return None


def _give(key, conn):
    with _lock:
        pool = _idle.setdefault(key, [])
        if len(pool) < MAX_IDLE and conn.sock is not None:
            pool.append((conn, time.monotonic()))
            return
    conn.close()


def _send(key, path, request, timeout):
    headers = {'User-Agent': 'audio-answer', **dict(request.header_items())}
    for attempt in (0, 1):
        conn = _take(key) if attempt == 0 else None
        reused = conn is not None
        if conn is None:
            conn = _new(key, timeout)
        else:
            conn.timeout = timeout
            conn.sock.settimeout(timeout)
        try:
            conn.request(request.get_method(), path, body=request.data, headers=headers)
            return conn, conn.getresponse()
        except STALE_ERRORS:
            conn.close()
            if not reused:
                raise
        except BaseException:
            conn.close()
            raise


@contextmanager
def urlopen(request, timeout):
    """Drop-in for ``urllib.request.urlopen`` used as a context manager."""
    target = None
    if not _urlopen_replaced() and isinstance(request, urllib.request.Request):
        target = _target(request.full_url)
    if target is None:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            yield response
        return
    key, path = target
    try:
        conn, response = _send(key, path, request, timeout)
    except (OSError, http.client.HTTPException) as exc:
        raise urllib.error.URLError(exc) from None
    reusable = False
    try:
        if response.status >= 300:
            body = response.read()
            raise urllib.error.HTTPError(request.full_url, response.status, response.reason,
                                         response.headers, io.BytesIO(body))
        yield response
        # Only fully consumed responses leave the socket in a reusable state.
        reusable = response.isclosed() and not response.will_close
    finally:
        if reusable:
            _give(key, conn)
        else:
            conn.close()


def warm(url, max_age=30, count=1):
    """Open a connection in the background unless a recent idle one exists."""
    try:
        target = _target(url)
    except ValueError:
        return False
    if target is None:
        return False
    key = target[0]
    now = time.monotonic()
    with _lock:
        ready=sum(c.sock is not None and now-s<max_age for c,s in _idle.get(key,[]))
        if key in _warming or ready>=count:
            return False
        _warming.add(key)

    def run():
        try:
            conn = _new(key, 10)
            conn.connect()
            with _lock:
                # Old idle sockets are likely to have been dropped by the server.
                pool = _idle.setdefault(key, [])
                for old, stamp in [item for item in pool if time.monotonic() - item[1] >= max_age]:
                    pool.remove((old, stamp))
                    old.close()
            _give(key, conn)
            for _ in range(max(0,min(count,MAX_IDLE)-ready-1)):
                extra=_new(key,10)
                try:extra.connect();_give(key,extra)
                except Exception:extra.close();break
        except Exception:
            pass
        finally:
            with _lock:
                _warming.discard(key)
    threading.Thread(target=run, daemon=True).start()
    return True


def close_all():
    with _lock:
        pools = list(_idle.values())
        _idle.clear()
    for pool in pools:
        for conn, _ in pool:
            conn.close()
