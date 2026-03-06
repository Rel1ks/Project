#!/usr/bin/env python3
"""
Simple console text editor using blessed library.
Features:
- Text editing with arrow keys
- Page up/down navigation
- Search functionality
- Save/Open files
- Line numbers
- Status bar
- Cyrillic support
"""

import sys
import os
import ctypes

if sys.platform == 'win32':
    import msvcrt
else:
    msvcrt = None

# Enable UTF-8 encoding for Windows console
if sys.platform == 'win32':
    try:
        # Set console code page to UTF-8
        os.system('chcp 65001 >nul 2>&1')
    except Exception:
        pass

    try:
        # Enable VT100/ANSI support on Windows 10+
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 7)
    except Exception:
        pass


def is_jetbrains_mono_installed():
    """Check if JetBrains Mono font is installed on Windows."""
    if sys.platform != 'win32':
        return False
    
    try:
        # Check Windows registry for the font
        import winreg
        fonts_key = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
        
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, fonts_key) as key:
            # Check for JetBrains Mono variants
            font_names = [
                "JetBrains Mono",
                "JetBrains Mono (TrueType)",
                "JetBrains Mono Bold",
                "JetBrains Mono Bold (TrueType)",
                "JetBrains Mono Regular",
                "JetBrains Mono Regular (TrueType)",
            ]
            for font_name in font_names:
                try:
                    winreg.QueryValueEx(key, font_name)
                    return True
                except FileNotFoundError:
                    continue
        
        # Also check current user fonts
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, fonts_key) as key:
                for font_name in font_names:
                    try:
                        winreg.QueryValueEx(key, font_name)
                        return True
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            pass
            
    except Exception:
        pass
    
    return False

from blessed import Terminal

class Key:
    """Simple key event class."""
    def __init__(self, name=None, printable=False, code=-1, char=None):
        self.name = name
        self._printable = printable
        self.code = code
        self.char = char

    def isprintable(self):
        return self._printable


# Command Pattern for Undo/Redo
class Command:
    """Base command class for undoable operations."""
    def execute(self):
        pass
    
    def undo(self):
        pass


class InsertCharCommand(Command):
    """Command to insert a character."""
    def __init__(self, editor, char):
        self.editor = editor
        self.char = char
        self.y = editor.cursor_y
        self.x = editor.cursor_x
    
    def execute(self):
        line = self.editor.lines[self.y]
        self.editor.lines[self.y] = line[:self.x] + self.char + line[self.x:]
        self.editor.cursor_x = self.x + 1
    
    def undo(self):
        self.editor.cursor_y = self.y
        self.editor.cursor_x = self.x
        line = self.editor.lines[self.y]
        if self.x < len(line):
            self.editor.lines[self.y] = line[:self.x] + line[self.x + 1:]


class InsertNewlineCommand(Command):
    """Command to insert a newline."""
    def __init__(self, editor):
        self.editor = editor
        self.y = editor.cursor_y
        self.x = editor.cursor_x
        self.original_line = None
    
    def execute(self):
        self.original_line = self.editor.lines[self.y][:]
        line = self.editor.lines[self.y]
        after = line[self.x:]
        self.editor.lines[self.y] = line[:self.x]
        self.editor.lines.insert(self.y + 1, after)
        self.editor.cursor_y = self.y + 1
        self.editor.cursor_x = 0
    
    def undo(self):
        self.editor.lines[self.y] = self.original_line
        del self.editor.lines[self.y + 1]
        self.editor.cursor_y = self.y
        self.editor.cursor_x = self.x


class DeleteCharCommand(Command):
    """Command to delete a character."""
    def __init__(self, editor):
        self.editor = editor
        self.y = editor.cursor_y
        self.x = editor.cursor_x
        self.deleted_char = None
        self.merged_line = None
    
    def execute(self):
        line = self.editor.lines[self.y]
        if self.x < len(line):
            self.deleted_char = line[self.x]
            self.editor.lines[self.y] = line[:self.x] + line[self.x + 1:]
        elif self.y > 0:
            # Merge with previous line
            prev_line = self.editor.lines[self.y - 1]
            self.merged_line = prev_line
            self.editor.lines[self.y - 1] = prev_line + line
            del self.editor.lines[self.y]
            self.editor.cursor_y = self.y - 1
            self.editor.cursor_x = len(prev_line)
    
    def undo(self):
        if self.deleted_char is not None:
            line = self.editor.lines[self.y]
            self.editor.lines[self.y] = line[:self.x] + self.deleted_char + line[self.x:]
            self.editor.cursor_y = self.y
            self.editor.cursor_x = self.x
        elif self.merged_line is not None:
            line = self.editor.lines[self.y]
            self.editor.lines[self.y - 1] = self.merged_line
            self.editor.lines.insert(self.y, line[len(self.merged_line):])
            self.editor.cursor_y = self.y
            self.editor.cursor_x = self.x


class BackspaceCommand(Command):
    """Command to delete character before cursor."""
    def __init__(self, editor):
        self.editor = editor
        self.y = editor.cursor_y
        self.x = editor.cursor_x
        self.deleted_char = None
        self.cursor_before_x = None
        self.merged_line = None
        self.line_after_merge = None
    
    def execute(self):
        if self.x > 0:
            line = self.editor.lines[self.y]
            self.deleted_char = line[self.x - 1]
            self.cursor_before_x = self.x - 1
            self.editor.lines[self.y] = line[:self.x - 1] + line[self.x:]
            self.editor.cursor_x = self.x - 1
        elif self.y > 0:
            # Merge with previous line
            prev_line = self.editor.lines[self.y - 1]
            line = self.editor.lines[self.y]
            self.merged_line = prev_line
            self.line_after_merge = line
            self.editor.lines[self.y - 1] = prev_line + line
            del self.editor.lines[self.y]
            self.editor.cursor_y = self.y - 1
            self.editor.cursor_x = len(prev_line)
    
    def undo(self):
        if self.deleted_char is not None:
            line = self.editor.lines[self.y]
            self.editor.lines[self.y] = line[:self.cursor_before_x] + self.deleted_char + line[self.cursor_before_x:]
            self.editor.cursor_y = self.y
            self.editor.cursor_x = self.x
        elif self.merged_line is not None:
            self.editor.lines[self.y - 1] = self.merged_line
            self.editor.lines.insert(self.y, self.line_after_merge)
            self.editor.cursor_y = self.y
            self.editor.cursor_x = self.x


