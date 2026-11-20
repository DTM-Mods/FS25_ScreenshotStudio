"""Screenshots for a mod repo: the ModHub upload set and the pictures for the README and dtmmods.com.

    python fs25_screenshots.py studio [<folder>]                  what Screenshot Studio has taken
    python fs25_screenshots.py sheet  <folder> [--open]           numbered contact sheet to pick from
    python fs25_screenshots.py pick   <repo> <folder> <n> [<n> ...] [--align left|center|right] [--no-modhub]
    python fs25_screenshots.py add    <repo> <image> [<image> ...] [--align left|center|right] [--no-modhub]
    python fs25_screenshots.py modhub <repo> <n> [<n> ...]          the ModHub set again, from these README pictures
    python fs25_screenshots.py check  <repo>
    python fs25_screenshots.py new    [--since YYYY-MM-DD]        your newest game/Steam screenshots
    python fs25_screenshots.py caption <repo> <n> "Title" ["more text"] [--at top] [--clear]
                                                                  text on screenshots/<n>.jpg (README/site only)
    python fs25_screenshots.py renumber <repo>                     01.jpg, 02.jpg, ... -> 1.jpg, 2.jpg, ...

<repo> is a mod repo folder, or just its name (FS25_PX150XL): then the repo of that name under
the fs2025 projects folder. <folder> is a Screenshot Studio folder name (e.g. FS25_PX150XL, from
modSettings/FS25_ScreenshotStudio/) or any folder path. The numbers are the ones on the sheet.

Two sets per repo:
  modhub/screenshots/<n>.jpg   the ModHub upload: 1600x900, unedited (no caption, nothing added)
  screenshots/<n>.jpg          README, dtmmods.com, KingMods: 1920x1080 (1600x900 from a 1600x900 shot, never
                               enlarged), captions allowed (caption)

pick/add: crop each picture to 16:9 (ultrawide 32:9 shots: the middle, or --align left/right) and save it in
both sets (next free number in each). The order is the ModHub order: pick the clean, UI-free hero shot first.
--no-modhub: README/site only (e.g. a picture with a modder's name in it). modhub: the ModHub set made again from
the README pictures with these numbers, in this order (their uncaptioned originals). What Screenshot Studio
knows about a picture (kind, HUD, light, color; from its _shots_*.xml) goes into the JPEG's comment, so check
still knows it after the picture is renamed.

check: the ModHub set: at least 3, all 1600x900 JPG, no caption; picture 1 without HUD and not a menu shot; one
taken while working (a burst shot) among the first three; and what a script can guess from the pixels: white
background, near duplicates, too dark or washed out. "!" breaks a rule (exit code 1), "?" is worth a look.

screenshots/ and modhub/ are development folders, so the shared build never puts them in the mod zip.

GIANTS' FS25 ModHub guidelines (as the DTM-Mods CI README sums them up, 2026-11-17): at least 3 screenshots,
1600x900, unedited in-game images (no caption bars, frames, logos or added text, nothing AI-made); the first one
without UI; machinery at work within the first three; no white background; no modder references (DTM, DTM Mods,
dtmmods.com, PropaineX, Fennell) anywhere in them; the store image doesn't count.
"""
import argparse, datetime, glob, json, os, re, shutil, sys
import xml.etree.ElementTree as ET
from PIL import Image, ImageDraw, ImageFont, ImageStat

W, H = 1920, 1080          # README / dtmmods.com pictures (screenshots/)
MW, MH = 1600, 900         # the ModHub upload set (modhub/screenshots/)
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
MODHUB_TAG = "shot"        # the ModHub copies' comment starts with this: no modder name in what goes to GIANTS
KEYS = ("kind", "hud", "light", "color", "from", "caption")
MODDERS = "DTM, DTM Mods, dtmmods.com, PropaineX, Fennell"

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


def to_comment(meta, tag=TAG):
    return (tag + "; " + "; ".join(f"{k}={meta[k]}" for k in KEYS if meta.get(k) is not None)).encode("utf-8")


