"""Screenshots for a mod repo, ready for ModHub and dtmmods.com.

    python fs25_screenshots.py studio [<folder>]                  what Screenshot Studio has taken
    python fs25_screenshots.py sheet  <folder> [--open]           numbered contact sheet to pick from
    python fs25_screenshots.py pick   <repo> <folder> <n> [<n> ...] [--align left|center|right]
    python fs25_screenshots.py add    <repo> <image> [<image> ...] [--align left|center|right]
    python fs25_screenshots.py check  <repo>
    python fs25_screenshots.py new    [--since YYYY-MM-DD]        your newest game/Steam screenshots

<repo> is a mod repo folder, or just its name (FS25_PX150XL): then the repo of that name under
the fs2025 projects folder. <folder> is a Screenshot Studio folder name (e.g. FS25_PX150XL, from
modSettings/FS25_ScreenshotStudio/) or any folder path. The numbers are the ones on the sheet.

pick/add: crop each picture to 16:9 (ultrawide 32:9 shots: the middle, or --align left/right),
scale it to 1920x1080 and save it as <repo>/screenshots/NN.jpg (next free number). The order is
the ModHub order: pick the clean, HUD-free hero shot first. What Screenshot Studio knows about a
picture (kind, HUD, light, color; from its _shots_*.xml) goes into the JPEG's comment, so check
still knows it after the picture is renamed.

check: at least 3 screenshots, all 1920x1080 JPG; 01 without HUD and not a menu shot; one taken
while working (a burst shot); and what a script can guess from the pixels: white background, near
duplicates, too dark or washed out. "!" breaks a rule (exit code 1), "?" is worth a look.

screenshots/ is a top-level development folder, so the shared build never puts it in the mod zip.

GIANTS ModHub Guidelines v5.9.1, item 5.1: at least 3 screenshots, one with the machine or tool
working; the first one without HUD and without text; text only in English; no logos, watermarks,
links, credits or version numbers; no white background; the store image doesn't count.
"""
import argparse, datetime, glob, os, re, sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageStat

W, H = 1920, 1080
PICS = (".jpg", ".jpeg", ".png")
DOCS = os.path.expanduser(r"~\OneDrive\Documents\My Games\FarmingSimulator2025")
if not os.path.isdir(DOCS):
    DOCS = os.path.expanduser(r"~\Documents\My Games\FarmingSimulator2025")
STUDIO = os.path.join(DOCS, "modSettings", "FS25_ScreenshotStudio")
STEAM = r"C:\Program Files (x86)\Steam\userdata\*\760\remote\2300320\screenshots\*.jpg"
# where the mod repos live: two levels above this repo (fs2025\FS25_Fennell\FS25_ScreenshotStudio)
PROJECTS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
SKIP = {".git", ".venv", "node_modules", "old_mods", "backups", "__pycache__"}
TAG = "DTM Screenshot Studio"
KEYS = ("kind", "hud", "light", "color", "from")

# check thresholds (pixel guesses, so only warnings)
WHITE = 235            # a channel above this counts as white
WHITE_EDGE = 0.5       # this much white along the left, right and bottom edges: white background
DARK = 40              # mean brightness (0-255) below this: too dark
BLOWN = 0.2            # this much of the picture at full brightness: washed out
SAME = 6               # dHash bits (of 64) that may differ for two pictures to count as the same


def find_repo(repo):
    """A path stays a path; a bare name is looked up (up to 3 levels deep) under PROJECTS."""
    if os.path.isdir(repo) or "\\" in repo or "/" in repo:
        return repo
    hits = []
    for top, dirs, _ in os.walk(PROJECTS):
        dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
        for d in dirs:
            if d.lower() == repo.lower() and os.path.isfile(os.path.join(top, d, "modDesc.xml")):
                hits.append(os.path.join(top, d))
        if os.path.relpath(top, PROJECTS).count(os.sep) >= 1:
            dirs[:] = []
    if len(hits) == 1:
        return hits[0]
    if not hits:
        sys.exit(f"No mod repo called {repo} under {PROJECTS}; give the full path")
    sys.exit(f"{repo} is ambiguous, give the full path:\n  " + "\n  ".join(hits))


def studio_dir(folder):
    return folder if os.path.isdir(folder) else os.path.join(STUDIO, folder)


def pictures(folder):
    d = studio_dir(folder)
    return sorted(os.path.join(d, f) for f in os.listdir(d)
                  if f.lower().endswith(PICS) and not f.startswith("_"))


