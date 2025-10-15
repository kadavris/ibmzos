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
        self.termscript: x3270Script = atermscript
        self.debug: int = 0

    def debug_level(self, level: int) -> None:
        if level < 0:
            self.debug = 0
        elif level > 9:
            self.debug = 9
        else:
            self.debug = level

    def get_browse_header(self) -> Optional[Tuple[str, int, int, int, str]]:
        """
        Extracts the header information on browser/editor screen:
        0: dataset name
        1: row/line number
        2: leftmost column on screen
        3: right (max?) columns
        4: mode: BROWSE|EDIT
        """
        screen = self.termscript.get_screen_content()
        if len(screen) < 3:
            return None

        # TODO: determine what is the 2nd number after 'Col'
        # Example: ' BROWSE BISR.WFADO.R98.DBMACS(VGGDWR12)      Line 0000000000 Col 001 080 '
        match = re.match(r'\s*(BROWSE|EDIT\S*)\s+(\S+)\s+(Row|Line)\s+(\d+)\s+Col\s+(\d+)\s+(\d+)',
                         screen[2], re.IGNORECASE)
        if match:
            return match.group(2), int(match.group(4)), int(match.group(5)), int(match.group(6)), match.group(1)

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
        Issues a command on the Command ===> line.
        """
        r, c = self.termscript.find_text(r'Command ===>')

        if r == -1:
            print("ispf.command(): Looks like we're not in ISPF here?", file=sys.stderr)
            return False

        #    2            15                <- 48 ->                      63           75
        #    |            |                                               |            |
        # .  Command ===>                                                  Scroll ===> CSR   .
        # Pad the command with spaces to the end of the input field

        self.termscript.script_cmd(f"MoveCursor({r},15)")
        command_str = command + (' ' * (48 - len(command)))

        self.termscript.script_cmd(f'String "{command_str}\\n"')

        # TODO: need to detect syntax errors - yellow top right corner (requires checking screen attributes/colors?)
        return True


#####################################################################
if __name__ == "__main__":
    print("x3270 ISPF: This module should only be imported")
    sys.exit(1)
