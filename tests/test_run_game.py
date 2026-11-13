"""Offline test of tools/fs25_run_game.py: everything but starting the game.

    python tests/test_run_game.py

Savegames and the installed version from a made-up Documents folder, the autorun.xml the mod
reads, the savegame backup put back after an autosave (and left alone when nothing changed),
and reading the log while the game writes it.
"""
import importlib.util, os, shutil, sys, tempfile, threading, time
import xml.etree.ElementTree as ET
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
spec = importlib.util.spec_from_file_location("fs25_run_game", os.path.join(ROOT, "tools", "fs25_run_game.py"))
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)

failures = []
def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond:
        failures.append(msg)

tmp = tempfile.mkdtemp(prefix="ss_run_")
docs = os.path.join(tmp, "FarmingSimulator2025")
studio = os.path.join(docs, "modSettings", "FS25_ScreenshotStudio")
work = os.path.join(studio, "autorun")

def career(index, name, map_title, mods):
    d = os.path.join(docs, f"savegame{index}")
    os.makedirs(d)
    mods_xml = "".join(f'<mod modName="{m}" title="x" version="1.0.0.0"/>' for m in mods)
    with open(os.path.join(d, "careerSavegame.xml"), "w", encoding="utf-8-sig") as f:
        f.write(f'<?xml version="1.0" encoding="utf-8" standalone="no"?><careerSavegame><settings>'
                f'<savegameName>{name}</savegameName><mapTitle>{map_title}</mapTitle>'
                f'<saveDateFormatted>2026-11-09</saveDateFormatted></settings>{mods_xml}</careerSavegame>')
    with open(os.path.join(d, "vehicles.xml"), "w") as f:
        f.write("<vehicles/>")
    return d

career(1, "Farm", "NF Marsch 4fach oG", ["FS25_ScreenshotStudio", "FS25_AutoDrive"])
career(20, "Test", "Catuaí", ["FS25_AutoDrive"])
os.makedirs(os.path.join(docs, "savegame3"))          # empty slot: no careerSavegame.xml
saves = rg.savegames(docs)
check([s["index"] for s in saves] == [1, 20], f"savegames 1 and 20, empty slot left out ({[s['index'] for s in saves]})")
check(saves[0]["hasMod"] and not saves[1]["hasMod"] and saves[1]["map"] == "Catuaí", "mod switched on: save 1 yes, save 20 no")

check(rg.installed_version(docs) is None, "no zip in mods: no installed version")
os.makedirs(os.path.join(docs, "mods"))
with zipfile.ZipFile(os.path.join(docs, "mods", "FS25_ScreenshotStudio.zip"), "w") as zf:
    zf.writestr("modDesc.xml", "<modDesc><version>0.1.0.0</version></modDesc>")
check(rg.installed_version(docs) == "0.1.0.0", "installed version read from the zip")
check(rg.repo_version() and rg.repo_version() != "0.1.0.0", f"repo version from modDesc.xml ({rg.repo_version()})")

# --- autorun.xml: what the mod reads (autorun#savegame, autorun#created, autorun.step(i))
import datetime
path = rg.write_autorun(["ssEnter", "ssLight golden", 'ssColors "x" & <y>'], 1, studio=studio,
                        now=datetime.datetime(2026, 11, 12, 18, 30, 5))
root = ET.parse(path).getroot()
check(root.tag == "autorun" and root.get("savegame") == "1" and root.get("created") == "20261112_183005",
      "autorun.xml: save and time as the mod expects")
check([s.text for s in root.findall("step")] == ["ssEnter", "ssLight golden", 'ssColors "x" & <y>'], "steps in order, escaped")
check(rg.remove_autorun(studio) and not os.path.exists(path) and not rg.remove_autorun(studio), "autorun.xml removed")

# --- backup: nothing changed -> left alone; autosave -> backup back, changed folder kept
sg = os.path.join(docs, "savegame1")
zip_path, before = rg.backup(sg, work=work, stamp="A")
check(os.path.isfile(zip_path) and set(zipfile.ZipFile(zip_path).namelist()) == {"careerSavegame.xml", "vehicles.xml"},
      "backup zip has the savegame files")
check(rg.restore_if_changed(sg, zip_path, before, work=work, stamp="A") is None, "nothing changed: nothing restored")
time.sleep(0.05)
with open(os.path.join(sg, "vehicles.xml"), "w") as f:
    f.write("<vehicles>changed by autosave</vehicles>")
with open(os.path.join(sg, "new.xml"), "w") as f:
    f.write("<new/>")
kept = rg.restore_if_changed(sg, zip_path, before, work=work, stamp="B")
check(kept is not None and open(os.path.join(sg, "vehicles.xml")).read() == "<vehicles/>"
      and not os.path.exists(os.path.join(sg, "new.xml")), "autosave: the backup is back")
check(kept and "changed by autosave" in open(os.path.join(kept, "vehicles.xml")).read(), "the changed savegame is kept")

