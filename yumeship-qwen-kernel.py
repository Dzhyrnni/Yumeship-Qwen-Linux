import random
import datetime
import tkinter as tk
from tkinter import ttk


# ============================================================================
# PALETTE: "Jerusalem Scroll" — a Jewish legacy theme (gold / teal / stone)
# Classic TempleOS orange-on-blue, re-toned to menorah gold on starry indigo
# with Jerusalem-stone tan and Ark teal accents. Retro DOS feel preserved.
# ============================================================================
BG_BLUE = "#141A2E"        # deep starry-night indigo (page / terminal backdrop)
BG_BLUE_DEEP = "#0E1322"   # darker surface (panels, treeview field, status)
BG_BLUE_ALT = "#1B2640"    # raised element (buttons, tab bars, headers)
ORANGE = "#E6C96A"         # menorah gold (primary text, prompts)
ORANGE_DIM = "#9C8E6E"     # Jerusalem-stone tan (secondary text, facts, icons)
ORANGE_BRIGHT = "#F5E6B0"  # light gold-cream (bright text, selected tab)
ORANGE_RED = "#C1502E"     # terracotta (warnings, boot hint)
BORDER_BLUE = "#6E6044"    # stone-brown border / bevel
SELECT = "#3BA8A8"         # Ark teal (selection, active states)

# semantic aliases (same values)
BG_PAGE = BG_BLUE
BG_PANEL = BG_BLUE_DEEP
BG_RAISED = BG_BLUE_ALT
FG_GOLD = ORANGE
FG_STONE = ORANGE_DIM
FG_CREAM = ORANGE_BRIGHT
FG_TERRA = ORANGE_RED
BORDER_STONE = BORDER_BLUE
ACCENT_TEAL = SELECT

FONT_MONO = ("DejaVu Sans Mono", 11)
FONT_MONO_SM = ("DejaVu Sans Mono", 9)
FONT_UI = ("Segoe UI", 9)
FONT_UI_BOLD = ("Segoe UI", 9, "bold")


# ============================================================================
# Virtual Environment (fake OS identity)
# ============================================================================
class VirtualEnv:
    def __init__(self):
        self.user = "rebbe"
        self.hostname = "YUshiveOS"
        self.os_name = "YUshiveLinux"
        self.version = "0.3.0"
        self.kernel = "YUmeKernel 0.3 (shomer Shabbat)"
        self.volume = "CholentHD"
        self.fs_type = "KosherFS"
        self.arch = "x86_64 (observant)"
        self.cpu_hz = "74-MHz (unclamped, like the clock in shul)"
        self.memory = "640K (more than enough for anyone)"
        self.boot_time = datetime.datetime.now()
        self.boot_sequence = 0
        self.uptime_seconds = 0

    def uptime_str(self):
        s = self.uptime_seconds
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        return f"{h}:{m:02d}:{sec:02d}"

    def tick(self):
        self.uptime_seconds += 1


VENV = VirtualEnv()


# ============================================================================
# Virtual Filesystem (self-contained, simulated)
# ============================================================================
class VFSNode:
    def __init__(self, name, ntype, content="", perms="rwxr-xr-x"):
        self.name = name
        self.type = ntype  # 'dir' | 'file'
        self.content = content
        self.perms = perms
        self.mtime = datetime.datetime.now()
        self.children = {}

    @property
    def size(self):
        if self.type == "dir":
            return 0
        return len(self.content.encode("utf-8", errors="replace"))


