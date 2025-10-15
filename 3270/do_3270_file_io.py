"""
This program is a toolset interacting with 3270 terminal emulator
by https://x3270.bgp.nu/ team. You need to enable scripting port for it to work.
The main function is to allow mundane file transfer from/to EDIT and BROWSE
ISPF sessions, because of BOFHs who disable standard and easily audited means
to celebrate security-through-obscurity centennial event.
Written by Andrej Pakhutin (pakhutin@gmail.com)
"""
import os.path
import sys
import argparse
import re
import time
from x3270scripting import x3270Script
from x3270ispf import x3270ISPF
from typing import List, Tuple, Optional


#####################################################################
def bail_out(exit_code: int) -> None:
    """
    Cleanly close all sensitive things, then exit. In the future may do something good.
    :param exit_code: system exit code
    :return: None
    """
    sys.exit(exit_code)


#####################################################################
def ask_user(header: str, **choices) -> str:
    """
    Construct and display the riddle and wait for the user's answer. Check against the list of valid variants
    :param header: The head of text of the request
    :param choices: "one-letter, lowercase choice code":"Human-readable item description"
    :return:
    """
    print(header)
    while True:
        print("\n".join([f"{opt}) {desc}" for opt, desc in choices]))
        a = input("> ").lower()
        if a in choices.keys():
            return a

        print("\n! ERROR. Incorrect input.")


#####################################################################
# File   Edit   Edit_Settings   Menu   Utilities   Compilers   Test   Help
# ----------------------------------------------------------------------------
# EDIT  ZUSER.PROGRAM.CNTL(SORTCNTL) - 01.00  Columns 00001 00072
# Command ===>                      Scroll ===> CSR
# **************************** Top of Data *****************************
# 000010 SORT FIELDS=(1,3,CH,A)
def send_file(in_fname: str) -> None:
    """
    Will try to type-in the provided file's content into already opened EDIT session in ISPF
    :param in_fname: source file name
    :return: None
    """
    # TODO: Maybe read PROFILE and determine if we need to tailor it to the file content, like CAPS.
    global cmd_line

    try:
        infile = open(in_fname, 'r')
    except IOError as infile_e:
        print(f"Error opening input file {in_fname}: {infile_e}", file=sys.stderr)
        bail_out(1)

    header = ispf.get_browse_header()
    if header[4] != 'EDIT':
        print("!ERROR. Not in EDIT mode", file=sys.stderr)
        bail_out(1)

    has_lc_chars = False
    has_non_print = False
    print(". Reading source file")
    content = []

    while line := infile.readline():
        lcheck = str(line).strip()
        if not lcheck.isupper():
            has_lc_chars = True

        if not lcheck.isprintable():
            has_non_print = True

        content.append(line)

    infile.close()

    if has_lc_chars:
        a = ask_user("? The file has lowercase characters. Do you want to:",
                     # c='CAPS OFF',
                     i='Ignore', a='Abort')
        if a == 'c':
            pass
        elif a == 'i':
            pass
        elif a == 'a':
            return

    if has_non_print and not cmd_line.hex:
        a = ask_user("? The file has NON-PRINTABLE characters. Do you want to:",
                     # h='Use hex mode',
                     a='Abort')
        if a == 'h':
            pass
        elif a == 'i':
            pass

    rlen = 0
    for c in content:
        lc = len(c)
        if lc > rlen:
            rlen = lc

    if rlen > 80:
        print("!ERROR: Some lines length is > 80")
        return


