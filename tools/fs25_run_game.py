"""Starts Farming Simulator 25 with a savegame, lets Screenshot Studio take its pictures, ends the game.

    python fs25_run_game.py saves                                 your savegames, and which have the mod
    python fs25_run_game.py run <save> [--plan smoke|orbit|colors|lights|burst] [--steps "ssOrbit" ...]
                                       [--target "PX150"] [--keep-open] [--sheet] [--anyway] [--dry-run]
    python fs25_run_game.py plans                                 what each plan does

What run does:
  1. checks: the game isn't running; the Screenshot Studio zip in your mods folder is this repo's
     version (it never copies it there: you install it yourself); the save has the mod switched on
  2. backs up the savegame folder (modSettings/FS25_ScreenshotStudio/autorun/backup_*.zip)
  3. writes modSettings/FS25_ScreenshotStudio/autorun.xml with the steps; the mod runs it only in
     that save, only within 20 minutes, and deletes it once read
  4. starts the game through Steam: -autoStartSavegameId <save> -skipStartVideos
  5. follows log.txt and prints what Screenshot Studio does (and its errors)
  6. when the steps are done: ends the game without saving (the mod quits it, or the script ends the
     process), and if the game wrote to the savegame meanwhile (autosave), puts the backup back and
     keeps the changed folder in modSettings/FS25_ScreenshotStudio/autorun/
  7. lists the new pictures; --sheet makes a contact sheet per folder

Set the save up once: park the machine somewhere nice, stand next to it (or sit in it), save. The
plans start with ssEnter, which gets into the nearest vehicle and switches to an outside camera.
After loading, the game waits on a START screen: the script presses Enter in the game window for you
(--no-press: you do); the steps start 10 s after the save is running.
"""
import argparse, datetime, glob, os, re, shutil, subprocess, sys, time, zipfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fs25_screenshots as shots  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOD_NAME = "FS25_ScreenshotStudio"
APP_ID = "2300320"
PROCESS = "FarmingSimulator2025Game.exe"
DOCS = shots.DOCS
STUDIO = shots.STUDIO
WORK = os.path.join(STUDIO, "autorun")       # backups, kept savegames, log copies

PLANS = {
    "smoke": ["ssEnter", "ssLight golden", "ssShot auto", "ssOrbit", "ssLight morning", "ssShot auto",
              "ssLight overcast", "ssShot auto", "ssBurst 3 1", "ssColors", "ssLight off", "quit"],
    "orbit": ["ssEnter", "ssLight golden", "ssOrbit", "ssLight off", "quit"],
    "colors": ["ssEnter", "ssLight midday", "ssColors", "ssLight off", "quit"],
    "lights": ["ssEnter", "ssLight golden", "ssShot auto", "ssLight morning", "ssShot auto", "ssLight midday", "ssShot auto",
               "ssLight overcast", "ssShot auto", "ssLight off", "quit"],
    "burst": ["ssEnter", "ssBurst 10 2", "quit"],
}
PLAN_TEXT = {
    "smoke": "everything once: lights, clean shot, orbit, burst, every color (tests the mod in the real game)",
    "orbit": "golden hour orbit",
    "colors": "every color at midday",
    "lights": "a clean shot in each light",
    "burst": "10 shots, one every 2 s (drive it yourself, or watch it stand)",
}


# ---------------------------------------------------------------- savegames and the mod
def savegames(docs=DOCS):
    """[{index, name, map, date, hasMod, path}] of savegame1..N with a careerSavegame.xml."""
    out = []
    for path in glob.glob(os.path.join(docs, "savegame*")):
        m = re.fullmatch(r"savegame(\d+)", os.path.basename(path))
        xml = os.path.join(path, "careerSavegame.xml")
        if not m or not os.path.isfile(xml):
            continue
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        def text(key):
            el = root.find(key)
            return el.text if el is not None and el.text else ""
        mods = {el.get("modName") for el in root.iter("mod")}
        out.append({"index": int(m.group(1)), "name": text("settings/savegameName"), "map": text("settings/mapTitle"),
                    "date": text("settings/saveDateFormatted"), "hasMod": MOD_NAME in mods, "path": path})
    return sorted(out, key=lambda s: s["index"])


def mod_version(modDesc_text):
    m = re.search(r"<version>\s*([^<\s]+)\s*</version>", modDesc_text)
    return m.group(1) if m else None


