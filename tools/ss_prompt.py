"""The step window: how far the run is and what you do now, beside the game while the runner takes pictures
(python ss_prompt.py <file> [<runner pid>]); the same idea as Video Studio's step window.

A small window beside the game window (on top of its corner if the screen has no room). It never takes the
focus and clicks go through it, so the game keeps the keyboard and mouse; the pictures are rendered by the game,
so the window is never in them.

fs25_run_game.py writes what to show into a JSON file (modSettings/FS25_ScreenshotStudio/autorun/prompt.json);
the window reads it a few times a second and closes a few seconds after the runner says so, or when the runner
is gone.

A step you do by hand: write what to do after " # " in the step. Best a waitgo step, which waits for you:
    "waitgo # Middle-click, then open the mode menu on the green bar"
    "ssUi 1"
    "waitgo # Pick Milk Transport, switch it ON and click AutoDrive's power button"
The runner sends the step without the comment. While it runs, the window says YOUR TURN with the text and says
it out loud; when you're done, say "next" (or "go", "done") or press Right Shift + 9, and the runner writes the
go file the game waits for (autorun_go_<step>.txt). "pause" / Right Shift + 8 only shows that you're away: a
waitgo waits anyway, at most its <max seconds> (600). A timed step with a comment ("wait 60 # ...") shows a
countdown instead and goes on by itself. Shortly before a step by hand the window says GET READY.
Voice: Windows' own offline speech (ss_speak.ps1 says the steps, ss_listen.ps1 hears a few words); the keys
always work, also without a microphone.
"""
import json, os, sys, threading, time

HAND_MARK = " # "
READY_S = 20          # GET READY this long before a step you do by hand
PAUSE_KEYS = (0xA1, 0x38)      # Right Shift + 8: pause / go on
NEXT_KEYS = (0xA1, 0x39)       # Right Shift + 9: done, next
KEY_HELP = 'When you\'re done, say "next" (or "go", "done") or press Right Shift + 9.'
WORDS = {"next": "next", "next step": "next", "go": "next", "ready": "next", "done": "next",
         "pause": "pause", "wait": "pause", "go on": "resume", "continue": "resume"}
HERE = os.path.dirname(os.path.abspath(__file__))
LISTENER = os.path.join(HERE, "ss_listen.ps1")
SPEAKER = os.path.join(HERE, "ss_speak.ps1")
DEAF_AFTER_S = 0.8             # the voice control ignores this long after the spoken words end (echo)
GO_FILE = "autorun_go_%d.txt"  # the game's waitgo step goes on when this appears (next to autorun.xml)


def split_hand(step):
    """'wait 60 # Do this' -> ('wait 60', 'Do this'); a step without a comment -> (step, None)."""
    cmd, mark, text = (step or "").partition(HAND_MARK)
    return (cmd.strip(), text.strip() or None) if mark else (step, None)


def _num(words, i, default):
    try:
        return float(words[i])
    except (IndexError, ValueError):
        return default


def step_seconds(step):
    """About how long a step takes, for the progress bar (a waitgo: about a minute of yours)."""
    w = split_hand(step)[0].split()
    if not w:
        return 1
    c = w[0]
    if c == "wait":
        return _num(w, 1, 1)
    if c == "waitgo":
        return min(_num(w, 1, 60), 60)
    if c == "ssUi":
        return _num(w, 1, 5) + 2
    if c == "ssBurst":
        return _num(w, 1, 20) * _num(w, 2, 3) + 2
    if c == "ssOrbit":
        return _num(w, 1, 8) * 2 + 10
    if c == "ssColors":
        return 60
    return {"ssShot": 4, "ssEnter": 4, "ssLight": 5, "ssMove": 6, "ssMenu": 3, "ssClick": 2, "ssKeys": 5,
            "quit": 1}.get(c, 1.5)