#####################################################################
def receive_file(out_fname: str) -> None:
    """
    Scrapes dataset content in BROWSE/EDIT session to a local file.
    :param out_fname: File name to save data to. Can be None/'' to get a name from the page header
    :return: None
    """
    global cmd_line

    file = out_fname

    if not file:
        header = ispf.get_browse_header()
        if header:
            file = header[0]
        else:
            print("Could not determine dataset name for output file. Exiting.", file=sys.stderr)
            bail_out(1)

    if os.path.exists(file):  # make sure we will not overwrite existing files
        file += '_' + str(time.time())

    try:
        outfile = open(file, 'w')
    except IOError as outfile_e:
        print(f"Error opening output file {file}: {outfile_e}", file=sys.stderr)
        bail_out(1)

    # Apply options
    if cmd_line.top and not ispf.command('top'):
        return

    if cmd_line.hex and not ispf.command('hex on'):
        return

    screen = term.get_screen_content()

    # setting page mode if needed
    old_page_mode = screen[3][75:79].rstrip()
    if old_page_mode != 'PAGE':
        term.field_fill(3, 75, "PAGE")

    if cmd_line.cmd_line.debug:
        print(f". Grabbing to file: {file}")

    lines_saved = 0
    bytes_saved = 0

    # --- Fixed Record Length (<= 80) and not HEX mode ---
    if REC_LEN <= 80 and not cmd_line.hex:
        if cmd_line.debug:
            print(". Fixed/Standard Record Mode")

        while True:
            screen = term.get_screen_content()

            # Data starts from row 4 (index 4) up to the second-to-last row
            for line in screen[4:-1]:
                if re.search(r'^\s+\*\*End\*\*\s+|\s*\*{10,} Bottom of Data \*{10,}$', line):
                    outfile.close()
                    print(f"+ Finished. Lines saved: {lines_saved}, bytes: {bytes_saved}")
                    break

                lines_saved += 1
                bytes_saved += len(line)
                outfile.write(line + "\r\n")

            # Page down (PF8)
            term.script_cmd("pf 8")

    # --- Variable Record Length or HEX mode ---
    # ********************************* Top of Data *********************************
    # ------------------------------------------------------------------------------
    # :H3 ID=BRHEX SUBJECT=’BROWSE COMMANDS - HEX’.
    # 7CF4CC7CDCCE4EECDCCE77CDDEEC4CDDDCDCE464CCE74
    # A83094E2985702421533ED296625036441542000857DB
    # ------------------------------------------------------------------------------
    # HEX - DISPLAYING DATA IN HEXADECIMAL FORMAT
    # CCE464CCEDDCECDC4CCEC4CD4CCECCCCCDCD4CDDDCE
    # 8570004927318957041310950857145394130669413
    else:
        if cmd_line.debug:
            print(". Variable Record Length or HEX Mode")

        line_buf_size = 51
        line_buf = [''] * line_buf_size

        while True:
            screen = term.get_screen_content()

            # Check if we're scrolled right too far (empty data lines on screen)
            empty_screen = True
            for line_idx in range(4, len(screen) - 1):
                if screen[line_idx].strip():  # Check for non-whitespace characters
                    empty_screen = False
                    break

            if empty_screen:
                if cmd_line.debug:
                    print(". Found empty screen while scrolling right.")

                # Flush the current line buffer to the file
                for line in line_buf:
                    if line:
                        outfile.write(line + "\n")

                line_buf = [''] * line_buf_size  # Reset buffer

                # Move back to the beginning of the line (LEFT/RIGHT 0) and page down (PF8)
                ispf.command("right 0")  # Scroll all the way left
                term.script_cmd("pf 8")  # Page down

                continue  # Go to next page

            # Process the screen data
            line_idx = 4
            while line_idx < len(screen) - 1:
                line = screen[line_idx]
                line_buf_idx = line_idx - 4

                if re.search(r'^\s+\*\*End\*\*\s+|\s*\*{10,} Bottom of Data \*{10,}$', line):
                    # End of file detected, flush and exit
                    for buffered_line in line_buf:
                        if buffered_line:
                            outfile.write(buffered_line + "\n")
                    break

                if cmd_line.hex:
                    # HEX mode show 4 screen lines per record:
                    # Line L+0: ("-" * 79)
                    # Line L+1: Char display (we'll ignore this obviously)
                    # Line L+2: Hex high-byte
                    # Line L+3: Hex low-byte

                    # Validate
                    if screen[line_idx] != ("-" * 79):
                        print("!ERROR: bad initial position for the hex mode. no dashes", file=sys.stderr)
                        bail_out(1)

                    line_idx += 2
                    # Check bounds before accessing L+1 and L+2
                    if line_idx + 1 >= len(screen):  # Not sure if this can ever happen really
                        print("!ERROR: incomplete set of lines for the hex mode.", file=sys.stderr)
                        bail_out(1)

                    # Initialize the current segment for this line
                    current_segment_bytes = bytearray()

                    # now line_idx is the high nibble, line_idx+1 is the low nibble
                    for pos in range(0, 79):
                        # Construct the two-digit hex string and convert to byte
                        hex_char_h = screen[line_idx][pos]
                        hex_char_l = screen[line_idx + 1][pos]

                        if hex_char_h == ' ':
                            break

                        try:
                            current_segment_bytes.append(int(hex_char_h + hex_char_l, 16))
                        except ValueError:
                            break

                        line_buf[line_buf_idx] += current_segment_bytes

                        line_idx += 2  # Skip the two hex lines we just processed

                else:
                    # Variable length mode - simply concatenate the line (scrolling right)
                    line_buf[line_buf_idx] += line
                    line_idx += 1

            # Scroll for next segment
            if REC_LEN > 80 or REC_LEN == 0:
                # Scroll right (PF11) for more columns
                term.script_cmd("pf 11")
            else:
                # Scroll down (PF8) for next page of data
                term.script_cmd("pf 8")

    if old_page_mode != 'PAGE':
        term.field_fill(3, 75, old_page_mode)


