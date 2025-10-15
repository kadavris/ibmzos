"""
This module is a toolset interacting with 3270 terminal emulator
by https://x3270.bgp.nu/ team. You need to enable scripting port for it to work.
Written by Andrej Pakhutin (pakhutin@gmail.com)
"""
import sys
import socket
import re
from typing import List, Tuple, Optional

# EBCDIC to ASCII. This is very simple approximation, mostly for the \w stuff to work
E2A = [
    #  0     1     2     3     4     5     6     7     8     9     a     b     c     d     e     f
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,  # 00
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,  # 10
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0xf8, 0x2f,  # 20
    0xf8, 0xf8, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0xf8, 0x3f,  # 30
    0x20, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0x2e, 0x3c, 0x28, 0x2b, 0x7c,  # 40
    0x26, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0x21, 0x24, 0x2a, 0x29, 0x3b, 0x5e,  # 50
    0x2d, 0x2f, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0x7c, 0x2c, 0x25, 0x5f, 0x3e, 0x3f,  # 60
    0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0x3a, 0x23, 0x40, 0x27, 0x3d, 0x22,  # 70
    0xf8, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8,  # 80
    0xf8, 0x6a, 0x6b, 0x6c, 0x6d, 0x6e, 0x6f, 0x70, 0x71, 0x72, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8,  # 90
    0xf8, 0x7e, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79, 0x7a, 0xf8, 0xf8, 0xf8, 0x5b, 0xf8, 0xf8,  # a0
    0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0x5d, 0xf8, 0xf8,  # b0
    0x7b, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8,  # c0
    0x7d, 0x4a, 0x4b, 0x4c, 0x4d, 0x4e, 0x4f, 0x50, 0x51, 0x52, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8,  # d0
    0x5c, 0xf8, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5a, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8,  # e0
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8, 0xf8   # f0
]


def e2a(e: str) -> str:
    """
    Convert EBCDIC string to ASCII
    :param e: input
    :return: ASCII string
    """
    a = ""
    for c in e:
        a += E2A[ord(c)]

    return a