def installed_version(docs=DOCS):
    """Version of the zip in the mods folder (read only), or None."""
    z = os.path.join(docs, "mods", MOD_NAME + ".zip")
    if not os.path.isfile(z):
        return None
    with zipfile.ZipFile(z) as zf:
        return mod_version(zf.read("modDesc.xml").decode("utf-8", "replace"))


def repo_version():
    with open(os.path.join(REPO, "modDesc.xml"), encoding="utf-8") as f:
        return mod_version(f.read())


# ---------------------------------------------------------------- autorun file
def write_autorun(steps, save, studio=STUDIO, now=None):
    os.makedirs(studio, exist_ok=True)
    root = ET.Element("autorun", savegame=str(save), created=(now or datetime.datetime.now()).strftime("%Y%m%d_%H%M%S"))
    for s in steps:
        ET.SubElement(root, "step").text = s
    ET.indent(root)
    path = os.path.join(studio, "autorun.xml")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def remove_autorun(studio=STUDIO):
    path = os.path.join(studio, "autorun.xml")
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


# ---------------------------------------------------------------- savegame backup
def snapshot(folder):
    out = {}
    for top, _, files in os.walk(folder):
        for f in files:
            p = os.path.join(top, f)
            st = os.stat(p)
            out[os.path.relpath(p, folder)] = (st.st_size, st.st_mtime_ns)
    return out


