# ModHub upload: DTM Screenshot Studio

What to enter in the GIANTS ModHub upload form for this mod. Each text box below has a copy button on GitHub.

<img src="icon_512.png" alt="Mod icon" width="160">

**Mod Icon (512x512):** [`icon_512.png`](icon_512.png)

| Field | Value |
|-------|-------|
| Title English | DTM Screenshot Studio |
| Title German | DTM Screenshot Studio |
| Title French | DTM Screenshot Studio |
| Version | `0` `2` `2` `3` |
| Author | DTM Mods, Fennell |
| Manufacturer | Lizard |
| Category 1 | Gameplay |
| Category 2 | Not Set |
| Category 3 | Not Set |

## Title English
```text
DTM Screenshot Studio
```

## Title German
```text
DTM Screenshot Studio
```

## Title French
```text
DTM Screenshot Studio
```

## Description English
```text
A tool for modders: the game takes the screenshots of your mod for the ModHub and your website. Park your machine or building somewhere nice, press a key and get framed pictures without the HUD, at 1920x1080 where the game allows it. Single player only.

- Right Ctrl + 1: clean shot of the current view, without HUD.
- Right Ctrl + 2: orbit. 12 framed shots from all around the vehicle you sit in (with everything attached) or the nearest building.
- Right Ctrl + 3: UI shot. Waits 5 seconds so you can open a menu, then saves the screen with the menu.
- Right Ctrl + 4: light. Golden hour, morning mist, midday sun and overcast; one more press brings the old time back.
- Right Ctrl + 5: burst. A clean shot every 3 seconds for a minute while you work.
- Right Ctrl + 6: every color. The same view once in each shop color; your vehicle itself doesn't change.
- Walls, poles and tree crowns in the way are avoided; other mods' screen drawing is hidden during shots.

How to use: pictures go to modSettings/FS25_ScreenshotStudio/<mod name>/. The keys can be changed in Options > Controls.

Changelog 0.2.2.2:
- New console commands ssClick, ssTab and ssType: press buttons, switch tabs and type into menus.
- ssView can take the framed shots from further away.
- Pictures are numbered 1.jpg, 2.jpg and so on.
```

## Description German
```text
Ein Werkzeug für Modder: Das Spiel nimmt die Screenshots deiner Mod für den ModHub und deine Webseite auf. Stell dein Fahrzeug oder Gebäude hin, drück eine Taste und du bekommst gerahmte Bilder ohne HUD, in 1920x1080, wo das Spiel es erlaubt. Nur Einzelspieler.

- Rechte Strg + 1: sauberes Bild der aktuellen Ansicht, ohne HUD.
- Rechte Strg + 2: Rundum. 12 Bilder von allen Seiten des Fahrzeugs, in dem du sitzt (mit allem Angehängten), oder des nächsten Gebäudes.
- Rechte Strg + 3: Menü-Bild. Wartet 5 Sekunden, damit du ein Menü öffnen kannst, und speichert dann den Bildschirm mit dem Menü.
- Rechte Strg + 4: Licht. Goldene Stunde, Morgennebel, Mittagssonne und bewölkt; ein weiterer Druck bringt die alte Uhrzeit zurück.
- Rechte Strg + 5: Serie. Eine Minute lang alle 3 Sekunden ein sauberes Bild, während du arbeitest.
- Rechte Strg + 6: Jede Farbe. Dieselbe Ansicht einmal in jeder Shop-Farbe; dein Fahrzeug selbst bleibt, wie es ist.
- Wände, Masten und Baumkronen im Weg werden umgangen; was andere Mods auf den Bildschirm zeichnen, ist während der Bilder ausgeblendet.

So geht's: Die Bilder landen in modSettings/FS25_ScreenshotStudio/<Modname>/. Die Tasten lassen sich unter Optionen > Steuerung ändern.

Changelog 0.2.2.2:
- Neue Konsolenbefehle ssClick, ssTab und ssType: Knöpfe drücken, Reiter wechseln und in Menüs tippen.
- ssView kann die gerahmten Bilder aus größerer Entfernung aufnehmen.
- Die Bilder sind durchnummeriert: 1.jpg, 2.jpg und so weiter.
```

## Description French
```text
Un outil pour les moddeurs : le jeu prend les captures d'écran de votre mod pour le ModHub et votre site. Placez votre véhicule ou bâtiment, appuyez sur une touche et obtenez des images cadrées sans HUD, en 1920x1080 quand le jeu le permet. Solo uniquement.

- Ctrl droit + 1 : image propre de la vue actuelle, sans HUD.
- Ctrl droit + 2 : tour complet. 12 images cadrées tout autour du véhicule où vous êtes assis (avec tout ce qui est attelé) ou du bâtiment le plus proche.
- Ctrl droit + 3 : image de menu. Attend 5 secondes pour que vous ouvriez un menu, puis enregistre l'écran avec le menu.
- Ctrl droit + 4 : lumière. Heure dorée, brume matinale, soleil de midi et ciel couvert ; un appui de plus remet l'heure d'avant.
- Ctrl droit + 5 : rafale. Une image propre toutes les 3 secondes pendant une minute, pendant que vous travaillez.
- Ctrl droit + 6 : chaque couleur. La même vue une fois dans chaque couleur du magasin ; votre véhicule lui-même ne change pas.
- Les murs, poteaux et cimes d'arbres gênants sont évités ; ce que les autres mods dessinent à l'écran est masqué pendant les prises.

Utilisation : les images vont dans modSettings/FS25_ScreenshotStudio/<nom du mod>/. Les touches se changent dans Options > Commandes.

Changelog 0.2.2.2 :
- Nouvelles commandes de console ssClick, ssTab et ssType : appuyer sur des boutons, changer d'onglet et taper dans les menus.
- ssView peut prendre les images cadrées de plus loin.
- Les images sont numérotées 1.jpg, 2.jpg, etc.
```

## Before uploading

- Owner's decision whether this goes to ModHub at all: it is a modding tool, single player only (it switches itself off in multiplayer), and the website says it never goes on a server or the ModHub. GIANTS may not accept a developer tool.
- The companion download `ScreenshotStudio_Tools.zip` (Python tools) cannot go on ModHub; the texts above do not mention it.
- Missing translations in the mod itself: there is no French at all (modDesc and `translations/` have only English and German). The French texts here do not add French to the mod.
- The German description in modDesc.xml is older than the text above (no 12 orbit shots, no changelog); update it if the in-game text should match.
