import sys, os, ctypes, time, shutil

if sys.platform == 'win32':
    import msvcrt
    try:
        os.system('chcp 65001 >nul 2>&1')
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-10), 7)
    except: pass
else:
    msvcrt = None

def wrap_line(line, width):
    if not line: return [""]
    wrapped, current = [], ""
    for char in line:
        if len(current) >= width:
            wrapped.append(current)
            current = ""
        current += char
    wrapped.append(current) if current else None
    return wrapped or [""]

from blessed import Terminal

class TextEditor:
    def __init__(self):
        self.term = Terminal()
        self.lines, self.cursor_x, self.cursor_y, self.scroll_y = [""], 0, 0, 0
        self.filename, self.modified = None, False
        self.message = ""
        self.search_text, self.search_index, self.search_matches = "", -1, []
        self.selection_start = self.selection_end = None
        self.selection_active = False
        self.clipboard = ""
        self.undo_stack, self.redo_stack = [], []
        self.last_command, self.visual_lines = None, []
        self._build_visual_lines()
        self.last_term_width, self.last_term_height = self.term.width, self.term.height

    def get_visible_height(self): return self.term.height - 1
    def get_line_num_width(self): return max(2, len(str(max(1, len(self.lines)))))
    def get_visible_width(self): return max(10, self.term.width - (self.get_line_num_width() + 1))

    def _build_visual_lines(self):
        self.visual_lines = []
        vw = self.get_visible_width()
        for li, line in enumerate(self.lines):
            for wi, vt in enumerate(wrap_line(line, vw)):
                self.visual_lines.append((li, wi, vt, line))

    def _short_path(self, p):
        if not p: return "Untitled"
        try: return os.path.relpath(p, os.path.expanduser('~'))
        except: return p

    def _norm_path(self, raw):
        if not raw: return ""
        p = raw.strip().replace('\x1b[200~', '').replace('\x1b[201~', '')
        if len(p) >= 2 and p[0] == '"' and p[-1] == '"': p = p[1:-1]
        p = os.path.expanduser(p)
        return os.path.abspath(p) if not os.path.isabs(p) else p

    def logical_to_visual(self, ly, lx):
        vw = self.get_visible_width()
        for vy, (li, wi, vt, fl) in enumerate(self.visual_lines):
            if li == ly:
                sx, ex = wi * vw, min((wi + 1) * vw, len(fl))
                if sx <= lx < ex or (wi == len(wrap_line(fl, vw)) - 1 and lx >= sx):
                    return vy, lx - sx
        return 0, 0

    def visual_to_logical(self, vy):
        if 0 <= vy < len(self.visual_lines):
            li, wi, vt, fl = self.visual_lines[vy]
            return li, wi * self.get_visible_width()
        return 0, 0

    def move_cursor_visual(self, vy, vx):
        if 0 <= vy < len(self.visual_lines):
            li, wi, vt, fl = self.visual_lines[vy]
            self.cursor_y = li
            self.cursor_x = min(vx + wi * self.get_visible_width(), len(fl))

    def scroll_to_cursor(self):
        vh = self.get_visible_height()
        vy, _ = self.logical_to_visual(self.cursor_y, self.cursor_x)
        if vy < self.scroll_y: self.scroll_y = vy
        elif vy >= self.scroll_y + vh: self.scroll_y = vy - vh + 1

    def insert_char(self, ch):
        if self.search_text: self.search_text = ""; self.search_matches = []; self.search_index = -1
        line = self.lines[self.cursor_y]
        self.lines[self.cursor_y] = line[:self.cursor_x] + ch + line[self.cursor_x:]
        self.cursor_x += 1; self.modified = True; self._build_visual_lines()

    def insert_newline(self):
        line = self.lines[self.cursor_y]
        after = line[self.cursor_x:]
        self.lines[self.cursor_y] = line[:self.cursor_x]
        self.lines.insert(self.cursor_y + 1, after)
        self.cursor_y += 1; self.cursor_x = 0
        self.modified = True; self._build_visual_lines()

    def delete_char(self):
        line = self.lines[self.cursor_y]
        if self.cursor_x < len(line):
            self.lines[self.cursor_y] = line[:self.cursor_x] + line[self.cursor_x + 1:]
        elif self.cursor_y > 0:
            self.lines[self.cursor_y - 1] += line
            del self.lines[self.cursor_y]
            self.cursor_y -= 1; self.cursor_x = len(self.lines[self.cursor_y])
        self.modified = True; self._build_visual_lines()

    def backspace(self):
        if self.cursor_x > 0:
            line = self.lines[self.cursor_y]
            self.lines[self.cursor_y] = line[:self.cursor_x - 1] + line[self.cursor_x:]
            self.cursor_x -= 1
        elif self.cursor_y > 0:
            prev = self.lines[self.cursor_y - 1]
            self.lines[self.cursor_y - 1] = prev + self.lines[self.cursor_y]
            del self.lines[self.cursor_y]
            self.cursor_y -= 1; self.cursor_x = len(prev)
        self.modified = True; self._build_visual_lines()

    def undo(self):
        if self.undo_stack:
            self.redo_stack.append(self.undo_stack.pop())
            self.modified = True; self._build_visual_lines()
            self.message = "Undo"

    def redo(self):
        if self.redo_stack:
            self.undo_stack.append(self.redo_stack.pop())
            self.modified = True; self._build_visual_lines()
            self.message = "Redo"

    def save_file(self, fn=None):
        if fn: self.filename = self._norm_path(fn)
        if not self.filename: self.message = "No filename"; return False
        try:
            with open(self.filename, 'w', encoding='utf-8') as f:
                f.write('\n'.join(self.lines))
            self.modified = False
            self.message = f"Saved: {self._short_path(self.filename)}"
            return True
        except Exception as e: self.message = f"Error: {e}"; return False

    def open_file(self, fn):
        n = self._norm_path(fn)
        try:
            with open(n, 'r', encoding='utf-8') as f:
                self.lines = f.read().split('\n') or [""]
            self.filename = n; self.cursor_x = self.cursor_y = self.scroll_y = 0
            self.modified = False; self._build_visual_lines()
            self.message = f"Opened: {self._short_path(self.filename)}"
            return True
        except Exception as e: self.message = f"Error: {e}"; return False

    def find_matches(self):
        self.search_matches = []
        if not self.search_text: return
        sl = self.search_text.lower()
        for li, line in enumerate(self.lines):
            start = 0
            while True:
                pos = line.lower().find(sl, start)
                if pos == -1: break
                self.search_matches.append((li, pos, pos + len(self.search_text)))
                start = pos + 1

    def next_match(self):
        if not self.search_matches: return
        self.search_index = (self.search_index + 1) % len(self.search_matches)
        li, st, _ = self.search_matches[self.search_index]
        self.cursor_y, self.cursor_x = li, st
        self.scroll_to_cursor()

    def select_all(self):
        last_i = len(self.lines) - 1
        while last_i > 0 and len(self.lines[last_i]) == 0: last_i -= 1
        self.selection_start = (0, 0)
        self.selection_end = (last_i, len(self.lines[last_i]))
        self.selection_active = True

    def delete_selection(self):
        if not self.selection_active or not self.selection_start or not self.selection_end:
            return
        sl, sc = self.selection_start
        el, ec = self.selection_end
        if sl == el:
            line = self.lines[sl]
            self.lines[sl] = line[:sc] + line[ec:]
        else:
            self.lines[sl] = self.lines[sl][:sc] + self.lines[el][ec:]
            del self.lines[sl + 1:el + 1]
        self.cursor_y, self.cursor_x = sl, sc
        self.selection_active = False
        self.selection_start = self.selection_end = None
        self.modified = True; self._build_visual_lines()

    def replace_selection(self, ch):
        self.delete_selection()
        self.insert_char(ch)

    def get_key(self):
        if sys.platform == 'win32':
            if not msvcrt.kbhit(): return None
            ch = msvcrt.getwch()
            if not ch:
                return None
            
            o = ord(ch)
            
            if o == 27:
                if not msvcrt.kbhit(): return type('K', (), {'name': 'ESC', 'isprintable': lambda s: False})()
                c2 = msvcrt.getwch()
                if c2 == '[':
                    c3 = msvcrt.getwch()
                    codes = {'A':'KEY_UP','B':'KEY_DOWN','C':'KEY_RIGHT','D':'KEY_LEFT','H':'KEY_HOME','F':'KEY_END'}
                    if c3 in codes: return type('K', (), {'name': codes.get(c3,'KEY_UNKNOWN'), 'isprintable': lambda s: False})()
                    if c3 in ('3','5','6') and msvcrt.kbhit():
                        c4 = msvcrt.getwch()
                        if c4 == '~':
                            ks = {'3':'KEY_DELETE','5':'KEY_PAGEUP','6':'KEY_PAGEDOWN'}
                            return type('K', (), {'name': ks.get(c3,'KEY_UNKNOWN'), 'isprintable': lambda s: False})()
                return type('K', (), {'name': 'ESC', 'isprintable': lambda s: False})()
            
            if o == 224:
                c2 = msvcrt.getwch()
                if not c2: return None
                c2o = ord(c2)
                name = {72:'KEY_UP',80:'KEY_DOWN',75:'KEY_LEFT',77:'KEY_RIGHT',71:'KEY_HOME',79:'KEY_END',73:'KEY_PAGEUP',81:'KEY_PAGEDOWN',83:'KEY_DELETE'}.get(c2o)
                if not name and c2 == 'S': name = 'KEY_DELETE'
                if not name and c2 == 'G': name = 'KEY_HOME'
                if not name and c2 == 'O': name = 'KEY_END'
                if not name and c2 == 'I': name = 'KEY_PAGEUP'
                if not name and c2 == 'Q': name = 'KEY_PAGEDOWN'
                if name: return type('K', (), {'name': name, 'isprintable': lambda s: False})()
                return type('K', (), {'name': 'KEY_UNKNOWN', 'isprintable': lambda s: False})()
            
            if o == 13: return type('K', (), {'name': 'ENTER', 'isprintable': lambda s: False})()
            if o in (8, 127): return type('K', (), {'name': 'KEY_BACKSPACE', 'isprintable': lambda s: False})()
            if o == 9: return type('K', (), {'name': 'TAB', 'isprintable': lambda s: False})()
            if o == 0 or o in (91, 59): return None
            if 1 <= o <= 26:
                ctrl_codes = {1:'KEY_CTRL_A',2:'KEY_CTRL_B',3:'KEY_CTRL_C',4:'KEY_CTRL_D',5:'KEY_CTRL_E',6:'KEY_CTRL_F',7:'KEY_CTRL_G',8:'KEY_CTRL_H',9:'KEY_CTRL_I',10:'KEY_CTRL_J',11:'KEY_CTRL_K',12:'KEY_CTRL_L',13:'KEY_CTRL_M',14:'KEY_CTRL_N',15:'KEY_CTRL_O',16:'KEY_CTRL_P',17:'KEY_CTRL_Q',18:'KEY_CTRL_R',19:'KEY_CTRL_S',20:'KEY_CTRL_T',21:'KEY_CTRL_U',22:'KEY_CTRL_V',23:'KEY_CTRL_W',24:'KEY_CTRL_X',25:'KEY_CTRL_Y',26:'KEY_CTRL_Z'}
                nm = ctrl_codes.get(o)
                if nm: return type('K', (), {'name': nm, 'isprintable': lambda s: False})()
            if o >= 32:
                return type('K', (), {'name': None, 'isprintable': lambda s: True, 'char': ch})()
            return None
        else:
            k = self.term.inkey(timeout=0.01)
            return k if k else None

    def draw(self):
        out = []
        w = out.append
        w(self.term.home + self.term.clear)
        vh = self.term.height - 1
        vw = self.get_visible_width()
        lnw = self.get_line_num_width()
        vlines, nl = self.visual_lines, len(self.visual_lines)

        for i in range(vh):
            vi = self.scroll_y + i
            if vi >= nl: w(f'\033[{i+1};1H{" " * (lnw + 1 + vw)}'); continue
            li, wi, vt, fl = vlines[vi]
            w(f'\033[{i+1};1H\033[1m{li+1:>{lnw}}\033[0m ' if wi == 0 else f'\033[{i+1};1H{" " * lnw} ')
            w(f'\033[{i+1};{lnw+2}H')
            if self.selection_active and self.selection_start and self.selection_end:
                sl, sc = self.selection_start
                el, ec = self.selection_end
                if sl <= li <= el:
                    vs = wi * vw
                    ss = sc - vs if li == sl else 0
                    se = ec - vs if li == el else len(vt)
                    ss, se = max(0, ss), min(len(vt), se)
                    if ss > 0: w(vt[:ss])
                    if ss < se: w(f'\033[7m{vt[ss:se]}\033[0m')
                    if se < len(vt): w(vt[se:])
                else: w(vt)
            elif self.search_text and self.search_matches:
                for p, m in self._highlight_search(vt, li): w(f'\033[43m\033[30m{p}\033[0m' if m else p)
            else: w(vt)
            if len(vt) < vw - 1: w(' ' * (vw - 1 - len(vt)))

        status = f" {self._short_path(self.filename)} "
        if self.modified: status += "| [*] "
        status += f"| Ln {self.cursor_y+1}, Col {self.cursor_x+1} "
        if self.selection_active and self.selection_start and self.selection_end:
            sl, sc = self.selection_start
            el, ec = self.selection_end
            status += f"| Sel: {el-sl+1} line(s) "
        if self.search_text: status += f"| Search: {self.search_text} "
        if self.message: status += f"| {self.message}"
        w(f'\033[{vh};1H\033[7m{status.ljust(self.term.width)}\033[0m')

        vy, vx = self.logical_to_visual(self.cursor_y, self.cursor_x)
        cy, cx = vy - self.scroll_y + 1, lnw + 2 + vx
        if 1 <= cy <= vh and vy < nl:
            ch = vlines[vy][2][vx] if vx < len(vlines[vy][2]) else ' '
            w(f'\033[{cy};{cx}H\033[7m{ch}\033[0m')
        sys.stdout.write(''.join(out)); sys.stdout.flush()

    def _highlight_search(self, text, li):
        if not self.search_text or not self.search_matches: return [(text, False)]
        res, last = [], 0
        for ml, st, en in self.search_matches:
            if ml != li: continue
            if st >= len(text): break
            if st < last: continue
            if st > last: res.append((text[last:st], False))
            res.append((text[st:min(en,len(text))], True)); last = en
        if last < len(text): res.append((text[last:], False))
        return res or [(text, False)]

    def prompt(self, ptext):
        sys.stdout.write('\033[?25l'); sys.stdout.flush()
        prow = self.term.height - 1

        def draw(s, pos):
            sys.stdout.write(f'\033[{prow+1};1H\033[K{ptext}')
            if pos <= len(s):
                sys.stdout.write(s[:pos])
                c = s[pos] if pos < len(s) else ' '
                sys.stdout.write(f'\033[7m{c}\033[0m' + s[pos+1:])
            else: sys.stdout.write(s)
            sys.stdout.flush()

        s, pos = "", 0; draw(s, pos)
        while True:
            if sys.platform == 'win32':
                if not msvcrt.kbhit(): time.sleep(0.01); continue
                ch = msvcrt.getwch()
                o = ord(ch)
                if o == 13: break
                if o == 8 and pos > 0: s = s[:pos-1] + s[pos:]; pos -= 1; draw(s, pos)
                elif o == 27:
                    if msvcrt.kbhit():
                        c2 = msvcrt.getwch()
                        if c2 == '[' and msvcrt.kbhit():
                            c3 = msvcrt.getwch()
                            if c3 == 'C' and pos < len(s): pos += 1; draw(s, pos)
                            elif c3 == 'D' and pos > 0: pos -= 1; draw(s, pos)
                    else: return None
                elif o >= 32: s = s[:pos] + ch + s[pos:]; pos += 1; draw(s, pos)
            else:
                k = self.term.inkey()
                nm, st = k.name, str(k)
                if nm in ('ENTER','KEY_ENTER') or st in ('\r','\n'): break
                if nm == 'KEY_BACKSPACE' and pos > 0: s = s[:pos-1] + s[pos:]; pos -= 1; draw(s, pos)
                elif nm == 'KEY_LEFT' and pos > 0: pos -= 1; draw(s, pos)
                elif nm == 'KEY_RIGHT' and pos < len(s): pos += 1; draw(s, pos)
                elif k.isprintable(): s = s[:pos] + k + s[pos:]; pos += 1; draw(s, pos)
        sys.stdout.write('\033[?25h'); sys.stdout.flush()
        return s

    def run(self):
        if len(sys.argv) > 1:
            self.open_file(sys.argv[1] if os.path.isabs(sys.argv[1]) else os.path.abspath(sys.argv[1]))
        with self.term.fullscreen(), self.term.cbreak():
            sys.stdout.write('\033[?25l'); sys.stdout.flush()
            self.draw()
            while True:
                if self.term.width != self.last_term_width or self.term.height != self.last_term_height:
                    self.last_term_width, self.last_term_height = self.term.width, self.term.height
                    self._build_visual_lines(); self.draw()
                ch = self.get_key()
                if not ch: continue
                self.message = ""
                nm = ch.name if hasattr(ch, 'name') else None

                if nm == 'ESC':
                    if not sys.platform == 'win32':
                        nc = self.term.inkey(timeout=0.01)
                        if nc:
                            ns = nc.name
                            if ns == 'KEY_UP' and self.cursor_y > 0: self.cursor_y -= 1
                            elif ns == 'KEY_DOWN' and self.cursor_y < len(self.lines) - 1: self.cursor_y += 1
                            elif ns == 'KEY_LEFT':
                                if self.cursor_x > 0: self.cursor_x -= 1
                                elif self.cursor_y > 0: self.cursor_y -= 1; self.cursor_x = len(self.lines[self.cursor_y])
                            elif ns == 'KEY_RIGHT':
                                if self.cursor_x < len(self.lines[self.cursor_y]): self.cursor_x += 1
                                elif self.cursor_y < len(self.lines) - 1: self.cursor_y += 1; self.cursor_x = 0
                            elif ns == '/': self._search()
                            elif ns == 'n': self.next_match()
                            elif ns == 's': fn = self.prompt("Save: "); self.save_file(fn) if fn else None
                            elif ns == 'o': fn = self.prompt("Open: "); self.open_file(fn) if fn else None
                            elif ns == 'q':
                                if self.modified:
                                    c = self.prompt("Unsaved. Quit? (y/n): ")
                                    if c and c.lower() == 'y': break
                                else: break
                    else:
                        if self.modified:
                            c = self.prompt("Unsaved. Quit? (y/n): ")
                            if c and c.lower() == 'y': break
                        else: break

                elif nm == 'KEY_UP':
                    vy, vx = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    if vy > 0: self.move_cursor_visual(vy - 1, vx)
                elif nm == 'KEY_DOWN':
                    vy, vx = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    if vy < len(self.visual_lines) - 1: self.move_cursor_visual(vy + 1, vx)
                elif nm == 'KEY_LEFT':
                    if self.cursor_x > 0: self.cursor_x -= 1
                    elif self.cursor_y > 0: self.cursor_y -= 1; self.cursor_x = len(self.lines[self.cursor_y])
                elif nm == 'KEY_RIGHT':
                    if self.cursor_x < len(self.lines[self.cursor_y]): self.cursor_x += 1
                    elif self.cursor_y < len(self.lines) - 1: self.cursor_y += 1; self.cursor_x = 0
                elif nm == 'KEY_HOME':
                    vy, _ = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    _, wi, _, _ = self.visual_lines[vy]
                    self.cursor_x = wi * self.get_visible_width()
                elif nm == 'KEY_END':
                    vy, _ = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    _, wi, _, fl = self.visual_lines[vy]
                    self.cursor_x = min((wi + 1) * self.get_visible_width(), len(fl))
                elif nm == 'KEY_PAGEUP':
                    vy, vx = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    self.move_cursor_visual(max(0, vy - self.get_visible_height()), vx)
                elif nm == 'KEY_PAGEDOWN':
                    vy, vx = self.logical_to_visual(self.cursor_y, self.cursor_x)
                    self.move_cursor_visual(min(len(self.visual_lines) - 1, vy + self.get_visible_height()), vx)
                elif nm in ('KEY_BACKSPACE','KEY_DELETE'):
                    if self.selection_active:
                        self.delete_selection()
                        self.message = "Selection deleted"
                    else:
                        self.backspace() if nm == 'KEY_BACKSPACE' else self.delete_char()
                elif nm in ('KEY_ENTER','ENTER'): self.insert_newline()
                elif nm == 'TAB': self.insert_char('    ')
                elif nm == 'KEY_F2': fn = self.prompt("Save: "); self.save_file(fn) if fn else None

                if nm and nm.startswith('KEY_CTRL_'):
                    code = ch.code if hasattr(ch, 'code') else -1
                    if nm == 'KEY_CTRL_S': self.save_file()
                    elif nm == 'KEY_CTRL_O':
                        fn = self.prompt("Open: ")
                        if fn: self.open_file(fn)
                    elif nm == 'KEY_CTRL_F': self._search()
                    elif nm == 'KEY_CTRL_A': self.select_all()
                    elif nm == 'KEY_CTRL_Z': self.undo()
                    elif nm == 'KEY_CTRL_Y': self.redo()
                    elif nm == 'KEY_CTRL_Q':
                        if self.modified:
                            c = self.prompt("Unsaved. Quit? (y/n): ")
                            if c and c.lower() == 'y': break
                        else: break
                elif nm and nm.startswith('KEY_F'):
                    pass

                elif nm is None or nm == 'KEY_UNKNOWN':
                    if hasattr(ch, 'isprintable') and ch.isprintable() and hasattr(ch, 'char'):
                        if self.selection_active:
                            self.replace_selection(ch.char)
                        else:
                            self.insert_char(ch.char)

                self.scroll_to_cursor()
                self.draw()
        sys.stdout.write('\033[?25h'); sys.stdout.flush()

    def _search(self):
        t = self.prompt("Search: ")
        if t:
            self.search_text = t; self.search_index = -1
            self.find_matches()
            if self.search_matches:
                self.next_match()
                self.message = f"Found {len(self.search_matches)}"
            else: self.message = "No matches"

def install():
    src = os.path.abspath(__file__)
    install_dir = os.path.join(os.environ['LOCALAPPDATA'], 'pup-editor')
    bat_dir = os.path.join(os.environ['LOCALAPPDATA'], 'Microsoft', 'WindowsApps')
    
    if not os.path.exists(install_dir):
        os.makedirs(install_dir)
    
    dst = os.path.join(install_dir, 'editor.py')
    shutil.copy2(src, dst)
    
    bat_path = os.path.join(bat_dir, 'pup.bat')
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\npython "{dst}" %*\n')
    
    print(f"pup editor installed!")
    print(f"Location: {install_dir}")
    print(f"Command: pup")
    print("Restart terminal to use.")

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--install':
        install()
    else:
        try: TextEditor().run()
        except KeyboardInterrupt: pass

if __name__ == "__main__": main()