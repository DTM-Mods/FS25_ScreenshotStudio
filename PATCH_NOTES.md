# DTM Screenshot Studio: patch notes

The release page of a version takes its text from the section of that version here.

## 0.2.2.4

- With ModMux installed, **ssQuiet** (hide other mods' drawing during shots) and **ssClear** (framed views move around
  things in the way) are also switches on ModMux's LIVE tab, and ModMux remembers them between loads.

## 0.2.2.3

- The author now shows as **DTM Mods, Fennell** in the mod list.

## 0.2.2.2

- **Clicking in menus:** `ssClick` presses a button on the open dialog or screen by its text or id, for example a page's own tabs (Player Trading+'s Incoming, Outgoing, Standing orders). Only buttons that show; a disabled one isn't pressed.
- **Tabs:** `ssTab` switches a tab of the open page (Settings > Controls) or another page of the open screen.
- **Typing:** `ssType qty 20000` writes into the field whose id has the first word in it.
- **Wider views:** `ssView 35 50 3` takes the framed shots from three times as far, with more of the surroundings in the picture.
- **Cleaner menu shots:** other mods' own drawing (AutoDrive lines and the like) stays hidden in UI shots, while the menus still draw.
- **Pages that don't open:** the log says why (the page's own enabled check, the page the menu is on, which pages are off).
- **Runner:** `--without-mod FS25_OldMod` switches a mod off in the save for that run only, for one that clashes with the mod being photographed. The mod list is put back afterwards.
- **Picking:** pictures are numbered 1.jpg, 2.jpg and so on; `renumber` turns an older set into plain numbers.

## 0.2.1.6

- **Menu shots:** `ssMenu` opens a screen, dialog or in-game menu page by name, mods' pages too (`ssMenu` alone lists them all), checks that the page really shows, and closes it again. `ssType tractor` writes text straight into the screen's search field: the shop with Searchables shows its results without any typing.
- **Runner:** the `menus` plan with `--menu` and `--folder` takes a UI shot of each menu; autorun steps go on while a menu pauses the game; a UI shot of a page that didn't open is skipped.
- **Typing keys** (`ssKeys`) holds each key longer and waits after a chord like Ctrl+F.

## 0.2.1.3

- The release now has two zips: `FS25_ScreenshotStudio.zip` (the mod, into the mods folder) and `ScreenshotStudio_Tools.zip` (the game runner, contact sheets, picking, captions, checks and their shortcuts; unzip it anywhere, needs Python 3 with Pillow).
- The mod itself is unchanged from 0.2.1.2 apart from its version number.

## 0.2.1.2

First release. A tool for modders: the game takes the screenshots of a mod for the GIANTS ModHub and dtmmods.com.

- **Shots:** clean shot, orbit (12 framed views), UI shot, burst while working, every shop color (with the hitched header or trailer recolored too), four light presets.
- **Framing:** the camera frames the whole machine from its size, work areas and parts; buildings by their placement area. Walls, poles, cars and tree crowns in the way are avoided.
- **Targets:** `ssTarget` picks any vehicle, implement or building by name; `ssMove` takes a machine with what is hitched to it to an open place and back.
- **Clean pictures:** other mods' drawing (Courseplay, AutoDrive) and the game's hints are hidden during shots.
- **Menus:** `ssMenu` opens screens and in-game menu pages (mods' pages too) for UI shots.
- **Tools (ScreenshotStudio_Tools.zip):** a runner that starts the game with a save, takes a whole plan of pictures by itself and quits; contact sheets, picking into the repo, captions within the ModHub rules, and checks of the ModHub screenshot rules.
