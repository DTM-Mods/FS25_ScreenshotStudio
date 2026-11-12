"""Offline test of ScreenshotStudio.lua: the game's engine functions are stubbed in Lua (lupa).

    python tests/test_screenshot_studio.py

Checks the orbit (camera positions, aim, restoring camera and HUD), finding the screenshot
method (render writes nothing here, so it must fall back to the screen), the UI countdown and
golden hour. lupa is Lua 5.5; the mod targets 5.1, so the script avoids 5.2+ syntax anyway.
"""
import math, os, sys
from lupa import LuaRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lua = LuaRuntime(unpack_returned_tuples=True)

STUBS = r'''
unpack = unpack or table.unpack
math.atan2 = math.atan2 or function(y, x) return math.atan(y, x) end   -- Lua 5.1 has it, 5.5 doesn't
T = { now = 100.0, files = {}, nodes = {}, nextNode = 1, logs = {}, notes = {}, renderCalls = 0, saveCalls = 0,
      writeRender = false, folders = {}, commands = {} }
function getTimeSec() return T.now end
function print(s) table.insert(T.logs, s) end
function getDate(f) return "20261112_120000" end
function getUserProfileAppPath() return "C:/profile/" end
function createFolder(p) T.folders[p] = true end
function fileExists(p) return T.files[p] == true end
function loadXMLFile() return 0 end
function createXMLFile(name, path) T.settingsPath = path; return 1 end
function setXMLString(x, k, v) T.settingsValue = v end
function getXMLString() return nil end
function saveXMLFile() end
function delete(n) end
function renderScreenshot(path, w, h, aspect, fmt, ...)
    T.renderCalls = T.renderCalls + 1
    assert(w == 1920 and h == 1080, "render size")
    if T.writeRender then T.files[path] = true end
end
function saveScreenshot(path) T.saveCalls = T.saveCalls + 1; T.files[path] = true end
local function newNode(x, y, z) local id = T.nextNode; T.nextNode = id + 1; T.nodes[id] = {x = x or 0, y = y or 0, z = z or 0, dir = {0, 0, 1}}; return id end
function createCamera() return newNode() end
function getRootNode() return 0 end
function link() end
function setFastShadowUpdate() end
function setWorldTranslation(n, x, y, z) local o = T.nodes[n]; o.x, o.y, o.z = x, y, z end
function getWorldTranslation(n) local o = T.nodes[n]; return o.x, o.y, o.z end
function setDirection(n, dx, dy, dz, ux, uy, uz) T.nodes[n].dir = {dx, dy, dz} end
function localDirectionToWorld(n, x, y, z) local d = T.nodes[n].dir; return d[1], d[2], d[3] end
function getTerrainHeightAtWorldPos(t, x, y, z) return 100 end
function addConsoleCommand(name, desc, fn, target) T.commands[name] = {fn, target} end
function removeConsoleCommand(name) T.commands[name] = nil end
function addModEventListener(l) T.listener = l end
MathUtil = { vector2Length = function(x, z) return math.sqrt(x * x + z * z) end }
Utils = { appendedFunction = function(a, b) return function(...) if a then a(...) end b(...) end end }
PlayerInputComponent = { registerGlobalPlayerActionEvents = function() end }
InputAction = { SS_CLEAN_SHOT = 1, SS_ORBIT = 2, SS_UI_SHOT = 3, SS_GOLDEN_HOUR = 4 }
T.actions = {}
g_inputBinding = { registerActionEvent = function(self, a, target, cb) T.actions[a] = cb; return true, a end,
                   setActionEventTextVisibility = function() end }
Gui = { update = function() end }
FSBaseMission = { INGAME_NOTIFICATION_OK = 1 }
g_cameraManager = { active = 999, cams = {},
    addCamera = function(self, c) self.cams[c] = true end,
    removeCamera = function(self, c) self.cams[c] = nil end,
    getActiveCamera = function(self) return self.active end,
    setActiveCamera = function(self, c) self.active = c end }
local hud = { visible = true }
function hud:getIsVisible() return self.visible end
function hud:setIsVisible(v) self.visible = v end
T.env = { currentMonotonicDay = 10, currentDay = 10, dayTime = 8 * 3600000, daysPerPeriod = 1,
    lighting = { update = function() end },
    weather = { consoleCommandWeatherSet = function(self, t) T.weather = t end } }
function T.env:setEnvironmentTime(md, d, t, dpp, delta) self.currentMonotonicDay, self.currentDay, self.dayTime = md, d, t end
g_currentMission = { hud = hud, missionDynamicInfo = { isMultiplayer = false }, terrainRootNode = 5,
    environment = T.env, placeableSystem = { placeables = {} },
    addIngameNotification = function(self, kind, text) table.insert(T.notes, text) end }
-- a tractor facing +X at (100, 100, 50) with a mod implement
local tractorNode = newNode(100, 100, 50); T.nodes[tractorNode].dir = {1, 0, 0}
local implNode = newNode(94, 100, 50)
local implement = { rootNode = implNode, size = { length = 6, width = 9, height = 3 }, customEnvironment = "FS25_PX150XL" }
T.tractor = { rootNode = tractorNode, size = { length = 6, width = 3, height = 3 }, customEnvironment = nil }
function T.tractor:getRootVehicle() return self end
function T.tractor:getChildVehicles() return { self, implement } end
function T.tractor:getName() return "M1240" end
g_localPlayer = { vehicle = T.tractor }
function g_localPlayer:getCurrentVehicle() return self.vehicle end
function g_localPlayer:getPosition() return 0, 100, 0 end
g_currentModName = "FS25_ScreenshotStudio"
g_currentModDirectory = "C:/mods/FS25_ScreenshotStudio/"
'''
lua.execute(STUBS)
lua.execute(open(os.path.join(ROOT, 'scripts', 'ScreenshotStudio.lua'), encoding='utf-8').read())
T, SS, G = lua.eval('T'), lua.eval('ScreenshotStudio'), lua.globals()