class Progress:
    """The whole run: which folder (mod) is being shot and about how far along, from the autorun steps."""
    def __init__(self, steps, clock=time.time):
        self.steps, self.clock = list(steps or []), clock
        self.weights = [step_seconds(s) for s in self.steps]
        self.total = sum(self.weights) or 1
        self.folder_at, folders, cur = [], [], None
        for s in self.steps:
            w = split_hand(s)[0].split()
            if w[:1] == ["ssFolder"]:
                cur = w[1] if len(w) > 1 else None
                if cur and cur not in folders:
                    folders.append(cur)
            self.folder_at.append(cur)
        self.folders = folders
        self.index, self.since = None, None

    def index_of(self, step):
        try:
            return int((step or "0/0").split("/", 1)[0]) - 1
        except ValueError:
            return -1

    def at(self, step):
        """The bar for the autorun's 'N/M ...' step line: {frac, label, left}."""
        now = self.clock()
        n = self.index_of(step)
        if n != self.index:
            self.index, self.since = n, now
        if n < 0 or not self.steps:
            return {"frac": 0.0, "label": "Starting", "left": round(self.total)}
        n = min(n, len(self.steps) - 1)
        done = sum(self.weights[:n]) + min(now - self.since, self.weights[n])
        frac = max(0.0, min(1.0, done / self.total))
        f = self.folder_at[n]
        label = (f"{f} ({self.folders.index(f) + 1} of {len(self.folders)})" if f and len(self.folders) > 1
                 else (f or "Pictures"))
        return {"frac": round(frac, 3), "label": label, "left": round(self.total - done)}

    def ends_at(self, n):
        """When step n (0-based) should be over, by the estimate."""
        if self.since is None or self.index is None or n < self.index:
            return None
        return self.since + sum(self.weights[self.index:n + 1])

    def starts_at(self, n):
        if self.since is None or self.index is None or n <= self.index:
            return None
        return self.since + sum(self.weights[self.index:n])


SAYS = {
    "ssEnter": "Getting in (or walking to) the machine",
    "ssTarget": "Picking what to photograph",
    "ssFolder": "Starting the next set of pictures",
    "ssLight": "Setting the light and the time of day",
    "ssMove": "Moving the machine",
    "ssShot": "Taking a picture",
    "ssOrbit": "Taking pictures all round it",
    "ssBurst": "Taking a burst of pictures",
    "ssColors": "Taking it in every color",
    "ssUi": "Taking a picture of the screen",
    "ssMenu": "Opening a menu",
    "ssClick": "Clicking in the menu",
    "ssTab": "Opening a tab",
    "ssKeys": "Pressing keys in the game",
    "ssView": "Setting the camera angle",
    "ssQuiet": "Hiding or showing other mods' drawing",
    "wait": "Waiting for things to settle",
    "quit": "Closing the game",
}


def step_says(step):
    """'11/36 ssOrbit 6' -> 'Taking pictures all round it'."""
    cmd = (step or "").partition(" ")[2].split()
    if not cmd:
        return ""
    if cmd[0] == "ssLight" and len(cmd) > 1 and cmd[1] == "off":
        return "Putting the time of day back"
    if cmd[0] == "ssMenu" and len(cmd) > 1 and cmd[1] == "close":
        return "Closing the menu"
    return SAYS.get(cmd[0], "")


def step_text(step):
    """'5/12 ssShot auto' -> 'Step 5 of 12: ssShot auto'."""
    if not step:
        return ""
    num, _, cmd = step.partition(" ")
    a, _, b = num.partition("/")
    return f"Step {a} of {b}" + (f": {' '.join(cmd.split()[:3])}" if cmd.strip() else "")


def key_down(vk):
    try:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)
    except (OSError, AttributeError):
        return False


def powershell(script, stdin=False):
    import subprocess
    return subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                            stdin=subprocess.PIPE if stdin else None, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


class Keys:
    """Right Shift + 8 / 9 read straight from the keyboard, so they work in every game menu too."""
    def __init__(self, read=key_down, poll=0.03):
        self.read, self.poll = read, poll
        self.events, self.down = [], {}
        self.lock = threading.Lock()
        self.stopped = threading.Event()

    def check(self):
        for name, (a, b) in (("pause", PAUSE_KEYS), ("next", NEXT_KEYS)):
            d = self.read(a) and self.read(b)
            if d and not self.down.get(name):
                self.push(name)
            self.down[name] = d

    def start(self):
        def loop():
            while not self.stopped.wait(self.poll):
                self.check()
        threading.Thread(target=loop, daemon=True).start()
        return self

    def take(self):
        with self.lock:
            ev, self.events = self.events, []
        return ev

    def push(self, event):
        with self.lock:
            self.events.append(event)

    def stop(self):
        self.stopped.set()


