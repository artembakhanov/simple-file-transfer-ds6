import json
import os
import types
import socket
import selectors
from enum import Enum
from threading import Thread
import glob

# Constants
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8800
BUFFER_SIZE = 2048
DIRECTORY = "./server_files"
META = "./server_meta"
RED = "\u001b[31;1m"
GREEN = "\u001b[32;1m"
YELLOW = "\u001b[33;1m"
RESET = "\u001b[0m"


class ClientState(Enum):
    """
    Client state. Used for selector.
    """
    NEW = (0, True)  # client is writing
    GOT_FILE_NAME = (1, False)  # server is writing
    TRANSMITTING = (2, True)  # client is writing
    FINISHED_TRANSMITTING = (3, False)  # no one is writing


clients = {}  # clients dict. (addr, port) -> client(addr, outb, state, file, file_size, file_got, retry)


def remove_client(addr):
    """Remove a client from a list"""
    global clients
    del clients[addr]


class Conductor(Thread):
    def __init__(self, selector):
        super().__init__(daemon=True)
        self.selector = selector
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def run(self):
        next_name = 1

        self.sock.bind((SERVER_HOST, SERVER_PORT))
        self.sock.listen()
        while True:
            con, addr = self.sock.accept()

            # not blocking
            con.setblocking(False)
            # new client - addr - unique identifier
            client = types.SimpleNamespace(addr=addr, outb=b'', state=ClientState.NEW, file=None, file_size=None,
                                           file_got=0, retry=0)
            clients[addr] = client
            print(f"{GREEN}[+] {client.addr} - Connected{RESET}")

            events = selectors.EVENT_READ | selectors.EVENT_WRITE
            # register this socket to selector for both READ and WRITE events
            self.selector.register(con, events, data=client)


class MultiClientServer(Thread):
    def __init__(self, selector):
        super().__init__(daemon=True)
        self.selector = selector

    def _get_file_info(self, sock, client):
        """
        Receive information about file: size and file name
        """
        data = sock.recv(BUFFER_SIZE)

        # get file information
        file_info = json.loads(data.decode())
        file_name = file_info['file_name']

        # get extension and
        file_name_parts = file_name.rsplit(".", 1)

        # if no extension
        if len(file_name_parts) == 1:
            file_name_parts.append("")
        # add dot to the extension name
        else:
            file_name_parts[1] = "." + file_name_parts[1]

        # for each file there is a meta file
        # it stores the counter
        meta_file = f"{META}/{file_name}.meta"
        if not os.path.isfile(meta_file):
            # file is new
            file_counter = 0
            server_file_name = file_name
        else:
            # file is not new
            with open(meta_file) as f:
                file_counter = int(f.read())
            # create new copy name
            server_file_name = f"{file_name_parts[0]}_copy{file_counter}{file_name_parts[1]}"
        with open(meta_file, 'w') as f:
            # write next counter
            f.write(str(file_counter + 1))

        # answer to the client that the operation is successful
        # put the answer to the box. it will be sent later
        client.outb = json.dumps({"success": True, "copy": file_counter != 1, "server_file_name": server_file_name,
                                  "message": "If you see this message everything is fine:)"}).encode()

        # update client information
        client.file = open(f"{DIRECTORY}/{server_file_name}", "wb")
        client.state = ClientState.GOT_FILE_NAME
        client.file_size = file_info['size']
        client.got = 0

        print(f"{GREEN}[i] {client.addr} - New file: {file_name}:{server_file_name}{RESET}")

    def _get_file_part(self, sock, client):
        """
        Get a part of the file.
        Trigger only if the client in the TRANSMITTING state.
        """

        # if the file is already fully transferred
        if client.got >= client.file_size:
            self._close(sock, client)
            return

        # get file part
        data = sock.recv(BUFFER_SIZE)

        # no data?
        if not data:
            if client.retry > 10:
                # most probably the client is down
                self._close(sock, client)
                return
            # give a chance to the client if it did not send any data
            print(f"{RED}[!] {client.addr} - data packet is empty; retries left {10 - client.retry}{RESET}")
            client.retry += 1
            return

        # update client information
        client.retry = 0
        client.got += len(data)
        client.file.write(data)

    def _close(self, sock, client):
        """
        Remove a client and close the connection with it.
        """

        # close file and remove the client
        client.file.close()
        remove_client(client.addr)
        # don't forget to unregister this socket
        self.selector.unregister(sock)
        sock.close()

        print(f"{GREEN}[-] {client.addr} - Disconnected{RESET}")

    def _read(self, sock, client):
        """
        Read action. Called if read is possible for a current client.
        """
        if client.state == ClientState.NEW:
            self._get_file_info(sock, client)
        elif client.state == ClientState.TRANSMITTING:
            self._get_file_part(sock, client)

    def _write(self, sock, client):
        """
        Read action. Called if read is possible for a current client.
        """
        if client.state == ClientState.GOT_FILE_NAME:
            # if the file name is got then we need to send a confirmation message
            # and start waiting for file transferring
            sock.send(client.outb)
            client.state = ClientState.TRANSMITTING

    def run(self):
        while True:
            # get sockets which are ready for smth (READ or WRITE)
            events = self.selector.select(timeout=None)
            for key, mask in events:
                sock = key.fileobj
                client = key.data
                # if there is something to READ and the client is in read state
                if mask & selectors.EVENT_READ and client.state.value[1]:
                    self._read(sock, client)

                # if the client ready to receive some data and the client is in the write state
                if mask & selectors.EVENT_WRITE and not client.state.value[1]:
                    self._write(sock, client)


def main():
    sel = selectors.DefaultSelector()
    MultiClientServer(sel).start()
    conductor = Conductor(sel)
    conductor.start()
    conductor.join()


if __name__ == "__main__":
    main()
