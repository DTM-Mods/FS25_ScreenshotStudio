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

# --- captions: text on a picture, within the ModHub rules; the original kept
shots = os.path.join(repo, "screenshots")
with open(os.path.join(shots, "02.jpg"), "rb") as f:
    before = f.read()
code, out = run("caption", repo, "2", "Robot feeding", "The robot fills all four troughs on its own, every hour.")
with Image.open(os.path.join(shots, "02.jpg")) as im:
    im.load(); after = im.copy(); meta = tool.from_comment(im)
with Image.open(os.path.join(shots, "originals", "02.jpg")) as im:
    im.load(); orig = im.copy()
diff_bottom = sum(abs(a - b) for a, b in zip(after.crop((0, 1000, 1920, 1080)).tobytes(), orig.crop((0, 1000, 1920, 1080)).tobytes()))
diff_top = sum(abs(a - b) for a, b in zip(after.crop((0, 0, 1920, 200)).tobytes()[:30000], orig.crop((0, 0, 1920, 200)).tobytes()[:30000]))
check(code == 0 and diff_bottom > 1000000 and diff_top < 30000 * 3, f'caption: a band at the bottom, the rest of the picture as it was ({diff_bottom}, {diff_top})')
check(meta.get("caption") == "yes" and meta.get("kind") == "burst", f"the JPEG comment still says what it is, and that it has a caption ({meta})")
import json
check(json.load(open(os.path.join(shots, "captions.json")))["02.jpg"]["title"] == "Robot feeding", "listed in captions.json")
code, out = run("caption", repo, "2", "Robot feeding at night")
with Image.open(os.path.join(shots, "originals", "02.jpg")) as im:
    im.load(); still = im.copy()
check(code == 0 and still.tobytes() == orig.tobytes(), "a new caption is drawn on the original, not on the old caption")
for args, why in [(("1", "Hero shot"), "01 must have no text"), (("3", "See dtmmods.com"), "a link"),
                  (("3", "New in v1.2"), "a version number"), (("3", "Made by Fennell"), "credits"),
                  (("3", "Schweinestall für 400 Tiere"), "aren't English")]:
    code, out = run("caption", repo, *args)
    check(code == 1 and why in out and "Not written" in out, f"refused: {args[1]!r} ({why})")
code, out = run("caption", repo, "1", "Mehr auf dtmmods.com", "--site")
check(code == 0 and os.path.isfile(os.path.join(shots, "site", "01.jpg")) and not os.path.isfile(os.path.join(shots, "originals", "01.jpg")) is False,
      "--site: a dtmmods.com copy with any text, ModHub's 01 untouched")
with Image.open(os.path.join(shots, "01.jpg")) as im:
    check(tool.from_comment(im).get("caption") is None, "01 itself has no caption")
code, out = run("check", repo)
check(code == 0 and "02.jpg  caption: Robot feeding at night" in out, "check lists the captions")
json.dump({"01.jpg": {"title": "Hero"}}, open(os.path.join(shots, "captions.json"), "w"))
code, out = run("check", repo)
check(code == 1 and "01.jpg caption: 01 must have no text" in out, "check: a caption on 01 breaks the rule")
json.dump({"02.jpg": {"title": "Robot feeding at night"}}, open(os.path.join(shots, "captions.json"), "w"))
code, out = run("caption", repo, "2", "--clear")
with open(os.path.join(shots, "02.jpg"), "rb") as f:
    check(f.read() == before and not os.path.isfile(os.path.join(shots, "captions.json")), "--clear: the original back, byte for byte")

# --- 01 not from the studio, and fewer than 3
shutil.rmtree(os.path.join(repo, "screenshots"))
run("add", repo, os.path.join(studio, "wide_steam.jpg"))
code, out = run("check", repo)
check(code == 1 and "ModHub wants at least 3" in out and "check by eye that it has no HUD" in out
      and "none is a burst shot" in out, "one Steam shot: too few, HUD unknown, nothing in action")

shutil.rmtree(tmp, ignore_errors=True)
print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