class Voice:
    """Says each step out loud (ss_speak.ps1) and listens for your answer (ss_listen.ps1): Windows' own offline
    speech, a few words only. It doesn't listen while it speaks, so its own words don't count as yours."""
    def __init__(self, keys, echo=print, clock=time.time):
        self.keys, self.echo, self.clock = keys, echo, clock
        self.listener = self.speaker = None
        self.deaf_until = 0.0
        self.speaking = False
        self.heard = None

    def feed(self, line):
        """A line from the listener: 'next|0.91'. The event it makes, or None."""
        word, _, _ = line.strip().partition("|")
        ev = WORDS.get(word.strip().lower())
        if ev is None or self.speaking or self.clock() < self.deaf_until:
            return None
        self.keys.push(ev)
        self.heard = (word.strip(), self.clock())
        return ev

    def said(self):
        self.speaking = False
        self.deaf_until = self.clock() + DEAF_AFTER_S

    def say(self, text):
        if self.speaker is None or self.speaker.poll() is not None:
            return
        self.speaking = True
        try:
            self.speaker.stdin.write(text.replace("\n", " ") + "\n")
            self.speaker.stdin.flush()
        except OSError:
            self.speaking = False

    def start(self):
        try:
            self.speaker = powershell(SPEAKER, stdin=True)
            self.listener = powershell(LISTENER)
        except OSError as e:
            self.echo(f"! No voice ({e}): the keys still work")
            return self

        def read_speaker():
            for line in self.speaker.stdout:
                if line.strip() == "said":
                    self.said()

        def read_listener():
            for line in self.listener.stdout:
                if line.strip() == "listening":
                    self.echo('Voice on: it says each step by hand and waits for "next" (or Right Shift + 9)')
                else:
                    self.feed(line)
        threading.Thread(target=read_speaker, daemon=True).start()
        threading.Thread(target=read_listener, daemon=True).start()
        return self

    def stop(self):
        for p in (self.listener, self.speaker):
            if p is not None and p.poll() is None:
                p.kill()


def is_waitgo(step):
    return split_hand(step)[0].split()[:1] == ["waitgo"]


class Director:
    """Keeps the step window up to date: tick(watch) while the game runs (watch: the runner's LogWatch). Steps by
    hand (a " # " comment) are said out loud; a waitgo one ends when you say "next" or press Right Shift + 9: then
    it writes the go file into go_dir, where the game waits for it."""
    def __init__(self, steps, path, go_dir=None, window=True, clock=time.time, keys=None, voice=True, echo=print):
        self.steps = list(steps or [])
        self.hand = {i: t for i, t in ((i, split_hand(s)[1]) for i, s in enumerate(self.steps)) if t}
        self.progress = Progress(self.steps, clock)
        self.path, self.go_dir, self.window, self.clock = path, go_dir, window, clock
        self.keys, self.voice, self.echo = keys, voice, echo
        self.proc, self.last, self.bar = None, None, None
        self.spoken, self.gone, self.paused, self.ready_said = set(), set(), False, set()

    def speak(self, text):
        if hasattr(self.voice, "say"):
            self.voice.say(text)

    def start(self):
        self.say("wait", "Getting ready", "Nothing to do: the game starts by itself.")
        if self.hand and self.keys is None:
            self.keys = Keys().start()
        # the voice (and with it the microphone) only once the save is running: twice the game hung at 55 %
        # "loading map" with the listener already holding the microphone (22 Nov 2026)
        if self.window and self.proc is None:
            import subprocess
            exe = sys.executable
            w = os.path.join(os.path.dirname(exe), "pythonw.exe")
            try:
                self.proc = subprocess.Popen([w if os.path.isfile(w) else exe, os.path.abspath(__file__), self.path,
                                              str(os.getpid())])
            except OSError as e:
                print(f"! The step window didn't open: {e}")
        return self

    def write(self, data):
        data = dict(data, pid=os.getpid(), bar=self.bar)
        if data == self.last:
            return
        self.last = data
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, self.path)

    def say(self, state, title, detail="", until=None, coming=None):
        """state: wait (hands off), ready (your turn soon), you (your turn), done."""
        self.write({"state": state, "title": title, "detail": detail, "until": until, "next": coming})

    def tick(self, watch):
        if not watch.started:
            self.bar = None
            if watch.entered or watch.loaded:
                self.say("wait", "Loading the save", "Hands off: the runner presses START by itself.")
            else:
                self.say("wait", "Starting the game", "Hands off: Steam starts it with the save.")
            return False
        if self.voice is True and self.hand:
            self.voice = Voice(self.keys, echo=self.echo).start()      # the save is running now
        self.bar = self.progress.at(watch.step)
        n = self.progress.index
        events = self.keys.take() if self.keys is not None else []
        upcoming = sorted(i for i in self.hand if i > (n if n is not None else -1))
        after = self.hand[upcoming[0]] if upcoming else None
        if n is not None and n in self.hand and n not in self.gone:
            waits = is_waitgo(self.steps[n])
            if n not in self.spoken:
                self.spoken.add(n)
                self.paused = False
                self.speak(f"Your turn. {self.hand[n]}.")
            for ev in events:
                if ev == "pause" or (ev == "resume" and self.paused):
                    self.paused = not self.paused
                    self.speak("Paused. Say go on when you're back." if self.paused else f"{self.hand[n]}.")
                elif ev == "next" and waits and not self.paused:
                    self.go(n + 1)
                    self.gone.add(n)
                    self.speak("Thanks. Hands off now.")
                    self.say("wait", "Thanks: hands off now", "The run goes on by itself.")
                    return False
            if self.paused:
                self.say("pause", "Paused", 'Say "go on" or press Right Shift + 8 when you\'re back. The game waits.',
                         coming=self.hand[n])
            elif waits:
                self.say("you", self.hand[n], KEY_HELP + "\nThe game waits for you.", coming=after)
            else:
                self.say("you", self.hand[n], "The run goes on by itself when the time is up.",
                         until=self.progress.ends_at(n), coming=after)
            return False
        if upcoming:
            start = self.progress.starts_at(upcoming[0])
            if start is not None and start - self.clock() <= READY_S:
                if upcoming[0] not in self.ready_said:
                    self.ready_said.add(upcoming[0])
                    self.speak("Get ready.")
                self.say("ready", "Get ready: your turn", f"Next: {self.hand[upcoming[0]]}", until=start)
                return False
        self.say("wait", step_says(watch.step) or "Taking pictures: hands off",
                 f"Hands off the keyboard and mouse, please.\n{step_text(watch.step)}")
        return False

    def go(self, number):
        """The go file for step <number> (1-based, as the game counts): its waitgo goes on."""
        if not self.go_dir:
            return None
        path = os.path.join(self.go_dir, GO_FILE % number)
        with open(path, "w", encoding="utf-8") as f:
            f.write("go\n")
        return path

    def close(self, title="Done", detail="The computer is yours."):
        if self.keys is not None:
            self.keys.stop()
        if hasattr(self.voice, "stop"):
            self.voice.stop()
        if self.bar is not None:
            self.bar = dict(self.bar, frac=1.0, left=0)
        self.say("done", title, detail)
        self.write({"state": "exit", "after": 8, "title": title, "detail": detail})