# ---------------------------------------------------------------- what a picture is
def shot_info(folder):
    """{file name: {kind, hud, light, color}} from the _shots_*.xml lists Screenshot Studio writes."""
    info = {}
    for path in glob.glob(os.path.join(studio_dir(folder), "_shots_*.xml")):
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            print(f"? {os.path.basename(path)} can't be read, skipped")
            continue
        for shot in root.iter("shot"):
            if shot.get("file"):
                info[shot.get("file")] = {k: shot.get(k) for k in KEYS if shot.get(k) is not None}
    return info


def label(meta):
    """Short text for lists and the sheet: 'orbit, golden' / 'ui, HUD' / 'color Red'."""
    if not meta:
        return ""
    parts = [meta.get("kind", "?") + (" " + meta["color"] if meta.get("color") else "")]
    if meta.get("hud") == "true":
        parts.append("HUD")
    if meta.get("light") not in (None, "game"):
        parts.append(meta["light"])
    return ", ".join(parts)


def to_comment(meta):
    return (TAG + "; " + "; ".join(f"{k}={meta[k]}" for k in KEYS if meta.get(k) is not None)).encode("utf-8")


def from_comment(im):
    raw = im.info.get("comment")
    if not raw:
        return None
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
    if not text.startswith(TAG):
        return None
    return dict(re.findall(r"(\w+)=([^;]*)", text))


# ---------------------------------------------------------------- pictures into the repo
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


def add(repo, images, align, metas=None):
    out = os.path.join(repo, "screenshots")
    os.makedirs(out, exist_ok=True)
    taken = [int(os.path.splitext(f)[0]) for f in os.listdir(out) if os.path.splitext(f)[0].isdigit()]
    n = max(taken, default=0)
    for i, src in enumerate(images):
        with Image.open(src) as raw:
            im = raw.convert("RGB")
        if min(im.size) < 1080:
            print(f"! {src}: {im.size[0]}x{im.size[1]} is smaller than 1080p, skipped")
            continue
        im = crop_16_9(im, align).resize((W, H), Image.LANCZOS)
        meta = dict((metas or {}).get(src) or {})
        meta["from"] = os.path.basename(src)
        n += 1
        dst = os.path.join(out, f"{n:02d}.jpg")
        im.save(dst, "JPEG", quality=90, optimize=True, comment=to_comment(meta))
        tags = label(meta)
        print(f"{dst}  ({os.path.getsize(dst) // 1024} KB)  from {os.path.basename(src)}" + (f"  [{tags}]" if tags else ""))
    return check(repo)


def pick(repo, folder, numbers, align):
    files = pictures(folder)
    info = shot_info(folder)
    chosen = []
    for n in numbers:
        if not 1 <= n <= len(files):
            sys.exit(f"No picture {n} in {folder} (1-{len(files)})")
        chosen.append(files[n - 1])
    return add(repo, chosen, align, {f: info.get(os.path.basename(f)) for f in chosen})


# ---------------------------------------------------------------- check
def dhash(im):
    g = im.convert("L").resize((9, 8), Image.LANCZOS)
    px = g.tobytes()                         # one byte per pixel (getdata is going away in Pillow 14)
    return sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])


def white_edges(im):
    """Share of near-white pixels along the left, right and bottom edges (the sky is left out)."""
    small = im.convert("RGB").resize((192, 108))
    w, h = small.size
    bw, bh = w // 20, h // 12
    boxes = [(0, 0, bw, h), (w - bw, 0, w, h), (0, h - bh, w, h)]
    total = white = 0
    for box in boxes:
        data = small.crop(box).tobytes()     # r, g, b, r, g, b, ...
        for i in range(0, len(data), 3):
            total += 1
            white += min(data[i], data[i + 1], data[i + 2]) > WHITE
    return white / total


def pixel_notes(im):
    notes = []
    gray = im.convert("L")
    mean = ImageStat.Stat(gray).mean[0]
    if white_edges(im) > WHITE_EDGE:
        notes.append("looks like a white background (not allowed)")
    if mean < DARK:
        notes.append(f"very dark (brightness {mean:.0f} of 255)")
    hist = gray.histogram()
    if sum(hist[250:]) / (im.size[0] * im.size[1]) > BLOWN:
        notes.append("washed out (a lot of pure white)")
    return notes