class VirtualFS:
    def __init__(self):
        self.root = VFSNode("/", "dir", perms="drwxr-xr-x")
        self.total_capacity = 128 * 1024 * 1024  # fake 128MB disk
        self._seed()

    # ---- path helpers -----------------------------------------------------
    def _split(self, path):
        parts = [p for p in path.split("/") if p and p != "/"]
        return parts

    def resolve(self, path, cwd="/Home"):
        """Return the node at path, or None. Supports absolute and relative."""
        if not path:
            path = cwd
        elif path == "~":
            path = "/Home"
        elif path.startswith("~/"):
            path = "/Home/" + path[2:]
        elif not path.startswith("/"):
            path = cwd.rstrip("/") + "/" + path if cwd != "/" else "/" + path

        parts = self._split(path)
        node = self.root
        for part in parts:
            if part in ("", "."):
                continue
            if part == "..":
                node = self._parent_of(node)
                if node is None:
                    return None
                continue
            if node.type != "dir" or part not in node.children:
                return None
            node = node.children[part]
        return node

    def _parent_of(self, node):
        if node is self.root:
            return None
        # walk the tree to find parent
        parent = self._find_parent(self.root, node)
        return parent

    def _find_parent(self, cur, target):
        if cur.type != "dir":
            return None
        for child in cur.children.values():
            if child is target:
                return cur
            p = self._find_parent(child, target)
            if p is not None:
                return p
        return None

    def _path_of(self, node):
        """Return virtual absolute path string for a node."""
        if node is self.root:
            return "/"
        path = []
        def walk(cur, cur_path):
            if cur is node:
                path.append(cur_path)
                return True
            if cur.type != "dir":
                return False
            for child in cur.children.values():
                p = cur_path.rstrip("/") + "/" + child.name if cur_path != "/" else "/" + child.name
                if walk(child, p):
                    return True
            return False
        walk(self.root, "/")
        return path[0] if path else "/"

    def join(self, base, *parts):
        segs = [s.strip("/") for s in (base,) + parts if s]
        return "/" + "/".join(s for s in segs if s) if segs else "/"

    # ---- filesystem ops ---------------------------------------------------
    def listdir(self, path, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None or node.type != "dir":
            return None
        return node.children

    def read(self, path, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None:
            return None
        if node.type == "dir":
            return "EISDIR"
        return node.content

    def write(self, path, content, cwd="/Home", append=False):
        node = self.resolve(path, cwd)
        if node is None:
            # create the file at the given path
            return self.mkfile(path, content=content, cwd=cwd)
        if node.type == "dir":
            return "EISDIR"
        node.content = node.content + content if append else content
        node.mtime = datetime.datetime.now()
        return None

    def mkdir(self, path, cwd="/Home"):
        parts = self._split(path)
        if not parts:
            return "EEXIST"
        raw_abs = path.startswith("/") or path.startswith("~/")
        parent = self._resolve_parent(parts, cwd, raw_abs)
        if parent is None:
            return "ENOENT"
        name = parts[-1]
        if name in parent.children:
            return "EEXIST"
        parent.children[name] = VFSNode(name, "dir", perms="drwxr-xr-x")
        return None

    def mkfile(self, path, content="", cwd="/Home"):
        parts = self._split(path)
        if not parts:
            return "EEXIST"
        raw_abs = path.startswith("/") or path.startswith("~/")
        parent = self._resolve_parent(parts, cwd, raw_abs)
        if parent is None:
            return "ENOENT"
        name = parts[-1]
        if name in parent.children:
            return "EEXIST"
        parent.children[name] = VFSNode(name, "file", content=content, perms="-rw-r--r--")
        return None

    def _resolve_parent(self, parts, cwd, raw_abs=False):
        """Resolve the parent directory node for a path.

        parts: split components of the path
        cwd:   current directory (virtual path)
        raw_abs: True if the original path was absolute
        """
        if len(parts) == 1:
            # parent is the cwd itself (or / for absolute single name)
            if raw_abs:
                node = self.resolve("/", "/")
            else:
                node = self.resolve(cwd, "/")
        else:
            if raw_abs:
                parent_path = "/" + "/".join(parts[:-1])
                node = self.resolve(parent_path, "/")
            else:
                parent_path = "/".join(parts[:-1])
                node = self.resolve(parent_path, cwd)
        if node is not None and node.type == "dir":
            return node
        return None

    def rm(self, path, cwd="/Home"):
        parts = self._split(path)
        if not parts:
            return "EROOT"
        parent = self._resolve_parent(parts, cwd, path.startswith("/") or path.startswith("~/"))
        if parent is None:
            return "ENOENT"
        name = parts[-1]
        if name not in parent.children:
            return "ENOENT"
        if name in ("Home", "System", "C", "Boot"):
            return "EPROTECT"
        del parent.children[name]
        return None

    def mv(self, src, dst, cwd="/Home"):
        node = self.resolve(src, cwd)
        if node is None:
            return "ENOENT"
        dst_node = self.resolve(dst, cwd)
        if dst_node is not None and dst_node.type == "dir":
            # move into dir keeping name
            dst = self.join(self._path_of(dst_node), node.name)
        sparts = self._split(src)
        sparent = self._resolve_parent(sparts, cwd, src.startswith("/") or src.startswith("~/"))
        if sparent is None:
            return "ENOENT"
        dparts = self._split(dst)
        dparent = self._resolve_parent(dparts, cwd, dst.startswith("/") or dst.startswith("~/"))
        if dparent is None:
            return "ENOENT"
        sparent.children.pop(node.name, None)
        node.name = dparts[-1]
        dparent.children[node.name] = node
        return None

    def disk_usage(self):
        total = 0
        def walk(node):
            nonlocal total
            total += node.size
            if node.type == "dir":
                for c in node.children.values():
                    walk(c)
        walk(self.root)
        return total

    def find(self, pattern, cwd="/Home", start="/"):
        hits = []
        root = self.resolve(start, cwd)
        def walk(node, cur_path):
            if pattern in node.name:
                hits.append(cur_path)
            if node.type == "dir":
                for c in node.children.values():
                    p = cur_path.rstrip("/") + "/" + c.name if cur_path != "/" else "/" + c.name
                    walk(c, p)
        if root:
            start_path = start if start.startswith("/") else cwd
            walk(root, start_path)
        return hits

    def walk(self, start="/", cwd="/Home"):
        root = self.resolve(start, cwd)
        out = []
        if root is None:
            return out
        def visit(node, cur_path, depth):
            out.append((cur_path, node, depth))
            if node.type == "dir":
                for c in node.children.values():
                    p = cur_path.rstrip("/") + "/" + c.name if cur_path != "/" else "/" + c.name
                    visit(c, p, depth + 1)
        visit(root, start if start.startswith("/") else cwd, 0)
        return out

    def stat(self, path, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None:
            return None
        return node

    # ---- seeding ----------------------------------------------------------
    def _seed(self):
        HO = VFSNode("Home", "dir", perms="drwxr-xr-x")
        SY = VFSNode("System", "dir", perms="drwxr-xr-x")
        C = VFSNode("C", "dir", perms="drwxr-xr-x")
        BO = VFSNode("Boot", "dir", perms="drwxr-xr-x")
        TEMP = VFSNode("Temp", "dir", perms="drwxrwxrwx")
        LOGS = VFSNode("Logs", "dir", perms="drwxr-xr-x")

        SY.children["Kernel.HC"] = VFSNode("Kernel.HC", "file", content=(
            "// YUme Kernel - compiled by the hand of the Rebbe\n"
            "U0 Kernel( ) {\n"
            "  \"Welcome to YUshiveOS.\\n\";\n"
            "  Davening(HA_SHEM);\n"
            "}\n"
        ), perms="-rw-r--r--")
        SY.children["README.txt"] = VFSNode("README.txt", "file", content=(
            "YUshiveLinux - a tribute to a certain holy OS,\n"
            "now with a fine Yiddish accent.\n"
            "Everything here is virtual. Nothing touches your real machine.\n"
            "Type 'help' in the Terminal (and press TAB to hurry).\n"
            "Blessed be HaShem, and pass the kreplach.\n"
        ), perms="-rw-r--r--")
        SY.children["FirstBoot.HC"] = VFSNode("FirstBoot.HC", "file", content=(
            "U0 FirstBoot( ) {\n"
            "  \"A virgin boot! Check the cholent.\\n\";\n"
            "  Sleep(2000);\n"
            "  \"Ring of fire test... OK, under the sukkah.\\n\";\n"
            "}\n"
        ), perms="-rw-r--r-")
        SY.children["CLI.HC"] = VFSNode("CLI.HC", "file", content=(
            "// The command line interpreter.\n"
            "U0 CLI( ) { for(;;) \"%s$\", CLI_Prompt; }\n"
        ), perms="-rw-r--r-")
        SY.children["Temple.txt"] = VFSNode("Temple.txt", "file", content=(
            "The Holy Temple stood in Jerusalem, the center of all worship.\n"
            "Its successor, some say, was a lonely operating system.\n"
            "This one is virtual, but the prayers are real.\n"
            "Its graphics are a love letter to the C64 and the menorah.\n"
        ), perms="-rw-r--r--")

        APPS = VFSNode("Apps", "dir", perms="drwxr-xr-x")
        APPS.children["Editor.HC"] = VFSNode("Editor.HC", "file", content=(
            "// A simple text editor. It even corrects your Yiddish.\n"
            "U0 Editor( ) { ... }\n"
        ), perms="-rw-r--r-")
        APPS.children["Solitaire.HC"] = VFSNode("Solitaire.HC", "file", content=(
            "// Card game. There is no game. Only cards.\n"
            "U0 Solitaire( ) { ... }\n"
        ), perms="-rw-r--r--")
        UTILS = VFSNode("Utils", "dir", perms="drwxr-xr-x")
        UTILS.children["Bochs.HC"] = VFSNode("Bochs.HC", "file", content="// Emulator. Very virtual, very good.\n", perms="-rw-r--r-")
        UTILS.children["Chess.HC"] = VFSNode("Chess.HC", "file", content="// It cheats. Ask its mother.\n", perms="-rw-r--r-")
        GAMES = VFSNode("OurGames", "dir", perms="drwxr-xr-x")
        GAMES.children["Dreidel.SYM"] = VFSNode("Dreidel.SYM", "file", content=":C64: REM 10 PRINT GIMEL; 20 GOTO 10\n", perms="-rw-r--r-")
        YESHIVA = VFSNode("Yeshiva", "dir", perms="drwxr-xr-x")
        YESHIVA.children["DafYomi.txt"] = VFSNode("DafYomi.txt", "file", content=(
            "Daf Yomi - one page a day.\n"
            "Today's tractate: Berakhot, page 2a.\n"
            "Question: when may the Shema be recited?\n"
            "Answer: when the defrag is finished.\n"
        ), perms="-rw-r--r--")
        C.children["Apps"] = APPS
        C.children["Utils"] = UTILS
        C.children["OurGames"] = GAMES
        C.children["Yeshiva"] = YESHIVA

        BO.children["BOOT.BIN"] = VFSNode("BOOT.BIN", "file", content="\x7fELF fake boot image (certified by the mashgiach)\n", perms="-rwxr-xr-x")

        TEMP.children["swap.tmp"] = VFSNode("swap.tmp", "file", content="x" * 512, perms="-rw-r--r--")

        LOGS.children["boot.log"] = VFSNode("boot.log", "file", content=(
            "[0.000] YUshiveBIOS starting...\n"
            "[0.050] 640K RAM detected (more than enough for anyone).\n"
            "[0.120] IDE HD0: CholentHD detected, warm and blessed.\n"
            "[0.180] Davening... OK.\n"
            "[0.200] Ring-0 entered (there is no ring 1,2,3).\n"
            "[1.000] YUshiveOS is alive. Shabbat shalom.\n"
        ), perms="-rw-r--r--")

        self.root.children["Home"] = HO
        self.root.children["System"] = SY
        self.root.children["C"] = C
        self.root.children["Boot"] = BO
        self.root.children["Temp"] = TEMP
        self.root.children["Logs"] = LOGS

        # a few starter files in /Home
        HO.children["Welcome.txt"] = VFSNode("Welcome.txt", "file", content=(
            "Hello, beloved user.\n"
            "You are in a virtual machine with a fine Yiddish accent.\n"
            "Nothing here is real except the blessings.\n"
        ), perms="-rw-r--r--")
        HO.children["Notes.HC"] = VFSNode("Notes.HC", "file", content="// Composition notebook, page one.\n", perms="-rw-r--r--")
        RECIPES = VFSNode("Recipes", "dir", perms="drwxr-xr-x")
        RECIPES.children["Cholent.txt"] = VFSNode("Cholent.txt", "file", content=(
            "Cholent, the OS of the slow cooker.\n"
            "Beans, barley, meat, potatoes, and patience.\n"
            "Simmer overnight. Do not disturb. It is running.\n"
        ), perms="-rw-r--r--")
        HO.children["Recipes"] = RECIPES


VFS = VirtualFS()


# ============================================================================
# YUshiveOS boot screen (joke loader)
# ============================================================================
BOOT_TEXTS = [
    "Waking the Rebbe for a question...",
    "Checking if the cholent is ready... it always is.",
    "Setting the oven before Shabbat...",
    "Searching the car for chometz...",
    "Polishing the menorah (all eight branches)...",
    "Counting the Omer again... started at Sheni...",
    "Saying the Shehecheyanu for the new boot...",
    "Davening... OK.",
    "Loading the siddur, correct orientation...",
    "Measuring the mezuzah at a 45-degree angle...",
    "Rolling the megillah... slight static.",
    "Slicing the challah... it will rise.",
    "Blessing the keyboard buffer with a brocha...",
    "Synchronizing the 74-MHz clock in shul...",
    "Consulting the Rebbe's Machine for approval...",
]

BOOT_FACTS = [
    "There are 613 mitzvot; YUshiveOS plans 613 commands (about 30 so far).",
    "KosherFS always passes inspection on the first try.",
    "Six days thou shalt create; on the seventh thou shalt run defrag.",
    "Shalom means hello, goodbye, and peace - a very efficient shell command.",
    "The first Yeshivah ran on parchment; we upgraded to punch cards.",
    "A two-way endless glass tile animated in YUshiveOS takes 74-MHz.",
    "The Rebbe's Machine has 640K of RAM - more than enough for anyone.",
    "God's original code was compressed; the Omer is the decompressor.",
    "Every JUMP instruction must be checked for gomar.",
    "KosherC is a dialect of C - C with a spine and a yarmulke.",
    "YUshiveOS boots fast because, like a bris, it is done quickly.",
    "5770 is the year, Jerusalem will be the compiler flag.",
]


class BootSplash(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_win = master
        self.overrideredirect(True)
        self.configure(bg=BG_BLUE)
        self.attributes("-topmost", True)

        self._center_on(master)
        self._build_ui()
        self.step = 0
        self.after(0, self._tick)

    def _center_on(self, master):
        self.update_idletasks()
        mw, mh = master.winfo_width(), master.winfo_height()
        w, h = 560, 320
        x = master.winfo_x() + (mw - w) // 2
        y = master.winfo_y() + (mh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        frame = tk.Frame(self, bg=BG_BLUE, bd=2, relief=tk.GROOVE, highlightbackground=BORDER_BLUE, highlightthickness=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        title = tk.Label(
            frame, text="YUshiveOS - Startup", bg=BG_BLUE, fg=ORANGE,
            font=("DejaVu Sans Mono", 14, "bold"),
        )
        title.pack(pady=(18, 4))

        self.status_var = tk.StringVar(value=" Booting...")
        status = tk.Label(
            frame, textvariable=self.status_var, bg=BG_BLUE, fg=ORANGE_BRIGHT,
            font=("DejaVu Sans Mono", 10), anchor="w",
        )
        status.pack(fill=tk.X, padx=24, pady=(6, 2))

        self.fact_var = tk.StringVar(value="")
        fact = tk.Label(
            frame, textvariable=self.fact_var, bg=BG_BLUE, fg=ORANGE_DIM,
            font=("DejaVu Sans Mono", 9), anchor="w", wraplength=480, justify="left",
        )
        fact.pack(fill=tk.X, padx=24, pady=(4, 10))

        self.percent_var = tk.StringVar(value=" 0%")
        pct = tk.Label(
            frame, textvariable=self.percent_var, bg=BG_BLUE, fg=ORANGE,
            font=("DejaVu Sans Mono", 12, "bold"),
        )
        pct.pack(pady=(4, 2))

        self.bar = ttk.Progressbar(frame, mode="determinate", maximum=100, length=480)
        self.bar.pack(padx=24, pady=(2, 6))

        hint = tk.Label(
            frame, text="Please don't spill chicken soup on your computer.",
            bg=BG_BLUE, fg=ORANGE_RED, font=("DejaVu Sans Mono", 9),
        )
        hint.pack(pady=(2, 10))

    def _tick(self):
        if self.step >= 100:
            self._finish()
            return

        self.bar["value"] = self.step
        self.percent_var.set(f" {self.step}%")

        if self.step % 15 == 0:
            self.status_var.set(" " + random.choice(BOOT_TEXTS))
            self.fact_var.set(" " + random.choice(BOOT_FACTS))

        self.step += 2
        self.master_win.update_idletasks()
        self.after(60, self._tick)

    def _finish(self):
        self.bar["value"] = 100
        self.percent_var.set(" 100%")
        self.status_var.set(" YUshiveOS is ready. Shabbat shalom!")
        self.master_win.after(400, self._close)

    def _close(self):
        self.master_win.reveal_dashboard()
        self.destroy()


# ============================================================================
# Terminal: pure built-in virtual shell
# ============================================================================
class YumeTerminal(tk.Frame):
    BUILTINS = (
        "help", "clear", "exit", "ls", "cd", "pwd", "mkdir", "rmdir", "rm",
        "touch", "mv", "cp", "cat", "echo", "find", "tree", "df", "file",
        "whoami", "hostname", "uname", "date", "uptime", "vol", "firstboot",
        "neofetch", "reboot", "oy", "shabbat",
    )

    def __init__(self, parent, initial_cwd="/Home", on_cwd_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)

        self.cwd = initial_cwd
        self.on_cwd_change = on_cwd_change

        self.text = tk.Text(
            self,
            bg=BG_BLUE,
            fg=ORANGE,
            insertbackground=ORANGE_BRIGHT,
            selectbackground=SELECT,
            font=FONT_MONO,
            relief=tk.FLAT,
            padx=10,
            pady=10,
            undo=False,
            insertwidth=2,
        )
        self.text.pack(fill=tk.BOTH, expand=True)

        self.text.mark_set("input_start", tk.END)
        self.text.mark_gravity("input_start", tk.LEFT)

        # Tk's Text widget starts with a single trailing newline already in the
        # buffer; clear it so the first prompt begins on line 1.
        self.text.delete("1.0", "end-1c")

        self._insert_prompt()

        self.text.bind("<Key>", self._on_key_press)
        self.text.bind("<BackSpace>", self._on_backspace)
        self.text.bind("<Return>", self._on_enter)
        self.text.bind("<Button-1>", self._on_click)
        self.text.bind("<Control-c>", self._on_ctrl_c)
        self.text.bind("<Control-l>", self._on_ctrl_l)
        self.text.bind("<Up>", self._on_up_arrow)
        self.text.bind("<Down>", self._on_down_arrow)

        self.command_history = []
        self.history_index = -1
        self.current_input = ""

        self._tab_matches = None
        self._tab_index = -1
        self._tab_base = ""
        self._tab_kinds = None

        self.text.bind("<Tab>", self._on_tab)
        self._setup_context_menu()

    # ---- prompt / display -------------------------------------------------
    def _prompt_str(self):
        return f"{VENV.user}@{VENV.hostname}:{self.cwd}$ "

    def _insert_prompt(self):
        # Anchor `input_start` at the INSERT cursor (a real position at the end
        # of the prompt), NOT at tk.END. Tk's Text keeps an always-present
        # trailing newline, so `end` is one past the real text and a mark there
        # makes reading `input_start .. end-1c` return an empty range.
        self.text.insert(tk.END, self._prompt_str())
        self.text.mark_set("input_start", self.text.index(tk.INSERT))
        self.text.mark_set(tk.INSERT, "input_start")
        self.text.see(tk.END)

    def _get_input(self):
        return self.text.get("input_start", "end-1c").strip()

    def _get_raw_input(self):
        return self.text.get("input_start", "end-1c")

    def _clear_terminal(self):
        self.text.delete("1.0", tk.END)
        self._insert_prompt()

    def _cwd_changed(self):
        self._update_prompt_in_place()
        if self.on_cwd_change:
            self.on_cwd_change(self.cwd)

    def _update_prompt_in_place(self):
        pass  # prompt is re-rendered on next _insert_prompt

    # ---- input protection ---------------------------------------------------
    def _on_key_press(self, event):
        if event.keysym != "Tab":
            self._reset_tab_state()
        if event.state & 4:
            return
        if self.text.compare(self.text.index(tk.INSERT), "<", "input_start"):
            self.text.mark_set(tk.INSERT, tk.END)

    def _on_backspace(self, event):
        if self.text.compare(self.text.index(tk.INSERT), "<=", "input_start"):
            return "break"
        self._reset_tab_state()

    def _on_click(self, event):
        self._reset_tab_state()
        self.after(1, self._check_cursor_position)

    def _check_cursor_position(self):
        if self.text.compare(self.text.index(tk.INSERT), "<", "input_start"):
            self.text.mark_set(tk.INSERT, tk.END)

    def _on_ctrl_c(self, event):
        current = self._get_input()
        if current:
            self.text.insert(tk.END, "^C\n")
            self._insert_prompt()
        return "break"

    def _on_ctrl_l(self, event):
        self._clear_terminal()
        return "break"

    def _on_up_arrow(self, event):
        if self.command_history:
            self._reset_tab_state()
            if self.history_index == -1:
                self.current_input = self._get_input()
                self.history_index = len(self.command_history) - 1
            elif self.history_index > 0:
                self.history_index -= 1
            else:
                return "break"
            self._set_input(self.command_history[self.history_index])
        return "break"

    def _on_down_arrow(self, event):
        if self.history_index == -1:
            return "break"
        self._reset_tab_state()
        if self.history_index < len(self.command_history) - 1:
            self.history_index += 1
            self._set_input(self.command_history[self.history_index])
        else:
            self.history_index = -1
            self._set_input(self.current_input)
        return "break"

    def _set_input(self, text):
        self.text.delete("input_start", "end-1c")
        self.text.insert(tk.END, text)
        self.text.mark_set(tk.INSERT, tk.END)
        self.text.see(tk.END)

    def _reset_tab_state(self):
        self._tab_matches = None
        self._tab_index = -1
        self._tab_kinds = None

    def _tab_candidates(self, token, is_first):
        # returns list of (completion_text, kind) with kind in ("cmd", "dir", "file")
        matches = []
        if not is_first:
            node = None
            if "/" in token:
                idx = token.rfind("/")
                parent_path = token[:idx] or "/"
                prefix = token[idx + 1:]
                keep = token[:idx + 1]
                parent = VFS.resolve(parent_path, self.cwd)
                if parent is not None and parent.type == "dir":
                    node = parent
            else:
                node = VFS.resolve(self.cwd, self.cwd)
                prefix = token
                keep = ""
            if node is not None:
                for name, child in node.children.items():
                    if name.startswith(prefix):
                        kind = "dir" if child.type == "dir" else "file"
                        matches.append((keep + name, kind))
        for name in self.BUILTINS:
            if name.startswith(token) and not any(n == name for n, _ in matches):
                matches.append((name, "cmd"))
        return matches

    def _tab_suffix(self, kind):
        if kind == "dir":
            return "/"
        if kind == "cmd":
            return " "
        return ""

    def _on_tab(self, event):
        line = self._get_raw_input()
        if not line:
            token = ""
            base = ""
        elif line.endswith(" "):
            base = line
            token = ""
        else:
            token = line.split()[-1]
            base = line[:len(line) - len(token)]

        if self._tab_matches is None:
            is_first = (" " not in base)
            matches = self._tab_candidates(token, is_first)
            if not matches:
                return "break"
            self._tab_base = base
            self._tab_matches = [name for name, _ in matches]
            self._tab_kinds = [kind for _, kind in matches]
            self._tab_index = -1

        self._tab_index = (self._tab_index + 1) % len(self._tab_matches)
        name = self._tab_matches[self._tab_index]
        suffix = self._tab_suffix(self._tab_kinds[self._tab_index])
        self._set_input(self._tab_base + name + suffix)
        return "break"

    def _on_enter(self, event):
        cmd = self._get_input()
        self._reset_tab_state()
        self.text.insert(tk.END, "\n")
        if cmd:
            self.command_history.append(cmd)
            self.history_index = -1
            self.current_input = ""
            self._execute(cmd)
        else:
            self._insert_prompt()
        return "break"

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0, bg=BG_BLUE, fg=ORANGE, activebackground=SELECT, activeforeground=ORANGE_BRIGHT, font=FONT_UI)
        self.context_menu.add_command(label="Copy", command=lambda: self.text.event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Paste", command=lambda: self.text.event_generate("<<Paste>>"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Clear", command=self._clear_terminal)
        self.text.bind("<Button-3>", self._show_context_menu)

    def _show_context_menu(self, event):
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    # ---- command dispatch --------------------------------------------------
    def _execute(self, cmd):
        parts = cmd.split()
        if not parts:
            self._insert_prompt()
            return
        name = parts[0]
        args = parts[1:]

        table = {
            "help": self._cmd_help,
            "clear": self._cmd_clear,
            "exit": self._cmd_exit,
            "ls": self._cmd_ls,
            "cd": self._cmd_cd,
            "pwd": self._cmd_pwd,
            "mkdir": self._cmd_mkdir,
            "rmdir": self._cmd_rmdir,
            "rm": self._cmd_rm,
            "touch": self._cmd_touch,
            "mv": self._cmd_mv,
            "cp": self._cmd_cp,
            "cat": self._cmd_cat,
            "echo": self._cmd_echo,
            "find": self._cmd_find,
            "tree": self._cmd_tree,
            "df": self._cmd_df,
            "file": self._cmd_file,
            "whoami": self._cmd_whoami,
            "hostname": self._cmd_hostname,
            "uname": self._cmd_uname,
            "date": self._cmd_date,
            "uptime": self._cmd_uptime,
            "vol": self._cmd_vol,
            "firstboot": self._cmd_firstboot,
            "neofetch": self._cmd_neofetch,
            "reboot": self._cmd_reboot,
            "oy": self._cmd_oy,
            "shabbat": self._cmd_shabbat,
        }

        if name in table:
            table[name](args)
        else:
            self.text.insert(tk.END, f"yumesh: command not found: {name}  (try 'help')\n")
            self._insert_prompt()

    # ---- builtins -----------------------------------------------------------
    def _cmd_help(self, args):
        lines = [
            "YUshiveLinux Shell  -  the Toy CLI",
            "======================================",
            " FILES (all virtual, all kosher)",
            "   ls [-l] [-a] [path]   list directory",
            "   cd <path>             change directory",
            "   pwd                   print working directory",
            "   mkdir <path>          make directory",
            "   rmdir <path>          remove empty directory",
            "   rm <path>             remove file",
            "   touch <path>          create empty file",
            "   mv <src> <dst>        move/rename",
            "   cp <src> <dst>        copy",
            "   cat <file>            print file",
            "   echo <text> [> file]  print (or redirect)",
            "   find <name> [path]    search files",
            "   tree [path]           show tree",
            "   df                    disk usage",
            "   file <path>           identify file",
            " SYSTEM (FAKE)",
            "   whoami  hostname  uname  date",
            "   uptime  vol       firstboot  neofetch",
            "   clear   help      exit  reboot",
            "   oy      shabbat",
            "",
            " Pro tip: press TAB to complete commands and file names.",
            " All file operations live in a virtual filesystem.",
            " Nothing real is touched. Blessed be HaShem.",
        ]
        self.text.insert(tk.END, "\n".join(lines) + "\n")
        self._insert_prompt()

    def _cmd_clear(self, args):
        self._clear_terminal()

    def _cmd_exit(self, args):
        parent_win = self._get_gui_parent()
        if parent_win:
            parent_win.close_tab_for(self)
        else:
            self._insert_prompt()

    def _cmd_pwd(self, args):
        self.text.insert(tk.END, self.cwd + "\n")
        self._insert_prompt()

    def _cmd_cd(self, args):
        if not args:
            target = "/Home"
        else:
            target = args[0]
        node = VFS.resolve(target, self.cwd)
        if node is None:
            self.text.insert(tk.END, f"cd: {target}: no such directory\n")
            self._insert_prompt()
            return
        if node.type != "dir":
            self.text.insert(tk.END, f"cd: {target}: not a directory\n")
            self._insert_prompt()
            return
        self.cwd = VFS._path_of(node)
        self._cwd_changed()
        self._insert_prompt()

    def _cmd_ls(self, args):
        show_all = any(a in ("-a", "-la", "-al") for a in args)
        show_long = any(a in ("-l", "-la", "-al") for a in args)
        paths = [a for a in args if not a.startswith("-")]
        if not paths:
            paths = ["."]

        for path in paths:
            target = self.cwd if path == "." else path
            children = VFS.listdir(target, self.cwd)
            if children is None:
                node = VFS.resolve(target, self.cwd)
                if node is not None and node.type == "file":
                    self.text.insert(tk.END, path + "\n")
                else:
                    self.text.insert(tk.END, f"ls: {path}: no such file or directory\n")
                continue

            entries = sorted(children.values(), key=lambda n: (n.type != "dir", n.name.lower()))
            if not show_all:
                entries = [e for e in entries if not e.name.startswith(".")]

            if len(paths) > 1:
                self.text.insert(tk.END, path + ":\n")

            if show_long:
                for e in entries:
                    kind = "D" if e.type == "dir" else "-"
                    name = e.name + "/" if e.type == "dir" else e.name
                    mtime = e.mtime.strftime("%b %d %H:%M")
                    self.text.insert(tk.END, f"{kind} {e.perms} {e.size:>8} {mtime}  {name}\n")
            else:
                display = []
                for e in entries:
                    display.append(e.name + "/" if e.type == "dir" else e.name)
                for i in range(0, len(display), 5):
                    self.text.insert(tk.END, "  ".join(display[i:i+5]) + "\n")
        self._insert_prompt()

    def _cmd_mkdir(self, args):
        if not args:
            self.text.insert(tk.END, "mkdir: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            rc = VFS.mkdir(p, self.cwd)
            if rc == "EEXIST":
                self.text.insert(tk.END, f"mkdir: {p}: already exists\n")
            elif rc == "ENOENT":
                self.text.insert(tk.END, f"mkdir: {p}: no such file or directory\n")
        self._insert_prompt()

    def _cmd_rmdir(self, args):
        if not args:
            self.text.insert(tk.END, "rmdir: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"rmdir: {p}: no such file or directory\n")
            elif node.type != "dir":
                self.text.insert(tk.END, f"rmdir: {p}: not a directory\n")
            elif node.children:
                self.text.insert(tk.END, f"rmdir: {p}: directory not empty\n")
            else:
                VFS.rm(p, self.cwd)
        self._insert_prompt()

    def _cmd_rm(self, args):
        if not args:
            self.text.insert(tk.END, "rm: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"rm: {p}: no such file or directory\n")
            elif node.type == "dir":
                self.text.insert(tk.END, f"rm: {p}: is a directory (use rmdir)\n")
            else:
                rc = VFS.rm(p, self.cwd)
                if rc == "EPROTECT":
                    self.text.insert(tk.END, f"rm: {p}: protected by HaShem\n")
        self._insert_prompt()

    def _cmd_touch(self, args):
        if not args:
            self.text.insert(tk.END, "touch: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                VFS.mkfile(p, cwd=self.cwd)
            else:
                node.mtime = datetime.datetime.now()
        self._insert_prompt()

    def _cmd_mv(self, args):
        if len(args) != 2:
            self.text.insert(tk.END, "mv: usage: mv <src> <dst>\n")
            self._insert_prompt()
            return
        rc = VFS.mv(args[0], args[1], self.cwd)
        if rc == "ENOENT":
            self.text.insert(tk.END, f"mv: {args[0]}: no such file or directory\n")
        self._insert_prompt()

    def _cmd_cp(self, args):
        if len(args) != 2:
            self.text.insert(tk.END, "cp: usage: cp <src> <dst>\n")
            self._insert_prompt()
            return
        src = VFS.resolve(args[0], self.cwd)
        if src is None or src.type == "dir":
            self.text.insert(tk.END, f"cp: {args[0]}: cannot copy\n")
            self._insert_prompt()
            return
        dst_node = VFS.resolve(args[1], self.cwd)
        if dst_node is not None and dst_node.type == "dir":
            dst = VFS.join(VFS._path_of(dst_node), src.name)
        else:
            dst = args[1]
        VFS.mkfile(dst, content=src.content, cwd=self.cwd)
        self._insert_prompt()

    def _cmd_cat(self, args):
        if not args:
            self.text.insert(tk.END, "cat: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"cat: {p}: no such file\n")
            elif node.type == "dir":
                self.text.insert(tk.END, f"cat: {p}: is a directory\n")
            else:
                content = node.content
                self.text.insert(tk.END, content)
                if content and not content.endswith("\n"):
                    self.text.insert(tk.END, "\n")
        self._insert_prompt()

    def _cmd_echo(self, args):
        parts = args
        redirect = None
        text_parts = parts
        if parts and parts[0] == ">":
            redirect = parts[1]
            text_parts = []
        elif ">" in parts:
            idx = parts.index(">")
            text_parts = parts[:idx]
            if idx + 1 < len(parts):
                redirect = parts[idx + 1]

        text = " ".join(text_parts)

        if args and args[0] == "-n":
            text = " ".join(args[1:]) if ">" not in args else text
            if redirect:
                rc = VFS.write(redirect, text + "\n", self.cwd)
                if rc:
                    self.text.insert(tk.END, f"echo: {redirect}: cannot write\n")
            else:
                self.text.insert(tk.END, text)
        else:
            if redirect:
                rc = VFS.write(redirect, text + "\n", self.cwd)
                if rc:
                    self.text.insert(tk.END, f"echo: {redirect}: cannot write\n")
            else:
                self.text.insert(tk.END, text + "\n")
        self._insert_prompt()

    def _cmd_find(self, args):
        if not args:
            self.text.insert(tk.END, "find: usage: find <name> [path]\n")
            self._insert_prompt()
            return
        pattern = args[0]
        start = args[1] if len(args) > 1 else "/"
        hits = VFS.find(pattern, self.cwd, start)
        if hits:
            self.text.insert(tk.END, "\n".join(hits) + "\n")
        self._insert_prompt()

    def _cmd_tree(self, args):
        start = args[0] if args else "/"
        for path, node, depth in VFS.walk(start, self.cwd):
            indent = "  " * depth
            name = node.name + "/" if node.type == "dir" else node.name
            self.text.insert(tk.END, indent + name + "\n")
        self._insert_prompt()

    def _cmd_df(self, args):
        used = VFS.disk_usage()
        cap = VFS.total_capacity
        pct = int((used / cap) * 100) if cap else 0
        self.text.insert(tk.END, f"Filesystem  Size  Used  Avail  Use%\n")
        self.text.insert(tk.END, f"{VENV.volume:10s}  128M  {used//1024:>3}K   {used//1024:>3}K  {pct}%\n")
        self._insert_prompt()

    def _cmd_file(self, args):
        if not args:
            self.text.insert(tk.END, "file: missing operand\n")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"file: {p}: cannot open\n")
            elif node.type == "dir":
                self.text.insert(tk.END, f"{p}: directory\n")
            elif node.name.endswith((".HC",".C",".H")):
                self.text.insert(tk.END, f"{p}: KosherC source text (a holy gift)\n")
            elif node.name.endswith((".BIN",".SYM",".TMP")):
                self.text.insert(tk.END, f"{p}: {VENV.arch} binary image\n")
            else:
                self.text.insert(tk.END, f"{p}: {VENV.fs_type} text file\n")
        self._insert_prompt()

    def _cmd_whoami(self, args):
        self.text.insert(tk.END, VENV.user + "\n")
        self._insert_prompt()

    def _cmd_hostname(self, args):
        self.text.insert(tk.END, VENV.hostname + "\n")
        self._insert_prompt()

    def _cmd_uname(self, args):
        flag = args[0] if args else ""
        if flag == "-a":
            self.text.insert(tk.END, f"{VENV.os_name} {VENV.version} {VENV.hostname} {VENV.kernel} {VENV.arch}\n")
        else:
            self.text.insert(tk.END, VENV.os_name + "\n")
        self._insert_prompt()

    def _cmd_date(self, args):
        self.text.insert(tk.END, datetime.datetime.now().strftime("%a %b %d %H:%M:%S %Y") + "\n")
        self._insert_prompt()

    def _cmd_uptime(self, args):
        self.text.insert(tk.END, f" up {VENV.uptime_str()},  1 user,  load average: 0.74, 0.74, 0.74\n")
        self._insert_prompt()

    def _cmd_vol(self, args):
        self.text.insert(tk.END, (
            f"Volume in drive {VENV.volume[0]} is {VENV.volume}\n"
            f"Volume Serial Number is 613-5770   (a blessed year)\n"
            f"File System is {VENV.fs_type}\n"
            f"CPU is {VENV.cpu_hz}\n"
            f"Memory is {VENV.memory}\n"
        ))
        self._insert_prompt()

    def _cmd_firstboot(self, args):
        self._display_firstboot()
        self._insert_prompt()

    def _cmd_neofetch(self, args):
        logo = [
            "      /\\       ",
            "     /  \\      ",
            "    / /\\ \\     ",
            "   / /  \\ \\    ",
            "   \\ \\  / /    ",
            "    \\ \\/ /     ",
            "     \\  /      ",
            "      \\/       ",
        ]
        info = [
            f"{VENV.user}@{VENV.hostname}",
            "─" * 18,
            f"OS: {VENV.os_name} {VENV.version}",
            f"Host: {VENV.hostname}",
            f"Kernel: {VENV.kernel}",
            f"Uptime: {VENV.uptime_str()}",
            f"Memory: {VENV.memory}",
            f"Shell: yumesh 0.3",
            f"Vol: {VENV.volume} (Kosher)",
        ]
        for i in range(max(len(logo), len(info))):
            left = logo[i] if i < len(logo) else " " * 14
            right = info[i] if i < len(info) else ""
            self.text.insert(tk.END, f"  {left}  {right}\n")
        self._insert_prompt()

    def _cmd_reboot(self, args):
        parent_win = self._get_gui_parent()
        self.text.insert(tk.END, f"Rebooting {VENV.hostname}...\n")
        self.update_idletasks()
        if parent_win:
            parent_win.after(600, parent_win.trigger_reboot)

    def _cmd_oy(self, args):
        self.text.insert(tk.END, "OY VEY.\n")
        self._insert_prompt()

    def _cmd_shabbat(self, args):
        self.text.insert(tk.END, (
            "Shabbat shalom! The kernel is resting now.\n"
            "No commands until after havdalah. The sunrise calculations are on us.\n"
        ))
        self._insert_prompt()

    def _display_firstboot(self):
        self.text.insert(tk.END, (
            "*** YUshiveOS First Boot ***\n"
            "A virgin boot! Check the cholent.\n"
            "Memtest: 640K OK (more than enough for anyone).\n"
            "HD0: CholentHD detected, warm and blessed.\n"
            "Ring-0 entered. There is no ring 1, 2, or 3. Nor a ring on a finger.\n"
            "Davening... OK.\n"
            "Welcome, beloved user. Shabbat shalom.\n"
        ))

    def _get_gui_parent(self):
        p = self.master
        while p is not None:
            if isinstance(p, YumeGUI):
                return p
            p = p.master
        return None


# ============================================================================
# File Browser (virtual filesystem)
# ============================================================================
class FileBrowser(tk.Frame):
    def __init__(self, parent, initial_path="/Home", on_path_change=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)

        self.current_path = initial_path
        self.on_path_change = on_path_change

        self._build_ui()
        self._navigate_to(self.current_path)

    def _build_ui(self):
        nav_bar = tk.Frame(self, bg=BG_BLUE)
        nav_bar.pack(fill=tk.X, padx=5, pady=(5, 0))

        btn_back = ttk.Button(nav_bar, text=" <-- ", command=self._go_back)
        btn_back.pack(side=tk.LEFT, padx=2)

        btn_home = ttk.Button(nav_bar, text=" Home ", command=self._go_home)
        btn_home.pack(side=tk.LEFT, padx=2)

        btn_up = ttk.Button(nav_bar, text=" Up ", command=self._go_back)
        btn_up.pack(side=tk.LEFT, padx=2)

        self.path_var = tk.StringVar(value=self.current_path)
        self.path_entry = ttk.Entry(nav_bar, textvariable=self.path_var, font=FONT_MONO_SM)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.path_entry.bind("<Return>", self._on_path_entry)

        btn_go = ttk.Button(nav_bar, text=" Go ", command=self._on_go_click)
        btn_go.pack(side=tk.LEFT, padx=2)

        cols = ("Size", "Modified", "Permissions")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings")
        self.tree.heading("#0", text="Name", anchor="w")
        self.tree.heading("Size", text="Size", anchor="w")
        self.tree.heading("Modified", text="Modified", anchor="w")
        self.tree.heading("Permissions", text="Mode", anchor="w")

        self.tree.column("#0", width=320, minwidth=200)
        self.tree.column("Size", width=90, minwidth=70)
        self.tree.column("Modified", width=150, minwidth=100)
        self.tree.column("Permissions", width=100, minwidth=80)

        scrollbar_y = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar_y.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(5, 0), pady=5)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y, pady=5, padx=(0, 5))

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self._setup_context_menu()

    def _setup_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=0, bg=BG_BLUE, fg=ORANGE, activebackground=SELECT, activeforeground=ORANGE_BRIGHT, font=FONT_UI)
        self.context_menu.add_command(label="Open", command=self._context_open)
        self.context_menu.add_command(label="Open in Terminal", command=self._context_open_terminal)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy Path", command=self._context_copy_path)
        self.context_menu.add_command(label="Refresh", command=self._refresh)
        self.context_menu.add_command(label="New Directory", command=self._context_new_dir)

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _context_open(self):
        sel = self.tree.selection()
        if sel:
            self._open_item(sel[0])

    def _context_open_terminal(self):
        sel = self.tree.selection()
        if sel:
            name = self.tree.item(sel[0], "text")
            node = VFS.resolve(name, self.current_path)
            target = self.current_path
            if node is not None and node.type == "dir":
                target = VFS._path_of(node)
            parent_win = self._get_gui_parent()
            if parent_win:
                parent_win.open_terminal_at(target)

    def _context_copy_path(self):
        sel = self.tree.selection()
        if sel:
            path = self.tree.item(sel[0], "text")
            full = VFS.join(self.current_path, path)
            self.clipboard_clear()
            self.clipboard_append(full)

    def _context_new_dir(self):
        sel = self.tree.selection()
        name = self.tree.item(sel[0], "text") if sel else None
        base = self.current_path if not (name and (node := VFS.resolve(name, self.current_path)) and node.type == "dir") else VFS._path_of(node)
        n = 1
        while VFS.resolve(VFS.join(base, f"NewDir{n}"), self.current_path) is not None:
            n += 1
        VFS.mkdir(VFS.join(base, f"NewDir{n}"))
        self._navigate_to(self.current_path)

    def _get_gui_parent(self):
        p = self.master
        while p is not None:
            if isinstance(p, YumeGUI):
                return p
            p = p.master
        return None

    def _navigate_to(self, path):
        node = VFS.resolve(path)
        if node is None or node.type != "dir":
            return
        self.current_path = VFS._path_of(node)
        self.path_var.set(self.current_path)
        self.tree.delete(*self.tree.get_children())

        for child in sorted(node.children.values(), key=lambda c: (c.type != "dir", c.name.lower())):
            size = "--" if child.type == "dir" else FileBrowser._format_size(child.size)
            mtime = child.mtime.strftime("%Y-%m-%d %H:%M")
            name = child.name + "/" if child.type == "dir" else child.name
            self.tree.insert("", tk.END, text=name, values=(size, mtime, child.perms))

        if self.on_path_change:
            self.on_path_change(self.current_path)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            self._open_item(sel[0])

    def _open_item(self, item):
        name = self.tree.item(item, "text")
        node = VFS.resolve(name, self.current_path)
        if node is not None and node.type == "dir":
            self._navigate_to(VFS._path_of(node))

    def _go_back(self):
        node = VFS.resolve(self.current_path)
        parent = VFS._parent_of(node) if node else None
        if parent is not None:
            self._navigate_to(VFS._path_of(parent))

    def _go_home(self):
        self._navigate_to("/Home")

    def _on_path_entry(self, event=None):
        self._on_go_click()

    def _on_go_click(self):
        target = self.path_var.get().strip()
        if target:
            node = VFS.resolve(target)
            if node is not None and node.type == "dir":
                self._navigate_to(VFS._path_of(node))

    def _refresh(self):
        self._navigate_to(self.current_path)

    @staticmethod
    def _format_size(size):
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}K"
        elif size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f}M"
        else:
            return f"{size / (1024 * 1024 * 1024):.1f}G"


# ============================================================================
# Main GUI
# ============================================================================
class YumeGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("YUshiveLinux - YUshiveOS")
        self.geometry("1024x680")
        self.minsize(800, 500)

        self.configure(bg=BG_BLUE)
        self._apply_theme()

        self.active_processes = {}
        self.tab_buttons = {}
        self.cwd = "/Home"
        self.revealed = False

        self._build_layout()

        # boot splash over the window (dashboard stays as the default tab)
        self.after(300, self._start_boot)

        self._start_status_clock()

    # ---- theme ---------------------------------------------------------------
    def _apply_theme(self):
        style = ttk.Style(self)
        try:
            style.theme_use("default")
        except tk.TclError:
            pass

        style.configure("TFrame", background=BG_BLUE)
        style.configure("Header.TFrame", background=BG_BLUE_DEEP)
        style.configure("Status.TFrame", background=BG_BLUE_DEEP)

        style.configure(
            "TButton",
            background=BG_BLUE_ALT,
            foreground=ORANGE,
            bordercolor=BORDER_BLUE,
            lightcolor=BG_BLUE,
            darkcolor=BG_BLUE_DEEP,
            borderwidth=2,
            focusthickness=0,
            padding=(10, 5),
            font=FONT_UI_BOLD,
        )
        style.map("TButton", background=[("active", SELECT)], foreground=[("active", ORANGE_BRIGHT)])

        style.configure("TNotebook", background=BG_BLUE, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=BG_BLUE_ALT,
            foreground=ORANGE_DIM,
            padding=(12, 6),
            font=FONT_UI_BOLD,
            borderwidth=1,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", BG_BLUE)],
            foreground=[("selected", ORANGE_BRIGHT)],
        )

        style.configure(
            "Treeview",
            background=BG_BLUE_DEEP,
            fieldbackground=BG_BLUE_DEEP,
            foreground=ORANGE,
            rowheight=26,
            borderwidth=0,
            font=FONT_UI,
        )
        style.configure("Treeview.Heading", background=BG_BLUE_ALT, foreground=ORANGE_BRIGHT, font=FONT_UI_BOLD)
        style.map("Treeview", background=[("selected", SELECT)], foreground=[("selected", ORANGE_BRIGHT)])

        style.configure("TEntry", fieldbackground=BG_BLUE_DEEP, foreground=ORANGE, insertcolor=ORANGE_BRIGHT, borderwidth=2)

        style.configure(
            "Horizontal.TProgressbar",
            troughcolor=BG_BLUE_DEEP,
            background=ORANGE,
            bordercolor=BORDER_BLUE,
            lightcolor=ORANGE,
            darkcolor=ORANGE,
        )

    # ---- layout ---------------------------------------------------------------
    def _build_layout(self):
        top_bar = ttk.Frame(self, style="Header.TFrame")
        top_bar.pack(side=tk.TOP, fill=tk.X)

        inner_bar = tk.Frame(top_bar, bg=BG_BLUE_DEEP)
        inner_bar.pack(fill=tk.X, padx=8, pady=6)

        lbl_logo = tk.Label(
            inner_bar, text="YUshiveOS", bg=BG_BLUE_DEEP, fg=ORANGE_BRIGHT,
            font=("DejaVu Sans Mono", 13, "bold"),
        )
        lbl_logo.pack(side=tk.LEFT, padx=(0, 15))

        btn_term = ttk.Button(inner_bar, text="Terminal", command=self.open_terminal)
        btn_term.pack(side=tk.LEFT, padx=4)

        btn_files = ttk.Button(inner_bar, text="File Manager", command=self.open_file_manager)
        btn_files.pack(side=tk.LEFT, padx=4)

        btn_info = ttk.Button(inner_bar, text="System Info", command=self.open_system_info)
        btn_info.pack(side=tk.LEFT, padx=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<Button-2>", self._on_middle_click_tab)

        self.status_bar = ttk.Frame(self, style="Status.TFrame")
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        inner_status = tk.Frame(self.status_bar, bg=BG_BLUE_DEEP)
        inner_status.pack(fill=tk.X, padx=8, pady=2)

        self.status_left = tk.Label(
            inner_status, text="", bg=BG_BLUE_DEEP, fg=ORANGE_DIM, font=FONT_MONO_SM, anchor="w",
        )
        self.status_left.pack(side=tk.LEFT)

        self.status_right = tk.Label(
            inner_status, text="", bg=BG_BLUE_DEEP, fg=ORANGE_DIM, font=FONT_MONO_SM, anchor="e",
        )
        self.status_right.pack(side=tk.RIGHT)

        # Dashboard placeholder (shown after boot)
        self.dashboard_holder = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_holder, text=" Dashboard ")
        self._populate_dashboard(self.dashboard_holder)

    def _populate_dashboard(self, frame):
        for w in frame.winfo_children():
            w.destroy()

        banner = [
            "                /\\            ",
            "               /  \\           ",
            "              / /\\ \\          ",
            "             / /  \\ \\         ",
            "             \\ \\  / /         ",
            "              \\ \\/ /          ",
            "               \\  /           ",
            "                \\/            ",
            "                               ",
            "   YUshiveOS - a TempleOS-inspired virtual machine,",
            "   now with a fine Yiddish accent.",
        ]
        body = tk.Frame(frame, bg=BG_BLUE)
        body.pack(fill=tk.BOTH, expand=True)
        for line in banner:
            tk.Label(body, text=line, bg=BG_BLUE, fg=ORANGE, font=("DejaVu Sans Mono", 14, "bold")).pack(anchor="w", padx=24)

        tk.Label(
            body, text="— Blessed be HaShem, and praise His holy delis —",
            bg=BG_BLUE, fg=ORANGE_BRIGHT, font=("DejaVu Sans Mono", 10),
        ).pack(anchor="w", padx=24, pady=(8, 20))

        info_items = [
            ("System", f"{VENV.os_name} {VENV.version}"),
            ("Kernel", VENV.kernel),
            ("User", VENV.user),
            ("Host", VENV.hostname),
            ("Volume", VENV.volume),
            ("Memory", VENV.memory),
            ("CPU", VENV.cpu_hz),
        ]
        for label, value in info_items:
            row = tk.Frame(body, bg=BG_BLUE)
            row.pack(anchor="w", padx=32, pady=1)
            tk.Label(row, text=label, bg=BG_BLUE, fg=ORANGE_DIM, font=("DejaVu Sans Mono", 10, "bold"), width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=BG_BLUE, fg=ORANGE, font=("DejaVu Sans Mono", 10), anchor="w").pack(side=tk.LEFT)

        btn_row = tk.Frame(body, bg=BG_BLUE)
        btn_row.pack(anchor="w", padx=24, pady=(24, 4))
        ttk.Button(btn_row, text=" Terminal ", command=self.open_terminal).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text=" File Manager ", command=self.open_file_manager).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text=" System Info ", command=self.open_system_info).pack(side=tk.LEFT, padx=4)

        tk.Label(
            body, text=random.choice(BOOT_FACTS), bg=BG_BLUE, fg=ORANGE_DIM,
            font=("DejaVu Sans Mono", 9), wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(30, 0))

    # ---- boot / reveal -----------------------------------------------------
    def _start_boot(self):
        self.boot = BootSplash(self)

    def reveal_dashboard(self):
        self.revealed = True
        try:
            self.notebook.select(self.dashboard_holder)
        except tk.TclError:
            pass

    def trigger_reboot(self):
        # close all tabs, replay boot
        for tab in list(self.tab_buttons.keys()):
            try:
                self.close_tab(tab)
            except Exception:
                pass
        self.after(200, self._start_boot)

    # ---- tabs --------------------------------------------------------------
    def add_app_tab(self, app_title, process=None):
        tab_frame = ttk.Frame(self.notebook)

        tab_header = tk.Frame(tab_frame, bg=BG_BLUE_ALT, height=28)
        tab_header.pack(fill=tk.X)
        tab_header.pack_propagate(False)

        tab_label = tk.Label(tab_header, text="  " + app_title, bg=BG_BLUE_ALT, fg=ORANGE_BRIGHT, font=FONT_UI_BOLD)
        tab_label.pack(side=tk.LEFT)

        close_btn = tk.Label(
            tab_header, text=" [X] ", bg=BG_BLUE_ALT, fg=ORANGE_DIM,
            font=FONT_UI_BOLD, cursor="hand2", padx=4,
        )
        close_btn.pack(side=tk.RIGHT, padx=2)

        tab_content = tk.Frame(tab_frame, bg=BG_BLUE)
        tab_content.pack(fill=tk.BOTH, expand=True)

        self.tab_buttons[tab_frame] = (tab_header, close_btn)

        def on_close(event=None):
            self.close_tab(tab_frame)

        close_btn.bind("<Button-1>", on_close)
        tab_label.bind("<Button-1>", on_close)

        if process:
            self.active_processes[tab_frame] = process

        self.notebook.add(tab_frame, text="")
        self.notebook.select(tab_frame)
        return tab_content

    def close_tab(self, tab_frame):
        if not tab_frame:
            return
        proc = self.active_processes.pop(tab_frame, None)
        if proc and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

        btns = self.tab_buttons.pop(tab_frame, None)
        if btns:
            btns[0].destroy()

        for child in tab_frame.winfo_children():
            child.destroy()

        try:
            self.notebook.forget(tab_frame)
        except tk.TclError:
            pass
        tab_frame.destroy()

    def close_tab_for(self, terminal_widget):
        tab = terminal_widget.master
        while tab is not None:
            # ttk.Frame is not a subclass of tk.Frame, so only rely on dict
            # membership (which is keyed by the tab frame itself).
            if tab in self.tab_buttons:
                self.close_tab(tab)
                return
            tab = tab.master

    def _on_middle_click_tab(self, event):
        try:
            element = self.notebook.identify(event.x, event.y)
            if not element:
                return
            index = self.notebook.index(f"@{event.x},{event.y}")
            tabs = self.notebook.tabs()
            if index < len(tabs):
                tab_frame = self.notebook.nametowidget(tabs[index])
                if tab_frame in self.tab_buttons:
                    self.close_tab(tab_frame)
        except tk.TclError:
            pass

    # ---- app launchers ------------------------------------------------------
    def open_terminal(self):
        tab = self.add_app_tab("Terminal")
        term = YumeTerminal(tab, initial_cwd=self.cwd, on_cwd_change=self._on_terminal_cwd_change)
        term.focus_set()

    def open_terminal_at(self, path):
        node = VFS.resolve(path)
        start = VFS._path_of(node) if node is not None else self.cwd
        tab = self.add_app_tab("Terminal")
        term = YumeTerminal(tab, initial_cwd=start, on_cwd_change=self._on_terminal_cwd_change)
        term.focus_set()

    def _on_terminal_cwd_change(self, cwd):
        self.cwd = cwd
        self._update_status_bar()

    def open_file_manager(self):
        tab = self.add_app_tab("File Manager")
        FileBrowser(tab, initial_path=self.cwd)

    def open_system_info(self):
        tab = self.add_app_tab("System Info")
        content = tk.Frame(tab, bg=BG_BLUE)
        content.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        tk.Label(content, text="YUshiveOS System Information", bg=BG_BLUE, fg=ORANGE_BRIGHT,
                 font=("DejaVu Sans Mono", 14, "bold")).pack(anchor="w", pady=(0, 15))

        info_data = [
            ("OS Name", VENV.os_name),
            ("Version", VENV.version),
            ("Kernel", VENV.kernel),
            ("Host", VENV.hostname),
            ("User", VENV.user),
            ("Arch", VENV.arch),
            ("CPU", VENV.cpu_hz),
            ("Memory", VENV.memory),
            ("Volume", VENV.volume),
            ("FS", VENV.fs_type),
            ("Boot Time", VENV.boot_time.strftime("%Y-%m-%d %H:%M:%S")),
        ]
        for label, value in info_data:
            row = tk.Frame(content, bg=BG_BLUE)
            row.pack(anchor="w", pady=3, fill=tk.X)
            tk.Label(row, text=f"{label}:", bg=BG_BLUE, fg=ORANGE_DIM, font=FONT_UI_BOLD, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=BG_BLUE, fg=ORANGE, font=FONT_MONO_SM, anchor="w").pack(side=tk.LEFT, fill=tk.X)

        tk.Label(content, text="\nAll values are pretend. The real OS remains untouched.", bg=BG_BLUE,
                 fg=ORANGE_DIM, font=FONT_MONO_SM).pack(anchor="w", pady=(20, 0))

    # ---- status bar ----------------------------------------------------------
    def _start_status_clock(self):
        self._update_status_bar()

    def _update_status_bar(self):
        VENV.tick()
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.status_left.config(text=f"  {VENV.user}@{VENV.hostname}  |  {self.cwd}       ")
        self.status_right.config(text=now + "   " + VENV.uptime_str() + "   ")
        self.after(1000, self._update_status_bar)


if __name__ == "__main__":
    app = YumeGUI()
    app.mainloop()