# ---------------------------------------------------------------- the window
COLORS = {"wait": ("#2b2f36", "#9aa3ad", "HANDS OFF"), "ready": ("#4a3a10", "#ffcc33", "GET READY"),
          "you": ("#0f3d1f", "#3ddc84", "YOUR TURN"), "done": ("#1d2a3a", "#6fb7ff", "DONE"),
          "pause": ("#3a1f3d", "#d68cff", "PAUSED"), "exit": ("#1d2a3a", "#6fb7ff", "DONE")}
GAME_EXE = "farmingsimulator2025game.exe"


def pid_alive(pid):
    try:
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return code.value == 259                        # STILL_ACTIVE
    except (OSError, AttributeError, ValueError):
        return True


def game_rect():
    """The game window's client area on screen (x, y, w, h), or None."""
    try:
        import ctypes
        from ctypes import wintypes
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def each(hwnd, _):
            if not u.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            h = k.OpenProcess(0x1000, False, pid.value)
            if h:
                buf, size = ctypes.create_unicode_buffer(520), wintypes.DWORD(520)
                if k.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)) and buf.value.lower().endswith(GAME_EXE):
                    found.append(hwnd)
                k.CloseHandle(h)
            return True

        u.EnumWindows(each, 0)
        if not found:
            return None
        r, o = wintypes.RECT(), wintypes.POINT()
        u.GetClientRect(found[0], ctypes.byref(r))
        u.ClientToScreen(found[0], ctypes.byref(o))
        return o.x, o.y, r.right, r.bottom
    except Exception:
        return None


def place(win_w, win_h, game, screen_w, screen_h, gap=16):
    """Where the window goes: right of the game, else left, else below, else on top of the game's corner."""
    if game is None:
        return screen_w - win_w - gap, gap
    x, y, w, h = game
    top = max(0, min(y, screen_h - win_h))
    if x + w + gap + win_w <= screen_w:
        return x + w + gap, top
    if x - gap - win_w >= 0:
        return x - gap - win_w, top
    if y + h + gap + win_h <= screen_h:
        return x, y + h + gap
    return x + w - win_w - gap, y + gap


