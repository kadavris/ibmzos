"""
    This module is a part of z/OS toolset interacting with 3270 terminal emulator
by https://x3270.bgp.nu/ team. You need to enable scripting port for it to work.
    The function is to provide ISPF top-level interactions, like EDIT/BROWSE control
and more.
This module depends on a low-level x3270 module of the same author.
Written by Andrej Pakhutin (pakhutin@gmail.com)
"""

import re
import sys
from typing import List, Tuple, Optional
from x3270scripting import x3270Script


class x3270ISPF:
    def __init__(self, atermscript: x3270Script):
        self.__termscript: x3270Script = atermscript
        self.__debug: int = 0

    def debug_level(self, level: int) -> None:
        if level < 0:
            self.__debug = 0
        elif level > 9:
            self.__debug = 9
        else:
            self.__debug = level

    def get_browse_header(self) -> Optional[Tuple[str, int, int, int, str]]:
        """
        Extracts the header information on browser/editor screen:
        0: dataset name
        1: row/line number
        2: leftmost column on screen
        3: right (max?) columns
        4: mode: BROWSE|EDIT
        """
        screen = self.__termscript.get_screen_content()
        if len(screen) < 3:
            return None

        # TODO: determine what is the 2nd number after 'Col'
        # Example: ' BROWSE BISR.WFADO.R98.DBMACS(VGGDWR12)      Line 0000000000 Col 001 080 '
        match = re.match(r'\s*(BROWSE)\s+(\S+)\s+(Row|Line)\s+(\d+)\s+Col\s+(\d+)\s+(\d+)',
                         screen[2], re.IGNORECASE)
        if match:  # return 0 - DSN, 1 - current row, 2 - current column, 3 - max(?) columns, 4 - 'BROWSE'
            return match.group(2), int(match.group(4)), int(match.group(5)), int(match.group(6)), match.group(1)

        # Example: 'EDIT DSNAME      Columns 00001 00072'
        match = re.match(r'\s*(EDIT)\s+(\S+).+?Columns (\d{5}) (\d{5})',
                         screen[2], re.IGNORECASE)
        if match:  # return 0 - DSN, 1 - -1/current row, 2 - current column, 3 - max columns, 4 - 'EDIT'
            return match.group(2), -1, int(match.group(3)), int(match.group(4)), match.group(1)

        print("Error: probably not in BROWSE/EDIT", file=sys.stderr)
        return None

    #####################################################################
    def get_row_number(self) -> int:
        """
        Returns the current row number or -1 on error.
        """
        header = self.get_browse_header()

        if header:
            return header[1]

        print("Error: cannot get row number from screen", file=sys.stderr)

        return -1

    #####################################################################
    def command(self, command: str) -> bool:
        """
        Issues a command on the Command ===> line of ISPF.
        """
        if len(command) > 48:
            return False

        r, c = self.__termscript.find_text(r'Command ===>')

        if r == -1:
            print("!ERROR: ispf.command(): Looks like we're not in ISPF here?", file=sys.stderr)
            return False

        #    2            15                <- 48 ->                      63           75
        #    |            |                                               |            |
        # .  Command ===>                                                  Scroll ===> CSR   .
        # Pad the command with spaces to the end of the input field

        self.__termscript.script_cmd(f"MoveCursor({r},15)")
        command_str = command + (' ' * (48 - len(command)))

        self.__termscript.script_cmd(f'String "{command_str}\n"')

        # TODO: need to detect syntax errors - yellow top right corner (requires checking screen attributes/colors?)
        return True

    #####################################################################
    def edit_get_profile(self) -> Optional[dict]:
        """
        Will query edit session for the PROFILE DATA
        and return (a subset) of it as dictionary
        """
        out = {}
        header = self.get_browse_header()
        if not header:
            return None

        if header[4] != 'EDIT':
            print("!ERROR: ispf.get_profile(): issued in other than EDIT mode")
            return None

        r, c = self.__termscript.find_text("=PROF>")
        if r == -1:
            self.command("PROFILE")
            r, c = self.__termscript.find_text("=PROF>")

        screen = self.__termscript.get_screen_content()
        if not screen or len(screen) < 5:
            return None

        while screen[r][0:6] == "=PROF>":
            for s in screen[r].split('.'):
                if m := re.match(r'(CAPS|HEX|NUMBER) O([NF])', s):
                    out[m.group(1).lower()] = m.group(2) == 'N'
            r += 1

        self.command("RESET")  # turn off profile

    #####################################################################
    def edit_insert(self, text: list) -> bool:
        """
        Will add lines from a list parameter as a text in edit session
        """
        screen = self.__termscript.get_screen_content()
        if not screen or len(screen) < 5:
            return False
    
        # looking for insert mode starting row: five dots/apostrophes at the line command area
        start_row = 5
        while screen[start_row][0:7] != '...... ' and screen[start_row][0:7] != "'''''' ":
            start_row += 1
            if start_row > len(screen):
                print("!ERROR ispf.edit_insert(): Can't find the insert point", file=sys.stderr)
                return False
    
        self.__termscript.script_cmd(f"MoveCursor({start_row},7)")
        for lidx, line in enumerate(text):
            llen = len(line)
            if llen == 0:
                line = ' '
            elif llen > 72:
                print(f"!WARNING: ispf.edit_insert(): truncated long input line #{lidx} ({llen}):\n>'{line}'",
                      file=sys.stderr)
                line = line[0:72]
    
            self.__termscript.script_cmd(f'String "{line}\n"')
    
        return True


#####################################################################
if __name__ == "__main__":
    print("x3270 ISPF: This module should only be imported")
    sys.exit(1)