#####################################################################
class x3270Script:

    def debug_level(self, level: int) -> None:
        if level < 0:
            self.debug = 0
        elif level > 9:
            self.debug = 9
        else:
            self.debug = level

    #####################################################################
    def connected(self) -> bool:
        if not self.sock:
            return False

        try:
            self.sock.sendall(b"\r\n")
        except socket.error:
            return False

        return True

    #####################################################################
    def connect(self, port: int = 3270, host: str = '127.0.0.1') -> bool:
        """
        Connects to terminal scription port
        """
        self.host = host
        self.port = port
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((host, port))
        except socket.error as se:
            print(f"x3270 Connection error to {host}:{port} - {se}", file=sys.stderr)
            return False

        if self.debug > 0:
            print(". x3270: Connected")

        return True

    # --- Low-Level Communication Functions ---
    #####################################################################
    def send_line(self, cmd: str) -> bool:
        """
        Sends a command string to the terminal with EOL at the end.
        :param cmd: command text
        :return: bool: success
        """
        if not self.sock:
            print("!ERROR: x3270: socket is not connected yet", file=sys.stderr)
            return False

        b = cmd.encode('ascii') + b"\r\n"
        try:
            self.sock.sendall(b)
        except socket.error as se:
            print(f"!ERROR: x3270: socket: {se}", file=sys.stderr)
            return False

        if self.debug > 4:
            # Use repr() to show control characters clearly
            print("> x3270 sent: " + repr(b.decode('ascii').strip()))

        return True

    #####################################################################
    def read_answer(self) -> List[str]:
        """
        Return terminal's response as a list of lines.
        List ends with 'ok' or 'error'.
        :return: list of lines
        """
        answer: List[str] = []
        line = b''

        if not self.sock:
            print("!ERROR: x3270: socket is not connected yet", file=sys.stderr)
            return answer

        # Read continuously until plain 'ok' or 'error' is received
        while True:
            try:
                # Read one byte at a time until EOL ([CR]LF) is found
                c = self.sock.recv(1)  # Should be mildly ineffective, but we'll see
            except (socket.error, EOFError) as se:
                print(f"!ERROR: x3270: socket: {se}", file=sys.stderr)
                # Add partial line if it exists before returning
                if line:
                    answer.append(line.decode('ascii', errors='ignore'))
                return answer

            if c == b'\x0d':  # CR
                continue

            if c != b'\x0a':  # not LF (end of line)
                line += c
                continue

            # got a complete line here. May be empty
            decoded_line = line.decode('ascii', errors='ignore')

            if decoded_line[0:6] == "data: ":
                decoded_line = decoded_line[6:]
                answer.append(decoded_line)

                if self.debug >= 5:
                    print("<<<x3270: ", decoded_line)
            else:  # status line
                if decoded_line == "ok" or decoded_line == "error":
                    if self.debug:
                        print(f"< x3270 terminal reply status: '{decoded_line}'")

                    answer.append(decoded_line)
                    return answer
                else:
                    print(f"<? x3270 unexpected terminal reply line: '{decoded_line}'")

            line = b''

        return answer

    #####################################################################
    def wait_for_unlock(self) -> None:
        """
        Waits for the 3270 keyboard to be unlocked.
        :return: None
        """
        self.send_line("Wait(Unlock)")

        a = self.read_answer()

        if a and a[-1] != 'ok':
            print("!x3270 Error waiting for unlock. The response is: ", file=sys.stderr)
            for r in a:
                print(">", r, file=sys.stderr)

    #####################################################################
    def script_cmd(self, cmd: str) -> str:
        """
        Sends a simple script command to the terminal and returns the status ('ok' or 'error').
        :param cmd: The command text to send to the terminal.
        :return: terminal's or remote answer
        """
        if self.debug:
            print(f". x3270 simple_cmd('{cmd}')")

        self.wait_for_unlock()
        self.send_line(cmd)
        a = self.read_answer()

        return a[-1] if a else 'error'

    #####################################################################
    def get_screen_size(self) -> Tuple[int, int]:
        """
        Queries and return screen rows and cols.
        :return: tuple: rows, cols or -1,-1 in case of error
        """
        a = self.script_cmd("Query(ScreenCurSize)")

        r = -1
        c = -1
        if a and a[-1] == 'ok':
            # The first data line contains 'data: <rows> <cols>'
            match = re.search(r'\s*(\d+)\s+(\d+)', a[0])
            if match:
                r, c = int(match.group(1)), int(match.group(2))
                if self.debug:
                    print(f". x3270 Screen size: {r}x{c}")
            else:
                print(f"x3270: Error parsing screen size response: {a[0]}", file=sys.stderr)
                return r, c
        else:
            print("x3270: Error getting screen size.", file=sys.stderr)
            return r, c

        return r, c

    #####################################################################
    # --- Advanced functions ---
    #####################################################################
    def get_screen_content(self) -> list[str]:
        """
        Retrieves the screen content and return as a list of strings.
        :return: list[str]. Empty in case of error
        """
        screen = []
        r, c = self.get_screen_size()
        if r == -1:
            return screen

        self.send_line("Ascii")

        a = self.read_answer()

        if not a or a[-1] != 'ok':
            return screen

        # Map and clean up the encasing dots and spaces from the 3270 script output
        for line in a[:-1]:  # Exclude the 'ok' status line
            match = re.match(r'^\s*\.+\s(.+?)\s*\.+\s*$', line)
            if match:
                screen.append(match.group(1).rstrip())
            else:
                # Fallback: keep the line
                screen.append(line)

        return screen

    #####################################################################
    def find_text(self, txt: str) -> Tuple[int, int]:
        """
        Will find (regexp) data on screen, returning row,col tuple of the beginning
        -1, -1 if not found
        """
        screen = self.get_screen_content()
        r, c = self.get_screen_size()

        from_zero_col = True if txt[0] == '^' else False

        y = 0
        while y != r:
            if from_zero_col:
                if re.search(txt,  screen[y]):
                    return y, 0
            else:
                if m := re.search(r'(.+?)' + txt, screen[y]):
                    return y, len(m.group(0))

            y += 1

        return -1, -1

    #####################################################################
    def field_fill(self, x: int, y: int, content: str) -> Optional[str]:
        """
        Will fill a screen field with data
        :param x: screen X (0-based)
        :param y: screen Y (0-based)
        :param content: string to put
        :return: old value
        """
        r, c = self.get_screen_size()
        if r == -1 or c < x or x < 0 or r < y or y < 0:
            return None

        self.script_cmd(f"MoveCursor({x},{y})")
        old_val = self.script_cmd("AsciiField")
        self.script_cmd(f'String "{content}"')

        return old_val

    #####################################################################
    def __init__(self, host, port):
        self.sock: socket = None
        self.host = ''
        self.port = -1
        self.debug: int = 0
        self.connect(port, host)


#####################################################################
if __name__ == "__main__":
    print("x3270scripting: This module should only be imported")
    exit(1)