#####################################################################
#####################################################################
# --- Main Logic ---
# --- Configuration and Command Line Parsing ---
ADDR = '127.0.0.1'
PORT = 3270
REC_LEN = 80

# Parse command line arguments
parser = argparse.ArgumentParser(add_help=True,
                                 description="Z/OS ISPF dataset scraping via 3270 terminal scripting.\n" +
                                 'Made by Andrej Pakhutin. pakhutin@gmail.com')
parser.add_argument('file', nargs='?',
                    help='The name of the file to put into editor or save the data to.')
parser.add_argument('-a', '--addr', default=ADDR, dest='addr',
                    help='Address of host to connect. Default is ' + ADDR)
parser.add_argument('-d', '--debug', type=int, default=0, dest='debug', help='debug level')
parser.add_argument('--hex', action='store_true', default=False, dest='hex',
                    help='Grab hexadecimal values (turns on hex mode in ISPF)')
parser.add_argument('-p', '--port', type=int, default=PORT, dest='port',
                    help='Port to connect to. Default is ' + str(PORT))
parser.add_argument('--rec-len', type=int, default=REC_LEN, dest='reclen', help='Record length. Default: 80')
parser.add_argument('-r', '--receive', action='store_true', dest='receive',
                    help='Receive file mode. Grabs content from EDIT/BROWSE.\n' +
                    'NOTE: The save file name is optional. It will be derived from the original name in browser')
parser.add_argument('-s', '--send', action='store_true', dest='send',
                    help='Send file mode. Fills in content in ISPF EDIT')
parser.add_argument('--top', action='store_true', default=False, dest='top',
                    help='Reposition to the top of the file before grabbing')

cmd_line = parser.parse_args()

# -----------------------------
ADDR = cmd_line.addr
PORT = cmd_line.port
REC_LEN = cmd_line.reclen

if cmd_line.send and cmd_line.receive:
    print("You can only send or receive file")
    sys.exit(1)

if not cmd_line.send and not cmd_line.receive:
    print("You need to use --send or --receive")
    sys.exit(1)

# --- Socket Setup ---
term = x3270Script(ADDR, PORT)
if not term.connected():
    sys.exit(1)

term.debug_level(cmd_line.debug)

ispf = x3270ISPF(term)
ispf.debug_level(cmd_line.debug)

# Initial connect and command to start the session if needed
if cmd_line.send:
    send_file(cmd_line.file)
elif cmd_line.receive:
    receive_file(cmd_line.file)

# .    Menu  Utilities  Compilers  Help                                              .
# .  ------------------------------------------------------------------------------- .
# .  BROWSE    BISR.WFADO.R98.DBMACS(VGGDWR12)          Line 0000000000 Col 001 080  .
# .  Command ===>                                                  Scroll ===> CSR   .
# . ********************************* Top of Data ********************************** .
# .                                                                                  .
# .                                                                                  .
# . ******************************** Bottom of Data ******************************** .
