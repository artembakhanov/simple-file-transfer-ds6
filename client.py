import argparse
import json
import os
import ntpath
import socket
import re
import time
import signal

# Constants
HOST_REGEX = "^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$"
PORT_REGEX = "^()([1-9]|[1-5]?[0-9]{2,4}|6[1-4][0-9]{3}|65[1-4][0-9]{2}|655[1-2][0-9]|6553[1-5])$"
RED = "\u001b[31;1m"
GREEN = "\u001b[32;1m"
YELLOW = "\u001b[33;1m"
RESET = "\u001b[0m"
BUFF_SIZE = 2048


def signal_handler(sig, frame):
    try:
        global sock
        sock.close()
    except:
        pass
    exit(0)


# Signals handlers for graceful exiting
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGQUIT, signal_handler)


# Progress Class
class Progress:
    message = f"\r{YELLOW}{{name}} |{{bar}}| Progress: {{progress:.2f}}%{RESET}"
    bar_size = 25
    update_eta_rate = 100

    def __init__(self, total, progress_name):
        if total <= 0:
            raise ValueError("total should be more than 0")

        self.last_time = [time.time()] * self.update_eta_rate
        self.total = total # maximum progress
        self.progress = 0 # current progress
        self.progress_name = progress_name # the name of the progress task
        self.eta_counter = -1

        # Start message
        print(
            self.message.format(name=self.progress_name, bar='█' * 0 + ' ' * self.bar_size, progress=0),
            end='')

    def update(self, new_progress):
        """
        Update the progress bar
        :param new_progress: amount of new done progress since the previous update
        """
        self.eta_counter = (self.eta_counter + 1) % self.update_eta_rate
        now = time.time()
        self.last_time[self.eta_counter] = now
        self.progress += new_progress

        # Calculate the number of bars and spaces for the progress bar
        bars = int(self.progress / self.total * self.bar_size)
        spaces = self.bar_size - bars

        print(self.message.format(name=self.progress_name,
                                  bar='█' * bars + " " * spaces,
                                  progress=min(100, (self.progress / self.total) * 100)), end='')
        if self.progress >= self.total:
            print(f"\r{GREEN}{self.progress_name} done!{RESET}\033[K")


# Parse arguments
parser = argparse.ArgumentParser(description="Client script for sending files to the server.\n"
                                             "Made by Artem Bakhanov as a DS lab assignment.")

parser.add_argument("file_name", help="path to the file to send", )
parser.add_argument("host", help="ip address or host address of the server")
parser.add_argument("port", help="port of the server script", type=int)

# Check arguments
args = parser.parse_args()

if not os.path.isfile(args.file_name):
    parser.error(f"{RED}File does not exist or file path is wrong{RESET}")

if not re.match(HOST_REGEX, args.host):
    parser.error(f"{RED}Not valid host name{RESET}")

if not re.match(PORT_REGEX, str(args.port)):
    parser.error(f"{RED}Not valid port{RESET}")

# Get information
file_name = args.file_name
file_size = os.path.getsize(file_name)
host = args.host
port = args.port

# Get the base name
# It will send file name without folders (directories)
file_basename = ntpath.basename(args.file_name)

# Create socket
print(f"{YELLOW}Connecting to {host}:{port}{RESET}", end='')
sock = socket.socket()
sock.connect((host, port))
print(f"\r{GREEN}Connected to {host}:{port}!{RESET}")

# Start transmitting file
print(f"{YELLOW}Sending file info...{RESET}", end='')
sock.sendall(f'{{"file_name": "{file_basename}", "size": {file_size}}}'.encode())

# Get the confirmation message
file_info = json.loads(sock.recv(BUFF_SIZE).decode())
print(f"\r{GREEN}File name on server: {file_info['server_file_name']}.{RESET}\n"
      f"{YELLOW}Starting transmitting the file...")

# Create progress bar
progress = Progress(file_size, "Sending file")

# Send file
with open(file_name, 'rb') as f:
    payload = f.read(BUFF_SIZE)
    while payload:
        sock.send(payload)
        progress.update(BUFF_SIZE)
        payload = f.read(BUFF_SIZE)
print(f"\033[F\033[F{GREEN}Finished{RESET}\033[K")

# Close the connection and exit
sock.close()
print(f"{GREEN}Connection closed{RESET}")
