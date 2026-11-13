# DTM Screenshot Studio: patch notes

The release page of a version takes its text from the section of that version here.

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
