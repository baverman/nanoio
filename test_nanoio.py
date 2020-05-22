import socket
from functools import wraps

import pytest
import threading
from nanoio import (Loop, run, recv, sendall, current_loop, send, spawn,
                    recv_until, accept)


class Error(Exception):
    pass


def timeout(duration=1):
    def decorator(fn):
        @wraps(fn)
        def inner(*args, **kwargs):
            error = None

            def worker():
                nonlocal error
                try:
                    fn(*args, **kwargs)
                except Exception as e:
                    error = e

            t = threading.Thread(target=worker, daemon=True)
            t.start()
            t.join(duration)
            assert not t.is_alive()
            if error:
                raise error
        return inner
    return  decorator


@timeout()
def test_simple():
    async def boo(do_raise):
        if do_raise:
            raise Error()
        else:
            return 10

    assert run(boo(False)) == 10

    with pytest.raises(Error):
        run(boo(True))


@timeout()
def test_wait_forever():
    loop = Loop()
    result = []

    async def foo(value):
        result.append(value)
        raise Exception('Boo')

    async def boo(value):
        await spawn(foo(value))
        result.append(await current_loop())

    loop.spawn(boo(1))
    loop.spawn(boo(2))
    loop.run()
    assert result == [loop, loop, 1, 2]


@timeout()
def test_ping():
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)
    result = []

    async def a_coro():
        await sendall(a, b'aaaa')
        result.append(await recv(a, 1024))
        result.append(await recv(a, 1024))

    async def b_coro():
        data = await recv(b, 1024)
        await send(b, data)
        b.shutdown(socket.SHUT_WR)

    loop = Loop()
    loop.spawn(a_coro())
    loop.spawn(b_coro())
    loop.run()

    assert result == [b'aaaa', b'']


@timeout()
def test_recv_until():
    a, b = socket.socketpair()
    a.setblocking(False)
    b.setblocking(False)

    async def coro():
        return await recv_until(b, b'-end-', 100, 1)

    a.sendall(b'aaaa-end-bbb')
    a.shutdown(socket.SHUT_WR)

    result = run(coro())
    assert result == (b'aaaa-end-', 4)

    result = run(coro())
    assert result == (b'bbb', -1)


@timeout()
def test_accept():
    loop = Loop()

    a = socket.socket()
    a.bind(('127.0.0.1', 0))
    a.listen(5)
    a.setblocking(False)

    async def handle():
        client, _addr = await accept(a)
        client.setblocking(False)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 16384)
        await sendall(client, b'1' * (1 << 17))
        client.shutdown(socket.SHUT_WR)

    async def reader():
        b = socket.create_connection(a.getsockname())
        b.setblocking(False)
        size = 0
        while True:
            data = await recv(b, 16384)
            if not data:
                break
            size += len(data)
        return size

    loop.spawn(handle())
    result = loop.run(reader())
    assert result == 1 << 17