# --- the log
w = rg.LogWatch()
out = w.feed("2026-11-12 18:31 Loading map\n[ScreenshotStudio] autorun: start")
check(out == [] and not w.started, "half a line waits for the rest")
out = w.feed("ed, 8 steps, first in 10 s\nError: some other mod broke\n")
check(w.started and out == ["[ScreenshotStudio] autorun: started, 8 steps, first in 10 s", "Error: some other mod broke"],
      f"lines of ours, and an error right after one ({out})")
out = w.feed("x\nx\nx\nx\nx\nx\nx\nError: far away from us\n")
check(out == [] and w.errors == 2, "errors far from our lines only counted")
out = w.feed("Error: Running LUA method 'update'.\n  dataS/scripts/x.lua(1) : ScreenshotStudio.lua:812: attempt to index nil\n")
check(len(out) == 1 and "ScreenshotStudio.lua:812" in out[0], "a call stack line naming our script")
w.feed("[ScreenshotStudio] autorun: done, 14 picture(s)\n[ScreenshotStudio] autorun: quitting\n")
check(w.done and w.quitting, "done and quitting seen")
w2 = rg.LogWatch()
w2.feed("[ScreenshotStudio] autorun: autorun.xml is for savegame 1, this is 8: not run\n")
check(w2.refused and not w2.started, "a refused autorun is noticed")

# --- the START screen: pressed once the mod is loading and the log has gone quiet
w5, pressed, said = rg.LogWatch(), [], []
p = rg.StartPresser(press=lambda: pressed.append(1) or True, echo=said.append)
w5.feed("2026-11-13 08:43:00 loading things\n", now=100)
p.tick(w5, now=130)
check(not pressed, "not before the mod says it's loading")
w5.feed("2026-11-13 08:43:53 [ScreenshotStudio] Loaded. Right Ctrl + 1 ...\n", now=140)
p.tick(w5, now=150)
check(w5.loaded and not pressed, "loading, log still busy: wait")
p.tick(w5, now=153)
check(len(pressed) == 1 and said == ["Pressing START (Enter) in the game window"], "12 s quiet: Enter pressed")
p.tick(w5, now=158)
check(len(pressed) == 1, "not again within 10 s")
p.tick(w5, now=164)
check(len(pressed) == 2, "again 10 s later while START is still up")
w5.feed("2026-11-13 08:45:25 Info: Entered Gameplay\n", now=170)
p.tick(w5, now=200)
check(w5.entered and len(pressed) == 2, "Entered Gameplay: no more presses")
off = rg.StartPresser(enabled=False, press=lambda: pressed.append(1) or True, echo=said.append)
w6 = rg.LogWatch(); w6.feed("[ScreenshotStudio] Loaded.\n", now=0)
off.tick(w6, now=100)
check(len(pressed) == 2, "--no-press: never")
fail = rg.StartPresser(press=lambda: False, echo=said.append)
fail.tick(w6, now=100)
check(said[-1].startswith("! Couldn't bring the game window"), "no game window: says to press it yourself")
check(rg.game_pids() == set(), "game_pids: none while the game is closed") if not rg.game_running() else None
# the mod-update dialog: right after "Auto start local savegame", before anything loads
w7, pressed7 = rg.LogWatch(), []
p7 = rg.StartPresser(press=lambda: pressed7.append(1) or True, echo=lambda s: None)
w7.feed("Available mod: (Hash: 10f1) (Version: 0.2.0.6) FS25_ScreenshotStudio\n", now=0)
p7.tick(w7, now=30)
check(not pressed7, "mod list read, no auto start yet: nothing")
w7.feed("Auto start local savegame (Id: 1)\n", now=40)
p7.tick(w7, now=50)
check(not pressed7, "auto start, log just written: wait")
p7.tick(w7, now=53)
check(w7.autostart and len(pressed7) == 1, "update dialog (quiet after auto start): Enter = START without updating")

# --- ssKeys: the mod logs them, the runner types them
check(rg.parse_keys("ctrl+f tractor enter Esc") == [("chord", ["ctrl", "f"]), ("text", "tractor"), ("chord", ["enter"]), ("chord", ["esc"])],
      "keys: chords, key names (any case), words to type")
check(rg.parse_keys("ctrl+f pause tractor enter")[1] == ("pause", 1.0), "keys: pause waits a second")
w8 = rg.LogWatch()
w8.feed("2026-11-13 11:00:01 [ScreenshotStudio] autorun: step 4/9 ssKeys ctrl+f tractor -> Keys for the runner to type: ctrl+f tractor\n")
typed, said = [], []
rg.KeyTyper(send=lambda spec: typed.append(spec) or True, echo=said.append).tick(w8)
check(typed == ["ctrl+f tractor"] and w8.keys == [] and said == ["Typing into the game: ctrl+f tractor"], "the typer types what the log asks, once")
check(rg.with_menus(["ssEnter", "quit"], ["UWMFrame", "ShopMenu"], "FS25_PlayerTradingPlus") ==
      ["ssEnter", "ssFolder FS25_PlayerTradingPlus", "ssMenu UWMFrame", "wait 2", "ssUi 1", "ssMenu close", "wait 1",
       "ssMenu ShopMenu", "wait 2", "ssUi 1", "ssMenu close", "wait 1", "quit"]
      and rg.with_menus(["ssEnter", "quit"], None, None) == ["ssEnter", "quit"], "--menu/--folder: open, UI shot, close; the folder first")

