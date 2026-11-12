"""Screenshots for a mod repo, ready for ModHub and dtmmods.com.

    python fs25_screenshots.py studio [<folder>]                  what Screenshot Studio has taken
    python fs25_screenshots.py sheet  <folder>                    numbered contact sheet to pick from
    python fs25_screenshots.py pick   <repo> <folder> <n> [<n> ...] [--align left|center|right]
    python fs25_screenshots.py add    <repo> <image> [<image> ...] [--align left|center|right]
    python fs25_screenshots.py check  <repo>
    python fs25_screenshots.py new    [--since YYYY-MM-DD]        your newest game/Steam screenshots

<folder> is a Screenshot Studio folder name (e.g. FS25_PX150XL, from
modSettings/FS25_ScreenshotStudio/) or any folder path. The numbers are the ones on the sheet.

pick/add: crop each picture to 16:9 (ultrawide 32:9 shots: the middle, or --align left/right),
scale it to 1920x1080 and save it as <repo>/screenshots/NN.jpg (next free number). The order is
the ModHub order: pick the clean, HUD-free hero shot first.
check: at least 3 screenshots, all 1920x1080 JPG, and the rules a script can't see.

screenshots/ is a top-level development folder, so the shared build never puts it in the mod zip.

GIANTS ModHub Guidelines v5.9.1, item 5.1: at least 3 screenshots, one with the machine or tool
working; the first one without HUD and without text; text only in English; no logos, watermarks,
links, credits or version numbers; no white background; the store image doesn't count.
"""
import argparse, datetime, glob, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
PICS = (".jpg", ".jpeg", ".png")
DOCS = os.path.expanduser(r"~\OneDrive\Documents\My Games\FarmingSimulator2025")
if not os.path.isdir(DOCS):
    DOCS = os.path.expanduser(r"~\Documents\My Games\FarmingSimulator2025")
STUDIO = os.path.join(DOCS, "modSettings", "FS25_ScreenshotStudio")
STEAM = r"C:\Program Files (x86)\Steam\userdata\*\760\remote\2300320\screenshots\*.jpg"


def studio_dir(folder):
    return folder if os.path.isdir(folder) else os.path.join(STUDIO, folder)


def pictures(folder):
    d = studio_dir(folder)
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith(PICS) and not f.startswith("_"))


def crop_16_9(im, align):
    w, h = im.size
    if w * 9 > h * 16:                       # too wide: cut the sides
        nw = h * 16 // 9
        x = {"left": 0, "right": w - nw}.get(align, (w - nw) // 2)
        im = im.crop((x, 0, x + nw, h))
    elif w * 9 < h * 16:                     # too tall: cut top and bottom evenly
        nh = w * 9 // 16
        y = (h - nh) // 2
        im = im.crop((0, y, w, y + nh))
    return im


def add(repo, images, align):
    out = os.path.join(repo, "screenshots")
    os.makedirs(out, exist_ok=True)
    taken = [int(os.path.splitext(f)[0]) for f in os.listdir(out) if os.path.splitext(f)[0].isdigit()]
    n = max(taken, default=0)
    for src in images:
        im = Image.open(src).convert("RGB")
        if min(im.size) < 1080:
            print(f"! {src}: {im.size[0]}x{im.size[1]} is smaller than 1080p, skipped")
            continue
        im = crop_16_9(im, align).resize((W, H), Image.LANCZOS)
        n += 1
        dst = os.path.join(out, f"{n:02d}.jpg")
        im.save(dst, "JPEG", quality=90, optimize=True)
        print(f"{dst}  ({os.path.getsize(dst) // 1024} KB)  from {os.path.basename(src)}")
    check(repo)


def check(repo):
    out = os.path.join(repo, "screenshots")
    files = sorted(glob.glob(os.path.join(out, "*.jpg")))
    ok = True
    for f in files:
        size = Image.open(f).size
        if size != (W, H):
            print(f"! {os.path.basename(f)} is {size[0]}x{size[1]}, not {W}x{H}"); ok = False
    if len(files) < 3:
        print(f"! {len(files)} screenshot(s), ModHub wants at least 3"); ok = False
    print(f"{len(files)} screenshot(s) in {out}" + (" - OK" if ok else ""))
    print("Check by eye: 01 has no HUD and no text; one shows it working; English only;"
          " no logos, watermarks, links, credits, version numbers; no white background.")
    return ok


def studio(folder):
    if folder:
        for i, f in enumerate(pictures(folder), 1):
            im = Image.open(f)
            print(f"{i:3d}  {im.size[0]}x{im.size[1]}  {os.path.basename(f)}")
        return
    if not os.path.isdir(STUDIO):
        print(f"Nothing yet in {STUDIO}")
        return
    for d in sorted(os.listdir(STUDIO)):
        p = os.path.join(STUDIO, d)
        if os.path.isdir(p) and d != "probe":
            print(f"{len(pictures(p)):4d}  {d}")


def sheet(folder, cols=4, tw=480):
    files = pictures(folder)
    if not files:
        print("No pictures"); return
    th = tw * 9 // 16
    rows = (len(files) + cols - 1) // cols
    img = Image.new("RGB", (cols * tw, rows * (th + 26)), (20, 51, 38))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arialbd.ttf", 18)
    except OSError:
        font = ImageFont.load_default()
    for i, f in enumerate(files):
        im = crop_16_9(Image.open(f).convert("RGB"), "center")
        im.thumbnail((tw, th))
        x, y = (i % cols) * tw, (i // cols) * (th + 26)
        img.paste(im, (x, y + 26))
        d.text((x + 6, y + 3), f"{i + 1}  {os.path.basename(f)}", fill=(233, 199, 122), font=font)
    dst = os.path.join(studio_dir(folder), "_sheet.jpg")
    img.save(dst, quality=85)
    print(dst)


def pick(repo, folder, numbers, align):
    files = pictures(folder)
    chosen = []
    for n in numbers:
        if not 1 <= n <= len(files):
            sys.exit(f"No picture {n} in {folder} (1-{len(files)})")
        chosen.append(files[n - 1])
    add(repo, chosen, align)


def new(since):
    files = glob.glob(STEAM) + glob.glob(os.path.join(DOCS, "screenshots", "*"))
    cut = datetime.datetime.fromisoformat(since).timestamp() if since else 0
    for f in sorted((f for f in files if os.path.getmtime(f) >= cut), key=os.path.getmtime):
        im = Image.open(f)
        t = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        print(f"{t}  {im.size[0]}x{im.size[1]}  {f}")


p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = p.add_subparsers(dest="cmd", required=True)
a = sub.add_parser("add"); a.add_argument("repo"); a.add_argument("images", nargs="+")
a.add_argument("--align", choices=["left", "center", "right"], default="center")
k = sub.add_parser("pick"); k.add_argument("repo"); k.add_argument("folder"); k.add_argument("numbers", nargs="+", type=int)
k.add_argument("--align", choices=["left", "center", "right"], default="center")
sub.add_parser("check").add_argument("repo")
sub.add_parser("studio").add_argument("folder", nargs="?")
sub.add_parser("sheet").add_argument("folder")
sub.add_parser("new").add_argument("--since")
args = p.parse_args()
if args.cmd == "add": add(args.repo, args.images, args.align)
elif args.cmd == "pick": pick(args.repo, args.folder, args.numbers, args.align)
elif args.cmd == "check": sys.exit(0 if check(args.repo) else 1)
elif args.cmd == "studio": studio(args.folder)
elif args.cmd == "sheet": sheet(args.folder)
else: new(args.since)