def from_comment(im):
    raw = im.info.get("comment")
    if not raw:
        return None
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw)
    if not (text.startswith(TAG + ";") or text.startswith(MODHUB_TAG + ";")):
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


def readme_dir(repo):
    return os.path.join(repo, "screenshots")


def modhub_dir(repo):
    return os.path.join(repo, "modhub", "screenshots")


def save_modhub(im, dst, meta):
    """The ModHub copy: 1600x900, nothing drawn on it, no caption flag, no modder name in the comment."""
    meta = {k: v for k, v in meta.items() if k != "caption"}
    im.resize((MW, MH), Image.LANCZOS).save(dst, "JPEG", quality=92, optimize=True, comment=to_comment(meta, MODHUB_TAG))


def add(repo, images, align, metas=None, modhub=True):
    out, hub = readme_dir(repo), modhub_dir(repo)
    os.makedirs(out, exist_ok=True)
    if modhub:
        os.makedirs(hub, exist_ok=True)
    n = max(numbered(out), default=0)
    m = max(numbered(hub), default=0)
    for i, src in enumerate(images):
        with Image.open(src) as raw:
            im = raw.convert("RGB")
        im = crop_16_9(im, align)
        if im.size[1] < MH:
            print(f"! {src}: {im.size[0]}x{im.size[1]} after the 16:9 crop is smaller than {MW}x{MH}, skipped")
            continue
        # README copy: 1920x1080, or 1600x900 from a smaller shot (a run with --resolution 1600x900): never enlarged
        im = im.resize((W, H) if im.size[1] >= H else (MW, MH), Image.LANCZOS)
        meta = dict((metas or {}).get(src) or {})
        meta["from"] = os.path.basename(src)
        n += 1
        dst = os.path.join(out, f"{n}.jpg")
        im.save(dst, "JPEG", quality=90, optimize=True, comment=to_comment(meta))
        tags = label(meta)
        line = f"{dst}  ({os.path.getsize(dst) // 1024} KB)  from {os.path.basename(src)}" + (f"  [{tags}]" if tags else "")
        if modhub:
            m += 1
            save_modhub(im, os.path.join(hub, f"{m}.jpg"), meta)
            line += f"  + modhub/screenshots/{m}.jpg"
        print(line)
    return check(repo)


def pick(repo, folder, numbers, align, modhub=True):
    files = pictures(folder)
    info = shot_info(folder)
    chosen = []
    for n in numbers:
        if not 1 <= n <= len(files):
            sys.exit(f"No picture {n} in {folder} (1-{len(files)})")
        chosen.append(files[n - 1])
    return add(repo, chosen, align, {f: info.get(os.path.basename(f)) for f in chosen}, modhub)


def modhub_set(repo, numbers):
    """The ModHub set made again from the README pictures with these numbers, in this order: each one's
    uncaptioned original (screenshots/originals/<n>.jpg) if it has a caption."""
    out, hub = readme_dir(repo), modhub_dir(repo)
    have = numbered(out)
    for n in numbers:
        if n not in have:
            sys.exit(f"No picture {n} in {out}")
    os.makedirs(hub, exist_ok=True)
    for old in numbered(hub).values():
        os.remove(old)
    for i, n in enumerate(numbers, 1):
        name = os.path.basename(have[n])
        original = os.path.join(out, "originals", name)
        src = original if os.path.isfile(original) else have[n]
        with Image.open(src) as raw:
            raw.load()
            meta = from_comment(raw) or {}
            im = crop_16_9(raw.convert("RGB"), "center")
        if meta.get("caption") == "yes" and src == have[n]:
            sys.exit(f"{name} has a caption but no original in screenshots/originals/: pick it again")
        save_modhub(im, os.path.join(hub, f"{i}.jpg"), meta)
        print(f"modhub/screenshots/{i}.jpg  from screenshots/{name}" + (" (its original, without the caption)" if src == original else ""))
    return check(repo)