def backup(folder, work=WORK, stamp=None):
    os.makedirs(work, exist_ok=True)
    stamp = stamp or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(work, f"backup_{os.path.basename(folder)}_{stamp}.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for top, _, files in os.walk(folder):
            for f in files:
                p = os.path.join(top, f)
                zf.write(p, os.path.relpath(p, folder))
    return path, snapshot(folder)


def restore_if_changed(folder, backup_zip, before, work=WORK, stamp=None):
    """If the game wrote to the savegame: keep the changed folder in work/, put the backup back.
    Returns the path of the kept folder, or None when nothing changed."""
    if snapshot(folder) == before:
        return None
    stamp = stamp or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    kept = os.path.join(work, f"{os.path.basename(folder)}_changed_{stamp}")
    shutil.move(folder, kept)
    with zipfile.ZipFile(backup_zip) as zf:
        zf.extractall(folder)
    return kept


# ---------------------------------------------------------------- the log
class LogWatch:
    """Fed with new log text; keeps what matters for the run."""
    def __init__(self):
        self.started = self.done = self.refused = self.quitting = False
        self.loaded = self.entered = False   # the mod is loading / START was pressed ("Entered Gameplay")
        self.autostart = False               # the game took -autoStartSavegameId (a mod-update dialog may follow)
        self.last_line_at = None             # when the last line came (the START screen writes nothing)
        self.step = None         # the last step the mod started: "3/12 ssShot"
        self.errors = 0
        self.lines = []          # Screenshot Studio lines and errors near them, to print
        self._buf = ""
        self._near = 0

    def feed(self, text, now=None):
        self._buf += text
        *lines, self._buf = self._buf.split("\n")
        if lines:
            self.last_line_at = now if now is not None else time.time()
        out = []
        for raw in lines:
            line = raw.rstrip("\r")
            if "[ScreenshotStudio] Loaded." in line:
                self.loaded = True
            elif "Auto start local savegame" in line:
                self.autostart = True
            elif "Entered Gameplay" in line:
                self.entered = True
            ours = "ScreenshotStudio" in line
            error = re.search(r"\b(Error|LUA call stack)\b", line) is not None
            if error:
                self.errors += 1
            if ours or (error and self._near > 0) or (self._near > 0 and line.startswith(("  ", "\t"))):
                out.append(line)
            self._near = 6 if ours or (error and self._near > 0) else max(0, self._near - 1)
            step = re.search(r"autorun: step (\d+/\d+ .*?) -> ", line)
            if step:
                self.step = step.group(1)
            if "autorun: started" in line:
                self.started = True
            elif "autorun: done" in line:
                self.done = True
            elif "autorun: quitting" in line:
                self.quitting = True
            elif "autorun:" in line and "not run" in line:
                self.refused = True
        self.lines += out
        return out


# ---------------------------------------------------------------- the START screens
# Two screens wait for Enter and log nothing meanwhile: "There are updates available for some
# selected mods ... START" right after the game logs "Auto start local savegame" (Enter = start
# without updating), and START after loading. Once the auto start is under way and the log has been
# quiet a while, the script brings the game window to the front and presses Enter, again every few
# seconds until the game logs "Entered Gameplay". Enter on a plain loading screen does nothing.
class StartPresser:
    QUIET = 12       # seconds without a log line
    EVERY = 10       # seconds between presses
    MAX = 8

    def __init__(self, enabled=True, press=None, echo=print):
        self.enabled, self.presses, self.last = enabled, 0, None
        self.press = press or press_start
        self.echo = echo

    def due(self, watch, now):
        return (self.enabled and (watch.autostart or watch.loaded) and not watch.entered and not watch.started
                and watch.last_line_at is not None and now - watch.last_line_at >= self.QUIET
                and (self.last is None or now - self.last >= self.EVERY) and self.presses < self.MAX)

    def tick(self, watch, now=None):
        now = now if now is not None else time.time()
        if self.due(watch, now):
            self.last, self.presses = now, self.presses + 1
            ok = self.press()
            self.echo("Pressing START (Enter) in the game window" if ok
                      else "! Couldn't bring the game window to the front: press START yourself")
        return False


def game_pids():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {PROCESS}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    pids = set()
    for row in out.splitlines():
        cells = [c.strip().strip('"') for c in row.split(",")]
        if len(cells) > 1 and cells[0].lower() == PROCESS.lower() and cells[1].isdigit():
            pids.add(int(cells[1]))
    return pids


def press_start():
    """Game window to the front, then Enter (with its scan code: games read the hardware key)."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
    except (ImportError, AttributeError, OSError):
        return False
    pids, windows = game_pids(), []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            windows.append(hwnd)
        return True

    user32.EnumWindows(each, 0)
    for hwnd in windows:
        user32.ShowWindow(hwnd, 9)                 # restore if minimised
        user32.keybd_event(0x12, 0, 0, 0)          # a tap of Alt lets this process change the foreground
        user32.keybd_event(0x12, 0, 2, 0)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
        if user32.GetForegroundWindow() == hwnd:
            user32.keybd_event(0x0D, 0x1C, 0, 0)   # Enter down / up
            time.sleep(0.08)
            user32.keybd_event(0x0D, 0x1C, 2, 0)
            return True
    return False


def follow_log(path, since, watch, should_stop, poll=0.5, echo=print):
    """Reads log.txt as the game writes it (the game starts a new one at launch)."""
    pos = 0
    while not should_stop():
        if os.path.isfile(path) and os.path.getmtime(path) >= since:
            with open(path, encoding="utf-8", errors="replace") as f:
                f.seek(0, os.SEEK_END)
                if f.tell() < pos:
                    pos = 0          # a new log
                f.seek(pos)
                text = f.read()
                pos = f.tell()
            for line in watch.feed(text):
                echo("  game| " + line)
        time.sleep(poll)


# ---------------------------------------------------------------- the game
def listed(tasklist_csv, name=PROCESS):
    """tasklist's table cuts image names at 25 characters (FarmingSimulator2025Game.ex); CSV keeps them."""
    return f'"{name.lower()}"' in tasklist_csv.lower()


def game_running():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {PROCESS}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return listed(out)


def steam_exe():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            exe = winreg.QueryValueEx(k, "SteamExe")[0]
            if os.path.isfile(exe):
                return exe
    except OSError:
        pass
    exe = r"C:\Program Files (x86)\Steam\steam.exe"
    return exe if os.path.isfile(exe) else None


def end_game():
    subprocess.run(["taskkill", "/IM", PROCESS, "/F"], capture_output=True)


CRASH_DUMPS = os.path.join(os.environ.get("LOCALAPPDATA", ""), "CrashDumps")


def crash_dumps(since, folder=CRASH_DUMPS):
    """Windows' crash dumps of the game written since `since` (it can take a minute to appear)."""
    return sorted(f for f in glob.glob(os.path.join(folder, PROCESS + ".*.dmp")) if os.path.getmtime(f) >= since)


def crash_logged(since):
    """Exception code of the game's "Application Error" in Windows' event log since `since`, or None.
    Windows writes that entry the moment the game crashes; the dump comes later."""
    ms = int((time.time() - since) * 1000) + 5000
    q = f"*[System[Provider[@Name='Application Error'] and TimeCreated[timediff(@SystemTime) <= {ms}]]]"
    try:
        out = subprocess.run(["wevtutil", "qe", "Application", f"/q:{q}", "/f:text", "/rd:true", "/c:20"],
                             capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for block in out.split("Event[")[1:]:
        if PROCESS.lower() in block.lower():
            m = re.search(r"Exception code:\s*(0x[0-9a-fA-F]+)", block)
            return m.group(1) if m else "?"
    return None


def ended_early(watch, crash, dumps):
    """What to say when the game is gone before the steps were done. crash: exception code or None."""
    where = f"during step {watch.step}" if watch.step else "before the first step"
    if crash is None and not dumps:
        return [f"! The game ended {where} (closed by hand? Windows logged no crash)"]
    out = [f"! The game CRASHED {where} (exception {crash or '?'})"]
    out.append(f"  dump: {dumps[-1]}" if dumps else f"  Windows writes a dump to {CRASH_DUMPS} within a minute")
    if watch.step and re.search(r" ss(Shot|Orbit|Burst|Colors)\b", watch.step):
        out.append("  If it was the first shot with render, the mod uses the screen method from the next start: run it again.")
    return out


def new_pictures(since, studio=STUDIO):
    out = {}
    for f in glob.glob(os.path.join(studio, "*", "*")):
        folder = os.path.basename(os.path.dirname(f))
        if folder in ("autorun", "probe") or os.path.basename(f).startswith("_"):
            continue
        if f.lower().endswith(shots.PICS) and os.path.getmtime(f) >= since:
            out.setdefault(folder, []).append(f)
    return out


def wait_for(cond, seconds, poll=1.0):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(poll)
    return cond()


def run(save, steps, keep_open=False, sheet=False, anyway=False, dry_run=False,
        start_timeout=900, timeout=2400, press=True):
    saves = {s["index"]: s for s in savegames()}
    if save not in saves:
        sys.exit(f"No savegame{save} in {DOCS} (see: saves)")
    sg = saves[save]
    problems = []
    if game_running():
        problems.append("the game is running: close it first")
    have, want = installed_version(), repo_version()
    if have is None:
        problems.append(f"{MOD_NAME}.zip isn't in your mods folder: install it first (this script never copies it there)")
    elif have != want:
        problems.append(f"your mods folder has {MOD_NAME} {have}, the repo is {want}: install the new zip first")
    if not sg["hasMod"]:
        problems.append(f"savegame{save} ({sg['name']}) doesn't have {MOD_NAME} switched on: add it in the mod list of that save")
    for p in problems:
        print("! " + p)
    if problems and not anyway:
        sys.exit("Stopped (--anyway to try regardless).")
    if not keep_open and steps[-1:] != ["quit"]:
        steps = steps + ["quit"]
    print(f"savegame{save}: {sg['name']} ({sg['map']}), {len(steps)} steps:")
    for i, s in enumerate(steps, 1):
        print(f"  {i:2d}. {s}")
    if dry_run:
        print("Dry run: nothing written, game not started.")
        return 0
    steam = steam_exe()
    if steam is None:
        sys.exit("Steam not found")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path, before = backup(sg["path"], stamp=stamp)
    print(f"Backup: {zip_path}")
    started_at = time.time()
    write_autorun(steps, save)
    log_path = os.path.join(DOCS, "log.txt")
    watch = LogWatch()
    result = 1
    try:
        subprocess.Popen([steam, "-applaunch", APP_ID, "-autoStartSavegameId", str(save), "-skipStartVideos"])
        print("Starting the game through Steam ...")
        if not wait_for(game_running, 180):
            print("! The game didn't start within 3 minutes")
            return 1
        import threading
        stop = threading.Event()
        t = threading.Thread(target=follow_log, args=(log_path, started_at - 5, watch, stop.is_set), daemon=True)
        t.start()
        presser = StartPresser(enabled=press)
        if not wait_for(lambda: presser.tick(watch) or watch.started or watch.refused or not game_running(), start_timeout):
            print(f"! No autorun after {start_timeout // 60} min. Waiting at a start screen? Is the mod active in that save?")
        elif watch.refused:
            print("! The mod didn't run the steps (see above)")
        elif not game_running():
            print("\n".join(ended_early(watch, crash_logged(started_at), crash_dumps(started_at))))
        else:
            finished = wait_for(lambda: watch.done or not game_running(), timeout)
            if watch.done:
                result = 0
                if keep_open:
                    print("Steps done; the game stays open (--keep-open). Save or not, as you like.")
                elif not wait_for(lambda: not game_running(), 20):
                    print("Ending the game (without saving)")
            elif finished:
                time.sleep(2)     # Windows writes the dump as the process goes
                print("\n".join(ended_early(watch, crash_logged(started_at), crash_dumps(started_at))))
            else:
                print(f"! Steps not done after {timeout // 60} min")
        stop.set()
        t.join(timeout=3)
    except KeyboardInterrupt:
        print("Stopped")
    finally:
        remove_autorun()
        if not keep_open:
            if game_running():
                end_game()
                wait_for(lambda: not game_running(), 30)
            time.sleep(2)   # file handles
            kept = restore_if_changed(sg["path"], zip_path, before, stamp=stamp)
            if kept:
                print(f"The game wrote to savegame{save} (autosave?): backup put back, the changed one is in {kept}")
            else:
                print(f"savegame{save} unchanged")
        if os.path.isfile(log_path):
            os.makedirs(WORK, exist_ok=True)
            shutil.copy2(log_path, os.path.join(WORK, f"log_{stamp}.txt"))

    print(f"\nlog: {watch.errors} error line(s) in the whole log (other mods too); copy in {WORK}")
    pics = new_pictures(started_at)
    for folder, files in sorted(pics.items()):
        print(f"\n{folder}: {len(files)} new picture(s)")
        shots.studio(os.path.join(STUDIO, folder))
        if sheet:
            shots.sheet(os.path.join(STUDIO, folder))
    if not pics:
        print("No new pictures")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("saves")
    sub.add_parser("plans")
    r = sub.add_parser("run")
    r.add_argument("save", type=int)
    r.add_argument("--plan", choices=sorted(PLANS), default="smoke")
    r.add_argument("--steps", nargs="+", help='your own steps instead of a plan, e.g. --steps "ssEnter" "ssOrbit 12"')
    r.add_argument("--target", help='what to photograph, by part of its name (ssTarget): e.g. --target "PX150"')
    r.add_argument("--move", action="store_true",
                   help="move it (with what is hitched) to your ssSpot or an open, flat place first, and back at the end")
    r.add_argument("--keep-open", action="store_true", help="leave the game running afterwards (no backup restore)")
    r.add_argument("--sheet", action="store_true", help="contact sheet of the new pictures")
    r.add_argument("--anyway", action="store_true", help="start even if a check fails")
    r.add_argument("--dry-run", action="store_true", help="only the checks and the steps")
    r.add_argument("--no-press", action="store_true", help="don't press START on the loading screen (you do)")
    args = p.parse_args(argv)
    if args.cmd == "saves":
        rows = savegames()
        if not rows:
            print(f"No savegames in {DOCS}")
        for s in rows:
            print(f"{s['index']:3d}  {'mod on ' if s['hasMod'] else '       '}  {s['name'][:30]:30s}  {s['map'][:24]:24s}  {s['date']}")
        print(f"\ninstalled {MOD_NAME}: {installed_version() or 'none'}, repo: {repo_version()}")
        return 0
    if args.cmd == "plans":
        for k in sorted(PLANS):
            print(f"{k:7s} {PLAN_TEXT[k]}\n        " + " / ".join(PLANS[k]))
        return 0
    steps = with_move(with_target(list(args.steps) if args.steps else list(PLANS[args.plan]), args.target), args.move)
    return run(args.save, steps, keep_open=args.keep_open, sheet=args.sheet, anyway=args.anyway, dry_run=args.dry_run,
               press=not args.no_press)


def with_move(steps, move):
    """ssMove after getting in (to your ssSpot or an open, flat place), ssMove back before quitting."""
    if not move:
        return steps
    out = [s for s in steps if not s.startswith("ssMove")]
    at = next((i + 1 for i, s in enumerate(out) if s.startswith("ssEnter")), 0)
    out.insert(at, "ssMove")
    end = out.index("quit") if "quit" in out else len(out)
    out.insert(end, "ssMove back")
    return out


def with_target(steps, target):
    """ssTarget first: ssEnter then gets into it (or the tractor it hangs on), and the orbit, the
    clean shots and every color are of it wherever it stands."""
    if not target:
        return steps
    return [f"ssTarget {target.strip()}"] + [s for s in steps if not s.startswith("ssTarget")]


if __name__ == "__main__":
    sys.exit(main())
