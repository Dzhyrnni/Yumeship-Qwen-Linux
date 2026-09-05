import random
import json
import math
import os
import re
import base64
import datetime
import tkinter as tk
from tkinter import ttk
from tkinter import simpledialog
from pathlib import Path

DISK_IMAGE = Path.home() / ".yushive" / "cholenthd.json"
CONF_IMAGE = Path.home() / ".yushive" / "conf.json"
RECYCLE_DIR = "/System/RecycleBin"
PKG_ROOT = "/C/Packages"
PKG_EXPORT_DIR = Path.home() / ".yushive" / "export"


def beep():
    try:
        root = tk._default_root
        if root is not None:
            root.bell()
    except Exception:
        pass


def _save_conf():
    try:
        CONF_IMAGE.parent.mkdir(parents=True, exist_ok=True)
        with open(CONF_IMAGE, "w") as f:
            json.dump({
                "env": VENV.env,
                "aliases": VENV.aliases,
                "history": list(YumeTerminal.history),
            }, f)
    except Exception:
        pass


def _load_conf():
    try:
        if not CONF_IMAGE.exists():
            return
        with open(CONF_IMAGE) as f:
            data = json.load(f)
        VENV.env.update(data.get("env", {}))
        VENV.aliases.update(data.get("aliases", {}))
        VENV.aliases.setdefault("pkg", "siddur")
        YumeTerminal.history = list(data.get("history", []))
    except Exception:
        pass


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
        self.env = {
            "USER": "rebbe",
            "HOSTNAME": "YUshiveOS",
            "HOME": "/Home",
            "PWD": "/Home",
            "SHELL": "yumesh",
            "PATH": "/System:/C/Apps:/C/Utils",
            "EDITER": "yumePad",
        }
        self.aliases = {"ll": "ls -l", "shalom": "shabbat", "pkg": "siddur"}

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
        self.inode = None
        self.locked = False

    @property
    def size(self):
        if self.type == "dir":
            return 0
        return len(self.content.encode("utf-8", errors="replace"))