def numbered(folder):
    """{number: path} of the numbered pictures in a screenshots folder: 1.jpg, 2.jpg (or 01.jpg, 02.jpg)."""
    out = {}
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            stem, ext = os.path.splitext(f)
            if ext.lower() == ".jpg" and stem.isdigit():
                out[int(stem)] = os.path.join(folder, f)
    return dict(sorted(out.items()))


def renumber(repo):
    """01.jpg, 02.jpg, ... -> 1.jpg, 2.jpg, ... in screenshots/ (originals/, site/), modhub/screenshots/ and captions.json."""
    out = os.path.join(repo, "screenshots")
    moved = 0
    for folder in (out, os.path.join(out, "originals"), os.path.join(out, "site"), modhub_dir(repo)):
        pics = numbered(folder)
        temp = {}
        for n, path in pics.items():                 # two steps: 1.jpg may exist next to 01.jpg in no case, but stay safe
            if os.path.basename(path) != f"{n}.jpg":
                tmp = os.path.join(folder, f"_renumber_{n}.jpg")
                os.replace(path, tmp)
                temp[n] = tmp
        for n, tmp in temp.items():
            os.replace(tmp, os.path.join(folder, f"{n}.jpg"))
            moved += 1
    listed = os.path.join(out, "captions.json")
    if os.path.isfile(listed):
        with open(listed, encoding="utf-8") as f:
            captions = json.load(f)
        captions = {(f"{int(os.path.splitext(k)[0])}.jpg" if os.path.splitext(k)[0].isdigit() else k): v
                    for k, v in captions.items()}
        with open(listed, "w", encoding="utf-8") as f:
            json.dump(captions, f, indent=2, ensure_ascii=False)
    print(f"{moved} picture(s) renamed in {out}")
    return moved


# ---------------------------------------------------------------- captions
# Text on a README / dtmmods.com picture (screenshots/<n>.jpg), explaining something. ModHub takes only
# unedited pictures, so captions never go into modhub/screenshots/ and no ModHub rule applies to them. The
# untouched picture stays in screenshots/originals/<n>.jpg and every caption is drawn on it afresh, so a
# caption can be changed or taken off (--clear) any time; screenshots/captions.json lists them. --site (from
# when captions could go to ModHub): a copy in screenshots/site/<n>.jpg, screenshots/<n>.jpg unchanged.


def font(size, bold):
    for name in (("segoeuib.ttf", "arialbd.ttf") if bold else ("segoeui.ttf", "arial.ttf")):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def wrap(draw, text, fnt, width):
    lines = []
    for para in text.split("\n"):
        line = ""
        for word in para.split():
            test = (line + " " + word).strip()
            if draw.textlength(test, font=fnt) <= width or not line:
                line = test
            else:
                lines.append(line)
                line = word
        lines.append(line)
    return lines


def draw_caption(im, title, text=None, at="bottom"):
    """A dark band across the picture with a heading and wrapped text; returns a new image."""
    im = im.convert("RGBA")
    w, h = im.size
    s = h / 1080
    pad, gap = int(56 * s), int(10 * s)
    ft, fx = font(int(46 * s), True), font(int(32 * s), False)
    probe = ImageDraw.Draw(im)
    tl = wrap(probe, title, ft, w - 2 * pad) if title else []
    xl = wrap(probe, text, fx, w - 2 * pad) if text else []
    lh_t, lh_x = int(58 * s), int(42 * s)
    band = pad // 2 + len(tl) * lh_t + (gap if tl and xl else 0) + len(xl) * lh_x + pad // 2
    y0 = h - band if at == "bottom" else 0
    over = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rectangle((0, y0, w, y0 + band), fill=(12, 20, 16, 178))
    d.rectangle((0, y0 + (0 if at == "bottom" else band - int(5 * s)), w, y0 + (int(5 * s) if at == "bottom" else band)),
                fill=(233, 199, 122, 255))
    y = y0 + pad // 2
    for line in tl:
        d.text((pad, y), line, font=ft, fill=(255, 255, 255, 255))
        y += lh_t
    y += gap if tl and xl else 0
    for line in xl:
        d.text((pad, y), line, font=fx, fill=(225, 232, 226, 255))
        y += lh_x
    return Image.alpha_composite(im, over).convert("RGB")