# --- is the game running: tasklist's table cuts the name, CSV doesn't
check(rg.listed('"FarmingSimulator2025Game.exe","18900","Console","1","9,812,004 K"\n')
      and not rg.listed("FarmingSimulator2025Game.ex    18900 Console    1  9,812,004 K\n")
      and not rg.listed("INFO: No tasks are running which match the specified criteria.\n"),
      "game process found in tasklist's CSV")
check(rg.game_running() in (True, False), "game_running answers (whether the game is open or not)")

# --- the game gone before the steps were done: crashed, or closed by hand
w4 = rg.LogWatch()
w4.feed("2026-11-13 07:41:05.371 [ScreenshotStudio] autorun: step 3/12 ssShot -> Taking a clean shot\n")
check(w4.step == "3/12 ssShot", f"last step remembered ({w4.step})")
msg = rg.ended_early(w4, "0xc0000005", [])
check("CRASHED during step 3/12 ssShot" in msg[0] and "0xc0000005" in msg[0] and "within a minute" in msg[1]
      and any("screen method" in m for m in msg), f"crash right away: event, dump still coming ({msg})")
msg = rg.ended_early(w4, None, [r"C:\dumps\FarmingSimulator2025Game.exe.1.dmp"])
check("CRASHED" in msg[0] and msg[1].endswith(".exe.1.dmp"), "crash seen only by its dump")
msg = rg.ended_early(rg.LogWatch(), None, [])
check(msg == ["! The game ended before the first step (closed by hand? Windows logged no crash)"], f"closed by hand ({msg})")
dumps = os.path.join(tmp, "CrashDumps")
os.makedirs(dumps)
for n in ["FarmingSimulator2025Game.exe.46932.dmp", "OneDrive.exe.35900.dmp"]:
    open(os.path.join(dumps, n), "w").close()
old = os.path.join(dumps, "FarmingSimulator2025Game.exe.1.dmp")
open(old, "w").close()
os.utime(old, (time.time() - 3600, time.time() - 3600))
found = rg.crash_dumps(time.time() - 60, dumps)
check([os.path.basename(f) for f in found] == ["FarmingSimulator2025Game.exe.46932.dmp"], f"only the game's new dumps ({found})")

# follow_log reads a log as it grows, and from the start when the game begins a new one
log = os.path.join(tmp, "log.txt")
with open(log, "w") as f:
    f.write("[ScreenshotStudio] old run\n")
w3, stop, seen = rg.LogWatch(), threading.Event(), []
t = threading.Thread(target=rg.follow_log, args=(log, 0, w3, stop.is_set, 0.05, seen.append))
t.start()
time.sleep(0.3)
with open(log, "w") as f:      # the game starts a new, shorter log
    f.write("[ScreenshotStudio] new\n")
time.sleep(0.3)
with open(log, "a") as f:
    f.write("[ScreenshotStudio] autorun: done, 1 picture(s)\n")
time.sleep(0.3)
stop.set(); t.join()
check(seen == ["  game| [ScreenshotStudio] old run", "  game| [ScreenshotStudio] new",
               "  game| [ScreenshotStudio] autorun: done, 1 picture(s)"] and w3.done, f"log followed ({seen})")

# --- new pictures since the start, not the backups or lists
os.makedirs(os.path.join(studio, "FS25_PX150XL"))
for n in ["orbit_1.png", "_sheet.jpg", "_shots_1_orbit.xml"]:
    open(os.path.join(studio, "FS25_PX150XL", n), "w").close()
pics = rg.new_pictures(time.time() - 60, studio=studio)
check({k: [os.path.basename(f) for f in v] for k, v in pics.items()} == {"FS25_PX150XL": ["orbit_1.png"]},
      f"new pictures, without the sheet, lists and autorun folder ({pics})")

check(rg.with_move(["ssTarget x", "ssEnter", "ssOrbit", "quit"], True) == ["ssTarget x", "ssEnter", "ssMove", "ssOrbit", "ssMove back", "quit"]
      and rg.with_move(["ssEnter", "quit"], False) == ["ssEnter", "quit"], "--move: ssMove after getting in, ssMove back before quitting")
check(rg.with_target(["ssEnter", "ssTarget x", "ssOrbit", "quit"], " PX150 XL ") == ["ssTarget PX150 XL", "ssEnter", "ssOrbit", "quit"]
      and rg.with_target(["ssEnter"], None) == ["ssEnter"], "--target: ssTarget first, once")
check(all(p[-1] == "quit" and p[0] == "ssEnter" for p in rg.PLANS.values()) and set(rg.PLANS) == set(rg.PLAN_TEXT),
      "every plan gets in first and quits at the end")

shutil.rmtree(tmp, ignore_errors=True)
print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
