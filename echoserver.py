import socket
import nanoio


async def handle(client, addr):
    while True:
        data = await nanoio.recv(client, 200)
        if not data:
            break

        await nanoio.send(client, data)


async def main():
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('127.0.0.1', 25000))
    sock.listen(100)
    sock.setblocking(False)
    while True:
        client, addr = await nanoio.accept(sock)
        client.setblocking(False)
        await nanoio.spawn(handle(client, addr))


if __name__ == '__main__':
    try:
        nanoio.run(main())
    except KeyboardInterrupt:
        pass