class DeleteSelectionCommand(Command):
    """Command to delete selected text."""
    def __init__(self, editor, selection_start, selection_end, clipboard_before):
        self.editor = editor
        self.selection_start = selection_start
        self.selection_end = selection_end
        self.clipboard_before = clipboard_before
        self.deleted_text = None
        self.original_lines = None
    
    def execute(self):
        self.original_lines = [line[:] for line in self.editor.lines]
        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end
        
        if start_line == end_line:
            self.deleted_text = self.editor.lines[start_line][start_col:end_col]
            self.editor.lines[start_line] = self.editor.lines[start_line][:start_col] + self.editor.lines[start_line][end_col:]
        else:
            # Collect deleted text
            deleted_lines = []
            for i in range(start_line, end_line + 1):
                if i == start_line:
                    deleted_lines.append(self.editor.lines[i][start_col:])
                elif i == end_line:
                    deleted_lines.append(self.editor.lines[i][:end_col])
                else:
                    deleted_lines.append(self.editor.lines[i])
            self.deleted_text = '\n'.join(deleted_lines)
            
            self.editor.lines[start_line] = self.editor.lines[start_line][:start_col] + self.editor.lines[end_line][end_col:]
            del self.editor.lines[start_line + 1:end_line + 1]
        
        self.editor.cursor_y = start_line
        self.editor.cursor_x = start_col
        self.editor.clipboard = self.deleted_text
    
    def undo(self):
        self.editor.lines = [line[:] for line in self.original_lines]
        self.editor.cursor_y = self.selection_start[0]
        self.editor.cursor_x = self.selection_start[1]
        self.editor.clipboard = self.clipboard_before


def wrap_line(line, width):
    """Wrap a line into multiple visual lines without breaking words."""
    if not line:
        return [""]
    
    wrapped = []
    current = ""
    
    for char in line:
        if len(current) >= width:
            wrapped.append(current)
            current = char
        else:
            current += char
    
    if current:
        wrapped.append(current)
    
    return wrapped if wrapped else [""]