def window(path, parent=None):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (OSError, AttributeError):
        pass
    import tkinter as tk
    W, H = 600, 360
    root = tk.Tk()
    root.title("Screenshot Studio: what to do")
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.attributes("-alpha", 0.94)
    frame = tk.Frame(root, bd=0, highlightthickness=4)
    frame.pack(fill="both", expand=True)
    tag = tk.Label(frame, font=("Segoe UI", 14, "bold"), anchor="w")
    title = tk.Label(frame, font=("Segoe UI", 22, "bold"), anchor="w", justify="left", wraplength=W - 40)
    detail = tk.Label(frame, font=("Segoe UI", 14), anchor="w", justify="left", wraplength=W - 40)
    clock = tk.Label(frame, font=("Segoe UI", 20, "bold"), anchor="w")
    coming = tk.Label(frame, font=("Segoe UI", 12), anchor="w", justify="left", wraplength=W - 40)
    for w_ in (tag, title, detail, clock, coming):
        w_.pack(fill="x", padx=18, pady=(8, 0))
    barbox = tk.Frame(frame, bd=0)
    barbox.pack(side="bottom", fill="x", padx=18, pady=(0, 14))
    barlabel = tk.Label(barbox, font=("Segoe UI", 12), anchor="w")
    barlabel.pack(fill="x")
    canvas = tk.Canvas(barbox, height=14, highlightthickness=0, bd=0)
    canvas.pack(fill="x", pady=(4, 0))
    try:      # never take the focus, clicks go through to the game, not in the taskbar
        import ctypes
        u = ctypes.windll.user32
        root.update_idletasks()
        hwnd = u.GetParent(root.winfo_id()) or root.winfo_id()
        ex = u.GetWindowLongW(hwnd, -20)
        u.SetWindowLongW(hwnd, -20, ex | 0x08000000 | 0x00000080 | 0x00000020 | 0x00080000)
    except (OSError, AttributeError):
        pass
    state = {"data": None, "mtime": None, "exit_at": None, "placed_at": 0}

    def refresh():
        now = time.time()
        try:
            m = os.path.getmtime(path)
            if m != state["mtime"]:
                with open(path, encoding="utf-8") as f:
                    state["data"], state["mtime"] = json.load(f), m
        except (OSError, ValueError):
            pass
        d = state["data"] or {"state": "wait", "title": "Getting ready"}
        if d.get("state") == "exit" and state["exit_at"] is None:
            state["exit_at"] = now + float(d.get("after", 8))
        if (state["exit_at"] and now >= state["exit_at"]) or (parent and not pid_alive(parent)):
            root.destroy()
            return
        if now - state["placed_at"] > 2:
            state["placed_at"] = now
            x, y = place(W, H, game_rect(), root.winfo_screenwidth(), root.winfo_screenheight())
            root.geometry(f"{W}x{H}+{x}+{y}")
        bg, fg, word = COLORS.get(d.get("state"), COLORS["wait"])
        for w_ in (frame, tag, title, detail, clock, coming, barbox, barlabel):
            w_.configure(bg=bg)
        bar = d.get("bar")
        canvas.delete("all")
        if bar:
            cw = max(canvas.winfo_width(), 10)
            canvas.configure(bg="#14171c")
            canvas.create_rectangle(0, 0, int(cw * bar.get("frac", 0)), 14, fill=fg, width=0)
            left = bar.get("left") or 0
            eta = "" if left <= 0 else (f", about {round(left / 60)} min left" if left >= 90 else ", under 2 min left")
            barlabel.configure(text=f"{bar.get('label') or 'Pictures'}: {round(100 * bar.get('frac', 0))} %{eta}", fg="#cfcfcf")
        else:
            canvas.configure(bg=bg)
            barlabel.configure(text="")
        frame.configure(highlightbackground=fg)
        tag.configure(text=word, fg=fg)
        title.configure(text=d.get("title", ""), fg="white")
        detail.configure(text=d.get("detail", ""), fg="#dddddd")
        until = d.get("until")
        clock.configure(text=f"{max(0, int(until - now + 0.99))} s" if until else "", fg=fg)
        coming.configure(text=f"Then: {d['next']}" if d.get("next") else "", fg="#bbbbbb")
        root.after(200, refresh)

    refresh()
    root.mainloop()


if __name__ == "__main__":
    window(sys.argv[1] if len(sys.argv) > 1 else "prompt.json", sys.argv[2] if len(sys.argv) > 2 else None)