failures = []
def check(cond, msg):
    print(('ok   ' if cond else 'FAIL ') + msg)
    if not cond:
        failures.append(msg)

def run(seconds, step=0.05):
    for _ in range(int(seconds / step)):
        T.now = T.now + step
        SS.update(SS, 16)
        SS.draw(SS)

SS.loadMap(SS)
check(all(T.commands[c] is not None for c in ['ssShot', 'ssOrbit', 'ssUi', 'ssGolden', 'ssFolder', 'ssRadius', 'ssProbe', 'ssMethod']), 'console commands registered')
G.PlayerInputComponent.registerGlobalPlayerActionEvents(None)
check(all(T.actions[i] is not None for i in range(1, 5)), 'four key actions registered')

# --- orbit with an unknown method: render writes nothing -> falls back to the screen
t = SS.getOrbitTarget(SS)
check(t.mod == 'FS25_PX150XL', f'orbit folder is the implement mod ({t.mod})')
check(abs(t.yaw - math.pi / 2) < 1e-6, 'orbit starts from the vehicle front')
T.actions[2](SS)
check(G.g_currentMission.hud.visible is False, 'HUD hidden during the orbit')
check(G.g_cameraManager.active == SS.camera, 'orbit camera is active')
cam = T.nodes[SS.camera]
dx, dy, dz = t.x - cam.x, t.y - cam.y, t.z - cam.z
d = cam.dir   # the camera's +Z; it looks along -Z, so -dir must point at the target
cos = -(d[1] * dx + d[2] * dy + d[3] * dz) / (math.sqrt(d[1]**2 + d[2]**2 + d[3]**2) * math.sqrt(dx*dx + dy*dy + dz*dz))
check(cos > 0.9999, 'camera looks at the target')
check(cam.y >= 101.2, 'camera stays above the ground')
run(40)
check(SS.session is None, 'orbit finished')
check(SS.method == 'screen', f'method found: {SS.method}')
check(T.settingsValue == 'screen', 'method saved in settings.xml')
saved = [k for k in T.files.keys() if 'FS25_PX150XL/orbit_' in k]
check(len(saved) == 12, f'12 orbit pictures (8 ring + 4 low): {len(saved)}')
check(G.g_cameraManager.active == 999, 'previous camera restored')
check(G.g_currentMission.hud.visible is True, 'HUD visible again')
check(T.renderCalls == 2, f'render tried once per format before falling back ({T.renderCalls})')

# --- next time the method is known: no more render attempts
T.renderCalls = 0
SS.consoleShot(SS)
run(2)
check(T.renderCalls == 0 and any('FS25_PX150XL/clean_' in k for k in T.files.keys()), 'clean shot uses the saved method')

# --- render works: ssMethod finds it again and keeps render_png
T.writeRender = True
SS.consoleMethod(SS, '')
SS.consoleShot(SS)
run(4)
check(SS.method == 'render_png', f'render_png found when it writes files ({SS.method})')
check(SS.consoleMethod(SS, 'nonsense').startswith('Unknown method'), 'ssMethod rejects unknown names')

# --- UI shot: keeps the HUD, waits, always uses the screen
T.saveCalls = 0
SS.consoleFolder(SS, 'FS25_Searchables')
SS.consoleUi(SS, '3')
check(G.g_currentMission.hud.visible is True, 'UI shot keeps the HUD')
run(2.5)
check(T.saveCalls == 0, 'UI shot waits for the countdown')
G.Gui.update()   # the countdown also runs from the GUI's update
run(1)
check(T.saveCalls == 1 and any('FS25_Searchables/ui_' in k for k in T.files.keys()), 'UI shot saved in the forced folder')

# --- busy and multiplayer
SS.consoleOrbit(SS)
check(SS.consoleShot(SS) == 'Busy or not possible', 'second batch refused while busy')
run(40)
G.g_currentMission.missionDynamicInfo.isMultiplayer = True
check(SS.consoleShot(SS) == 'Busy or not possible', 'refused in multiplayer')
G.g_currentMission.missionDynamicInfo.isMultiplayer = False

# --- golden hour on and off
env = T.env
msg = SS.toggleGolden(SS)
check(env.dayTime == int(18.5 * 3600000) and env.currentDay == 10 and T.weather == 'SUN', f'golden hour: 18:30, same day, sunny ({msg})')
SS.toggleGolden(SS)
check(env.dayTime == 8 * 3600000 and env.currentDay == 10, 'golden hour off: old time back')

# --- on foot near a mod building
G.g_localPlayer.vehicle = None
node = lua.eval('function(x, y, z) local id = T.nextNode; T.nextNode = id + 1; T.nodes[id] = {x = x, y = y, z = z, dir = {0, 0, 1}}; return id end')(30, 100, 40)
G.g_currentMission.placeableSystem.placeables[1] = lua.table_from({'rootNode': node, 'customEnvironment': 'FS25_PigBarnWithRobot'})
t = SS.getOrbitTarget(SS)
check(t is not None and t.mod == 'FS25_PigBarnWithRobot' and t.radius == 18, 'on foot: nearest mod building')

SS.deleteMap(SS)
check(SS.camera is None and T.commands['ssShot'] is None, 'deleteMap removes camera and commands')

print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