class TextEditor:
    def __init__(self):
        self.term = Terminal()
        self.lines = [""]  # Logical lines
        self.cursor_x = 0  # Column in logical line
        self.cursor_y = 0  # Logical line index
        self.scroll_y = 0  # Visual line scroll offset
        self.filename = None
        self.modified = False
        self.message = "" if is_jetbrains_mono_installed() else "Tip: Use JetBrains Mono font for best experience (configure in terminal settings)"
        self.search_text = ""
        self.search_index = -1
        self.search_matches = []
        self.is_windows = sys.platform == 'win32'

        # Selection for copy/cut/paste
        self.selection_start = None  # (line, col)
        self.selection_end = None  # (line, col)
        self.selection_active = False
        self.clipboard = ""

        # Undo/Redo using Command Pattern
        self.undo_stack = []
        self.redo_stack = []
        self.max_undo = 100
        self.last_command = None  # For batching consecutive commands
        self.last_command_time = 0

        # Visual line mapping: list of (logical_line_idx, wrap_line_idx, visual_text)
        self.visual_lines = []
        self._build_visual_lines()

        # Отслеживание размеров терминала
        self.last_term_width = self.term.width
        self.last_term_height = self.term.height

    def _display_path(self, path):
        """Return short path for status/messages."""
        if not path:
            return "Untitled"
        try:
            return os.path.relpath(path, os.path.expanduser('~'))
        except ValueError:
            # On Windows relpath may fail for different drives
            return path

    def _normalize_input_path(self, raw_path):
        """Normalize path from prompt input."""
        if raw_path is None:
            return None

        path = raw_path.strip()
        if not path:
            return ""

        # Strip bracketed-paste markers sometimes sent by terminals
        path = path.replace('\x1b[200~', '').replace('\x1b[201~', '')

        # Strip wrapping quotes
        if len(path) >= 2 and path[0] == '"' and path[-1] == '"':
            path = path[1:-1]

        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        return path

    def get_visible_height(self):
        return self.term.height - 1  # Reserve exactly 1 line for status bar at the bottom

    def get_line_num_width(self):
        """Width of line number column."""
        return max(2, len(str(max(1, len(self.lines)))))

    def get_visible_width(self):
        # Reserve space for line numbers + one separating space.
        return max(10, self.term.width - (self.get_line_num_width() + 1))

    def _build_visual_lines(self):
        """Build visual line mapping from logical lines with soft wrap."""
        self.visual_lines = []
        visible_width = self.get_visible_width()

        for line_idx, line in enumerate(self.lines):
            wrapped = wrap_line(line, visible_width)
            for wrap_idx, visual_text in enumerate(wrapped):
                self.visual_lines.append((line_idx, wrap_idx, visual_text, line))

    def execute_command(self, command, batch_with_previous=False):
        import time
        current_time = time.time()
        
        should_batch = False
        if batch_with_previous and self.last_command:
            # Group commands if they are the same type and less than 0.5 sec has passed
            if type(command) is type(self.last_command):
                time_diff = current_time - self.last_command_time
                if time_diff < 0.5:
                    should_batch = True
        
        if not should_batch:
            # Clear redo stack when new independent action is performed
            self.redo_stack = []
        
        # Execute the command itself
        command.execute()
        self.modified = True
        self._build_visual_lines()
        
        # Пересчитываем поиск если активен
        if self.search_text:
            self.find_search_matches()

        if should_batch and self.undo_stack:
            # If we need to group - pop the last entry and combine
            last_item = self.undo_stack.pop()
            if isinstance(last_item, list):
                last_item.append(command)
                self.undo_stack.append(last_item)
            else:
                self.undo_stack.append([last_item, command])
        else:
            # Add as a new entry
            self.undo_stack.append(command)
            
            # Limit history size
            if len(self.undo_stack) > self.max_undo:
                self.undo_stack.pop(0)
                
        self.last_command = command
        self.last_command_time = current_time

    def undo(self):
        """Отмена последнего действия."""
        if self.undo_stack:
            item = self.undo_stack.pop()
            # Если это группа команд (вставка), откатываем их все в обратном порядке
            if isinstance(item, list):
                for cmd in reversed(item):
                    cmd.undo()
            else:
                item.undo()

            self.redo_stack.append(item)
            self.modified = True
            self._build_visual_lines()
            # Пересчитываем поиск если активен
            if self.search_text:
                self.find_search_matches()
            self.message = "Undo"
            self.last_command = None
            return True
        return False

    def redo(self):
        """Повтор отмененного действия."""
        if self.redo_stack:
            item = self.redo_stack.pop()
            # Если это группа, выполняем их заново в прямом порядке
            if isinstance(item, list):
                for cmd in item:
                    cmd.execute()
            else:
                item.execute()

            self.undo_stack.append(item)
            self.modified = True
            self._build_visual_lines()
            # Пересчитываем поиск если активен
            if self.search_text:
                self.find_search_matches()
            self.message = "Redo"
            return True
        return False

    def get_visual_line_count(self):
        """Get total number of visual lines."""
        return len(self.visual_lines)
    
    def logical_to_visual(self, logical_y, logical_x):
        """Convert logical position to visual line index and visual x."""
        visible_width = self.get_visible_width()
        visual_y = 0
        for line_idx, wrap_idx, visual_text, full_line in self.visual_lines:
            if line_idx == logical_y:
                # Check if cursor is in this wrapped line
                start_x = wrap_idx * visible_width
                end_x = min((wrap_idx + 1) * visible_width, len(full_line))
                if start_x <= logical_x < end_x or (wrap_idx == len(wrap_line(full_line, visible_width)) - 1 and logical_x >= start_x):
                    return visual_y, logical_x - start_x
            visual_y += 1
        # Fallback - find first visual line for this logical line
        for i, (line_idx, wrap_idx, visual_text, full_line) in enumerate(self.visual_lines):
            if line_idx == logical_y:
                return i, logical_x % visible_width
        return 0, 0
    
    def visual_to_logical(self, visual_y):
        """Convert visual line index to logical line index and x offset."""
        if 0 <= visual_y < len(self.visual_lines):
            line_idx, wrap_idx, visual_text, full_line = self.visual_lines[visual_y]
            return line_idx, wrap_idx * self.get_visible_width()
        return 0, 0
    
    def move_cursor_visual(self, visual_y, visual_x):
        """Move cursor using visual coordinates."""
        if 0 <= visual_y < len(self.visual_lines):
            line_idx, wrap_idx, visual_text, full_line = self.visual_lines[visual_y]
            self.cursor_y = line_idx
            self.cursor_x = min(visual_x + wrap_idx * self.get_visible_width(), len(full_line))
    
    def scroll_to_cursor(self):
        """Scroll to keep cursor visible."""
        visible_height = self.get_visible_height()
        
        # Get current visual line position
        visual_y, _ = self.logical_to_visual(self.cursor_y, self.cursor_x)
        
        if visual_y < self.scroll_y:
            self.scroll_y = visual_y
        elif visual_y >= self.scroll_y + visible_height:
            self.scroll_y = visual_y - visible_height + 1

    def select_all(self):
        """Select all text in file."""
        if self.lines:
            # Find last line with any content
            last_line_idx = len(self.lines) - 1
            # Skip completely empty lines at the end
            while last_line_idx > 0 and len(self.lines[last_line_idx]) == 0:
                last_line_idx -= 1
            last_line_len = len(self.lines[last_line_idx])
            self.selection_start = (0, 0)
            self.selection_end = (last_line_idx, last_line_len)
            self.selection_active = True
            self.message = f"Selected: {last_line_idx + 1} line(s)"

    def clear_selection(self):
        """Clear current selection."""
        self.selection_start = None
        self.selection_end = None
        self.selection_active = False

    def get_selected_text(self):
        """Get text from selection."""
        if not self.selection_active or not self.selection_start or not self.selection_end:
            return ""
        
        start_line, start_col = self.selection_start
        end_line, end_col = self.selection_end
        
        if start_line == end_line:
            return self.lines[start_line][start_col:end_col]
        
        result = []
        for i in range(start_line, end_line + 1):
            if i == start_line:
                result.append(self.lines[i][start_col:])
            elif i == end_line:
                result.append(self.lines[i][:end_col])
            else:
                result.append(self.lines[i])
        
        return '\n'.join(result)

    def delete_selection(self):
        """Delete selected text."""
        if not self.selection_active:
            return

        clipboard_before = self.clipboard
        command = DeleteSelectionCommand(self, self.selection_start, self.selection_end, clipboard_before)
        self.execute_command(command, batch_with_previous=False)
        self.clear_selection()

    def get_key(self):
        """Get key input, handling Windows Unicode properly. Non-blocking."""
        if self.is_windows:
            if not msvcrt.kbhit():
                return None

            ch = msvcrt.getwch()

            if ch == '\x1b':
                if not msvcrt.kbhit():
                    return Key(name='ESC', printable=False)
                ch2 = msvcrt.getwch()
                if ch2 == '[':
                    if not msvcrt.kbhit():
                        return Key(name='ESC', printable=False)
                    ch3 = msvcrt.getwch()

                    if ch3 == '1' and msvcrt.kbhit():
                        ch4 = msvcrt.getwch()
                        if ch4 == ';' and msvcrt.kbhit():
                            modifier = msvcrt.getwch()
                            if msvcrt.kbhit():
                                key_ch = msvcrt.getwch()
                                if modifier == '5':
                                    if key_ch == 'A': return Key(name='KEY_UP', printable=False, code=165)
                                    if key_ch == 'B': return Key(name='KEY_DOWN', printable=False, code=166)
                                    if key_ch == 'C': return Key(name='KEY_RIGHT', printable=False, code=167)
                                    if key_ch == 'D': return Key(name='KEY_LEFT', printable=False, code=168)
                                elif modifier in ('2', '6'):
                                    if key_ch == 'A': return Key(name='KEY_UP', printable=False, code=265)
                                    if key_ch == 'B': return Key(name='KEY_DOWN', printable=False, code=266)
                                    if key_ch == 'C': return Key(name='KEY_RIGHT', printable=False, code=267)
                                    if key_ch == 'D': return Key(name='KEY_LEFT', printable=False, code=268)

                    if ch3 == 'A': return Key(name='KEY_UP', printable=False)
                    if ch3 == 'B': return Key(name='KEY_DOWN', printable=False)
                    if ch3 == 'C': return Key(name='KEY_RIGHT', printable=False)
                    if ch3 == 'D': return Key(name='KEY_LEFT', printable=False)
                    if ch3 == 'H': return Key(name='KEY_HOME', printable=False)
                    if ch3 == 'F': return Key(name='KEY_END', printable=False)

                    if ch3 in ('3', '5', '6') and msvcrt.kbhit():
                        ch4 = msvcrt.getwch()
                        if ch4 == '~':
                            if ch3 == '3': return Key(name='KEY_DELETE', printable=False)
                            if ch3 == '5': return Key(name='KEY_PAGEUP', printable=False)
                            if ch3 == '6': return Key(name='KEY_PAGEDOWN', printable=False)

                    if ch3 == '1' and msvcrt.kbhit():
                        ch4 = msvcrt.getwch()
                        if ch4 == ';' and msvcrt.kbhit():
                            ch5 = msvcrt.getwch()
                            if msvcrt.kbhit():
                                ch6 = msvcrt.getwch()
                                if ch6 == 'P': return Key(name='KEY_F1', printable=False)
                                if ch6 == 'Q': return Key(name='KEY_F2', printable=False)
                                if ch6 == 'R': return Key(name='KEY_F3', printable=False)
                                if ch6 == 'S': return Key(name='KEY_F4', printable=False)
                return Key(name='ESC', printable=False)

            if ch in '\xe0\x00':
                if not msvcrt.kbhit():
                    return None
                ch2 = msvcrt.getwch()
                km = {'H':'KEY_UP','P':'KEY_DOWN','K':'KEY_LEFT','M':'KEY_RIGHT',
                      'G':'KEY_HOME','O':'KEY_END','I':'KEY_PAGEUP','Q':'KEY_PAGEDOWN',
                      'S':'KEY_DELETE','R':'KEY_F1','T':'KEY_F2','U':'KEY_F3','V':'KEY_F4',
                      'W':'KEY_F5','X':'KEY_F6','Y':'KEY_F7','Z':'KEY_F8',
                      'a':'KEY_F9','b':'KEY_F10','c':'KEY_F11','d':'KEY_F12'}
                return Key(name=km.get(ch2, ch2), printable=False)

            och = ord(ch)
            if och == 27: return Key(name='ESC', printable=False)
            if och == 13: return Key(name='ENTER', printable=False)
            if och in (8, 127): return Key(name='KEY_BACKSPACE', printable=False)
            if och == 9: return Key(name='TAB', printable=False)
            if och == 0: return None
            if och in (91, 59): return None  # ANSI chars: [ ;
            if och == 19: return Key(name=None, printable=False, code=19)
            if och == 20: return Key(name=None, printable=False, code=20)
            if och == 15: return Key(name=None, printable=False, code=15)
            if och == 17: return Key(name=None, printable=False, code=17)
            if och == 6: return Key(name=None, printable=False, code=6)
            if och == 1:
                try:
                    if ctypes.windll.user32.GetKeyState(0x10) & 0x8000:
                        return Key(name=None, printable=False, code=2)
                except: pass
                return Key(name=None, printable=False, code=1)
            if och == 26: return Key(name=None, printable=False, code=26)
            if och == 25: return Key(name=None, printable=False, code=25)
            return Key(name=None, printable=True, code=och, char=ch)
        else:
            return self.term.inkey(timeout=0.01)

    def move_cursor(self, y, x):
        self.cursor_y = max(0, min(y, len(self.lines) - 1))
        self.cursor_x = max(0, min(x, len(self.lines[self.cursor_y])))

    def scroll_to_cursor(self):
        """Scroll to keep cursor visible."""
        visible_height = self.get_visible_height()
        
        # Get current visual line position
        visual_y, _ = self.logical_to_visual(self.cursor_y, self.cursor_x)
        
        if visual_y < self.scroll_y:
            self.scroll_y = visual_y
        elif visual_y >= self.scroll_y + visible_height:
            self.scroll_y = visual_y - visible_height + 1

    def draw(self):
        """Draw the editor screen with soft-wrap support."""
        output = []
        write = output.append
        write(self.term.home)
        write(self.term.clear)

        # Резервируем только 1 строку для статус-бара в самом низу
        visible_height = self.term.height - 1
        visible_width = self.get_visible_width()
        vlines = self.visual_lines
        nlines = len(vlines)

        # Dynamic width based on current line count (e.g. 1..9, 10..99, 100+)
        line_num_width = self.get_line_num_width()

        for i in range(visible_height):
            visual_idx = self.scroll_y + i
            if visual_idx >= nlines:
                # Пустая строка
                write(f'\033[{i+1};1H{" " * (line_num_width + 1)}' + ' ' * visible_width)
                continue

            line_idx, wrap_idx, visual_text, full_line = vlines[visual_idx]

            # Отрисовка номера строки или пустого места для продолжения
            if wrap_idx == 0:
                write(f'\033[{i+1};1H\033[1m{line_idx + 1:>{line_num_width}}\033[0m ')
            else:
                write(f'\033[{i+1};1H{" " * line_num_width} ')

            # Позиционируем курсор для текста после номера строки
            write(f'\033[{i+1};{line_num_width+2}H')

            # Отрисовка текста с поддержкой выделения
            if self.selection_active and self.selection_start and self.selection_end:
                start_line, start_col = self.selection_start
                end_line, end_col = self.selection_end
                if start_line <= line_idx <= end_line:
                    visual_start = wrap_idx * visible_width
                    sel_start = max(0, start_col - visual_start) if line_idx == start_line else 0
                    sel_end = min(end_col - visual_start, len(visual_text)) if line_idx == end_line else len(visual_text)
                    sel_start = max(0, min(sel_start, len(visual_text)))
                    sel_end = max(sel_start, min(sel_end, len(visual_text)))
                    if sel_start > 0:
                        write(visual_text[:sel_start])
                    if sel_start < sel_end:
                        write(f'\033[7m{visual_text[sel_start:sel_end]}\033[0m')
                    if sel_end < len(visual_text):
                        write(visual_text[sel_end:])
                    if len(visual_text) < visible_width - 1:
                        write(' ' * (visible_width - 1 - len(visual_text)))
                else:
                    write(visual_text)
                    if len(visual_text) < visible_width - 1:
                        write(' ' * (visible_width - 1 - len(visual_text)))
            elif self.search_text and self.search_matches:
                for part, is_match in self.highlight_search(visual_text, line_idx):
                    write(f'\033[43m\033[30m{part}\033[0m' if is_match else part)
                if len(visual_text) < visible_width - 1:
                    write(' ' * (visible_width - 1 - len(visual_text)))
            else:
                write(visual_text)
                if len(visual_text) < visible_width - 1:
                    write(' ' * (visible_width - 1 - len(visual_text)))

        # Статус-бар на самой последней строке во всю ширину
        status = f" {self._display_path(self.filename)} "
        if self.modified:
            status += "| [*] "
        status += f"| Line {self.cursor_y + 1}, Col {self.cursor_x + 1} "
        if self.selection_active and self.selection_start and self.selection_end:
            sl, sc = self.selection_start
            el, ec = self.selection_end
            status += f"| Selected: {el-sl+1} line(s) "
        if self.search_text:
            status += f"| Search: {self.search_text} "
        # Добавляем сообщение в конец статус-бара
        if self.message:
            status += f"| {self.message}"

        # Рисуем статус-бар на ПОСЛЕДНЕЙ строке терминала во всю ширину
        # Используем явную позицию: последняя строка = visible_height + 1
        status_row = visible_height + 1
        write(f'\033[{status_row};1H\033[7m{status.ljust(self.term.width)}\033[0m')

        # Курсор
        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
        cursor_y = visual_y - self.scroll_y + 1
        cursor_x = line_num_width + 2 + visual_x  # Текст начинается с line_num_width + 2
        if 1 <= cursor_y <= visible_height and visual_y < len(vlines):
            _, _, vt, _ = vlines[visual_y]
            ch = vt[visual_x] if visual_x < len(vt) else ' '
            # Показываем курсор и на пустой позиции (инвертированный пробел)
            write(f'\033[{cursor_y};{cursor_x}H\033[7m{ch}\033[0m')

        sys.stdout.write(''.join(output))
        sys.stdout.flush()

    def highlight_search(self, text, line_idx):
        """Return list of (text, is_match) tuples."""
        if not self.search_text or not self.search_matches:
            return [(text, False)]

        result = []
        last_end = 0

        for match_line_idx, start, end in self.search_matches:
            if match_line_idx != line_idx:
                continue
            if start >= len(text):
                break
            if end > len(text):
                end = len(text)
            if start < last_end:
                continue

            if start > last_end:
                result.append((text[last_end:start], False))
            result.append((text[start:end], True))
            last_end = end

        if last_end < len(text):
            result.append((text[last_end:], False))

        return result if result else [(text, False)]

    def find_search_matches(self):
        """Find all occurrences of search text."""
        self.search_matches = []
        if not self.search_text:
            return

        search_lower = self.search_text.lower()
        for line_idx, line in enumerate(self.lines):
            line_lower = line.lower()
            start = 0
            while True:
                pos = line_lower.find(search_lower, start)
                if pos == -1:
                    break
                self.search_matches.append((line_idx, pos, pos + len(self.search_text)))
                start = pos + 1

    def next_match(self):
        if not self.search_matches:
            return
        self.search_index = (self.search_index + 1) % len(self.search_matches)
        # Find which line and position this match is on
        line_idx, start, end = self.search_matches[self.search_index]
        self.cursor_y = line_idx
        self.cursor_x = start
        self.scroll_to_cursor()

    def insert_char(self, ch):
        # При вводе текста после поиска - очищаем поиск
        if self.search_text:
            self.search_text = ""
            self.search_matches = []
            self.search_index = -1
        command = InsertCharCommand(self, ch)
        self.execute_command(command, batch_with_previous=True)

    def insert_newline(self):
        command = InsertNewlineCommand(self)
        self.execute_command(command, batch_with_previous=False)

    def delete_char(self):
        command = DeleteCharCommand(self)
        self.execute_command(command, batch_with_previous=True)

    def backspace(self):
        command = BackspaceCommand(self)
        self.execute_command(command, batch_with_previous=True)

    def save_file(self, filename=None):
        if filename:
            self.filename = self._normalize_input_path(filename)
        if not self.filename:
            self.message = "No filename specified"
            return False

        display_filename = self._display_path(self.filename)

        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.lines))
            self.modified = False
            self.message = f"Saved: {display_filename}"
            return True
        except Exception as e:
            self.message = f"Error saving: {e}"
            return False

    def open_file(self, filename):
        normalized = self._normalize_input_path(filename)
        try:
            with open(normalized, 'r', encoding='utf-8') as f:
                content = f.read()
            self.lines = content.split('\n')
            if not self.lines:
                self.lines = [""]
            self.filename = normalized
            self.cursor_x = 0
            self.cursor_y = 0
            self.scroll_y = 0
            self.modified = False
            self._build_visual_lines()
            self.message = f"Opened: {self._display_path(self.filename)}"
            return True
        except Exception as e:
            self.message = f"Error opening: {e}"
            return False

    def prompt(self, prompt_text):
        """Get input from user with tab completion for files."""
        # Store cursor position
        prompt_row = self.term.height - 1
        
        def draw_prompt(input_str, cursor_pos, show_cursor=True):
            """Draw the prompt with cursor."""
            # Move to prompt row and clear line using ANSI codes
            sys.stdout.write(f'\033[{prompt_row + 1};1H\033[K')
            sys.stdout.write(prompt_text)
            
            # Draw input string with cursor
            if show_cursor and cursor_pos <= len(input_str):
                # Draw text before cursor
                sys.stdout.write(input_str[:cursor_pos])
                # Draw cursor (inverted character or block)
                if cursor_pos < len(input_str):
                    char_under_cursor = input_str[cursor_pos]
                    sys.stdout.write(f'\033[7m{char_under_cursor}\033[0m')
                    # Draw rest of string
                    sys.stdout.write(input_str[cursor_pos + 1:])
                else:
                    # Cursor at end - draw inverted space
                    sys.stdout.write(f'\033[7m \033[0m')
            else:
                sys.stdout.write(input_str)
            
            sys.stdout.flush()
        
        # Initial draw
        draw_prompt("", 0)

        input_str = ""
        cursor_pos = 0  # Position within input string
        
        while True:
            if self.is_windows:
                if not msvcrt.kbhit():
                    import time
                    time.sleep(0.01)
                    continue
                ch = msvcrt.getwch()
                
                # Handle Tab completion
                if ord(ch) == 9:  # Tab
                    if input_str:
                        completed = self._complete_path(input_str)
                        if completed and completed != input_str:
                            input_str = completed
                            cursor_pos = len(input_str)
                            draw_prompt(input_str, cursor_pos)
                    continue
                
                if ord(ch) == 13:  # Enter
                    return input_str
                elif ord(ch) == 8 or ord(ch) == 127:  # Backspace
                    if cursor_pos > 0:
                        input_str = input_str[:cursor_pos-1] + input_str[cursor_pos:]
                        cursor_pos -= 1
                        draw_prompt(input_str, cursor_pos)
                elif ord(ch) == 27:  # ESC
                    # Check for ANSI escape sequence (arrow keys)
                    if msvcrt.kbhit():
                        ch2 = msvcrt.getwch()
                        if ch2 == '[':
                            if msvcrt.kbhit():
                                ch3 = msvcrt.getwch()
                                # Handle PageUp/PageDown/Delete (5~, 6~, 3~)
                                if ch3 in ('3', '5', '6'):
                                    if msvcrt.kbhit():
                                        ch4 = msvcrt.getwch()
                                        if ch4 == '~':
                                            # Игнорировать PageUp/PageDown/Delete в prompt
                                            draw_prompt(input_str, cursor_pos)
                                            continue
                                if ch3 == 'C' and cursor_pos < len(input_str):  # Right arrow
                                    cursor_pos += 1
                                    draw_prompt(input_str, cursor_pos)
                                elif ch3 == 'D' and cursor_pos > 0:  # Left arrow
                                    cursor_pos -= 1
                                    draw_prompt(input_str, cursor_pos)
                    else:
                        return None
                elif ord(ch) == 75:  # Left arrow (in some modes)
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        draw_prompt(input_str, cursor_pos)
                elif ord(ch) == 77:  # Right arrow (in some modes)
                    if cursor_pos < len(input_str):
                        cursor_pos += 1
                        draw_prompt(input_str, cursor_pos)
                elif ord(ch) >= 32:  # Printable
                    input_str = input_str[:cursor_pos] + ch + input_str[cursor_pos:]
                    cursor_pos += 1
                    draw_prompt(input_str, cursor_pos)
            else:
                ch = self.term.inkey()
                ch_name = ch.name
                ch_str = str(ch)

                if ch_name in ('ENTER', 'KEY_ENTER', 'KEY_CTRL_M', 'KEY_CTRL_J') or ch_str in ('\r', '\n'):
                    return input_str
                elif ch_name in ('TAB', 'KEY_TAB', 'KEY_CTRL_I') or ch_str == '\t':
                    if input_str:
                        completed = self._complete_path(input_str)
                        if completed and completed != input_str:
                            input_str = completed
                            cursor_pos = len(input_str)
                            draw_prompt(input_str, cursor_pos)
                    continue
                elif ch_name in ('KEY_BACKSPACE', 'KEY_DELETE', 'KEY_CTRL_H', 'KEY_CTRL_?') or ch_str in ('\x08', '\x7f'):
                    if cursor_pos > 0:
                        input_str = input_str[:cursor_pos-1] + input_str[cursor_pos:]
                        cursor_pos -= 1
                        draw_prompt(input_str, cursor_pos)
                elif ch_name in ('ESC', 'KEY_ESCAPE', 'KEY_CTRL_[') or ch_str == '\x1b':
                    return None
                elif ch_name == 'KEY_LEFT':
                    if cursor_pos > 0:
                        cursor_pos -= 1
                        draw_prompt(input_str, cursor_pos)
                elif ch_name == 'KEY_RIGHT':
                    if cursor_pos < len(input_str):
                        cursor_pos += 1
                        draw_prompt(input_str, cursor_pos)
                elif ch.isprintable():
                    input_str = input_str[:cursor_pos] + ch + input_str[cursor_pos:]
                    cursor_pos += 1
                    draw_prompt(input_str, cursor_pos)
        
        return input_str

    def _complete_path(self, path):
        """Complete file/directory path."""
        import glob as globmod
        import ntpath
        
        # Handle quoted paths (for spaces)
        if path.startswith('"'):
            if '"' in path[1:]:
                return path
            search_path = path[1:]
            prefix = '"'
        else:
            search_path = path
            prefix = ''
        
        # Expand ~ to home directory
        if search_path.startswith('~'):
            search_path = os.path.expanduser(search_path)
        
        # Get directory and base
        if os.path.isdir(search_path):
            # Complete inside directory
            search_path = search_path.rstrip('\\/') + '/*'
            prefix = prefix + os.path.dirname(search_path) + '/' if os.path.dirname(search_path) else prefix
        
        # Try to complete
        try:
            matches = globmod.glob(search_path + '*')
        except Exception:
            return path
        
        if len(matches) == 1:
            return prefix + matches[0]
        elif len(matches) > 1:
            # Find common prefix
            common = os.path.commonprefix(matches)
            if common and common != search_path:
                return prefix + common
        
        return path

    def search(self):
        """Search for text in the document."""
        search_term = self.prompt("Search: ")
        if search_term:
            self.search_text = search_term
            self.search_index = -1
            self.find_search_matches()
            if self.search_matches:
                self.next_match()
                self.message = f"Found {len(self.search_matches)} matches"
            else:
                self.message = "No matches found"

    def run(self):
        if len(sys.argv) > 1:
            # Convert to absolute path for opening
            filename = os.path.abspath(sys.argv[1]) if not os.path.isabs(sys.argv[1]) else sys.argv[1]
            self.open_file(filename)
        
        # Save terminal settings (Unix only)
        old_settings = None
        if not self.is_windows:
            try:
                import termios
                old_settings = termios.tcgetattr(sys.stdin.fileno())
            except (ImportError, OSError):
                pass  # Windows doesn't have termios

        with self.term.fullscreen(), self.term.cbreak():
            # Hide cursor and disable echo
            sys.stdout.write('\033[?25l')
            sys.stdout.flush()

            try:
                self.draw()
                draw = self.draw
                get_key = self.get_key
                term = self.term

                while True:
                    # Проверка ресайза терминала
                    if term.width != self.last_term_width or term.height != self.last_term_height:
                        self.last_term_width = term.width
                        self.last_term_height = term.height
                        self._build_visual_lines()
                        draw()
                        continue

                    ch = get_key()
                    # На Linux inkey(timeout=...) возвращает пустую строку при отсутствии ввода.
                    # Важно отфильтровать ее, иначе она воспринимается как "printable"
                    # и курсор двигается вправо бесконечно.
                    if ch is None or ch == "":
                        continue

                    self.message = ""
                    nm = ch.name

                    if nm == 'ESC':
                        # Check for special key sequences
                        if not self.is_windows:
                            next_ch = self.term.inkey(timeout=0.01)
                            if next_ch:
                                if next_ch.name == 'KEY_UP':
                                    if self.cursor_y > 0:
                                        self.cursor_y -= 1
                                        self.move_cursor(self.cursor_y, self.cursor_x)
                                elif next_ch.name == 'KEY_DOWN':
                                    if self.cursor_y < len(self.lines) - 1:
                                        self.cursor_y += 1
                                        self.move_cursor(self.cursor_y, self.cursor_x)
                                elif next_ch.name == 'KEY_LEFT':
                                    if self.cursor_x > 0:
                                        self.cursor_x -= 1
                                    elif self.cursor_y > 0:
                                        self.cursor_y -= 1
                                        self.cursor_x = len(self.lines[self.cursor_y])
                                elif next_ch.name == 'KEY_RIGHT':
                                    if self.cursor_x < len(self.lines[self.cursor_y]):
                                        self.cursor_x += 1
                                    elif self.cursor_y < len(self.lines) - 1:
                                        self.cursor_y += 1
                                        self.cursor_x = 0
                                elif next_ch.name == 'KEY_HOME':
                                    self.cursor_x = 0
                                elif next_ch.name == 'KEY_END':
                                    self.cursor_x = len(self.lines[self.cursor_y])
                                elif next_ch.name == 'KEY_PAGEUP':
                                    self.cursor_y = max(0, self.cursor_y - self.get_visible_height())
                                elif next_ch.name == 'KEY_PAGEDOWN':
                                    self.cursor_y = min(len(self.lines) - 1, self.cursor_y + self.get_visible_height())
                                elif next_ch == 'n':
                                    self.next_match()
                                elif next_ch == '/':
                                    self.search()
                                elif next_ch == 's':
                                    filename = self.prompt("Save as: ")
                                    if filename:
                                        self.save_file(filename)
                                elif next_ch == 'o':
                                    filename = self.prompt("Open: ")
                                    if filename:
                                        self.open_file(filename)
                                elif next_ch == 'q':
                                    if self.modified:
                                        confirm = self.prompt("Unsaved changes. Quit anyway? (y/n): ")
                                        if confirm and confirm.lower() == 'y':
                                            break
                                    else:
                                        break
                                self.last_command = None
                            else:
                                # Just ESC pressed
                                pass
                        else:
                            # Windows - ESC just quits
                            if self.modified:
                                confirm = self.prompt("Unsaved changes. Quit anyway? (y/n): ")
                                if confirm and confirm.lower() == 'y':
                                    break
                            else:
                                break

                    # Ctrl+Arrows - custom Windows codes from get_key().
                    # На Linux обычные стрелки имеют code 258/259/260/261, поэтому
                    # проверка ">= 100" ломает обычную навигацию.
                    windows_ctrl_arrow_codes = {165, 166, 167, 168, 265, 266, 267, 268}
                    is_windows_ctrl_arrow = self.is_windows and (ch.code in windows_ctrl_arrow_codes)

                    if nm in ('KEY_UP', 'KEY_DOWN', 'KEY_LEFT', 'KEY_RIGHT') and is_windows_ctrl_arrow:
                        if nm == 'KEY_LEFT':
                            if self.cursor_x > 0:
                                line = self.lines[self.cursor_y]
                                while self.cursor_x > 0 and line[self.cursor_x - 1] in ' \t':
                                    self.cursor_x -= 1
                                while self.cursor_x > 0 and line[self.cursor_x - 1] not in ' \t':
                                    self.cursor_x -= 1
                            elif self.cursor_y > 0:
                                self.cursor_y -= 1
                                self.cursor_x = len(self.lines[self.cursor_y])
                        elif nm == 'KEY_RIGHT':
                            line = self.lines[self.cursor_y]
                            while self.cursor_x < len(line) and line[self.cursor_x] not in ' \t':
                                self.cursor_x += 1
                            while self.cursor_x < len(line) and line[self.cursor_x] in ' \t':
                                self.cursor_x += 1
                            if self.cursor_x >= len(line) and self.cursor_y < len(self.lines) - 1:
                                self.cursor_y += 1
                                self.cursor_x = 0
                                line = self.lines[self.cursor_y]
                                while self.cursor_x < len(line) and line[self.cursor_x] in ' \t':
                                    self.cursor_x += 1
                        elif nm == 'KEY_UP':
                            self.cursor_y = 0
                            self.cursor_x = 0
                        elif nm == 'KEY_DOWN':
                            self.cursor_y = len(self.lines) - 1
                            self.cursor_x = 0
                        self.last_command = None
                        continue

                    elif nm == 'KEY_UP':
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        if visual_y > 0:
                            self.move_cursor_visual(visual_y - 1, visual_x)
                        self.last_command = None

                    elif nm == 'KEY_DOWN':
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        if visual_y < len(self.visual_lines) - 1:
                            self.move_cursor_visual(visual_y + 1, visual_x)
                        self.last_command = None

                    elif nm == 'KEY_LEFT':
                        if self.cursor_x > 0:
                            self.cursor_x -= 1
                        elif self.cursor_y > 0:
                            self.cursor_y -= 1
                            self.cursor_x = len(self.lines[self.cursor_y])
                        self.last_command = None

                    elif nm == 'KEY_RIGHT':
                        if self.cursor_x < len(self.lines[self.cursor_y]):
                            self.cursor_x += 1
                        elif self.cursor_y < len(self.lines) - 1:
                            self.cursor_y += 1
                            self.cursor_x = 0
                        self.last_command = None

                    elif nm == 'KEY_HOME':
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        line_idx, wrap_idx, visual_text, full_line = self.visual_lines[visual_y]
                        vw = self.get_visible_width()
                        self.cursor_x = wrap_idx * vw if self.cursor_x > wrap_idx * vw else 0
                        self.last_command = None

                    elif nm == 'KEY_END':
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        line_idx, wrap_idx, visual_text, full_line = self.visual_lines[visual_y]
                        vw = self.get_visible_width()
                        self.cursor_x = min((wrap_idx + 1) * vw, len(full_line))
                        self.last_command = None

                    elif nm == 'KEY_PAGEUP':
                        # Move up by visible height in visual lines
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        new_visual_y = max(0, visual_y - self.get_visible_height())
                        self.move_cursor_visual(new_visual_y, visual_x)
                        self.last_command = None

                    elif nm == 'KEY_PAGEDOWN':
                        visual_y, visual_x = self.logical_to_visual(self.cursor_y, self.cursor_x)
                        new_visual_y = min(len(self.visual_lines) - 1, visual_y + self.get_visible_height())
                        self.move_cursor_visual(new_visual_y, visual_x)
                        self.last_command = None

                    elif nm == 'KEY_BACKSPACE':
                        self.last_command = None
                        if self.selection_active:
                            self.delete_selection()
                        else:
                            self.backspace()

                    elif nm == 'KEY_DELETE':
                        self.last_command = None
                        if self.selection_active:
                            self.delete_selection()
                        else:
                            self.delete_char()

                    elif nm in ('KEY_ENTER', 'ENTER'):
                        self.last_command = None
                        if self.selection_active:
                            self.delete_selection()
                        self.insert_newline()

                    elif nm == 'TAB':
                        self.last_command = None
                        if self.selection_active:
                            self.delete_selection()
                        self.insert_char('    ')

                    elif ch.isprintable() and nm is None:
                        if self.selection_active:
                            self.delete_selection()
                        if self.is_windows and hasattr(ch, 'char'):
                            self.insert_char(ch.char)
                        else:
                            self.insert_char(ch)
                    
                    # Handle Ctrl shortcuts cross-platform:
                    # Windows custom reader sets numeric code, blessed sets KEY_CTRL_* names.
                    is_ctrl_s = (ch.code == 19 or nm == 'KEY_CTRL_S')
                    is_ctrl_shift_s = (ch.code == 20 or nm == 'KEY_CTRL_T')
                    is_ctrl_o = (ch.code == 15 or nm == 'KEY_CTRL_O')
                    is_ctrl_q = (ch.code == 17 or nm == 'KEY_CTRL_Q')
                    is_ctrl_f = (ch.code == 6 or nm == 'KEY_CTRL_F')
                    is_ctrl_a = (ch.code == 1 or nm == 'KEY_CTRL_A')
                    is_ctrl_z = (ch.code == 26 or nm == 'KEY_CTRL_Z')
                    is_ctrl_y = (ch.code == 25 or nm == 'KEY_CTRL_Y')

                    if is_ctrl_s:  # Ctrl+S - Save to current file
                        self.last_command = None
                        if self.filename and os.path.isfile(self.filename):
                            # Save to existing file
                            self.save_file()
                        else:
                            # No filename - prompt for one
                            filename = self.prompt("Save as: ")
                            if filename:
                                self.save_file(filename)

                    elif is_ctrl_shift_s:  # Ctrl+Shift+S (Windows) / Ctrl+T (blessed) - Save As
                        self.last_command = None
                        filename = self.prompt("Save as: ")
                        if filename:
                            self.save_file(filename)

                    elif nm == 'KEY_F2':
                        self.last_command = None
                        filename = self.prompt("Save as: ")
                        if filename:
                            self.save_file(filename)

                    elif is_ctrl_o:  # Ctrl+O
                        self.last_command = None
                        filename = self.prompt("Open file: ")
                        if filename:
                            check_path = self._normalize_input_path(filename)
                            if os.path.isfile(check_path):
                                self.open_file(check_path)
                            else:
                                self.message = f"File not found: {check_path}"

                    elif is_ctrl_q:  # Ctrl+Q
                        if self.modified:
                            confirm = self.prompt("Unsaved changes. Quit anyway? (y/n): ")
                            if confirm and confirm.lower() == 'y':
                                break
                        else:
                            break

                    elif is_ctrl_f:  # Ctrl+F
                        self.last_command = None
                        # Если поиск уже активен - отключаем его
                        if self.search_text:
                            self.search_text = ""
                            self.search_matches = []
                            self.search_index = -1
                            self.message = "Search cleared"
                        else:
                            self.search()

                    elif is_ctrl_a:  # Ctrl+A - Select all file
                        self.last_command = None
                        self.select_all()

                    elif is_ctrl_z:  # Ctrl+Z - Undo
                        self.last_command = None
                        self.undo()

                    elif is_ctrl_y:  # Ctrl+Y - Redo
                        self.last_command = None
                        self.redo()

                    self.scroll_to_cursor()
                    self.draw()
            finally:
                # Restore terminal settings (Unix only)
                if old_settings is not None:
                    try:
                        import termios
                        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                    except (ImportError, OSError):
                        pass
                # Show cursor on exit
                sys.stdout.write('\033[?25h')
                sys.stdout.flush()


def main():
    editor = TextEditor()
    try:
        editor.run()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