def check(repo):
    out = os.path.join(repo, "screenshots")
    files = sorted(glob.glob(os.path.join(out, "*.jpg")))
    ok = True

    def bad(msg):
        nonlocal ok
        print("! " + msg)
        ok = False

    metas, hashes = {}, {}
    for f in files:
        name = os.path.basename(f)
        with Image.open(f) as im:
            im.load()
            if im.size != (W, H):
                bad(f"{name} is {im.size[0]}x{im.size[1]}, not {W}x{H}")
            metas[name] = from_comment(im)
            for note in pixel_notes(im):
                print(f"? {name}: {note}")
            hashes[name] = dhash(im)
    if len(files) < 3:
        bad(f"{len(files)} screenshot(s), ModHub wants at least 3")

    names = list(hashes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if bin(hashes[a] ^ hashes[b]).count("1") <= SAME:
                print(f"? {a} and {b} look almost the same")

    if files:
        first = os.path.basename(files[0])
        m = metas.get(first)
        if not m or "kind" not in m:      # from elsewhere: only "from" is known
            print(f"? {first}: not from Screenshot Studio, so check by eye that it has no HUD and no text")
        elif m.get("hud") == "true" or m.get("kind") == "ui":
            bad(f"{first} is a {m.get('kind')} shot with HUD/menu; the first one must be clean (no HUD, no text)")
        if any((m or {}).get("kind") == "burst" for m in metas.values()):
            print("  in action: " + ", ".join(n for n, m in metas.items() if (m or {}).get("kind") == "burst"))
        else:
            print("? none is a burst shot: make sure one shows the machine working")
        for n, m in metas.items():
            if m and "kind" in m:
                print(f"  {n}  {label(m)}  (from {m.get('from', '?')})")

    print(f"{len(files)} screenshot(s) in {out}" + (" - OK" if ok else ""))
    print("Check by eye: no text in 01; English only; no logos, watermarks, links, credits, version numbers.")
    return ok


# ---------------------------------------------------------------- looking around
def studio(folder):
    if folder:
        info = shot_info(folder)
        for i, f in enumerate(pictures(folder), 1):
            im = Image.open(f)
            tags = label(info.get(os.path.basename(f)))
            print(f"{i:3d}  {im.size[0]}x{im.size[1]}  {os.path.basename(f)}" + (f"  [{tags}]" if tags else ""))
        return
    if not os.path.isdir(STUDIO):
        print(f"Nothing yet in {STUDIO}")
        return
    for d in sorted(os.listdir(STUDIO)):
        p = os.path.join(STUDIO, d)
        if os.path.isdir(p) and d not in ("probe", "autorun"):     # autorun: fs25_run_game.py's backups
            print(f"{len(pictures(p)):4d}  {d}")


def sheet(folder, cols=4, tw=480, open_it=False):
    files = pictures(folder)
    if not files:
        print("No pictures"); return
    info = shot_info(folder)
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
        tags = label(info.get(os.path.basename(f)))
        d.text((x + 6, y + 3), f"{i + 1}  {tags or os.path.basename(f)}", fill=(233, 199, 122), font=font)
    dst = os.path.join(studio_dir(folder), "_sheet.jpg")
    img.save(dst, quality=85)
    print(dst)
    if open_it:
        os.startfile(dst)


def new(since):
    files = glob.glob(STEAM) + glob.glob(os.path.join(DOCS, "screenshots", "*"))
    cut = datetime.datetime.fromisoformat(since).timestamp() if since else 0
    for f in sorted((f for f in files if os.path.getmtime(f) >= cut), key=os.path.getmtime):
        im = Image.open(f)
        t = datetime.datetime.fromtimestamp(os.path.getmtime(f)).strftime("%Y-%m-%d %H:%M")
        print(f"{t}  {im.size[0]}x{im.size[1]}  {f}")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add"); a.add_argument("repo"); a.add_argument("images", nargs="+")
    a.add_argument("--align", choices=["left", "center", "right"], default="center")
    k = sub.add_parser("pick"); k.add_argument("repo"); k.add_argument("folder"); k.add_argument("numbers", nargs="+", type=int)
    k.add_argument("--align", choices=["left", "center", "right"], default="center")
    sub.add_parser("check").add_argument("repo")
    sub.add_parser("studio").add_argument("folder", nargs="?")
    s = sub.add_parser("sheet"); s.add_argument("folder"); s.add_argument("--open", action="store_true")
    sub.add_parser("new").add_argument("--since")
    args = p.parse_args(argv)
    if getattr(args, "repo", None):
        args.repo = find_repo(args.repo)
    if args.cmd == "check": return 0 if check(args.repo) else 1
    if args.cmd == "add": add(args.repo, args.images, args.align)        # picking one at a time is fine
    elif args.cmd == "pick": pick(args.repo, args.folder, args.numbers, args.align)
    elif args.cmd == "studio": studio(args.folder)
    elif args.cmd == "sheet": sheet(args.folder, open_it=args.open)
    else: new(args.since)
    return 0


if __name__ == "__main__":
    sys.exit(main())