class VirtualFS:
    def __init__(self):
        self.root = VFSNode("/", "dir", perms="drwxr-xr-x")
        self.total_capacity = 128 * 1024 * 1024  # fake 128MB disk
        if not self._load():
            self._seed()
        self._ensure_recycle_bin()
        self._assign_inodes()

    # ---- persistence -----------------------------------------------------
    def _node_to_dict(self, node):
        return {
            "type": node.type,
            "perms": node.perms,
            "locked": node.locked,
            "orig": getattr(node, "orig_path", None),
            "mtime": node.mtime.isoformat(),
            "content": node.content if node.type != "dir" else None,
            "children": {n: self._node_to_dict(c) for n, c in node.children.items()},
        }

    def _dict_to_node(self, d, name):
        node = VFSNode(name, d["type"], perms=d.get("perms", "-rw-r--r--"))
        node.locked = d.get("locked", False)
        node.content = d.get("content", "") or ""
        node.mtime = datetime.datetime.fromisoformat(d["mtime"]) if d.get("mtime") else datetime.datetime.now()
        if d.get("orig"):
            node.orig_path = d["orig"]
        node.children = {n: self._dict_to_node(c, n) for n, c in d.get("children", {}).items()}
        return node

    def save(self):
        try:
            DISK_IMAGE.parent.mkdir(parents=True, exist_ok=True)
            with open(DISK_IMAGE, "w") as f:
                json.dump(self._node_to_dict(self.root), f)
            return True
        except Exception:
            return False

    def _load(self):
        try:
            if not DISK_IMAGE.exists():
                return False
            with open(DISK_IMAGE) as f:
                d = json.load(f)
            self.root = self._dict_to_node(d, "/")
            self.root.name = "/"
            return True
        except Exception:
            return False

    def destroy_disk(self):
        try:
            DISK_IMAGE.unlink(missing_ok=True)
        except OSError:
            pass

    def _assign_inodes(self):
        i = 1000
        def walk(node):
            nonlocal i
            node.inode = i
            i += 1
            for c in node.children.values():
                walk(c)
        walk(self.root)

    def _ensure_recycle_bin(self):
        sysnode = self.root.children.get("System")
        if sysnode is not None and sysnode.type == "dir" and "RecycleBin" not in sysnode.children:
            sysnode.children["RecycleBin"] = VFSNode("RecycleBin", "dir", perms="drwxrwxr-x")

    def empty_recycle_bin(self):
        sysnode = self.root.children.get("System")
        if sysnode is not None and "RecycleBin" in sysnode.children:
            sysnode.children["RecycleBin"].children.clear()
            self.save()

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
        self.save()
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
        self.save()
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
        self.save()
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
        node = parent.children[name]
        if node.locked:
            return "EPROTECT"
        del parent.children[name]
        self.save()
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
        self.save()
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

    def set_content(self, node, content):
        node.content = content
        node.mtime = datetime.datetime.now()
        self.save()

    def chmod(self, path, mode, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None:
            return "ENOENT"
        try:
            mode = mode.zfill(3)
            if not (len(mode) == 3 and all(c in "01234567" for c in mode)):
                return "EINVAL"
            def tri(d):
                v = int(d)
                return ("r" if v & 4 else "-") + ("w" if v & 2 else "-") + ("x" if v & 1 else "-")
            if mode == "000":
                node.locked = True
            else:
                node.locked = False
            node.perms = ("d" if node.type == "dir" else "-") + tri(mode[0]) + tri(mode[1]) + tri(mode[2])
            self.save()
            return None
        except Exception:
            return "EINVAL"

    def ln(self, src, dst, cwd="/Home"):
        target = self.resolve(src, cwd)
        if target is None:
            return "ENOENT"
        dparts = self._split(dst)
        dparent = self._resolve_parent(dparts, cwd, dst.startswith("/") or dst.startswith("~/"))
        if dparent is None:
            return "ENOENT"
        dname = dparts[-1]
        if dname in dparent.children:
            return "EEXIST"
        dparent.children[dname] = VFSNode(dname, "file", content="LINK:" + self._path_of(target), perms="lrwxrwxrwx")
        self.save()
        return None

    def du(self, path, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None:
            return None
        total = 0
        def walk(n):
            nonlocal total
            total += n.size
            if n.type == "dir":
                for c in n.children.values():
                    walk(c)
        walk(node)
        return total

    def trash(self, path, cwd="/Home"):
        node = self.resolve(path, cwd)
        if node is None:
            return "ENOENT"
        if node.locked:
            return "EPROTECT"
        parent = self._parent_of(node)
        if parent is None:
            return "EROOT"
        full = self._path_of(node)
        if full.startswith(RECYCLE_DIR):
            del parent.children[node.name]
            self.save()
            return None
        if full.startswith("/System") and len(full.split("/")) == 3:
            sysfile = full.split("/")[2]
            if node.type == "file" and sysfile in ("Kernel.HC", "README.txt", "FirstBoot.HC", "CLI.HC", "Temple.txt"):
                return "EPROTECT"
        self._ensure_recycle_bin()
        bin_node = self.root.children["System"].children["RecycleBin"]
        name = node.name
        if name in bin_node.children:
            base, i = name, 1
            while f"{base}.{i}" in bin_node.children:
                i += 1
            name = f"{base}.{i}"
        node.orig_path = full
        del parent.children[node.name]
        node.name = name
        bin_node.children[name] = node
        self.save()
        return None

    def restore(self, name, cwd="/Home"):
        self._ensure_recycle_bin()
        bin_node = self.root.children["System"].children["RecycleBin"]
        if name not in bin_node.children:
            return "ENOENT"
        node = bin_node.children.pop(name)
        target = getattr(node, "orig_path", None)
        parent = None
        if target:
            parent = self._resolve_parent(self._split(target), "/", True)
        if parent is None:
            parent = self.root.children.get("Home")
        if parent is None:
            return "ENOENT"
        pname = self._split(target)[-1] if target else node.name
        if pname in parent.children:
            pname = node.name
        node.name = pname
        parent.children[pname] = node
        if hasattr(node, "orig_path"):
            delattr(node, "orig_path")
        self.save()
        return None

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
            "FirstBoot( );\n"
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
        SY.children["RecycleBin"] = VFSNode("RecycleBin", "dir", perms="drwxrwxr-x")

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
        "edit", "chmod", "stat", "ln", "readlink", "du", "sudo", "env",
        "export", "alias", "unalias", "run", "ps", "weather", "panic",
        "gematria", "brocha", "god", "shutdown", "screensaver", "restore",
        "man", "help", "siddur", "holyc", "lisp", "basic",
    )
    history = []

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

        self.text.tag_configure("dir", foreground=ORANGE_BRIGHT)
        self.text.tag_configure("execfile", foreground=ACCENT_TEAL)
        self.text.tag_configure("hidden", foreground=ORANGE_DIM)
        self.text.tag_configure("dim", foreground=ORANGE_DIM)
        self.text.tag_configure("title", foreground=ORANGE_BRIGHT)
        self.text.tag_configure("error", foreground=ORANGE_RED)

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

        self.command_history = YumeTerminal.history
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
            _save_conf()
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

        if name in VENV.aliases:
            alias_cmd = (VENV.aliases[name] + " " + " ".join(args)).strip()
            self._execute(alias_cmd)
            return

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
            "edit": self._cmd_edit,
            "chmod": self._cmd_chmod,
            "stat": self._cmd_stat,
            "ln": self._cmd_ln,
            "readlink": self._cmd_readlink,
            "du": self._cmd_du,
            "sudo": self._cmd_sudo,
            "env": self._cmd_env,
            "export": self._cmd_export,
            "alias": self._cmd_alias,
            "unalias": self._cmd_unalias,
            "run": self._cmd_run,
            "ps": self._cmd_ps,
            "weather": self._cmd_weather,
            "panic": self._cmd_panic,
            "gematria": self._cmd_gematria,
            "brocha": self._cmd_brocha,
            "god": self._cmd_god,
            "shutdown": self._cmd_shutdown,
            "screensaver": self._cmd_screensaver,
            "restore": self._cmd_restore,
            "man": self._cmd_help,
            "siddur": self._cmd_siddur,
            "holyc": self._cmd_holyc,
            "lisp": self._cmd_lisp,
            "basic": self._cmd_basic,
        }

        if name in table:
            table[name](args)
        else:
            pkg_cmd = self._package_command(name)
            if pkg_cmd:
                self._run_script_file(pkg_cmd)
                return
            beep()
            self.text.insert(tk.END, f"yumesh: command not found: {name}  (try 'help', or 'siddur search')\n", "error")
            self._insert_prompt()

    def _expand_env(self, text):
        out = text
        for key, val in VENV.env.items():
            out = out.replace("$" + key, val)
        out = out.replace("$?", "0")
        return out

    # ---- builtins -----------------------------------------------------------
    HELP_TOPICS = {
    "ls": "ls [-l] [-a] [path]    list directory (colorized)",
    "cd": "cd [path]              change directory",
    "pwd": "pwd                   print working directory",
    "echo": "echo <text> [> file]   print (or redirect)",
    "edit": "edit <file>            open file in YumePad",
    "run": "run <file>            run a script file (pseudo-HolyC)",
    "chmod": "chmod <octal> <path>   change perms (000 = locked)",
    "stat": "stat <path>           detailed file info",
    "ln": "ln <src> <dst>        create a symbolic link",
    "readlink": "readlink <path>       show where a link points",
    "du": "du [path]             disk usage of a path",
    "sudo": "sudo <cmd>            you are already the Rebbe",
    "env": "env                   show environment variables",
    "export": "export KEY=value       set an environment variable",
    "alias": "alias name=cmd        define an alias",
    "unalias": "unalias <name>        remove an alias",
    "ps": "ps                    list processes",
    "weather": "weather               forecast for the holy land",
    "gematria": "gematria <word>        compute the numerical value",
    "brocha": "brocha               say a blessing",
    "god": "god                   theological facts",
    "panic": "panic                 simulate a kernel panic",
    "screensaver": "screensaver          show the star field now",
    "restore": "restore <name>        restore a file from the Recycle Bin",
    "shutdown": "shutdown              power off the machine",
    "siddur": "siddur <subcmd>      package manager: search/info/install/list/remove/publish/import",
    "holyc": "holyc <file.hc>        run a HolyC-lite script (mini-C: Print/if/for/while/functions)",
    "lisp": "lisp <file.lsp>|'expr'   evaluate LISP (define/lambda/if/car/cdr/cons/print)",
    "basic": "basic <file.bas>        run Yiddish BASIC (PRINT/LET/IF/THEN/GOTO/FOR/READ/DATA)",
    "vol": "vol                   disk volume info",
}

    def _cmd_help(self, args):
        topic = args[0] if args else None
        if topic:
            lines = [
                "YUshiveLinux manuals",
                "===================",
            ]
            if topic in self.HELP_TOPICS:
                lines.append(self.HELP_TOPICS[topic])
            elif topic in VENV.aliases:
                lines.append(f"alias {topic} = {VENV.aliases[topic]}  (it is a blessing)")
            else:
                lines.append(f"no manual entry for {topic}  (try 'help')")
            self.text.insert(tk.END, "\n".join(lines) + "\n")
            self._insert_prompt()
            return

        lines = [
            "YUshiveLinux Shell  -  the Toy CLI",
            "======================================",
            " FILES (all virtual, all kosher)",
            "   ls [-l] [-a] [path]   list directory",
            "   cd <path>             change directory",
            "   pwd                   print working directory",
            "   mkdir <path>          make directory",
            "   rmdir <path>          remove empty directory",
            "   rm <path>             remove file (to the Recycle Bin)",
            "   restore <name>        get it back from the Bin",
            "   touch <path>          create empty file",
            "   mv <src> <dst>        move/rename",
            "   cp <src> <dst>        copy",
            "   cat <file>            print file",
            "   echo <text> [> file]  print (or redirect)",
            "   find <name> [path]    search files",
            "   tree [path]           show tree",
            "   df                    disk usage",
            "   du [path]             size of a path",
            "   file <path>           identify file",
            "   ln <src> <dst>        symbolic link",
            "   chmod <octal> <path>  change permissions",
            "   stat <path>           inode, blocks, and blessings",
"   edit <file>           open YumePad",
             "   run <file>            run a script file",
             " PROGRAMMING",
             "   holyc <file.hc>        mini-C interpreter (Print/if/for/while/functions)",
             "   lisp <file.lsp>|expr   Scheme-style interpreter",
             "   basic <file.bas>       Yiddish BASIC (numbered lines)",
             " PACKAGES",
             "   siddur search|info|install|list|remove|publish|import",
             "   pkg = siddur           (alias)",
             " SHELL",
            "   sudo <cmd>  env  export KEY=val  alias  unalias",
            "   help [cmd]  man [cmd]  history (?): use Up/Down",
            " SYSTEM (FAKE)",
            "   whoami  hostname  uname  date",
            "   uptime  vol       firstboot  neofetch",
            "   clear   exit      reboot  shutdown",
            "   screensaver  ps  weather  panic",
            "   oy  shabbat  brocha  god  gematria",
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
                    tag = "dir" if e.type == "dir" else self._ls_tag(e)
                    self.text.insert(tk.END, f"{kind} {e.perms} {e.size:>8} {mtime}  {name}\n", tag)
            else:
                display = []
                for e in entries:
                    display.append((e.name + "/" if e.type == "dir" else e.name, self._ls_tag(e)))
                for i in range(0, len(display), 5):
                    chunk = display[i:i+5]
                    for j, (name, tag) in enumerate(chunk):
                        self.text.insert(tk.END, name, tag)
                        if j < len(chunk) - 1:
                            self.text.insert(tk.END, "  ")
                    self.text.insert(tk.END, "\n")
        self._insert_prompt()

    def _ls_tag(self, e):
        if e.type == "dir":
            return "dir"
        if e.locked or e.perms.endswith("x"):
            return "execfile"
        if e.name.startswith("."):
            return "hidden"
        return None

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
            self.text.insert(tk.END, "rm: missing operand\n", "error")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"rm: {p}: no such file or directory\n", "error")
            elif node.type == "dir":
                self.text.insert(tk.END, f"rm: {p}: is a directory (use rmdir)\n", "error")
            else:
                rc = VFS.trash(p, self.cwd)
                if rc == "EPROTECT":
                    beep()
                    self.text.insert(tk.END, f"rm: {p}: protected by HaShem (or locked by chmod 000)\n", "error")
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

        text = self._expand_env(" ".join(text_parts))

        if args and args[0] == "-n":
            text = self._expand_env(" ".join(args[1:])) if ">" not in args else text
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

    # ---- the new wave of builtins ----------------------------------------
    def _cmd_edit(self, args):
        if not args:
            self.text.insert(tk.END, "edit: missing operand\n", "error")
            self._insert_prompt()
            return
        parent_win = self._get_gui_parent()
        if parent_win is None:
            self.text.insert(tk.END, "edit: no GUI to edit in\n", "error")
            self._insert_prompt()
            return
        path = args[0]
        node = VFS.resolve(path, self.cwd)
        if node is None:
            self.text.insert(tk.END, f"edit: {path}: no such file\n", "error")
            self._insert_prompt()
            return
        if node.type == "dir":
            self.text.insert(tk.END, f"edit: {path}: is a directory (a Rebbe always has a chumash)\n", "error")
            self._insert_prompt()
            return
        parent_win.open_editor(VFS._path_of(node))

    def _cmd_chmod(self, args):
        if len(args) != 2:
            self.text.insert(tk.END, "chmod: usage: chmod <octal> <path>  (000 locks the file)\n", "error")
            self._insert_prompt()
            return
        rc = VFS.chmod(args[1], args[0], self.cwd)
        if rc == "ENOENT":
            self.text.insert(tk.END, f"chmod: {args[1]}: no such file or directory\n", "error")
        elif rc == "EINVAL":
            self.text.insert(tk.END, f"chmod: {args[0]}: invalid mode (try 755 or 000)\n", "error")
        self._insert_prompt()

    def _cmd_stat(self, args):
        if not args:
            self.text.insert(tk.END, "stat: missing operand\n", "error")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"stat: {p}: cannot stat\n", "error")
                continue
            full = VFS._path_of(node)
            blocks = max(node.size // 512 + 1, 1) if node.type != "dir" else 0
            lock = "locked (protected by HaShem)" if node.locked else "unlocked"
            self.text.insert(tk.END, (
                f"  File: {full}\n"
                f"  Type: {node.type}    Size: {node.size}    Blocks: {blocks}\n"
                f"  Perms: {node.perms}    {lock}\n"
                f"  Inode: {node.inode}    Modified: {node.mtime.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"  Blessed by: the Rebbe's Machine\n"
            ))
        self._insert_prompt()

    def _cmd_ln(self, args):
        if len(args) != 2:
            self.text.insert(tk.END, "ln: usage: ln <src> <dst>\n", "error")
            self._insert_prompt()
            return
        rc = VFS.ln(args[0], args[1], self.cwd)
        if rc == "ENOENT":
            self.text.insert(tk.END, f"ln: {args[0]}: no such file or directory\n", "error")
        elif rc == "EEXIST":
            self.text.insert(tk.END, f"ln: {args[1]}: already exists\n", "error")
        self._insert_prompt()

    def _cmd_readlink(self, args):
        if not args:
            self.text.insert(tk.END, "readlink: missing operand\n", "error")
            self._insert_prompt()
            return
        for p in args:
            node = VFS.resolve(p, self.cwd)
            if node is None:
                self.text.insert(tk.END, f"readlink: {p}: no such file\n", "error")
            elif node.content.startswith("LINK:"):
                self.text.insert(tk.END, node.content[5:] + "\n")
            else:
                self.text.insert(tk.END, f"readlink: {p}: not a symbolic link\n", "error")
        self._insert_prompt()

    def _cmd_du(self, args):
        start = args[0] if args else "."
        base = self.cwd if start == "." else start
        node = VFS.resolve(start, self.cwd)
        if node is None:
            self.text.insert(tk.END, f"du: {start}: no such path\n", "error")
            self._insert_prompt()
            return
        for path, n, _ in VFS.walk(self.cwd if start == "." else start, self.cwd):
            if n.type == "dir":
                sz = VFS.du(path, self.cwd)
                self.text.insert(tk.END, f"{sz:>8}  {path}\n")
        sz = VFS.du(base, self.cwd)
        self.text.insert(tk.END, f"{sz:>8}  {base} (total)\n")
        self._insert_prompt()

    def _cmd_sudo(self, args):
        if not args:
            self.text.insert(tk.END, "sudo: the Rebbe is already root. Everywhere is root.\n")
            self._insert_prompt()
            return
        self.text.insert(tk.END, "[sudo] password for rebbe: ******** (it was always empty)\n", "dim")
        self._execute(" ".join(args))

    def _cmd_env(self, args):
        for k in sorted(VENV.env):
            self.text.insert(tk.END, f"{k}={VENV.env[k]}\n")
        self._insert_prompt()

    def _cmd_export(self, args):
        if not args:
            self._cmd_env(args)
            return
        for a in args:
            if "=" in a:
                k, v = a.split("=", 1)
                VENV.env[k] = v
        _save_conf()
        self._insert_prompt()

    def _cmd_alias(self, args):
        if not args:
            for k, v in VENV.aliases.items():
                self.text.insert(tk.END, f"alias {k}='{v}'\n")
            self._insert_prompt()
            return
        for a in args:
            if "=" in a:
                k, v = a.split("=", 1)
                VENV.aliases[k.strip()] = v.strip()
        _save_conf()
        self._insert_prompt()

    def _cmd_unalias(self, args):
        if not args:
            self.text.insert(tk.END, "unalias: missing operand\n", "error")
            self._insert_prompt()
            return
        for a in args:
            VENV.aliases.pop(a, None)
        _save_conf()
        self._insert_prompt()

    def _run_script(self, content):
        out = []
        for raw in content.splitlines():
            line = raw.strip()
            if not line or line.startswith("//") or line.startswith("#"):
                continue
            low = line.replace(" ", "")
            if low.startswith("U0") or low.startswith("I64") or low in ("{", "}"):
                continue
            if line.startswith("Sleep"):
                continue
            for text in self._extract_quoted(line):
                out.append(self._expand_env(text))
            if len(out) > 200:
                break
        return out

    @staticmethod
    def _extract_quoted(line):
        out = []
        i = 0
        while i < len(line):
            if line[i] == '"':
                i += 1
                buf = []
                while i < len(line) and line[i] != '"':
                    if line[i:i+2] == "\\n":
                        buf.append("\n")
                        i += 2
                    else:
                        buf.append(line[i])
                        i += 1
                out.append("".join(buf))
            i += 1
        return out

    def _cmd_run(self, args):
        if not args:
            self.text.insert(tk.END, "run: missing operand (try run /System/FirstBoot.HC)\n", "error")
            self._insert_prompt()
            return
        path = args[0]
        node = VFS.resolve(path, self.cwd)
        if node is None:
            self.text.insert(tk.END, f"run: {path}: no such file\n", "error")
            self._insert_prompt()
            return
        if node.type == "dir":
            self.text.insert(tk.END, f"run: {path}: is a directory\n", "error")
            self._insert_prompt()
            return
        if path.lower().endswith(".hc"):
            for text in self._run_holyc(node.content):
                self.text.insert(tk.END, text + "\n")
        else:
            for text in self._run_script(node.content):
                self.text.insert(tk.END, text + "\n")
        self._insert_prompt()

    def _cmd_ps(self, args):
        self.text.insert(tk.END, "PID   CMD                           CPU      MEM\n")
        procs = [
            (1, "kugeld", "0.0%", "1M"),
            (2, "meshugas", "74%", "64K"),
            (3, "havdalah-daemon", "1.0%", "2K"),
            (4, "nachas (zombie)", "0.0%", "0K"),
            (5, "siddur-package-manager", "12%", "4K"),
            (6, f"yumesh (rebbe@{VENV.hostname})", "3%", "640K"),
        ]
        for pid, name, cpu, mem in procs:
            self.text.insert(tk.END, f"{pid:<5} {name:<29} {cpu:<8} {mem}\n")
        self.text.insert(tk.END, "6 processes; 1 cpu (74-MHz, unclamped, like the clock in shul)\n", "dim")
        self._insert_prompt()

    def _cmd_weather(self, args):
        self.text.insert(tk.END, (
            "Jerusalem Report (hashgachah reception: good)\n"
            "Forecast: partly cloudy, with a chance of gefilte fish.\n"
            "Humidity: a little klotsky. Wind: southerly, like the family.\n"
            "Tomorrow: brisky, but the sun will shine like a candelabra.\n"
        ))
        self._insert_prompt()

    def _cmd_panic(self, args):
        self.text.insert(tk.END, "panic: The Rebbe panics. It is a good thing.\n", "error")
        parent_win = self._get_gui_parent()
        if parent_win:
            parent_win.show_panic()
        else:
            self._insert_prompt()

    def _cmd_gematria(self, args):
        if not args:
            self.text.insert(tk.END, "gematria: usage: gematria <word>\n", "error")
            self._insert_prompt()
            return
        word = args[0].lower()
        val = sum(ord(c) - ord("a") + 1 for c in word if c.isalpha())
        self.text.insert(tk.END, f"The word '{args[0]}' equals {val} in gematria. Blessed is the computation.\n")
        if val == 613:
            self.text.insert(tk.END, "Aha! 613! The number of mitzvot. You may be the compiler.\n", "dir")
        self._insert_prompt()

    def _cmd_brocha(self, args):
        bless = random.choice([
            "Baruch HaShem for this blessed day of computing.",
            "Blessed art thou, who strengthens the CPU and gives recipe-blessings.",
            "May the stack never overflow, and your cholent overflow.",
            "How lovely is the complex; the accumulator is a pleasant companion.",
            "Blessed is the pointer that returns, and the loop that closes.",
        ])
        self.text.insert(tk.END, bless + "\n")
        self._insert_prompt()

    def _cmd_god(self, args):
        self.text.insert(tk.END, "There is one God. And one compiler. (There may be many buses.)\n")
        self._insert_prompt()

    def _cmd_shutdown(self, args):
        parent_win = self._get_gui_parent()
        if parent_win:
            parent_win.trigger_shutdown()
        else:
            self._insert_prompt()

    def _cmd_screensaver(self, args):
        parent_win = self._get_gui_parent()
        if parent_win:
            parent_win.start_screensaver(force=True)
        self._insert_prompt()

    def _cmd_restore(self, args):
        if not args:
            self.text.insert(tk.END, "restore: usage: restore <name>\n", "error")
            self._insert_prompt()
            return
        for a in args:
            rc = VFS.restore(a, self.cwd)
            if rc == "ENOENT":
                self.text.insert(tk.END, f"restore: {a}: not in the Recycle Bin\n", "error")
            else:
                self.text.insert(tk.END, f"restore: {a} has returned home.\n")
        self._insert_prompt()

    # ---- packages & languages --------------------------------------------
    def _run_holyc(self, content):
        out = []
        state = {"err": None}

        def err(s):
            state["err"] = s

        eng = HolyCEngine(on_out=lambda s: out.append(s) if state["err"] is None else None, on_error=err)
        eng.run_source(content)
        if state["err"]:
            return self._run_script(content)
        return out

    def _run_script_file(self, path):
        node = VFS.resolve(path, self.cwd)
        if node is None:
            self.text.insert(tk.END, f"yumesh: {path}: no such file\n", "error")
            self._insert_prompt()
            return
        if node.type == "dir":
            self.text.insert(tk.END, f"yumesh: {path}: is a directory\n", "error")
            self._insert_prompt()
            return
        content = node.content
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext == "hc":
            for text in self._run_holyc(content):
                self.text.insert(tk.END, text + "\n")
        elif ext == "lsp":
            lisp = LispInterpreter(
                on_out=lambda s: self.text.insert(tk.END, s + "\n"),
                on_error=lambda s: self.text.insert(tk.END, s + "\n", "error"),
            )
            lisp.run(content)
        elif ext == "bas":
            basic = BasicInterpreter(
                on_out=lambda s: self.text.insert(tk.END, s + "\n"),
                on_error=lambda s: self.text.insert(tk.END, s + "\n", "error"),
            )
            basic.run_source(content)
        else:
            for text in self._run_script(content):
                self.text.insert(tk.END, text + "\n")
        self._insert_prompt()

    def _package_command(self, name):
        return Siddur.command_path(name)

    def _cmd_holyc(self, args):
        if not args:
            self.text.insert(tk.END, "holyc: usage: holyc <file.hc>   (try holyc /System/FirstBoot.HC)\n", "error")
            self._insert_prompt()
            return
        self._run_script_file(args[0])

    def _cmd_lisp(self, args):
        if not args:
            self.text.insert(tk.END, "lisp: usage: lisp <file.lsp>  |  lisp '<expression>'\n", "error")
            self._insert_prompt()
            return
        first = args[0]
        node = VFS.resolve(first, self.cwd)
        if node is not None and node.type == "file":
            self._run_script_file(first)
            return
        lisp = LispInterpreter(
            on_out=lambda s: self.text.insert(tk.END, s + "\n"),
            on_error=lambda s: self.text.insert(tk.END, s + "\n", "error"),
        )
        lisp.run(" ".join(args))
        self._insert_prompt()

    def _cmd_basic(self, args):
        if not args:
            self.text.insert(tk.END, "basic: usage: basic <file.bas>\n", "error")
            self._insert_prompt()
            return
        self._run_script_file(args[0])

    def _cmd_siddur(self, args):
        if not args:
            self.text.insert(tk.END, (
                "siddur - the package manager of YUshiveOS\n"
                "  siddur search [query]    list packages from the registry\n"
                "  siddur info <name>       show package details\n"
                "  siddur install <name>    install a package\n"
                "  siddur list              show installed packages\n"
                "  siddur remove <name>     retire a package (to the Bin)\n"
                "  siddur publish <dir>     bundle a directory into a .pkg\n"
                "  siddur import <file.pkg> install a shared .pkg\n"
                "  siddur update            (offline siddur: the vineyard is yours)\n"
            ), "title")
            self._insert_prompt()
            return
        sub = args[0]
        rest = args[1:]
        if sub == "search":
            rows = Siddur.search(self, rest[0] if rest else None)
            if not rows:
                self.text.insert(tk.END, "siddur search: nothing found in the registry.\n", "dim")
            else:
                self.text.insert(tk.END, f"{len(rows)} package(s) available:\n")
                for name, ver, cat, desc in rows:
                    self.text.insert(tk.END, f"  {name:<16} {cat:<8} v{ver:<5} {desc}\n")
            self._insert_prompt()
            return
        if sub == "info":
            if not rest:
                self.text.insert(tk.END, "siddur info: usage: siddur info <name>\n", "error")
                self._insert_prompt()
                return
            name = rest[0]
            pkg = _DEMO_PACKAGES.get(name)
            if pkg is None:
                self.text.insert(tk.END, f"siddur info: {name}: no such package in the registry.\n", "error")
                self._insert_prompt()
                return
            self.text.insert(tk.END, (
                f"  {name}  v{pkg['version']}  by {pkg['author']}\n"
                f"  category: {pkg['category']}   entry: {pkg['entry']}   command: {pkg.get('cmd') or name}\n"
                f"  {pkg['desc']}\n"
            ))
            self._insert_prompt()
            return
        if sub == "install":
            if not rest:
                self.text.insert(tk.END, "siddur install: usage: siddur install <name>\n", "error")
                self._insert_prompt()
                return
            name = rest[0]
            rc = Siddur.install(self, name)
            if rc == "ENOENT":
                self.text.insert(tk.END, f"siddur install: {name}: no such package. Try 'siddur search'.\n", "error")
            elif rc == "EEXIST":
                self.text.insert(tk.END, f"siddur install: {name}: already installed.\n", "error")
            else:
                self.text.insert(tk.END, f"siddur: {name} installed to {PKG_ROOT}/{name}.\n"
                                       f"  Type '{name}' to run it, or 'siddur list'.\n")
            self._insert_prompt()
            return
        if sub == "list":
            inst = Siddur.installed()
            if not inst:
                self.text.insert(tk.END, "no packages installed yet. Try a blessing, and 'siddur search'.\n", "dim")
            else:
                for name, meta in inst:
                    ver = meta.get("version", "?")
                    cmd = meta.get("cmd") or name
                    cat = meta.get("category", "?")
                    self.text.insert(tk.END, f"  {name:<16} {cat:<8} v{ver:<5} cmd: {cmd}\n")
            self._insert_prompt()
            return
        if sub == "remove":
            if not rest:
                self.text.insert(tk.END, "siddur remove: usage: siddur remove <name>\n", "error")
                self._insert_prompt()
                return
            name = rest[0]
            rc = Siddur.remove(self, name)
            if rc == "ENOENT":
                self.text.insert(tk.END, f"siddur remove: {name}: not installed.\n", "error")
            elif rc == "EPROTECT":
                self.text.insert(tk.END, f"siddur remove: {name}: protected by a shomer.\n", "error")
            else:
                self.text.insert(tk.END, f"siddur: {name} removed. It rests in the Recycle Bin.\n")
            self._insert_prompt()
            return
        if sub == "publish":
            if not rest:
                self.text.insert(tk.END, "siddur publish: usage: siddur publish <directory>\n", "error")
                self._insert_prompt()
                return
            rc = Siddur.publish(self, rest[0])
            if rc == "ENOENT":
                self.text.insert(tk.END, f"siddur publish: {rest[0]}: no such directory.\n", "error")
            elif rc == "EMPTY":
                self.text.insert(tk.END, "siddur publish: nothing to bundle in that directory.\n", "error")
            else:
                vfs_path, real = rc
                self.text.insert(tk.END, f"siddur publish: bundled to {vfs_path}\n")
                if real:
                    self.text.insert(tk.END, f"  Share it: the portable copy is at {real}\n")
                    self.text.insert(tk.END, "  Friends install it with:  siddur import <file.pkg>\n")
                else:
                    self.text.insert(tk.END, "  (real export dir unavailable; the VFS copy will do)\n")
            self._insert_prompt()
            return
        if sub == "import":
            if not rest:
                self.text.insert(tk.END, "siddur import: usage: siddur import <file.pkg>\n", "error")
                self._insert_prompt()
                return
            rc = Siddur.import_pkg(self, rest[0])
            if rc == "ENOENT":
                self.text.insert(tk.END, f"siddur import: {rest[0]}: no such file.\n", "error")
            elif rc == "EBAD":
                self.text.insert(tk.END, "siddur import: not a valid .pkg bundle.\n", "error")
            elif rc == "EEXIST":
                self.text.insert(tk.END, "siddur import: that package is already installed.\n", "error")
            else:
                self.text.insert(tk.END, "siddur import: package installed. Share it, and be shared.\n")
            self._insert_prompt()
            return
        if sub == "update":
            self.text.insert(tk.END, "siddur update: this siddur is offline-only; the vineyard is yours.\n", "dim")
            self._insert_prompt()
            return
        self.text.insert(tk.END, f"siddur: unknown subcommand '{sub}'  (try 'siddur' alone)\n", "error")
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
# HolyC-lite: a tiny C-ish interpreter for .HC scripts (on the simmer)
# ============================================================================
class HolyCError(Exception):
    pass


class _ReturnSignal(Exception):
    def __init__(self, value=0):
        super().__init__()
        self.value = value


_PREC = {"||": 1, "&&": 2, "==": 3, "!=": 3, "<": 4, "<=": 4, ">": 4, ">=": 4,
         "+": 5, "-": 5, "*": 6, "/": 6, "%": 6}
_TYPES = ("I64", "U0", "U8", "U16", "U32")


def _expr_tokens(s):
    toks = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
        elif ch.isdigit():
            j = i
            while j < n and (s[j].isdigit() or s[j] == "_"):
                j += 1
            toks.append(("num", int(s[i:j].replace("_", ""))))
            i = j
        elif ch.isalpha() or ch == "_":
            j = i
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            toks.append(("id", s[i:j]))
            i = j
        elif ch == '"':
            j = i + 1
            buf = []
            while j < n and s[j] != '"':
                if s[j] == "\\" and j + 1 < n:
                    esc = s[j + 1]
                    buf.append("\n" if esc == "n" else esc)
                    j += 2
                else:
                    buf.append(s[j])
                    j += 1
            toks.append(("str", "".join(buf)))
            i = j + 1
        else:
            two = s[i:i + 2]
            if two in ("==", "!=", "<=", ">=", "&&", "||"):
                toks.append(("op", two))
                i += 2
            elif two in ("+=", "-=", "*=", "/=", "%=", "++", "--"):
                toks.append(("op", two))
                i += 2
            else:
                toks.append(("op", ch))
                i += 1
    return toks


def _expr_prefix(toks, i):
    if i >= len(toks):
        raise HolyCError("unexpected end of expression")
    kind, val = toks[i]
    if kind in ("num", "str"):
        return (kind, val), i + 1
    if kind == "id":
        if i + 1 < len(toks) and toks[i + 1] == ("op", "("):
            j = i + 2
            args = []
            if j < len(toks) and toks[j] != ("op", ")"):
                while True:
                    a, j = _expr_parse(toks, j)
                    args.append(a)
                    if j < len(toks) and toks[j] == ("op", ","):
                        j += 1
                    else:
                        break
            if j < len(toks) and toks[j] == ("op", ")"):
                j += 1
            return ("call", val, args), j
        return ("var", val), i + 1
    if kind == "op" and val == "(":
        node, j = _expr_parse(toks, i + 1)
        if j < len(toks) and toks[j] == ("op", ")"):
            j += 1
        return node, j
    if kind == "op" and val == "-":
        node, j = _expr_parse(toks, i + 1, 7)
        return ("neg", node), j
    if kind == "op" and val == "!":
        node, j = _expr_parse(toks, i + 1, 7)
        return ("not", node), j
    raise HolyCError(f"bad token '{val}'")


def _expr_parse(toks, i=0, min_prec=0):
    node, j = _expr_prefix(toks, i)
    while j < len(toks):
        kind, val = toks[j]
        if kind != "op" or val not in _PREC or _PREC[val] < min_prec:
            break
        j += 1
        right, j = _expr_parse(toks, j, _PREC[val] + 1)
        node = ("bin", val, node, right)
    return node, j


def _expr_eval(node, getvar=None, call=None, tick=None):
    if tick:
        tick()
    if node is None:
        return 0
    t = node[0]
    if t == "num":
        return node[1]
    if t == "str":
        return node[1]
    if t == "var":
        name = node[1]
        if getvar is not None:
            v = getvar(name)
            if v is not None:
                return v
        raise HolyCError(f"undefined identifier '{name}'")
    if t == "neg":
        return -_expr_eval(node[1], getvar, call, tick)
    if t == "not":
        return 0 if _expr_eval(node[1], getvar, call, tick) else 1
    if t == "call":
        name, args = node[1], node[2]
        vals = [_expr_eval(a, getvar, call, tick) for a in args]
        if call is not None:
            return call(name, vals)
        raise HolyCError(f"undefined function '{name}'")
    op, a, b = node[1], node[2], node[3]
    av = _expr_eval(a, getvar, call, tick)
    if op == "&&":
        return av and _expr_eval(b, getvar, call, tick)
    if op == "||":
        return av or _expr_eval(b, getvar, call, tick)
    bv = _expr_eval(b, getvar, call, tick)
    if op == "+":
        if isinstance(av, str) or isinstance(bv, str):
            return str(av) + str(bv)
        return av + bv
    for bad in (av, bv):
        if not isinstance(bad, int):
            raise HolyCError("arithmetic wants integers")
    if op == "-":
        return av - bv
    if op == "*":
        return av * bv
    if op == "/":
        return av // bv if bv else 0
    if op == "%":
        return av % bv if bv else 0
    if op == "==":
        return 1 if av == bv else 0
    if op == "!=":
        return 1 if av != bv else 0
    if op == "<":
        return 1 if av < bv else 0
    if op == "<=":
        return 1 if av <= bv else 0
    if op == ">":
        return 1 if av > bv else 0
    if op == ">=":
        return 1 if av >= bv else 0
    return 0


def _split_top(toks, sep):
    out, cur, depth = [], [], 0
    for t in toks:
        if t == ("op", "("):
            depth += 1
        elif t == ("op", ")"):
            depth -= 1
        if t == ("op", sep) and depth == 0:
            out.append(cur)
            cur = []
        else:
            cur.append(t)
    out.append(cur)
    return out


class HolyCEngine:
    MAX_STEPS = 20000
    MAX_DEPTH = 64

    def __init__(self, on_out=None, on_error=None):
        self.out = on_out or (lambda s: None)
        self.err = on_error or self.out
        self.defs = {}
        self.globals = {}
        self.frames = []
        self.steps = 0
        self.depth = 0
        self.lines = []
        self.pos = 0

    def _tick(self):
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise HolyCError("too many steps (the golem struck back)")

    def _scope(self):
        return self.frames[-1] if self.frames else self.globals

    def _getvar(self, name):
        for fr in reversed(self.frames):
            if name in fr:
                return fr[name]
        if name in self.globals:
            return self.globals[name]
        return None

    def _setvar(self, name, val):
        for fr in reversed(self.frames):
            if name in fr:
                fr[name] = val
                return
        self.globals[name] = val

    def run_source(self, content):
        self.lines = content.splitlines()
        self.pos = 0
        try:
            while self.pos < len(self.lines):
                self._run_line()
        except HolyCError as e:
            self.err(f"holyc: {e}")
        except _ReturnSignal:
            pass

    def _strip(self, line):
        out = []
        i, n = 0, len(line)
        in_str = False
        while i < n:
            ch = line[i]
            if ch == '"':
                in_str = not in_str
                out.append(ch)
            elif not in_str and line.startswith("//", i):
                break
            else:
                out.append(ch)
            i += 1
        return "".join(out)

    def _peek_stripped(self):
        if self.pos >= len(self.lines):
            return ""
        return self._strip(self.lines[self.pos]).strip()

    def _match_brace(self):
        balance = 0
        i = self.pos
        while i < len(self.lines):
            s = self.lines[i]
            balance += s.count("{") - s.count("}")
            if balance <= 0:
                return i
            i += 1
        raise HolyCError("unbalanced braces")

    def _match_from(self, start):
        balance = 0
        i = start
        while i < len(self.lines):
            balance += self.lines[i].count("{") - self.lines[i].count("}")
            if balance <= 0:
                return i
            i += 1
        raise HolyCError(f"unbalanced braces from line {start + 1}")

    def _ensure_brace(self, rest):
        if "{" not in rest:
            while True:
                self.pos += 1
                if self.pos >= len(self.lines):
                    raise HolyCError("missing '{'")
                nxt = self.lines[self.pos].strip()
                if nxt and "{" in nxt:
                    return

    def _run_line(self):
        if self.pos >= len(self.lines):
            return
        raw = self.lines[self.pos]
        s = self._strip(raw).strip().rstrip(";").strip()
        if not s or s in ("{", "}"):
            self.pos += 1
            return
        if s.startswith("#"):
            self.pos += 1
            return
        m = re.match(r"^(?:U0|I64|U8|U16|U32)\s+(\w+)\s*\(([^)]*)\)\s*", s)
        if m:
            self._parse_function(m, s)
            return
        if s.startswith("if "):
            self._run_if(s)
            return
        if s.startswith("for "):
            self._run_for(s)
            return
        if s.startswith("while "):
            self._run_while(s)
            return
        if re.match(r"^return\b", s):
            self.pos += 1
            node, _ = _expr_parse(_expr_tokens(s[len("return"):].lstrip()))
            raise _ReturnSignal(_expr_eval(node, self._getvar, self._call, self._tick))
        if re.match(r"^print(?:ln)?\b", s, re.IGNORECASE):
            self._run_print(s)
            return
        if re.match(r"^Sleep\b", s, re.IGNORECASE):
            m = re.match(r"^Sleep\s*\((.*)\)\s*$", s, re.IGNORECASE)
            if m:
                node, _ = _expr_parse(_expr_tokens(m.group(1)))
                _expr_eval(node, self._getvar, self._call, self._tick)
            self.pos += 1
            return
        if self._maybe_assign(s):
            return
        if s.startswith('"'):
            self.pos += 1
            node, _ = _expr_parse(_expr_tokens(s))
            self.out(str(_expr_eval(node, self._getvar, self._call, self._tick)))
            return
        try:
            node, j = _expr_parse(_expr_tokens(s))
            if j >= len(_expr_tokens(s)):
                _expr_eval(node, self._getvar, self._call, self._tick)
                self.pos += 1
                return
        except HolyCError:
            pass
        raise HolyCError(f"can't parse: '{s}' (line {self.pos + 1})")

    def _parse_function(self, m, s):
        name = m.group(1)
        params = [p.split()[-1] for p in m.group(2).split(",") if p.strip()]
        rest = s[m.end():]
        if "{" not in rest:
            while True:
                self.pos += 1
                if self.pos >= len(self.lines):
                    raise HolyCError(f"function '{name}' missing '{{'")
                if "{" in self.lines[self.pos]:
                    break
        self.defs[name] = (params, self.pos)
        self.pos = self._match_brace() + 1

    def _call(self, name, vals):
        if name == "Sleep":
            return 0
        d = self.defs.get(name)
        if d is None:
            raise HolyCError(f"undefined function '{name}'")
        if self.depth >= self.MAX_DEPTH:
            raise HolyCError("call depth exceeds the shtender")
        self.depth += 1
        try:
            params, body_start = d
            close = self._match_from(body_start)
            fr = {}
            for p, v in zip(params, vals):
                fr[p] = v
            self.frames.append(fr)
            saved = self.pos
            self.pos = body_start + 1
            result = 0
            try:
                while self.pos < close:
                    self._run_line()
            except _ReturnSignal as ret:
                result = ret.value
            self.pos = saved
            return result
        finally:
            self.frames.pop()
            self.depth -= 1

    def _run_print(self, s):
        m = re.match(r"^print(?:ln)?\s*\(?(.*)$", s, re.IGNORECASE)
        args_text = m.group(1).strip()
        if args_text.endswith(")"):
            args_text = args_text[:-1]
        pieces = []
        for tl in _split_top(_expr_tokens(args_text), ","):
            if not tl:
                continue
            node, _ = _expr_parse(tl)
            pieces.append(str(_expr_eval(node, self._getvar, self._call, self._tick)))
        self.out("".join(pieces))
        self.pos += 1

    def _maybe_assign(self, s):
        tl = _expr_tokens(s)
        if not tl:
            return False
        if len(tl) == 2 and tl[0][0] == "id" and tl[0][1] in _TYPES and tl[1][0] == "id":
            self._setvar(tl[1][1], 0)
            self.pos += 1
            return True
        if self._assign_toks(tl, s):
            self.pos += 1
            return True
        return False

    def _assign_toks(self, tl, src=None):
        if not tl:
            return False
        if len(tl) >= 4 and tl[0][0] == "id" and tl[0][1] in _TYPES and tl[1][0] == "id" and tl[2] == ("op", "="):
            name, i = tl[1][1], 3
        elif len(tl) >= 3 and tl[0][0] == "id" and tl[1] == ("op", "="):
            name, i = tl[0][1], 2
        elif len(tl) >= 2 and tl[0][0] == "id" and tl[1] == ("op", "++"):
            self._setvar(tl[0][1], self._getvar(tl[0][1]) + 1)
            return True
        elif len(tl) >= 2 and tl[0][0] == "id" and tl[1] == ("op", "--"):
            self._setvar(tl[0][1], self._getvar(tl[0][1]) - 1)
            return True
        elif len(tl) >= 3 and tl[0][0] == "id" and tl[1] == ("op", "+") and tl[2] == ("op", "+"):
            self._setvar(tl[0][1], self._getvar(tl[0][1]) + 1)
            return True
        elif len(tl) >= 3 and tl[0][0] == "id" and tl[1] == ("op", "-") and tl[2] == ("op", "-"):
            self._setvar(tl[0][1], self._getvar(tl[0][1]) - 1)
            return True
        elif len(tl) >= 3 and tl[0][0] == "id" and tl[1][0] == "op" and tl[1][1] in ("+=", "-=", "*=", "/=", "%="):
            name = tl[0][1]
            op = tl[1][1]
            node, _ = _expr_parse(tl[2:])
            cur = self._getvar(name)
            v = _expr_eval(node, self._getvar, self._call, self._tick)
            if op == "+=":
                cur = cur + v
            elif op == "-=":
                cur = cur - v
            elif op == "*=":
                cur = cur * v
            elif op == "/=":
                cur = cur // v if v else cur
            elif op == "%=":
                cur = cur % v if v else cur
            self._setvar(name, cur)
            return True
        else:
            return False
        node, _ = _expr_parse(tl[i:])
        self._setvar(name, _expr_eval(node, self._getvar, self._call, self._tick))
        return True

    def _run_if(self, s):
        m = re.match(r"^if\s*\((.*)\)\s*(.*)$", s)
        cond_text, rest = m.group(1), m.group(2)
        node, _ = _expr_parse(_expr_tokens(cond_text))
        cond = _expr_eval(node, self._getvar, self._call, self._tick)
        self._ensure_brace(rest)
        close = self._match_brace()
        body_start = self.pos + 1
        if cond:
            self.pos = body_start
            while self.pos < close:
                self._run_line()
            self.pos = close + 1
            return
        self.pos = close + 1
        nxt = self._peek_stripped()
        if nxt.startswith("else"):
            s2 = nxt[4:].strip()
            if s2.startswith("if"):
                self.pos += 1
                self._run_line()
                self.pos += 1
                return
            self.pos += 1
            if "{" not in s2:
                while self.pos < len(self.lines):
                    nxtline = self.lines[self.pos].strip()
                    if nxtline and "{" in nxtline:
                        break
                    self.pos += 1
            close2 = self._match_brace()
            self.pos = self.pos + 1
            while self.pos < close2:
                self._run_line()
            self.pos = close2 + 1

    def _run_for(self, s):
        m = re.match(r"^for\s*\((.*)\)\s*(.*)$", s)
        inner = m.group(1)
        parts = _split_top(_expr_tokens(inner), ";")
        parts = (parts + [[], [], []])[:3]
        init, cond, upd = parts[0], parts[1], parts[2]
        if init:
            self._assign_toks(init)
        cond_node, _ = _expr_parse(cond) if cond else (("num", 1), 0)
        self._ensure_brace(m.group(2))
        close = self._match_brace()
        body_start = self.pos + 1
        while _expr_eval(cond_node, self._getvar, self._call, self._tick):
            self.pos = body_start
            while self.pos < close:
                self._run_line()
            if upd:
                self._assign_toks(upd)
            else:
                break
        self.pos = close + 1

    def _run_while(self, s):
        m = re.match(r"^while\s*\((.*)\)\s*(.*)$", s)
        cond_node, _ = _expr_parse(_expr_tokens(m.group(1)))
        self._ensure_brace(m.group(2))
        close = self._match_brace()
        body_start = self.pos + 1
        while _expr_eval(cond_node, self._getvar, self._call, self._tick):
            self.pos = body_start
            while self.pos < close:
                self._run_line()
        self.pos = close + 1


# ============================================================================
# LISP: a compact Scheme-style interpreter ("the holy compiler")
# ============================================================================
class LispError(Exception):
    pass


class _Sym(str):
    __slots__ = ()

    def __repr__(self):
        return str(self)


class LispInterpreter:
    MAX_DEPTH = 300

    def __init__(self, on_out=None, on_error=None):
        self.out = on_out or (lambda s: None)
        self.err = on_error or self.out
        self.globals = {}
        self.depth = 0

    def _tick(self):
        self.depth += 1
        if self.depth > self.MAX_DEPTH:
            raise LispError("recursion too deep (the golem now jokes)")

    def _tokenize(self, src):
        out, i, n = [], 0, len(src)
        while i < n:
            c = src[i]
            if c.isspace():
                i += 1
            elif c == ";":
                j = src.find("\n", i)
                i = n if j < 0 else j + 1
            elif c == '"':
                j = i + 1
                while j < n and src[j] != '"':
                    j += 1
                out.append(src[i:j + 1])
                i = j + 1
            elif c in "()'":
                out.append(c)
                i += 1
            else:
                j = i
                while j < n and not src[j].isspace() and src[j] not in "();'":
                    j += 1
                out.append(src[i:j])
                i = j
        return out

    def _parse_pair(self, toks):
        if not toks:
            raise LispError("unexpected end of input")
        t = toks.pop(0)
        if t == "(":
            lst = []
            while toks and toks[0] != ")":
                lst.append(self._parse_pair(toks))
            if not toks:
                raise LispError("missing ')'")
            toks.pop(0)
            return lst
        if t == ")":
            raise LispError("unexpected ')'")
        if t == "'":
            return [_Sym("quote"), self._parse_pair(toks)]
        if t.startswith('"'):
            return t[1:-1]
        if t == "#t":
            return True
        if t == "#f":
            return False
        if t.lstrip("-").isdigit():
            return int(t)
        return _Sym(t)

    def _show(self, v):
        if v is None:
            return ""
        if v is True:
            return "#t"
        if v is False:
            return "#f"
        if isinstance(v, list):
            return "(" + " ".join(self._show(x) for x in v) + ")"
        return str(v)

    def _truthy(self, v):
        return v not in (False, None)

    def ev(self, expr, env):
        self._tick()
        if isinstance(expr, bool) or isinstance(expr, int) or expr is None:
            return expr
        if isinstance(expr, str) and not isinstance(expr, _Sym):
            return expr
        if isinstance(expr, _Sym):
            if expr in env:
                return env[expr]
            raise LispError(f"unbound symbol: {expr}")
        if not isinstance(expr, list) or not expr:
            return expr
        head = expr[0]
        if isinstance(head, _Sym) and head == "quote":
            return expr[1]
        if isinstance(head, _Sym) and head == "if":
            _, c, t, f = expr
            return self.ev(t if self._truthy(self.ev(c, env)) else f, env)
        if isinstance(head, _Sym) and head == "define":
            target = expr[1]
            if isinstance(target, list):
                name = target[0]
                params = list(target[1:])
                body = list(expr[2:])
                env[name] = ["closure", params, body, env]
            else:
                env[target] = self.ev(expr[2], env)
            return None
        if isinstance(head, _Sym) and head == "lambda":
            params = list(expr[1])
            body = list(expr[2:])
            return ["closure", params, body, env]
        if isinstance(head, _Sym) and head == "begin":
            val = None
            for sub in expr[1:]:
                val = self.ev(sub, env)
            return val
        if isinstance(head, _Sym) and head == "cond":
            for branch in expr[1:]:
                test = branch[0]
                if test == _Sym("else") or self._truthy(self.ev(test, env)):
                    return self.ev(branch[1], env)
            return None
        if isinstance(head, _Sym) and head == "and":
            for sub in expr[1:]:
                if not self._truthy(self.ev(sub, env)):
                    return False
            return True
        if isinstance(head, _Sym) and head == "or":
            for sub in expr[1:]:
                v = self.ev(sub, env)
                if self._truthy(v):
                    return v
            return False
        if isinstance(head, _Sym):
            fn = env.get(head, head)
        else:
            fn = self.ev(head, env)
        args = [self.ev(a, env) for a in expr[1:]]
        return self._apply(fn, args, env)

    def _apply(self, fn, args, env):
        if isinstance(fn, list) and fn and fn[0] == "closure":
            _, params, body, closure_env = fn
            newenv = dict(closure_env)
            for p, a in zip(params, args):
                newenv[p] = a
            val = None
            for bexpr in body:
                val = self.ev(bexpr, newenv)
            return val
        if not isinstance(fn, _Sym):
            raise LispError("not a function")
        name = str(fn)
        if name == "+":
            r = 0
            for a in args:
                r += a
            return r
        if name == "*":
            r = 1
            for a in args:
                r *= a
            return r
        if name == "-":
            r = args[0] if args else 0
            for a in args[1:]:
                r -= a
            return r
        if name == "/":
            r = args[0] if args else 0
            for a in args[1:]:
                r = r // a if a else 0
            return r
        if name == "%":
            return args[0] % args[1] if args[1] else 0
        if name in ("=", "eq?"):
            return args[0] == args[1]
        if name == "<":
            return args[0] < args[1]
        if name == ">":
            return args[0] > args[1]
        if name == "<=":
            return args[0] <= args[1]
        if name == ">=":
            return args[0] >= args[1]
        if name == "car":
            return args[0][0]
        if name == "cdr":
            return list(args[0][1:])
        if name == "cons":
            b = args[1]
            return [args[0]] + (b if isinstance(b, list) else [b])
        if name == "list":
            return list(args)
        if name == "append":
            out = []
            for a in args:
                out.extend(a)
            return out
        if name == "length":
            return len(args[0])
        if name == "reverse":
            return list(reversed(args[0]))
        if name == "atom?":
            return not isinstance(args[0], list)
        if name == "pair?":
            return isinstance(args[0], list)
        if name == "null?":
            return args[0] in ([], None)
        if name == "not":
            return not self._truthy(args[0])
        if name == "print":
            self.out(" ".join(self._show(a) for a in args))
            return None
        raise LispError(f"undefined function: {name}")

    def run(self, src):
        try:
            toks = self._tokenize(src)
            while toks:
                expr = self._parse_pair(toks)
                v = self.ev(expr, self.globals)
                if v is not None:
                    self.out(self._show(v))
        except LispError as e:
            self.err(f"lisp: {e}")


# ============================================================================
# Yiddish BASIC: numbered lines, PRINT/LET/IF/GOTO/FOR (one pastel yeshiva at a time)
# ============================================================================
class BasicError(Exception):
    pass


class BasicInterpreter:
    MAX_STEPS = 20000

    def __init__(self, on_out=None, on_error=None):
        self.out = on_out or (lambda s: None)
        self.err = on_error or self.out
        self.vars = {}
        self.lines = []
        self.pos = 0
        self.stack = []
        self.loops = []
        self.data = []
        self.ri = 0
        self.steps = 0

    def _tick(self):
        self.steps += 1
        if self.steps > self.MAX_STEPS:
            raise BasicError("too many steps (the loop is a dybbuk)")

    def _getvar(self, name):
        return self.vars.get(name)

    def _truthy(self, v):
        return v != 0

    def _expr_text(self, text):
        node, _ = _expr_parse(_expr_tokens(text))
        return _expr_eval(node, self._getvar, None, self._tick)

    def run_source(self, content):
        self._parse(content)
        try:
            n = len(self.lines)
            while 0 <= self.pos < n:
                self._tick()
                num, text = self.lines[self.pos]
                jump = self._run_stmt(text)
                self.pos = jump if jump is not None else self.pos + 1
        except _ReturnSignal:
            pass
        except BasicError as e:
            self.err(f"basic: {e}")

    def _parse(self, content):
        out = []
        data = []
        for raw in content.splitlines():
            s = raw.strip()
            if not s:
                continue
            up = s.upper()
            if up.startswith("DATA "):
                for item in s[5:].split(","):
                    item = item.strip()
                    if item == "":
                        continue
                    if item.lstrip("-").isdigit():
                        data.append(int(item))
                    else:
                        data.append(item)
                continue
            m = re.match(r"^(\d+)\s+DATA\s+(.*)$", s, re.IGNORECASE)
            if m:
                num = int(m.group(1))
                for item in m.group(2).split(","):
                    item = item.strip()
                    if item == "":
                        continue
                    if item.lstrip("-").isdigit():
                        data.append(int(item))
                    else:
                        data.append(item)
                out.append((num, ""))
                continue
            m = re.match(r"^(\d+)\s+(.*)$", s)
            if m:
                out.append((int(m.group(1)), m.group(2)))
            else:
                out.append((None, s))
        out.sort(key=lambda t: t[0] if t[0] is not None else 0)
        self.lines = out
        self.data = data

    def _find_line(self, num):
        for i, (lnum, _) in enumerate(self.lines):
            if lnum == num:
                return i
        raise BasicError(f"no line {num}")

    def _run_stmt(self, s):
        up = s.upper().strip()
        if not up or up.startswith("REM") or up.startswith("'"):
            return None
        if up.startswith("PRINT") or up.startswith("?"):
            text = s[5:].lstrip() if up.startswith("PRINT") else s[1:].lstrip()
            parts = self._split_print(text)
            self.out("".join(self._print_part(p) for p in parts))
            return None
        if up.startswith("LET "):
            m = re.match(r"^LET\s+(\w+)\s*=\s*(.+)$", s)
            if m:
                self.vars[m.group(1)] = self._expr_text(m.group(2))
            return None
        m = re.match(r"^(\w+)\s*=\s*(.+)$", s)
        if m:
            self.vars[m.group(1)] = self._expr_text(m.group(2))
            return None
        if up.find(" THEN ") > 0:
            j = up.find(" THEN ")
            cond_text = s[3:j].strip()
            then_text = s[j + 6:].strip()
            if self._truthy(self._expr_text(cond_text)):
                if then_text.lstrip("-").isdigit():
                    return self._find_line(int(then_text))
                if then_text.upper().startswith("GOTO"):
                    g = re.match(r"^GOTO\s+(\d+)$", then_text.upper())
                    return self._find_line(int(g.group(1)))
                if then_text.upper().startswith("PRINT") or then_text.upper().startswith("?"):
                    st = then_text[5:].lstrip() if then_text.upper().startswith("PRINT") else then_text[1:].lstrip()
                    self.out("".join(self._print_part(p) for p in self._split_print(st)))
                    return None
                m2 = re.match(r"^(\w+)\s*=\s*(.+)$", then_text)
                if m2:
                    self.vars[m2.group(1)] = self._expr_text(m2.group(2))
                    return None
            return None
        if up.startswith("FOR "):
            m = re.match(r"^FOR\s+(\w+)\s*=\s*(.+?)\s+TO\s+(.+?)\s*(?:STEP\s+(.+))?$", up)
            var, start, limit = m.group(1), m.group(2), m.group(3)
            step = m.group(4) if m.group(4) else "1"
            self.vars[var] = self._expr_text(start)
            self.loops.append({
                "var": var,
                "limit": self._expr_text(limit),
                "step": self._expr_text(step),
                "for_idx": self.pos,
            })
            return None
        if up.startswith("NEXT "):
            var = up[5:].strip()
            while self.loops and self.loops[-1]["var"] != var:
                self.loops.pop()
            if not self.loops:
                raise BasicError("NEXT without FOR")
            loop = self.loops[-1]
            self.vars[var] = self.vars.get(var, 0) + loop["step"]
            if (loop["step"] > 0 and self.vars[var] <= loop["limit"]) or (
                    loop["step"] < 0 and self.vars[var] >= loop["limit"]):
                return loop["for_idx"] + 1
            self.loops.pop()
            return None
        if up.startswith("GOTO "):
            g = re.match(r"^GOTO\s+(\d+)$", up)
            return self._find_line(int(g.group(1)))
        if up.startswith("GOSUB "):
            g = re.match(r"^GOSUB\s+(\d+)$", up)
            self.stack.append(self.pos + 1)
            return self._find_line(int(g.group(1)))
        if up.startswith("RETURN"):
            if not self.stack:
                raise BasicError("RETURN without GOSUB")
            return self.stack.pop()
        if up.startswith("END") or up.startswith("STOP"):
            raise _ReturnSignal()
        if up.startswith("READ "):
            for nm in s[5:].split(","):
                nm = nm.strip()
                if not nm:
                    continue
                if self.ri >= len(self.data):
                    raise BasicError("DATA is empty as a zinuk")
                self.vars[nm] = self.data[self.ri]
                self.ri += 1
            return None
        if up.startswith("INPUT"):
            body = s[5:].strip()
            prompt = body
            m = re.match(r'^"([^"]*)"\s*;\s*(\w+)$', body)
            if m:
                prompt, nm = m.group(1), m.group(2)
            else:
                nm = body.rstrip(";").strip()
            self.vars[nm] = self._input_value(prompt or (nm + "? "))
            return None
        raise BasicError(f"can't parse line: {s}")

    def _input_value(self, prompt):
        try:
            root = tk._default_root
            if root is None:
                return 0
            ans = simpledialog.askstring("Yiddish BASIC input", prompt, parent=root)
            if ans is None:
                return 0
            ans = ans.strip()
            if ans.lstrip("-").isdigit():
                return int(ans)
            return ans
        except Exception:
            return 0

    def _split_print(self, text):
        parts = []
        cur = ""
        mode = False
        i, n = 0, len(text)
        while i < n:
            ch = text[i]
            if mode:
                cur += ch
                if ch == '"':
                    mode = False
            elif ch == '"':
                cur += ch
                mode = True
            elif ch in ";,":
                parts.append(cur)
                parts.append(("sep", ch))
                cur = ""
            else:
                cur += ch
            i += 1
        parts.append(cur)
        return parts

    def _print_part(self, p):
        if isinstance(p, tuple):
            return "\t" if p[1] == "," else ""
        p = p.strip()
        if not p:
            return ""
        if p.startswith('"') and p.endswith('"') and len(p) >= 2:
            return p[1:-1]
        try:
            return str(self._expr_text(p))
        except (BasicError, HolyCError):
            return p


# ============================================================================
# Siddur: the package manager (mima'amakim it installs)
# ============================================================================
_DEMO_PACKAGES = {
    "latkes": {
        "version": "1.2",
        "author": "bubbe@YUshiveOS",
        "category": "food",
        "desc": "A proper latke countdown, with oil.",
        "entry": "latkes.HC",
        "cmd": "latkes",
        "files": {
            "latkes.HC": (
                "I64 n = 3;\n"
                "U0 Countdown( I64 k ) {\n"
                "  while ( k > 0 ) {\n"
                "    Print( \"- \", k, \" more before the oil...\\n\" );\n"
                "    k = k - 1;\n"
                "  }\n"
                "}\n"
                "Print( \"Take 3 potatoes. Shoyn.\\n\" );\n"
                "Countdown( n );\n"
                "Println( \"Golden and blessed.\" );\n"
            ),
        },
    },
    "daf-yomi": {
        "version": "0.9",
        "author": "mashekh@YUshiveOS",
        "category": "texts",
        "desc": "A [fake] daf of the day, imaginary but earnest.",
        "entry": "daf.HC",
        "cmd": "daf-yomi",
        "files": {
            "daf.HC": (
                "I64 day = 1;\n"
                "for ( day = 1; day <= 3; day++ ) {\n"
                "  Print( \"Daf \", day, \": a fine tractate of the imagination.\\n\" );\n"
                "}\n"
                "Println( \"(Not actual Torah - the real kind you should learn elsewhere.)\" );\n"
            ),
        },
    },
    "zmanim": {
        "version": "2.1",
        "author": "shoimer@YUshiveOS",
        "category": "texts",
        "desc": "Assumed zmanim for a perfectly sunny pretend day.",
        "entry": "zmanim.BAS",
        "cmd": "zmanim",
        "files": {
            "zmanim.BAS": (
                "REM Assumed zmanim for a sunny pretend day\n"
                "LET X = 5\n"
                "FOR I = 1 TO X\n"
                " PRINT \"Sunrise is very early. \", I\n"
                "NEXT I\n"
                "PRINT \"Derech: done for today.\"\n"
            ),
        },
    },
    "mishnayos": {
        "version": "1.0",
        "author": "tanna@YUshiveOS",
        "category": "texts",
        "desc": "Sample a few mishnayot (the flatbread of the mind).",
        "entry": "mishnayos.BAS",
        "cmd": "mishnayos",
        "files": {
            "mishnayos.BAS": (
                "10 DATA 6,7,5,9\n"
                "20 READ A,B,C,D\n"
                "30 PRINT \"Mishnayot sampled: \", A+B+C+D\n"
                "40 IF A + B > 10 THEN GOTO 60\n"
                "50 PRINT \"An easy masechet today.\"\n"
                "55 END\n"
                "60 PRINT \"A brisk review day.\"\n"
            ),
        },
    },
    "tanakh-quiz": {
        "version": "1.4",
        "author": "navi@YUshiveOS",
        "category": "games",
        "desc": "A tiny LISP quiz about the fruit basket of the desert.",
        "entry": "quiz.LSP",
        "cmd": "tanakh-quiz",
        "files": {
            "quiz.LSP": (
                "(define fruits '(fig pomegranate olive date))\n"
                "(define (len lst) (if (null? lst) 0 (+ 1 (len (cdr lst)))))\n"
                "(print \"The fruit basket holds \" (len fruits) \" kinds.\")\n"
                "(print \"First in the desert: \" (car fruits))\n"
                "(if (> (len fruits) 2) (print \"Enough for the table.\") (print \"Grow more.\"))\n"
            ),
        },
    },
    "schtick": {
        "version": "0.3",
        "author": "badchen@YUshiveOS",
        "category": "vibes",
        "desc": "A punchline, recursively chosen. Laugh or it is a mitzvah.",
        "entry": "schtick.LSP",
        "cmd": "schtick",
        "files": {
            "schtick.LSP": (
                "(define (choose lst) (if (null? (cdr lst)) (car lst) (choose (cdr lst))))\n"
                "(print (choose '(nu-so-a-segulah-is-how-you-look-at-it)))\n"
            ),
        },
    },
}


class Siddur:
    @staticmethod
    def _mkdirs(path):
        parts = path.strip("/").split("/")
        cur = ""
        for part in parts:
            cur += "/" + part
            if VFS.resolve(cur) is None:
                VFS.mkdir(cur)

    @staticmethod
    def installed():
        node = VFS.resolve(PKG_ROOT)
        if node is None or node.type != "dir":
            return []
        out = []
        for name, child in sorted(node.children.items()):
            if child.type != "dir":
                continue
            meta = {}
            m = VFS.resolve(PKG_ROOT + "/" + name + "/manifest.json")
            if m is not None:
                try:
                    meta = json.loads(m.content)
                except Exception:
                    meta = {}
            out.append((name, meta))
        return out

    @staticmethod
    def install(term, name):
        pkg = _DEMO_PACKAGES.get(name)
        if pkg is None:
            return "ENOENT"
        if VFS.resolve(f"{PKG_ROOT}/{name}") is not None:
            return "EEXIST"
        Siddur._mkdirs(PKG_ROOT)
        VFS.mkdir(f"{PKG_ROOT}/{name}")
        manifest = {
            "name": name,
            "version": pkg["version"],
            "author": pkg["author"],
            "category": pkg["category"],
            "desc": pkg["desc"],
            "entry": pkg["entry"],
            "cmd": pkg.get("cmd"),
        }
        VFS.write(f"{PKG_ROOT}/{name}/manifest.json", json.dumps(manifest, indent=2))
        for rel, content in pkg["files"].items():
            VFS.write(f"{PKG_ROOT}/{name}/{rel}", content)
        return None

    @staticmethod
    def remove(term, name):
        node = VFS.resolve(f"{PKG_ROOT}/{name}")
        if node is None or node.type != "dir":
            return "ENOENT"
        rc = VFS.trash(f"{PKG_ROOT}/{name}")
        return rc

    @staticmethod
    def package_manifest(name):
        for child_name, meta in Siddur.installed():
            if child_name == name:
                return meta
        return None

    @staticmethod
    def command_path(name):
        for pkg_name, meta in Siddur.installed():
            cmd = meta.get("cmd") or meta.get("name")
            if cmd == name and meta.get("entry"):
                return f"{PKG_ROOT}/{pkg_name}/{meta['entry']}"
        return None

    @staticmethod
    def collect_dir(node, prefix=""):
        files = {}
        for name, child in sorted(node.children.items()):
            rel = (prefix + "/" + name) if prefix else name
            if child.type == "dir":
                files.update(Siddur.collect_dir(child, rel))
            else:
                files[rel] = child.content
        return files

    @staticmethod
    def publish(term, dir_path):
        node = VFS.resolve(dir_path, term.cwd)
        if node is None or node.type != "dir":
            return "ENOENT"
        files = Siddur.collect_dir(node)
        files.pop("manifest.json", None)
        if not files:
            return "EMPTY"
        base = node.name
        entry = next((f for f in files if f.lower().endswith((".hc", ".lsp", ".bas"))), sorted(files)[0])
        meta = {
            "name": base,
            "version": "1.0",
            "author": f"{VENV.user}@{VENV.hostname}",
            "category": "misc",
            "desc": "A package freshly simmered.",
            "entry": entry,
            "cmd": base,
        }
        payload = {
            "format": "yushive-pkg",
            "files": {rel: base64.b64encode(content.encode("utf-8")).decode("ascii") for rel, content in files.items()},
        }
        payload.update({k: v for k, v in meta.items()})
        blob = json.dumps(payload, indent=2)
        vfs_path = "/Home/" + base + ".pkg"
        VFS.write(vfs_path, blob)
        try:
            PKG_EXPORT_DIR.mkdir(parents=True, exist_ok=True)
            real = PKG_EXPORT_DIR / (base + ".pkg")
            real.write_text(blob)
        except OSError:
            real = None
        return (vfs_path, real)

    @staticmethod
    def import_pkg(term, file_path):
        node = VFS.resolve(file_path, term.cwd)
        if node is None or node.type != "file":
            return "ENOENT"
        try:
            payload = json.loads(node.content)
        except Exception:
            return "EBAD"
        if payload.get("format") != "yushive-pkg":
            return "EBAD"
        name = payload.get("name")
        if not name:
            return "EBAD"
        if VFS.resolve(f"{PKG_ROOT}/{name}") is not None:
            return "EEXIST"
        Siddur._mkdirs(PKG_ROOT)
        VFS.mkdir(f"{PKG_ROOT}/{name}")
        meta = {k: payload.get(k) for k in ("name", "version", "author", "category", "desc", "entry", "cmd")}
        VFS.write(f"{PKG_ROOT}/{name}/manifest.json", json.dumps(meta, indent=2))
        for rel, b64 in payload.get("files", {}).items():
            content = base64.b64decode(b64).decode("utf-8")
            VFS.write(f"{PKG_ROOT}/{name}/{rel}", content)
        return None

    @staticmethod
    def search(term, query=None):
        rows = []
        q = (query or "").lower()
        for name, pkg in sorted(_DEMO_PACKAGES.items()):
            hay = " ".join([name, pkg["category"], pkg["desc"], pkg["author"]])
            if q and q not in hay.lower():
                continue
            rows.append((name, pkg["version"], pkg["category"], pkg["desc"]))
        return rows


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
        self.context_menu.add_command(label="Edit", command=self._context_edit)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Copy Path", command=self._context_copy_path)
        self.context_menu.add_command(label="Refresh", command=self._refresh)
        self.context_menu.add_command(label="New Directory", command=self._context_new_dir)

    def _context_edit(self):
        sel = self.tree.selection()
        if not sel:
            return
        name = self.tree.item(sel[0], "text")
        node = VFS.resolve(name, self.current_path)
        if node is not None and node.type == "file":
            parent_win = self._get_gui_parent()
            if parent_win:
                parent_win.open_editor(VFS._path_of(node))

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

        self.tree.tag_configure("fb_dir", foreground=ORANGE_BRIGHT, font=FONT_UI_BOLD)
        self.tree.tag_configure("fb_file", foreground=ORANGE)
        self.tree.tag_configure("fb_meta", foreground=ORANGE_DIM)
        self.tree.tag_configure("fb_hidden", foreground=ORANGE_DIM)

        for child in sorted(node.children.values(), key=lambda c: (c.type != "dir", c.name.lower())):
            size = "--" if child.type == "dir" else FileBrowser._format_size(child.size)
            mtime = child.mtime.strftime("%Y-%m-%d %H:%M")
            name = child.name + "/" if child.type == "dir" else child.name
            tags = ["fb_dir"] if child.type == "dir" else ["fb_file"]
            if child.name.startswith("."):
                tags.append("fb_hidden")
            self.tree.insert("", tk.END, text=name, values=(size, mtime, child.perms), tags=tags)

        if self.on_path_change:
            self.on_path_change(self.current_path)

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if sel:
            self._open_item(sel[0])

    def _open_item(self, item):
        name = self.tree.item(item, "text")
        node = VFS.resolve(name, self.current_path)
        if node is None:
            return
        if node.type == "dir":
            self._navigate_to(VFS._path_of(node))
        else:
            parent_win = self._get_gui_parent()
            if parent_win:
                parent_win.open_editor(VFS._path_of(node))

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
# YumePad: the text editor of the yeshiva
# ============================================================================
class YumePad(tk.Frame):
    def __init__(self, parent, path, **kwargs):
        super().__init__(parent, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)
        self.path = path
        self._status = "saved"

        bar = tk.Frame(self, bg=BG_BLUE_ALT)
        bar.pack(fill=tk.X)
        self.title_var = tk.StringVar(value=f"  YumePad - {path}")
        tk.Label(bar, textvariable=self.title_var, bg=BG_BLUE_ALT, fg=ORANGE_BRIGHT,
                 font=FONT_UI_BOLD).pack(side=tk.LEFT)
        ttk.Button(bar, text=" Close ", command=self.close).pack(side=tk.RIGHT, padx=3)
        ttk.Button(bar, text=" Save ", command=self.save).pack(side=tk.RIGHT, padx=3)

        self.editor = tk.Text(
            self, bg=BG_BLUE, fg=ORANGE, insertbackground=ORANGE_BRIGHT,
            selectbackground=SELECT, font=FONT_MONO, relief=tk.FLAT,
            padx=10, pady=10, undo=True, insertwidth=2, wrap="word",
        )
        self.editor.pack(fill=tk.BOTH, expand=True)

        node = VFS.resolve(self.path)
        if node is not None:
            self.editor.insert("1.0", node.content)
        self.editor.focus_set()

        self.status_var = tk.StringVar(value="  file is kosher (saved)")
        tk.Label(self, textvariable=self.status_var, bg=BG_BLUE_DEEP, fg=ORANGE_DIM,
                 font=FONT_MONO_SM, anchor="w").pack(fill=tk.X)

        self.editor.bind("<Control-s>", lambda e: (self.save(), "break")[1])
        self.editor.bind("<Any-KeyPress>", self._mark_dirty)

    def _mark_dirty(self, event):
        if self._status != "dirty":
            self._status = "dirty"
            self.title_var.set(f"  YumePad - {self.path} (dirty)")
            self.status_var.set("  unsaved changes - press Ctrl+S or Save")

    def save(self):
        node = VFS.resolve(self.path)
        text = self.editor.get("1.0", "end-1c")
        if node is not None and node.locked:
            beep()
            self.status_var.set("  permission dinied: the file is locked by chmod 000")
            return
        if node is None:
            VFS.mkfile(self.path, content=text)
        else:
            VFS.set_content(node, text)
        self._status = "saved"
        self.status_var.set("  file is kosher (saved)")
        self.title_var.set(f"  YumePad - {self.path}")

    def close(self):
        if self._status == "dirty":
            beep()
            self.status_var.set("  unsaved changes! Save first, or accept the crumbs.")
            return
        gui = self._get_gui_parent()
        if gui:
            gui.close_tab_for(self)

    def _get_gui_parent(self):
        p = self.master
        while p is not None:
            if isinstance(p, YumeGUI):
                return p
            p = p.master
        return None


# ============================================================================
# Star Field screen saver (a nod to a certain holy OS)
# ============================================================================
class Screensaver(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_win = master
        self.overrideredirect(True)
        self.configure(bg=BG_BLUE_DEEP)
        self.attributes("-topmost", True)
        w = master.winfo_width() or 1024
        h = master.winfo_height() or 680
        x = master.winfo_x()
        y = master.winfo_y()
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.canvas = tk.Canvas(self, bg=BG_BLUE_DEEP, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        sw = master.winfo_screenwidth()
        sh = master.winfo_screenheight()
        self.stars = [
            {
                "x": random.uniform(0, sw), "y": random.uniform(0, sh),
                "vx": random.uniform(-0.5, -0.05),
                "vy": random.uniform(-0.25, -0.02),
                "size": random.choice((1, 1, 2, 3)),
            }
            for _ in range(130)
        ]
        self.frame = 0
        self._dismissed = False
        self.canvas.bind("<Any-KeyPress>", self._dismiss)
        self.canvas.bind("<Any-Button>", self._dismiss)
        self.canvas.bind("<Motion>", self._dismiss)
        self.after(40, self._animate)

    def _dismiss(self, event=None):
        if self._dismissed:
            return
        self._dismissed = True
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.master_win is not None:
            self.master_win._screensaver_active = False
            self.master_win._arm_idle()

    def _animate(self):
        if self._dismissed:
            return
        self.canvas.delete("all")
        w = self.canvas.winfo_width() or 1024
        h = self.canvas.winfo_height() or 680
        for s in self.stars:
            s["x"] += s["vx"]
            s["y"] += s["vy"]
            if s["x"] < 0:
                s["x"] = w
            if s["y"] < 0:
                s["y"] = h
            color = FG_CREAM if s["size"] >= 3 else FG_GOLD
            self.canvas.create_rectangle(s["x"], s["y"], s["x"] + s["size"], s["y"] + s["size"],
                                         fill=color, outline="")
        cx, cy = w // 2, h // 2
        r = min(w, h) // 5
        offset = self.frame * 0.03

        def ring_pts(start_angle):
            pts = []
            for i in range(3):
                a = -math.pi / 2 + start_angle + i * 2 * math.pi / 3 + offset
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            return pts

        def flat(pts):
            return [c for p in pts for c in p]

        up = ring_pts(0)
        dn = ring_pts(math.pi / 3)
        self.canvas.create_line(flat(up + [up[0]]), fill=FG_GOLD, width=4)
        self.canvas.create_line(flat(dn + [dn[0]]), fill=FG_CREAM, width=4)
        self.canvas.create_text(cx, h - 30, text="YUshiveOS is resting now.",
                                fill=FG_STONE, font=("DejaVu Sans Mono", 11))

        self.frame += 1
        self.after(40, self._animate)


# ============================================================================
# Power sequence (reboot / shutdown screens)
# ============================================================================
class PowerSequence(tk.Toplevel):
    def __init__(self, master, mode="reboot"):
        super().__init__(master)
        self.master_win = master
        self.mode = mode
        self.overrideredirect(True)
        self.configure(bg=BG_BLUE)
        self.attributes("-topmost", True)
        w = master.winfo_width() or 1024
        h = master.winfo_height() or 680
        self.geometry(f"{w}x{h}+{master.winfo_x()}+{master.winfo_y()}")

        frame = tk.Frame(self, bg=BG_BLUE)
        frame.pack(fill=tk.BOTH, expand=True)

        if mode == "reboot":
            title = "YUshiveOS is rebooting"
            lines = [
                "Consulting the Rebbe one last time...",
                "Gathering the shmita of the disk...",
                "The Rebbe says: be back in a moment.",
            ]
        else:
            title = "YUshiveOS is shutting down"
            lines = [
                "It is now safe to daven.",
                "The cholent has been covered with a clean foil.",
                "Sessions are sed, files are kosher and saved.",
            ]
        tk.Label(frame, text=title, bg=BG_BLUE, fg=ORANGE_BRIGHT,
                 font=("DejaVu Sans Mono", 18, "bold")).pack(pady=48)
        for ln in lines:
            tk.Label(frame, text=ln, bg=BG_BLUE, fg=ORANGE,
                     font=("DejaVu Sans Mono", 11)).pack(pady=3)
        self.step = 0
        self.after(1800, self._finish)

    def _finish(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        if self.mode == "reboot":
            self.master_win.after(150, self.master_win._start_boot)
        else:
            self.master_win._close_os()


# ============================================================================
# Kernel panic (fake blue screen of death)
# ============================================================================
class PanicScreen(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_win = master
        self.overrideredirect(True)
        self.configure(bg="#0a0a00")
        self.attributes("-topmost", True)
        w = master.winfo_width() or 1024
        h = master.winfo_height() or 680
        self.geometry(f"{w}x{h}+{master.winfo_x()}+{master.winfo_y()}")
        tk.Label(
            self,
            text=(
                "KERNEL PANIC - ZYGOAT\n\n"
                "The Rebbe has panicked, which is a good thing.\n"
                "A fatal exception has occurred at 74:074AH in NUCHAS.\n"
                "The second temple has been rebuilt 0 times. Halt.\n\n"
                "This virtual machine will reboot after a short nap."
            ),
            bg="#0a0a00", fg="orange", font=("DejaVu Sans Mono", 13),
            justify="left",
        ).pack(pady=60, padx=40)
        self.after(3500, self._reboot)

    def _reboot(self):
        try:
            self.destroy()
        except tk.TclError:
            pass
        self.master_win.trigger_reboot()


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
        self.tab_titles = {}
        self.cwd = "/Home"
        self.revealed = False

        _load_conf()

        self._screensaver_active = False
        self._idle_after = None

        self._build_layout()

        # boot splash over the window (dashboard stays as the default tab)
        self.after(300, self._start_boot)

        self._start_status_clock()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        for seq in ("<Key>", "<Button-1>", "<Button-3>", "<Motion>"):
            self.bind_all(seq, self._on_user_activity, add="+")

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

        self.power_menu = tk.Menu(self, tearoff=0, bg=BG_BLUE, fg=ORANGE, activebackground=SELECT, activeforeground=ORANGE_BRIGHT, font=FONT_UI)
        self.power_menu.add_command(label="Shutdown", command=self.trigger_shutdown)
        self.power_menu.add_command(label="Reboot", command=self.trigger_reboot)
        self.power_menu.add_separator()
        self.power_menu.add_command(label="First Boot (wipe disk)", command=self.first_boot)
        btn_power = ttk.Menubutton(inner_bar, text="Power", menu=self.power_menu)
        btn_power.pack(side=tk.RIGHT, padx=4)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.notebook.bind("<Button-2>", self._on_middle_click_tab)

        self.taskbar = ttk.Frame(self, style="Status.TFrame")
        self.taskbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.taskbar_buttons = {}

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

        icon_row = tk.Frame(body, bg=BG_BLUE)
        icon_row.pack(anchor="w", padx=24, pady=(14, 2))
        for label, icon, cmd in [
            ("Terminal", ">_", self.open_terminal),
            ("Files", "[]", self.open_file_manager),
            ("YumePad", "~", lambda: self.open_editor("/Home/Welcome.txt")),
            ("Info", "i", self.open_system_info),
            ("Star Field", "*", lambda: self.start_screensaver(force=True)),
        ]:
            cell = tk.Frame(icon_row, bg=BG_BLUE)
            cell.pack(side=tk.LEFT, padx=12)
            tk.Label(cell, text=icon, bg=BG_BLUE_ALT, fg=ORANGE_BRIGHT, font=("DejaVu Sans Mono", 18, "bold"),
                     width=5, height=2, cursor="hand2").pack()
            tk.Label(cell, text=label, bg=BG_BLUE, fg=ORANGE, font=FONT_UI).pack()
            for w in cell.winfo_children()[:1]:
                w.bind("<Button-1>", lambda e, fn=cmd: fn())

        tk.Label(
            body, text=random.choice(BOOT_FACTS), bg=BG_BLUE, fg=ORANGE_DIM,
            font=("DejaVu Sans Mono", 9), wraplength=700, justify="left",
        ).pack(anchor="w", padx=24, pady=(30, 0))

    # ---- boot / reveal -----------------------------------------------------
    def _start_boot(self):
        self.boot = BootSplash(self)

    def reveal_dashboard(self):
        self.revealed = True
        beep()
        try:
            self.notebook.select(self.dashboard_holder)
        except tk.TclError:
            pass
        self._arm_idle()

    def trigger_reboot(self):
        # close all tabs, run the power sequence, then replay boot
        self._save_all()
        for tab in list(self.tab_buttons.keys()):
            try:
                self.close_tab(tab)
            except Exception:
                pass
        self.after(100, lambda: PowerSequence(self, mode="reboot"))

    def trigger_shutdown(self):
        self.after(100, lambda: PowerSequence(self, mode="shutdown"))

    def first_boot(self):
        VFS.destroy_disk()
        try:
            CONF_IMAGE.unlink(missing_ok=True)
        except OSError:
            pass
        self._save_all()
        self.trigger_reboot()

    def _save_all(self):
        VFS.save()
        _save_conf()

    def _on_close(self):
        self._save_all()
        self.destroy()

    def _close_os(self):
        self._save_all()
        VFS.empty_recycle_bin()
        self.destroy()

    def show_panic(self):
        self._save_all()
        self.after(500, lambda: PanicScreen(self))

    def open_editor(self, path):
        node = VFS.resolve(path)
        if node is None or node.type != "file":
            return
        content = self.add_app_tab("YumePad")
        YumePad(content, VFS._path_of(node))

    def start_screensaver(self, force=False):
        if self._screensaver_active:
            return
        if not self.revealed and not force:
            return
        self._screensaver_active = True
        Screensaver(self)

    def _arm_idle(self):
        if self._idle_after is not None:
            try:
                self.after_cancel(self._idle_after)
            except Exception:
                pass
        self._idle_after = self.after(60000, self._on_idle_timeout)

    def _on_idle_timeout(self):
        self._idle_after = None
        self.start_screensaver(force=True)

    def _on_user_activity(self, event=None):
        self._arm_idle()

    def _update_taskbar(self):
        for w in self.taskbar.winfo_children():
            w.destroy()
        self.taskbar_buttons = {}
        for tab_frame, title in self.tab_titles.items():
            if title.strip() in ("Dashboard",):
                continue
            btn = tk.Label(self.taskbar, text=" " + title + " ", bg=BG_BLUE_ALT, fg=ORANGE,
                           font=FONT_UI_BOLD, padx=6, pady=2, cursor="hand2")
            btn.pack(side=tk.LEFT, padx=2, pady=2)
            btn.bind("<Button-1>", lambda e, f=tab_frame: self.notebook.select(f))
            self.taskbar_buttons[tab_frame] = btn

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

        self.tab_titles[tab_frame] = app_title

        self.notebook.add(tab_frame, text="")
        self.notebook.select(tab_frame)
        self._update_taskbar()
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
        self.tab_titles.pop(tab_frame, None)

        for child in tab_frame.winfo_children():
            child.destroy()

        try:
            self.notebook.forget(tab_frame)
        except tk.TclError:
            pass
        self._update_taskbar()
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

        tk.Label(content, text="BIOS / BOARD", bg=BG_BLUE, fg=ORANGE_DIM,
                 font=("DejaVu Sans Mono", 10, "bold")).pack(anchor="w", pady=(0, 3))
        hardware = [
            ("BIOS", "YUshiveBIOS v1.06 (7 Tevet 5770)"),
            ("Board", "Mitzvah 613-5770 (a blessed year)"),
            ("Boot Device", "CholentHD (Primary & Only)"),
            ("Time Zone", "Yerushalayim Standard Time"),
            ("Disk Image", str(DISK_IMAGE)),
            ("AC Power", "74-MHz (unclamped)"),
        ]
        for label, value in hardware:
            row = tk.Frame(content, bg=BG_BLUE)
            row.pack(anchor="w", pady=2, fill=tk.X)
            tk.Label(row, text=f"{label}:", bg=BG_BLUE, fg=ORANGE_DIM, font=FONT_UI_BOLD,
                     width=14, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=BG_BLUE, fg=ORANGE, font=FONT_MONO_SM, anchor="w").pack(side=tk.LEFT, fill=tk.X)

        tk.Label(content, text="SYSTEM", bg=BG_BLUE, fg=ORANGE_DIM,
                 font=("DejaVu Sans Mono", 10, "bold")).pack(anchor="w", pady=(12, 3))
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
            ("Disk", f"{VENV.volume} (persistent, blessed)"),
            ("Boot Time", VENV.boot_time.strftime("%Y-%m-%d %H:%M:%S")),
        ]
        for label, value in info_data:
            row = tk.Frame(content, bg=BG_BLUE)
            row.pack(anchor="w", pady=3, fill=tk.X)
            tk.Label(row, text=f"{label}:", bg=BG_BLUE, fg=ORANGE_DIM, font=FONT_UI_BOLD, width=12, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=value, bg=BG_BLUE, fg=ORANGE, font=FONT_MONO_SM, anchor="w").pack(side=tk.LEFT, fill=tk.X)

        st = random.getstate()
        random.seed(613)
        load = [random.randint(1, 8) for _ in range(24)]
        random.setstate(st)
        tk.Label(content, text="CPU LOAD - 74-MHz, last 24 samples:", bg=BG_BLUE, fg=ORANGE_DIM,
                 font=("DejaVu Sans Mono", 10, "bold")).pack(anchor="w", pady=(14, 4))
        for i in range(0, 24, 4):
            row = "    " + "   ".join("[" + "#" * k + " " * (8 - k) + "]" for k in load[i:i+4])
            tk.Label(content, text=row, bg=BG_BLUE, fg=ORANGE_BRIGHT,
                     font=("DejaVu Sans Mono", 9)).pack(anchor="w")

        tk.Label(content, text="\nAll values are pretend. The real OS remains untouched.", bg=BG_BLUE,
                 fg=ORANGE_DIM, font=FONT_MONO_SM).pack(anchor="w", pady=(20, 0))

    # ---- status bar ----------------------------------------------------------
    def _start_status_clock(self):
        self._update_status_bar()

    def _update_status_bar(self):
        VENV.tick()
        now = datetime.datetime.now().strftime("%H:%M:%S")
        persist = "persistent" if DISK_IMAGE.exists() else "fresh"
        self.status_left.config(text=f"  {VENV.user}@{VENV.hostname}  |  {self.cwd}  |  CholentHD ({persist})       ")
        self.status_right.config(text=now + "   " + VENV.uptime_str() + "   ")
        self.after(1000, self._update_status_bar)


if __name__ == "__main__":
    app = YumeGUI()
    app.mainloop()
