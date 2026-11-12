# DTM Screenshot Studio

A tool for modders: the game takes the screenshots of your mod for the GIANTS ModHub and dtmmods.com. **Single player only** (the mod switches itself off in multiplayer), and it never goes on the server or the ModHub.

| Key | What it does |
|-----|--------------|
| **Right Ctrl + 1** | **Clean shot**: the current view without HUD |
| **Right Ctrl + 2** | **Orbit**: 12 shots from all around the vehicle you sit in (with everything attached), or the nearest building when you're on foot: 8 in a ring, 4 low three-quarter "hero" views |
| **Right Ctrl + 3** | **UI shot**: waits 5 seconds (open the menu meanwhile), then saves the screen with the menu |
| **Right Ctrl + 4** | **Golden hour**: 18:30 and sunshine; press again for the old time back (same day, so crops don't grow) |

The keys can be changed in Options > Controls. Pictures go to `Documents/My Games/FarmingSimulator2025/modSettings/FS25_ScreenshotStudio/<mod name>/`. The folder is the mod of what you photograph: an implement from a mod wins over a base-game tractor (the PX150 XL header on a MacDon M1240 goes to `FS25_PX150XL`).

## From the game to the repo

1. Load a single-player save, put the machine somewhere nice, **Right Ctrl + 4** for golden hour.
2. Sit in it and press **Right Ctrl + 2**. Hands off for about 15 seconds while the camera goes round.
3. Drive it into work and press **Right Ctrl + 1** for the "in action" shot (ModHub wants one). For script mods, open the mod's screen and use **Right Ctrl + 3**.
4. Pick the best ones:
   ```
   python tools/fs25_screenshots.py studio                     what's been taken, per mod
   python tools/fs25_screenshots.py sheet FS25_PX150XL         numbered contact sheet (_sheet.jpg)
   python tools/fs25_screenshots.py pick C:\Programming\...\FS25_PX150XL FS25_PX150XL 4 11 2
   ```
   `pick` puts them into the repo's `screenshots/` folder as `01.jpg`, `02.jpg`, ... in the order you give: **the first one is the clean hero shot** (no HUD, no text).
5. `python tools/fs25_screenshots.py check <repo>` makes sure there are at least 3, all 1920x1080.

The shared DTM build never puts `screenshots/` into the mod zip, so they don't count against the 128-file limit.

## ModHub screenshot rules

From the GIANTS ModHub Guidelines (v5.9.1, item 5.1):

- at least **3 screenshots**, one with the machine or tool **in an actual work environment**
- the **first one**: no HUD and no text
- text only in English; no logos, watermarks, links, credits or version numbers; no white background
- the shop picture (store image) doesn't count as a screenshot

## How the pictures are taken

`renderScreenshot` renders the 3D view at exactly 1920x1080 whatever your monitor is, without the HUD and without other mods' overlays (Courseplay, AutoDrive). GIANTS doesn't document it, so the first shot tries its formats one by one and remembers the first that writes a file (`settings.xml`). If none does, the mod hides the HUD and saves the screen instead; on an ultrawide monitor `fs25_screenshots.py` then crops the middle 16:9 (put the subject in the middle of the screen).

## Console

| Command | |
|---------|--|
| `ssShot` | clean shot |
| `ssOrbit [count] [distance]` | orbit with `count` ring shots (8) at `distance` metres (by size) |
| `ssUi [seconds]` | UI shot after `seconds` (5) |
| `ssGolden [hour]` | golden hour on/off at `hour` (18.5) |
| `ssFolder [name]` | folder for the next shots (e.g. `FS25_Searchables` for UI shots); empty = automatic |
| `ssRadius [metres]` | how big buildings are for the orbit (18) |
| `ssMethod [render_png\|render_jpg\|screen]` | force how pictures are taken; empty = find it again |
| `ssProbe` | tries every screenshot call and writes the results to the log (`modSettings/FS25_ScreenshotStudio/probe/`) |

## Tests

`python tests/test_screenshot_studio.py` runs the script against stubbed engine functions (needs Python `lupa`).

## License

MIT, see [LICENSE.txt](LICENSE.txt).