def caption(repo, number, title=None, text=None, at="bottom", clear=False, site=False):
    out = os.path.join(repo, "screenshots")
    path = numbered(out).get(number)
    if path is None:
        sys.exit(f"No picture {number} in {out}")
    name = os.path.basename(path)
    originals = os.path.join(out, "originals")
    original = os.path.join(originals, name)
    listed = os.path.join(out, "captions.json")
    captions = {}
    if os.path.isfile(listed):
        with open(listed, encoding="utf-8") as f:
            captions = json.load(f)
    if clear:
        if os.path.isfile(original):
            shutil.move(original, path)
        captions.pop(name, None)
        print(f"{name}: caption off, the original is back")
    else:
        if not title and not text:
            sys.exit("A caption needs a title or a text")
        if not os.path.isfile(original):
            os.makedirs(originals, exist_ok=True)
            shutil.copy2(path, original)
        with Image.open(original) as raw:
            raw.load()
            meta = from_comment(raw) or {}
            done = draw_caption(raw, title, text, at)
        if site:
            dst_dir = os.path.join(out, "site")
            os.makedirs(dst_dir, exist_ok=True)
            dst = os.path.join(dst_dir, name)
        else:
            dst = path
            meta["caption"] = "yes"
            captions[name] = {"title": title, "text": text, "at": at}
        done.save(dst, "JPEG", quality=90, optimize=True, comment=to_comment(meta))
        print(f"{dst}: caption \"{title or ''}\"" + (" (a copy; screenshots/" + name + " is unchanged)" if site else "")
              + " (README/site only; modhub/screenshots/ stays unedited)")
    if captions:
        with open(listed, "w", encoding="utf-8") as f:
            json.dump(captions, f, indent=2, ensure_ascii=False)
    elif os.path.isfile(listed):
        os.remove(listed)
    return True


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
    """The ModHub set (modhub/screenshots/) against the ModHub rules; the README set (screenshots/) listed."""
    hub, out = modhub_dir(repo), readme_dir(repo)
    files = list(numbered(hub).values())      # in number order: 2.jpg before 10.jpg
    ok = True

    def bad(msg):
        nonlocal ok
        print("! " + msg)
        ok = False

    print("ModHub set, modhub/screenshots/:")
    metas, hashes = {}, {}
    for f in files:
        name = os.path.basename(f)
        with Image.open(f) as im:
            im.load()
            if im.size != (MW, MH):
                bad(f"{name} is {im.size[0]}x{im.size[1]}, not {MW}x{MH}")
            metas[name] = from_comment(im)
            if (metas[name] or {}).get("caption") == "yes":
                bad(f"{name} has a caption: ModHub takes only unedited pictures (modhub {repo_name(repo)} <n> ... makes the set again)")
            for note in pixel_notes(im):
                print(f"? {name}: {note}")
            hashes[name] = dhash(im)
    if not files:
        bad("no ModHub set: pick puts one in modhub/screenshots/ (or modhub <repo> <n> ... from the README pictures)")
    elif len(files) < 3:
        bad(f"{len(files)} screenshot(s), ModHub wants at least 3")
    for extra in sorted(os.listdir(hub)) if os.path.isdir(hub) else []:
        if extra.lower().endswith(PICS) and os.path.join(hub, extra) not in files:
            print(f"? modhub/screenshots/{extra} isn't numbered (1.jpg, 2.jpg, ...): uploaded in which order?")

    names = list(hashes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if bin(hashes[a] ^ hashes[b]).count("1") <= SAME:
                print(f"? {a} and {b} look almost the same")

    if files:
        first = os.path.basename(files[0])
        m = metas.get(first)
        if not m or "kind" not in m:      # from elsewhere: only "from" is known
            print(f"? {first}: not from Screenshot Studio, so check by eye that it has no UI")
        elif m.get("hud") == "true" or m.get("kind") == "ui":
            bad(f"{first} is a {m.get('kind')} shot with HUD/menu; the first one must be without UI")
        working = [n for n, m in metas.items() if (m or {}).get("kind") == "burst"]
        if any(n in working for n in names[:3]):
            print("  in action: " + ", ".join(working))
        elif working:
            print(f"? the burst shot(s) {', '.join(working)} aren't among the first three: ModHub wants machinery at work there")
        else:
            print("? none is a burst shot: make sure one of the first three shows the machine working")
        for n, m in metas.items():
            if m and "kind" in m:
                print(f"  {n}  {label(m)}  (from {m.get('from', '?')})")
    print(f"{len(files)} screenshot(s) in {hub}" + (" - OK" if ok else ""))

    readme = list(numbered(out).values())
    print(f"README / dtmmods.com set, screenshots/: {len(readme)} picture(s)")
    for f in readme:
        with Image.open(f) as im:
            if im.size not in ((W, H), (MW, MH)):
                print(f"? {os.path.basename(f)} is {im.size[0]}x{im.size[1]}, not {W}x{H} (or {MW}x{MH})")
    listed = os.path.join(out, "captions.json")
    if os.path.isfile(listed):
        with open(listed, encoding="utf-8") as f:
            captions = json.load(f)
        for name, c in sorted(captions.items()):
            print(f"  {name}  caption: {c.get('title') or ''}" + (f" / {c['text']}" if c.get("text") else ""))

    print(f"Check the ModHub set by eye: no UI in picture 1; nothing added; no logos, links, version numbers; "
          f"no modder names ({MODDERS}) anywhere: monitor titles, mod lists, authors, farm names.")
    return ok


def repo_name(repo):
    return os.path.basename(os.path.normpath(repo))


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
    a.add_argument("--no-modhub", action="store_true", help="README/site only, not into modhub/screenshots/")
    k = sub.add_parser("pick"); k.add_argument("repo"); k.add_argument("folder"); k.add_argument("numbers", nargs="+", type=int)
    k.add_argument("--align", choices=["left", "center", "right"], default="center")
    k.add_argument("--no-modhub", action="store_true", help="README/site only, not into modhub/screenshots/")
    h = sub.add_parser("modhub"); h.add_argument("repo"); h.add_argument("numbers", nargs="+", type=int)
    sub.add_parser("check").add_argument("repo")
    sub.add_parser("studio").add_argument("folder", nargs="?")
    s = sub.add_parser("sheet"); s.add_argument("folder"); s.add_argument("--open", action="store_true")
    sub.add_parser("new").add_argument("--since")
    sub.add_parser("renumber").add_argument("repo")
    c = sub.add_parser("caption"); c.add_argument("repo"); c.add_argument("number", type=int)
    c.add_argument("title", nargs="?"); c.add_argument("text", nargs="?")
    c.add_argument("--at", choices=["bottom", "top"], default="bottom")
    c.add_argument("--clear", action="store_true", help="take the caption off (the original comes back)")
    c.add_argument("--site", action="store_true", help="a captioned copy in screenshots/site/, screenshots/<n>.jpg unchanged")
    args = p.parse_args(argv)
    if getattr(args, "repo", None):
        args.repo = find_repo(args.repo)
    if args.cmd == "check": return 0 if check(args.repo) else 1
    if args.cmd == "modhub": return 0 if modhub_set(args.repo, args.numbers) else 1
    if args.cmd == "renumber":
        renumber(args.repo)
        return 0
    if args.cmd == "caption":
        return 0 if caption(args.repo, args.number, args.title, args.text, args.at, args.clear, args.site) else 1
    if args.cmd == "add": add(args.repo, args.images, args.align, modhub=not args.no_modhub)    # one at a time is fine
    elif args.cmd == "pick": pick(args.repo, args.folder, args.numbers, args.align, not args.no_modhub)
    elif args.cmd == "studio": studio(args.folder)
    elif args.cmd == "sheet": sheet(args.folder, open_it=args.open)
    else: new(args.since)
    return 0


if __name__ == "__main__":
    sys.exit(main())
