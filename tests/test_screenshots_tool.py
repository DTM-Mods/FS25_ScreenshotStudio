"""Offline test of tools/fs25_screenshots.py with made-up pictures in a temp folder.

    python tests/test_screenshots_tool.py

A Screenshot Studio folder with a _shots_*.xml list: pick writes the README set (1920x1080) and the
ModHub set (modhub/screenshots/, 1600x900, unedited) and carries kind/HUD/light/color into the JPEG
comment; check stops a UI shot as 1, a captioned or wrong-sized ModHub picture and a missing set, finds
the burst shot, a white background, a near duplicate and a dark picture; captions stay on the README set.
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
check(code == 1 and "1.jpg is a ui shot" in out, "check: a UI shot as 1 breaks the rule")
check("in action: 3.jpg" in out, "check: the burst shot counts as in action")
shots = os.path.join(repo, "screenshots")
hub = os.path.join(repo, "modhub", "screenshots")
def comment(name, folder=None):
    with Image.open(os.path.join(folder or shots, name)) as im:
        return tool.from_comment(im)
meta = comment("2.jpg")
check(meta == {"kind": "clean", "hud": "false", "light": "golden", "from": "clean_20261112_120000_01.png"},
      f"JPEG comment keeps what it is ({meta})")
with Image.open(os.path.join(hub, "2.jpg")) as im:
    raw = im.info.get("comment") or b""
    check(im.size == (1600, 900) and raw.startswith(b"shot;") and b"DTM" not in raw,
          f"pick also writes the ModHub copy: 1600x900, no modder name in its comment ({im.size}, {raw[:30]})")
check(comment("2.jpg", hub) == meta, "the ModHub copy knows what it is too")

# --- clean one first, plus a white background, a duplicate, a dark one and a Steam shot
shutil.rmtree(shots); shutil.rmtree(os.path.join(repo, "modhub"))
code, out = run("pick", repo, studio, *(str(n[f]) for f in ["clean_20261112_120000_01.png", "burst_20261112_120200_01.png",
                "burst_20261112_120200_02.png", "color_20261112_120300_01_Red.png", "orbit_20261112_120400_01.png",
                "wide_steam.jpg"]))
code, out = run("check", repo)
check(code == 0 and "6 screenshot(s)" in out and "- OK" in out, "check passes with a clean 1")
check("? 2.jpg and 3.jpg look almost the same" in out, "near duplicate found")
check("? 4.jpg: looks like a white background" in out, "white background found")
check("? 5.jpg: very dark" in out, "dark picture found")
check("? 1.jpg" not in out and "? 6.jpg: looks like" not in out, "no false alarms on the normal ones")
check("no modder names" in out and "Fennell" in out, "check reminds of the modder names to look for")
with Image.open(os.path.join(shots, "6.jpg")) as im:
    check(im.size == (1920, 1080), "ultrawide cropped to 1920x1080 for the README")
with Image.open(os.path.join(hub, "6.jpg")) as im:
    check(im.size == (1600, 900), "... and 1600x900 for ModHub")
check(comment("6.jpg") == {"from": "wide_steam.jpg"},
      "a picture from elsewhere only knows where it came from")

# --- captions: README/site pictures only; the original kept; the ModHub copy untouched
with open(os.path.join(shots, "2.jpg"), "rb") as f:
    before = f.read()
with open(os.path.join(hub, "2.jpg"), "rb") as f:
    hub_before = f.read()
code, out = run("caption", repo, "2", "Robot feeding", "The robot fills all four troughs on its own, every hour.")
with Image.open(os.path.join(shots, "2.jpg")) as im:
    im.load(); after = im.copy(); meta = tool.from_comment(im)
with Image.open(os.path.join(shots, "originals", "2.jpg")) as im:
    im.load(); orig = im.copy()
diff_bottom = sum(abs(a - b) for a, b in zip(after.crop((0, 1000, 1920, 1080)).tobytes(), orig.crop((0, 1000, 1920, 1080)).tobytes()))
diff_top = sum(abs(a - b) for a, b in zip(after.crop((0, 0, 1920, 200)).tobytes()[:30000], orig.crop((0, 0, 1920, 200)).tobytes()[:30000]))
check(code == 0 and diff_bottom > 1000000 and diff_top < 30000 * 3, f'caption: a band at the bottom, the rest of the picture as it was ({diff_bottom}, {diff_top})')
check(meta.get("caption") == "yes" and meta.get("kind") == "burst", f"the JPEG comment still says what it is, and that it has a caption ({meta})")
with open(os.path.join(hub, "2.jpg"), "rb") as f:
    check(f.read() == hub_before, "the ModHub copy stays unedited")
import json
check(json.load(open(os.path.join(shots, "captions.json")))["2.jpg"]["title"] == "Robot feeding", "listed in captions.json")
code, out = run("caption", repo, "2", "Robot feeding at night")
with Image.open(os.path.join(shots, "originals", "2.jpg")) as im:
    im.load(); still = im.copy()
check(code == 0 and still.tobytes() == orig.tobytes(), "a new caption is drawn on the original, not on the old caption")
code, out = run("caption", repo, "3", "Mehr auf dtmmods.com, made by Fennell, v1.2")
check(code == 0, "README captions have no ModHub rules (links, names, versions, German)")
code, out = run("caption", repo, "1", "Hero shot")
check(code == 0, "a caption on the README's picture 1 is fine too")
code, out = run("check", repo)
check(code == 0 and "2.jpg  caption: Robot feeding at night" in out, "check lists the captions and still passes")
code, out = run("caption", repo, "2", "--clear")
with open(os.path.join(shots, "2.jpg"), "rb") as f:
    check(f.read() == before, "--clear: the original back, byte for byte")

# --- modhub: the ModHub set again from README pictures, captioned ones from their originals
code, out = run("modhub", repo, "3", "1", "5")
check(code == 0 and sorted(os.listdir(hub)) == ["1.jpg", "2.jpg", "3.jpg"], f"modhub: 3 pictures, the old set gone ({sorted(os.listdir(hub))})")
with Image.open(os.path.join(hub, "1.jpg")) as im:
    im.load(); first = im.copy(); m1 = tool.from_comment(im)
with Image.open(os.path.join(shots, "originals", "3.jpg")) as im:
    plain = im.convert("RGB").resize((1600, 900))
diff = sum(abs(a - b) for a, b in zip(first.crop((0, 830, 1600, 900)).tobytes(), plain.crop((0, 830, 1600, 900)).tobytes()))
check(diff < 1600 * 70 * 3 * 4 and "caption" not in (m1 or {}) and (m1 or {}).get("kind") == "burst",
      f"modhub 1.jpg is README 3 without its caption ({diff}, {m1})")
code, out = run("check", repo)
check(code == 0 and "in action: 1.jpg" in out, "the new set passes, the burst shot first")

# --- check: a captioned or wrong-sized ModHub picture, no ModHub set at all
first.save(os.path.join(hub, "2.jpg"), comment=tool.to_comment({"kind": "clean", "caption": "yes"}, tool.MODHUB_TAG))
Image.new("RGB", (1920, 1080), (90, 120, 60)).save(os.path.join(hub, "3.jpg"))
code, out = run("check", repo)
check(code == 1 and "2.jpg has a caption" in out and "3.jpg is 1920x1080, not 1600x900" in out,
      "check: a caption or 1920x1080 in the ModHub set breaks the rules")
shutil.rmtree(os.path.join(repo, "modhub"))
code, out = run("check", repo)
check(code == 1 and "no ModHub set" in out, "check: no ModHub set breaks the rules")

# --- a 1600x900 shot (a run with --resolution 1600x900): 1600x900 in both sets, never enlarged; smaller: skipped
small = os.path.join(tmp, "small_1600.png"); scene(small, 9, size=(1600, 900))
tiny = os.path.join(tmp, "tiny_1280.png"); scene(tiny, 10, size=(1280, 720))
code, out = run("add", repo, small, tiny, "--no-modhub")
last = max(tool.numbered(shots))
with Image.open(tool.numbered(shots)[last]) as im:
    check(im.size == (1600, 900) and "tiny_1280.png" in out and "skipped" in out,
          f"a 1600x900 shot stays 1600x900, a 1280x720 one is skipped ({im.size})")
os.remove(tool.numbered(shots)[last])

# --- --no-modhub: README only
code, out = run("pick", repo, studio, str(n["clean_20261112_120000_01.png"]), "--no-modhub")
check(not os.path.isdir(hub) and os.path.isfile(os.path.join(shots, "7.jpg")), "--no-modhub: README/site only")

# --- renumber: 01.jpg, 02.jpg (older picks) -> 1.jpg, 2.jpg, with originals, captions and the ModHub set
old = os.path.join(tmp, "old", "FS25_Old")
os.makedirs(os.path.join(old, "screenshots", "originals"))
os.makedirs(os.path.join(old, "modhub", "screenshots"))
for n_ in ("01", "02", "10"):
    scene(os.path.join(old, "screenshots", f"{n_}.jpg"), int(n_))
scene(os.path.join(old, "screenshots", "originals", "02.jpg"), 2)
scene(os.path.join(old, "modhub", "screenshots", "01.jpg"), 1, size=(1600, 900))
json.dump({"02.jpg": {"title": "Old caption"}}, open(os.path.join(old, "screenshots", "captions.json"), "w"))
code, out = run("renumber", old)
names = sorted(os.listdir(os.path.join(old, "screenshots")))
check(code == 0 and names == ["1.jpg", "10.jpg", "2.jpg", "captions.json", "originals"]
      and os.listdir(os.path.join(old, "screenshots", "originals")) == ["2.jpg"]
      and os.listdir(os.path.join(old, "modhub", "screenshots")) == ["1.jpg"]
      and list(json.load(open(os.path.join(old, "screenshots", "captions.json")))) == ["2.jpg"],
      f"renumber: plain numbers, originals, captions and the ModHub set too ({names})")
check([os.path.basename(f) for f in tool.numbered(os.path.join(old, "screenshots")).values()] == ["1.jpg", "2.jpg", "10.jpg"],
      "in number order: 2 before 10")

# --- 1 not from the studio, and fewer than 3
shutil.rmtree(shots)
run("add", repo, os.path.join(studio, "wide_steam.jpg"))
code, out = run("check", repo)
check(code == 1 and "ModHub wants at least 3" in out and "check by eye that it has no UI" in out
      and "none is a burst shot" in out, "one Steam shot: too few, UI unknown, nothing in action")

shutil.rmtree(tmp, ignore_errors=True)
print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
