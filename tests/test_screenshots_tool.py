"""Offline test of tools/fs25_screenshots.py with made-up pictures in a temp folder.

    python tests/test_screenshots_tool.py

A Screenshot Studio folder with a _shots_*.xml list: pick carries kind/HUD/light/color into the
JPEG comment; check stops a UI shot as 01, finds the burst shot, a white background, a
near duplicate and a dark picture.
"""
import contextlib, importlib.util, io, os, random, shutil, sys, tempfile
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("fs25_screenshots", os.path.join(ROOT, "tools", "fs25_screenshots.py"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

failures = []
def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond:
        failures.append(msg)

def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = tool.main(list(argv))
    return code, out.getvalue()

def scene(path, seed, size=(1920, 1080), bg=None, dark=False):
    """A field-ish picture: sky, ground, a few blocks; or a white studio background."""
    rnd = random.Random(seed)
    im = Image.new("RGB", size, bg or (120, 160, 210))
    d = ImageDraw.Draw(im)
    if bg is None:
        d.rectangle((0, size[1] // 2, size[0], size[1]), fill=(70, 110, 40))
    for _ in range(12):
        x, y = rnd.randrange(size[0] - 200), rnd.randrange(size[1] - 200)
        d.rectangle((x, y, x + rnd.randrange(60, 400), y + rnd.randrange(60, 300)),
                    fill=tuple(rnd.randrange(256) for _ in range(3)))
    if dark:
        im = im.point(lambda v: v // 8)
    im.save(path)

tmp = tempfile.mkdtemp(prefix="ss_tool_")
studio = os.path.join(tmp, "FS25_Fake")
repo = os.path.join(tmp, "repo", "FS25_Fake")
os.makedirs(studio); os.makedirs(repo)
open(os.path.join(repo, "modDesc.xml"), "w").write("<modDesc/>")

names = {
    "clean_20261112_120000_01.png": dict(seed=1),
    "ui_20261112_120100_01.png": dict(seed=2),
    "burst_20261112_120200_01.png": dict(seed=3),
    "burst_20261112_120200_02.png": dict(seed=3),            # the same again: near duplicate
    "color_20261112_120300_01_Red.png": dict(seed=4, bg=(250, 250, 250)),
    "orbit_20261112_120400_01.png": dict(seed=5, dark=True),
    "wide_steam.jpg": dict(seed=6, size=(3840, 1080)),
}
for n, kw in names.items():
    scene(os.path.join(studio, n), **kw)
open(os.path.join(studio, "_shots_20261112_120000_clean.xml"), "w").write(
    '<shots mod="FS25_Fake"><shot file="clean_20261112_120000_01.png" kind="clean" hud="false" light="golden"/></shots>')
open(os.path.join(studio, "_shots_20261112_120100_ui.xml"), "w").write(
    '<shots><shot file="ui_20261112_120100_01.png" kind="ui" hud="true" light="game"/></shots>')
open(os.path.join(studio, "_shots_20261112_120200_burst.xml"), "w").write(
    '<shots><shot file="burst_20261112_120200_01.png" kind="burst" hud="false" light="game"/>'
    '<shot file="burst_20261112_120200_02.png" kind="burst" hud="false" light="game"/></shots>')
open(os.path.join(studio, "_shots_20261112_120300_color.xml"), "w").write(
    '<shots><shot file="color_20261112_120300_01_Red.png" kind="color" hud="false" light="midday" color="Red"/></shots>')
open(os.path.join(studio, "_shots_broken.xml"), "w").write("<shots><shot")

files = [os.path.basename(f) for f in tool.pictures(studio)]
info = tool.shot_info(studio)
check(len(files) == 7 and "_shots_broken.xml" not in files, f"7 pictures, lists left out ({len(files)})")
check(info["color_20261112_120300_01_Red.png"]["color"] == "Red" and info["ui_20261112_120100_01.png"]["hud"] == "true",
      "shot lists read (a broken one is skipped)")
code, out = run("studio", studio)
check("[clean, golden]" in out and "[ui, HUD]" in out and "[color Red, midday]" in out, "studio shows what each one is")

# --- UI shot first: check says no
n = {f: i + 1 for i, f in enumerate(files)}
code, out = run("pick", repo, studio, str(n["ui_20261112_120100_01.png"]), str(n["clean_20261112_120000_01.png"]),
                str(n["burst_20261112_120200_01.png"]))
check(code == 0, "pick exits 0 even when check complains")
code, out = run("check", repo)
check(code == 1 and "01.jpg is a ui shot" in out, "check: a UI shot as 01 breaks the rule")
check("in action: 03.jpg" in out, "check: the burst shot counts as in action")
def comment(name):
    with Image.open(os.path.join(repo, "screenshots", name)) as im:
        return tool.from_comment(im)
meta = comment("02.jpg")
check(meta == {"kind": "clean", "hud": "false", "light": "golden", "from": "clean_20261112_120000_01.png"},
      f"JPEG comment keeps what it is ({meta})")

# --- clean one first, plus a white background, a duplicate, a dark one and a Steam shot
for f in os.listdir(os.path.join(repo, "screenshots")):
    os.remove(os.path.join(repo, "screenshots", f))
code, out = run("pick", repo, studio, *(str(n[f]) for f in ["clean_20261112_120000_01.png", "burst_20261112_120200_01.png",
                "burst_20261112_120200_02.png", "color_20261112_120300_01_Red.png", "orbit_20261112_120400_01.png",
                "wide_steam.jpg"]))
code, out = run("check", repo)
check(code == 0 and "6 screenshot(s)" in out and "- OK" in out, "check passes with a clean 01")
check("? 02.jpg and 03.jpg look almost the same" in out, "near duplicate found")
check("? 04.jpg: looks like a white background" in out, "white background found")
check("? 05.jpg: very dark" in out, "dark picture found")
check("? 01.jpg" not in out and "? 06.jpg: looks like" not in out, "no false alarms on the normal ones")
with Image.open(os.path.join(repo, "screenshots", "06.jpg")) as im:
    check(im.size == (1920, 1080), "ultrawide cropped to 1920x1080")
check(comment("06.jpg") == {"from": "wide_steam.jpg"},
      "a picture from elsewhere only knows where it came from")

# --- 01 not from the studio, and fewer than 3
for f in os.listdir(os.path.join(repo, "screenshots")):
    os.remove(os.path.join(repo, "screenshots", f))
run("add", repo, os.path.join(studio, "wide_steam.jpg"))
code, out = run("check", repo)
check(code == 1 and "ModHub wants at least 3" in out and "check by eye that it has no HUD" in out
      and "none is a burst shot" in out, "one Steam shot: too few, HUD unknown, nothing in action")

shutil.rmtree(tmp, ignore_errors=True)
print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
