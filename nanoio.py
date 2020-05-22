import types
import logging
import select

from collections import deque
from ssl import SSLWantReadError, SSLWantWriteError

TRAP_IO_WAIT = 0x01
TRAP_RESCHEDULE = 0x02
TRAP_IM_MASK = 0x10
TRAP_GET_LOOP = TRAP_IM_MASK + 0x01

WAIT_READ = 1
WAIT_WRITE = 2

log = logging.getLogger('nanoio')


@types.coroutine
def wait_io(sock, wait, fn, *args):
    yield TRAP_RESCHEDULE, None
    while True:
        try:
            return fn(*args)
        except SSLWantWriteError:  # pragma: no cover
            yield TRAP_IO_WAIT, (sock, WAIT_WRITE)
        except SSLWantReadError:  # pragma: no cover
            yield TRAP_IO_WAIT, (sock, WAIT_READ)
        except (BlockingIOError, InterruptedError):
            yield TRAP_IO_WAIT, (sock, wait)


@types.coroutine
def current_loop():
    return (yield TRAP_GET_LOOP, None)


def recv(sock, size, flags=0):
    return wait_io(sock, WAIT_READ, sock.recv, size, flags)


def send(sock, data, flags=0):
    return wait_io(sock, WAIT_WRITE, sock.send, data, flags)


def accept(sock):
    return wait_io(sock, WAIT_READ, sock.accept)


async def spawn(coro):
    return (await current_loop()).spawn(coro)


async def sendall(sock, data, flags=0):
    mv = memoryview(data)
    while mv:
        size = await wait_io(sock, WAIT_WRITE, sock.send, mv, flags)
        mv = mv[size:]


async def recv_until(sock, sentinel, max_size=65536, read_size=65536):
    size = 0
    buf = bytearray(max_size + read_size)
    mv = memoryview(buf)
    while size < max_size:
        count = await wait_io(sock, WAIT_READ, sock.recv_into, mv[size:], read_size)
        if not count:
            pos = -1
            break
        size += count
        pos = buf.find(sentinel, max(0, size-count-len(sentinel)), size)
        if pos >= 0:
            break
    return buf[:size], pos


def run(coro):
    loop = Loop()
    return loop.run(coro)


class Loop:
    def __init__(self):
        self.tasks = deque()

    def run(self, main_coro=None):
        tasks = self.tasks
        poptask = tasks.popleft
        appendtask = tasks.append

        read_events = {}
        write_events = {}
        EVENTS = [None, read_events, write_events]

        if main_coro:
            appendtask(main_coro)

        while True:
            while tasks:
                current = poptask()
                try:
                    t, args = current.send(None)
                    while t & TRAP_IM_MASK:
                        if t == TRAP_GET_LOOP:
                            t, args = current.send(self)
                        else:  # pragma: no cover
                            raise Exception('Invalid trap {}'.format(t))
                except StopIteration as e:
                    if main_coro and current is main_coro:
                        return e.value
                except Exception:
                    if main_coro and current is main_coro:
                        raise
                    else:
                        log.exception('Unhandled coro error')
                else:
                    if t == TRAP_IO_WAIT:
                        EVENTS[args[1]][args[0]] = current
                    elif t == TRAP_RESCHEDULE:
                        appendtask(current)
                    else:  # pragma: no cover
                        raise Exception('Invalid trap {}'.format(t))

            event_cnt = len(read_events) + len(write_events)
            if not event_cnt:
                break

            r, w, _ = select.select(read_events, write_events, [])
            for it in r:
                appendtask(read_events.pop(it))
            for it in w:
                appendtask(write_events.pop(it))

    def spawn(self, coro):
        self.tasks.append(coro)
        return coro
