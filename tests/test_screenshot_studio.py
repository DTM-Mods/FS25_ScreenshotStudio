"""Offline test of ScreenshotStudio.lua: the game's engine functions are stubbed in Lua (lupa).

    python tests/test_screenshot_studio.py

Checks the orbit (camera positions, aim, restoring camera and HUD), finding the screenshot
method (render writes nothing here, so it must fall back to the screen), the UI countdown, the
light presets, the burst, every color (copies loaded and deleted, the vehicle hidden and shown
again) and the _shots_*.xml lists. lupa is Lua 5.5; the mod targets 5.1, so the script avoids
5.2+ syntax anyway.
"""
import math, os, re, sys
from lupa import LuaRuntime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
lua = LuaRuntime(unpack_returned_tuples=True)

STUBS = r'''
unpack = unpack or table.unpack
math.atan2 = math.atan2 or function(y, x) return math.atan(y, x) end   -- Lua 5.1 has it, 5.5 doesn't
T = { now = 100.0, files = {}, nodes = {}, nextNode = 1, logs = {}, notes = {}, renderCalls = 0, saveCalls = 0,
      writeRender = false, folders = {}, commands = {}, xml = {}, nextXml = 1, xmlSaved = {}, loads = {},
      deleted = {}, loadDelay = 0.5, loadFails = {}, loadLog = {} }
function getTimeSec() return T.now end
function print(s) table.insert(T.logs, s) end
T.date = "20261112_120000"
function getDate(f) return T.date end
function getUserProfileAppPath() return "C:/profile/" end
function createFolder(p) T.folders[p] = true end
function fileExists(p) return T.files[p] == true or T.xmlFiles[p] ~= nil end
T.xmlFiles = {}    -- path -> { key = value }: files the mod can read
function loadXMLFile(name, path)
    local values = T.xmlFiles[path]
    if values == nil then return 0 end
    local id = T.nextXml; T.nextXml = id + 1; T.xml[id] = { path = path, values = values }; return id
end
function deleteFile(p) T.xmlFiles[p] = nil; T.files[p] = nil end
function doExit() T.exited = true end
function createXMLFile(name, path, root) local id = T.nextXml; T.nextXml = id + 1; T.xml[id] = { path = path, values = {} }; return id end
function setXMLString(x, k, v) T.xml[x].values[k] = v end
function getXMLString(x, k) local o = T.xml[x]; return o ~= nil and o.values[k] or nil end
function saveXMLFile(x) T.xmlSaved[T.xml[x].path] = T.xml[x].values end
function delete(n) end
T.SETTINGS = "C:/profile/modSettings/FS25_ScreenshotStudio/settings.xml"
function renderScreenshot(path, w, h, aspect, fmt, ...)
    T.renderCalls = T.renderCalls + 1
    assert(w == 1920 and h == 1080, "render size")
    -- what GIANTS' editor passes after the format (saveBillboards.lua)
    local a, want = { ... }, { 0, 0.0, 0.0, 0.0, 0.0, 3, 12, false }
    assert(select("#", ...) == #want, "render argument count " .. select("#", ...))
    for i = 1, #want do assert(a[i] == want[i], "render argument " .. (i + 5)) end
    local s = T.xmlSaved[T.SETTINGS]
    T.tryingAtRender = s ~= nil and s["screenshotStudio.trying"] or nil
    if T.writeRender then T.files[path] = true end
end
function saveScreenshot(path) T.saveCalls = T.saveCalls + 1; T.files[path] = true end
-- what other mods draw with; AutoDrive's drawing manager sits in its own mod environment
T.drawn = 0
function renderText() T.drawn = T.drawn + 1 end
function renderOverlay() T.drawn = T.drawn + 1 end
-- like an engine function the global table only gets from its metatable (rawget finds nothing)
setmetatable(_G, { __index = { drawFilledRect = function() T.drawn = T.drawn + 1 end } })
function drawDebugLine() T.drawn = T.drawn + 1 end
T.originalRenderText = renderText
FS25_AutoDrive = { ADDrawingManager = { lines = 0 } }
function FS25_AutoDrive.ADDrawingManager:addLineTask() self.lines = self.lines + 1 end
-- Courseplay with its own copy in its environment; another mod whose environment looks names up
-- in a separate table (not the global one)
FS25_Courseplay = { renderText = function() T.drawn = T.drawn + 1 end }
T.cpRenderText = FS25_Courseplay.renderText
T.safeGlobals = { renderOverlay = function() T.drawn = T.drawn + 1 end }
FS25_OtherMod = setmetatable({}, { __index = T.safeGlobals })
g_modManager = { getActiveMods = function(self)
    return { { modName = "FS25_AutoDrive" }, { modName = "FS25_Courseplay" }, { modName = "FS25_OtherMod" },
             { modName = "FS25_ScreenshotStudio" } } end }
function T.otherModsDraw()
    renderText(); renderOverlay(); drawFilledRect(); drawDebugLine()
    FS25_AutoDrive.ADDrawingManager:addLineTask()
    FS25_Courseplay.renderText(); FS25_OtherMod.renderOverlay()
end
function T.newNode(x, y, z) local id = T.nextNode; T.nextNode = id + 1; T.nodes[id] = {x = x or 0, y = y or 0, z = z or 0, dir = {0, 0, 1}, rot = {0, 0, 0}, visible = true}; return id end
local newNode = T.newNode
function createCamera() return newNode() end
function getRootNode() return 0 end
function link() end
function setFastShadowUpdate() end
function setWorldTranslation(n, x, y, z) local o = T.nodes[n]; o.x, o.y, o.z = x, y, z end
function getWorldTranslation(n) local o = T.nodes[n]; return o.x, o.y, o.z end
function getWorldRotation(n) local r = T.nodes[n].rot; return r[1], r[2], r[3] end
function setDirection(n, dx, dy, dz, ux, uy, uz) T.nodes[n].dir = {dx, dy, dz} end
function worldToLocal(n, x, y, z)
    local o = T.nodes[n]; local d = o.dir; local len = math.sqrt(d[1] * d[1] + d[3] * d[3])
    local fx, fz = d[1] / len, d[3] / len
    local dx, dz = x - o.x, z - o.z
    return dx * fz - dz * fx, y - o.y, dx * fx + dz * fz
end
-- obstacles: spheres { id, x, y, z, r }; raycastClosest calls back at once, like the game
T.obstacles, T.nodeObjects = {}, {}
CollisionFlag = { DEFAULT = 1, TREE = 2, DYNAMIC_OBJECT = 4, VEHICLE = 8, BUILDING = 16, STATIC_OBJECT = 32, TERRAIN = 64 }
function raycastClosest(x, y, z, dx, dy, dz, maxDist, cb, target, mask)
    local best, bestT
    for _, o in ipairs(T.obstacles) do
        local ox, oy, oz = x - o.x, y - o.y, z - o.z
        local b = ox * dx + oy * dy + oz * dz
        local c = ox * ox + oy * oy + oz * oz - o.r * o.r
        local disc = b * b - c
        if disc >= 0 then
            local t = -b - math.sqrt(disc)
            if t >= 0 and t <= maxDist and (bestT == nil or t < bestT) then best, bestT = o, t end
        end
    end
    if best ~= nil then target[cb](target, best.id, x + dx * bestT, y + dy * bestT, z + dz * bestT, bestT) end
end
-- local x right, y up, z forward (the node's dir, flat)
function localToWorld(n, x, y, z)
    local o = T.nodes[n]; local d = o.dir; local len = math.sqrt(d[1] * d[1] + d[3] * d[3])
    local fx, fz = d[1] / len, d[3] / len
    return o.x + x * fz + z * fx, o.y + y, o.z - x * fx + z * fz
end
function localDirectionToWorld(n, x, y, z) local d = T.nodes[n].dir; return d[1], d[2], d[3] end
function getVisibility(n) return T.nodes[n].visible end
function setVisibility(n, v) T.nodes[n].visible = v end
function getTerrainHeightAtWorldPos(t, x, y, z) return 100 end
function addConsoleCommand(name, desc, fn, target) T.commands[name] = {fn, target} end
function removeConsoleCommand(name) T.commands[name] = nil end
function addModEventListener(l) T.listener = l end
MathUtil = { vector2Length = function(x, z) return math.sqrt(x * x + z * z) end }
Utils = { appendedFunction = function(a, b) return function(...) if a then a(...) end b(...) end end }
PlayerInputComponent = { registerGlobalPlayerActionEvents = function() end }
InputAction = { SS_CLEAN_SHOT = 1, SS_ORBIT = 2, SS_UI_SHOT = 3, SS_GOLDEN_HOUR = 4, SS_BURST = 5, SS_COLORS = 6 }
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

-- weather and fog, the way FS25_RealisticWeather uses them
WeatherType = { SUN = 1, CLOUDY = 2, RAIN = 3, SNOW = 4 }
local fogTemplate = {}
function fogTemplate:createFromTemplate() return { groundFogWeatherTypes = {}, groundFogStartDayTimeMinutes = 300 } end
T.fogUpdater = { targetFog = "gameFog" }
function T.fogUpdater:setTargetFog(fog, time) self.targetFog = fog end
T.env = { currentMonotonicDay = 10, currentDay = 10, dayTime = 8 * 3600000, daysPerPeriod = 1, currentSeason = 3,
    lighting = { update = function() end },
    weather = { fogUpdater = T.fogUpdater, seasonToFog = { [3] = fogTemplate },
                consoleCommandWeatherSet = function(self, t) T.weather = t end } }
function T.env:setEnvironmentTime(md, d, t, dpp, delta) self.currentMonotonicDay, self.currentDay, self.dayTime = md, d, t end

-- loading vehicles: VehicleLoadingData calls back after T.loadDelay seconds (T.tickLoads)
VehicleLoadingState = { OK = 1, ERROR = 2 }
VehicleLoadingData = {}
VehicleLoadingData.__index = VehicleLoadingData
function VehicleLoadingData.new() return setmetatable({ addToPhysics = true, isSaved = true }, VehicleLoadingData) end
function VehicleLoadingData:setStoreItem(item) self.storeItem = item end
function VehicleLoadingData:setConfigurations(c) self.configurations = c end
function VehicleLoadingData:setPosition(x, y, z) self.pos = {x, y, z} end
function VehicleLoadingData:setRotation(x, y, z) self.rot = {x, y, z} end
function VehicleLoadingData:setIgnoreShopOffset(v) self.ignoreShopOffset = v end
function VehicleLoadingData:setAddToPhysics(v) self.addToPhysics = v end
function VehicleLoadingData:setIsSaved(v) self.isSaved = v end
function VehicleLoadingData:setOwnerFarmId(id) self.farmId = id end
function VehicleLoadingData:load(cb, target, args)
    table.insert(T.loadLog, { file = self.storeItem.xmlFilename, cfg = self.configurations, config = args.config })
    table.insert(T.loads, { data = self, cb = cb, target = target, args = args, at = T.now + T.loadDelay })
end
function T.tickLoads()
    for i = #T.loads, 1, -1 do
        local l = T.loads[i]
        if T.now >= l.at then
            table.remove(T.loads, i)
            local id = l.data.configurations[l.args.config or l.args.shot.config]
            if T.loadFails[id] and l.args.shot.config == "baseColor" then
                l.cb(l.target, {}, VehicleLoadingState.ERROR, l.args)
            else
                local node = T.newNode(l.data.pos[1], l.data.pos[2], l.data.pos[3])
                local copy = { rootNode = node, components = { { node = node } }, data = l.data, colorId = id }
                function copy:delete() table.insert(T.deleted, self.colorId) end
                function copy:setAbsolutePosition(x, y, z, rx, ry, rz, positions) self.placed = { x, y, z, positions } end
                T.lastCopy = copy
                l.cb(l.target, { copy }, VehicleLoadingState.OK, l.args)
            end
        end
    end
end
ConfigurationUtil = { SELECTOR_COLOR = 2, SELECTOR_MULTIOPTION = 1 }
g_vehicleConfigurationManager = { getConfigurationSelectorType = function(self, name)
    return name:find("Color") and 2 or 1 end }
T.storeItem = { xmlFilename = "px150xl.xml", configurations = {
    baseColor = { { name = "Red", index = 1 }, { name = "Green Metallic", index = 2 }, { name = "hidden", index = 3, isSelectable = false }, { name = "Blue", index = 4 } },
    rimColor = { { name = "Black", index = 1 }, { name = "Silver", index = 2 } },
    wheel = { { name = "narrow", index = 1 }, { name = "wide", index = 2 } } } }
g_storeManager = { getItemByXMLFilename = function(self, f) if f == "px150xl.xml" then return T.storeItem end end }

g_currentMission = { hud = hud, missionDynamicInfo = { isMultiplayer = false }, terrainRootNode = 5,
    missionInfo = { savegameIndex = 3 }, gameStarted = true,
    environment = T.env, placeableSystem = { placeables = {} }, vehicleSystem = { vehicles = {} },
    getNodeObject = function(self, id) return T.nodeObjects[id] end,
    addIngameNotification = function(self, kind, text) table.insert(T.notes, text) end }
-- a tractor facing +X at (100, 100, 50) with a mod implement (two components)
local tractorNode = newNode(100, 100, 50); T.nodes[tractorNode].dir = {1, 0, 0}
local implNode = newNode(94, 100, 50); T.nodes[implNode].rot = {0, 1.5, 0}
local implNode2 = newNode(92, 100, 50)
T.implement = { rootNode = implNode, components = { { node = implNode }, { node = implNode2 } },
    size = { length = 6, width = 9, height = 3 }, customEnvironment = "FS25_PX150XL",
    configFileName = "px150xl.xml", configurations = { baseColor = 1, rimColor = 2, wheel = 1 } }
function T.implement:getName() return "PX150 XL" end
function T.implement:getOwnerFarmId() return 1 end
T.tractor = { rootNode = tractorNode, size = { length = 6, width = 3, height = 3 }, customEnvironment = nil }
function T.tractor:getRootVehicle() return self end
function T.tractor:getChildVehicles() return { self, T.implement } end
function T.tractor:getName() return "M1240" end
function T.tractor:getIsEnterable() return true end
T.tractor.spec_enterable = { cameras = { { isInside = true }, { isInside = false } } }
function T.tractor:setActiveCameraIndex(i) self.camIndex = i end
function T.tractor:getIsMotorStarted() return self.motorOn == true end
function T.tractor:startMotor() self.motorOn = true end
g_localPlayer = { vehicle = T.tractor }
function g_localPlayer:getCurrentVehicle() return self.vehicle end
function g_localPlayer:getPosition() return 0, 100, 0 end
function g_localPlayer:requestToEnterVehicle(v) self.vehicle = v end
function g_localPlayer:leaveVehicle() self.vehicle = nil end
function g_localPlayer:teleportTo(x, y, z) T.teleported = { x, y, z } end
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
        T.tickLoads()
        SS.update(SS, 16)
        SS.draw(SS)

def files(part):
    return sorted(k for k in T.files.keys() if part in k)

same = lua.eval('function(a, b) return rawequal(a, b) end')   # lupa wrappers of one table aren't ==

def lua_list(t):
    return [t[i] for i in range(1, len(t) + 1)]

def shot_list(kind):
    """The values of the _shots_*_<kind>.xml (the stamp is fixed here, so the last one written)."""
    paths = [p for p in T.xmlSaved.keys() if p.endswith(f'_{kind}.xml')]
    return T.xmlSaved[paths[-1]] if paths else None

def shots_in(values):
    out, i = [], 0
    while values[f'shots.shot({i})#file'] is not None:
        out.append({k: values[f'shots.shot({i})#{k}'] for k in ('file', 'kind', 'hud', 'light', 'color')})
        i += 1
    return out

SS.loadMap(SS)
names = ['ssShot', 'ssView', 'ssClear', 'ssOrbit', 'ssUi', 'ssBurst', 'ssColors', 'ssLight', 'ssGolden', 'ssTarget', 'ssList', 'ssSpot', 'ssMove', 'ssEnter', 'ssMenu', 'ssKeys', 'ssFolder', 'ssQuiet', 'ssRadius', 'ssProbe', 'ssMethod']
check(all(T.commands[c] is not None for c in names), 'console commands registered')
G.PlayerInputComponent.registerGlobalPlayerActionEvents(None)
check(all(T.actions[i] is not None for i in range(1, 7)), 'six key actions registered')

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
settings = T.xmlSaved['C:/profile/modSettings/FS25_ScreenshotStudio/settings.xml']
check(settings is not None and settings['screenshotStudio.method'] == 'screen', 'method saved in settings.xml')
saved = files('FS25_PX150XL/orbit_')
check(len(saved) == 12, f'12 orbit pictures (8 ring + 4 low): {len(saved)}')
check(G.g_cameraManager.active == 999, 'previous camera restored')
check(G.g_currentMission.hud.visible is True, 'HUD visible again')
check(T.renderCalls == 2, f'render tried once per format before falling back ({T.renderCalls})')
lst = shot_list('orbit')
rows = shots_in(lst) if lst else []
check(len(rows) == 12 and all(r['kind'] == 'orbit' and r['hud'] == 'false' and r['light'] == 'game' for r in rows)
      and lst['shots#mod'] == 'FS25_PX150XL' and lst['shots#what'] == 'M1240',
      f'_shots_*_orbit.xml lists the 12 pictures, no HUD ({len(rows)})')
check(bool(rows) and rows[0]['file'] == 'orbit_20261112_120000_01.png', 'shot list has bare file names')

# --- next time the method is known: no more render attempts
T.renderCalls = 0
SS.consoleShot(SS)
run(2)
check(T.renderCalls == 0 and len(files('FS25_PX150XL/clean_')) == 1, 'clean shot uses the saved method')

# --- render works: ssMethod finds it again and keeps render_png
T.writeRender = True
SS.consoleMethod(SS, '')
SS.consoleShot(SS)
run(4)
check(SS.method == 'render_png', f'render_png found when it writes files ({SS.method})')
check(T.tryingAtRender == 'render_png', f'settings.xml says "trying render_png" before the render call ({T.tryingAtRender})')
settings = T.xmlSaved[T.SETTINGS]
check(settings['screenshotStudio.trying'] == 'render_png' and not SS.renderOk, 'still on trial right after the shot')
run(8)
settings = T.xmlSaved[T.SETTINGS]
check(settings['screenshotStudio.trying'] == '' and settings['screenshotStudio.method'] == 'render_png' and SS.renderOk,
      'alive 10 s later: render kept, "trying" gone')
T.renderCalls = 0
T.xmlSaved[T.SETTINGS] = None
SS.consoleShot(SS)
run(2)
check(T.renderCalls == 1 and T.xmlSaved[T.SETTINGS] is None, 'render known to be safe: no more settings writes per shot')
check(SS.consoleMethod(SS, 'nonsense').startswith('Unknown method'), 'ssMethod rejects unknown names')

# --- crash guard: the game died while trying render (settings.xml still says "trying")
T.xmlFiles[T.SETTINGS] = lua.table_from({'screenshotStudio.method': 'render_png', 'screenshotStudio.trying': 'render_png',
                                            'screenshotStudio.crashed': ''})
SS.method, SS.renderOk = None, False
SS.loadSettings(SS)
settings = T.xmlSaved[T.SETTINGS]
check(SS.method is None and SS.crashed.render_png and SS.crashed.render_jpg, 'after a crash: no render method, both formats out')
check(settings['screenshotStudio.trying'] == '' and settings['screenshotStudio.crashed'] == 'render_png render_jpg',
      f"crash written down ({settings['screenshotStudio.crashed']})")
check(any('ended while trying render_png' in l for l in lua_list(T.logs)), 'the log says why')
T.renderCalls, T.saveCalls = 0, 0
SS.consoleShot(SS)
run(4)
check(T.renderCalls == 0 and T.saveCalls == 1 and SS.method == 'screen', 'the next shot goes straight to the screen')
T.xmlFiles[T.SETTINGS] = T.xmlSaved[T.SETTINGS]
SS.crashed, SS.method = lua.table_from({}), None
SS.loadSettings(SS)
check(SS.crashed.render_png and SS.method == 'screen', 'the crash is remembered across starts')
check('without render' in SS.consoleMethod(SS, ''), 'ssMethod (empty) still leaves render out')
SS.consoleMethod(SS, 'render_png')
check(not SS.crashed.render_png and SS.method == 'render_png' and not SS.renderOk, 'ssMethod render_png insists, on trial again')
SS.consoleShot(SS)
run(1)
check(T.tryingAtRender == 'render_png', 'forced render is guarded too')
SS.deleteMap(SS)
check(T.xmlSaved[T.SETTINGS]['screenshotStudio.trying'] == '' and SS.trying is None, 'leaving the game normally: not a crash')
T.xmlFiles[T.SETTINGS] = None
SS.loadMap(SS)      # commands back; no settings file to read
SS.consoleShot(SS)
run(12)
check(SS.renderOk and SS.method == 'render_png' and SS.trying is None, 'forced render survives its trial')

# --- UI shot: keeps the HUD, waits, always uses the screen
T.saveCalls = 0
SS.consoleFolder(SS, 'FS25_Searchables')
SS.consoleUi(SS, '3')
check(G.g_currentMission.hud.visible is True, 'UI shot keeps the HUD')
run(2.5)
check(T.saveCalls == 0, 'UI shot waits for the countdown')
G.Gui.update()   # the countdown also runs from the GUI's update
run(1)
check(T.saveCalls == 1 and len(files('FS25_Searchables/ui_')) == 1, 'UI shot saved in the forced folder')
rows = shots_in(shot_list('ui'))
check(len(rows) == 1 and rows[0]['hud'] == 'true', 'UI shot is listed with HUD')
SS.consoleFolder(SS, '')

# --- busy and multiplayer
SS.consoleOrbit(SS)
check(SS.consoleShot(SS) == 'Busy or not possible', 'second batch refused while busy')
run(40)
G.g_currentMission.missionDynamicInfo.isMultiplayer = True
check(SS.consoleShot(SS) == 'Busy or not possible', 'refused in multiplayer')
G.g_currentMission.missionDynamicInfo.isMultiplayer = False

# --- burst: render leaves the HUD out anyway, so it stays up for driving; a shot every 3 s
T.actions[5](SS)
check(SS.session is not None and SS.session.kind == 'burst', 'burst started')
check(G.g_currentMission.hud.visible is True, 'burst with render: HUD stays for driving')
run(1)
check(len(files('FS25_PX150XL/burst_')) == 1, 'first burst shot right away')
run(3)
check(len(files('FS25_PX150XL/burst_')) == 2, 'second burst shot 3 s later')
run(6)
check(len(files('FS25_PX150XL/burst_')) == 4, f"one every 3 s ({len(files('FS25_PX150XL/burst_'))})")
T.actions[5](SS)     # again: stop
run(1)
check(SS.session is None, 'burst stopped by pressing again')
check(len(files('FS25_PX150XL/burst_')) == 4, 'no shots after stopping')
rows = shots_in(shot_list('burst'))
check(len(rows) == 4 and all(r['kind'] == 'burst' and r['hud'] == 'false' for r in rows), 'burst listed, no HUD')
SS.consoleMethod(SS, 'screen')
SS.consoleBurst(SS, '2', '1')
check(G.g_currentMission.hud.visible is False, 'burst with the screen method hides the HUD')
run(3)
check(SS.session is None and G.g_currentMission.hud.visible is True, 'ssBurst 2 1: done, HUD back')
SS.consoleMethod(SS, 'render_png')

# --- light presets
env = T.env
msg = SS.toggleGolden(SS)
check(env.dayTime == int(18.5 * 3600000) and env.currentDay == 10 and T.weather == 'SUN', f'golden hour: 18:30, same day, sunny ({msg})')
SS.toggleGolden(SS)
check(env.dayTime == 8 * 3600000 and env.currentDay == 10 and SS.light is None, 'golden hour off: old time back')
T.actions[4](SS)
check(SS.light == 1 and env.dayTime == int(18.5 * 3600000), 'Right Ctrl + 4: golden hour first')
T.actions[4](SS)
fog = T.fogUpdater.targetFog
check(env.dayTime == int(7.25 * 3600000) and fog != 'gameFog' and fog.groundFogGroundLevelDensity == 0.7
      and fog.groundFogWeatherTypes[1] is True and fog.groundFogEndDayTimeMinutes == 1439,
      'then morning mist: 07:15 with ground fog all day, also in sunshine')
SS.consoleShot(SS)
run(2)
rows = shots_in(shot_list('clean'))
check(rows[-1]['light'] == 'morning', f"shots know the light ({rows[-1]['light']})")
T.actions[4](SS)
check(env.dayTime == int(12.5 * 3600000) and T.fogUpdater.targetFog == 'gameFog', "then midday, the game's fog back")
T.actions[4](SS)
check(T.weather == 'CLOUDY' and env.dayTime == 13 * 3600000, 'then overcast')
T.actions[4](SS)
check(SS.light is None and env.dayTime == 8 * 3600000, 'then the old time back')
check(SS.consoleLight(SS, 'midday', '11').startswith('Light 3/4: midday sun, 11:00'), 'ssLight midday 11')
check(SS.consoleLight(SS, 'disco').startswith('Unknown light'), 'ssLight rejects unknown names')
SS.consoleLight(SS, 'off')
check(env.dayTime == 8 * 3600000, 'ssLight off')

# --- framing: the camera stands where the whole size box fits the 16:9 picture
def in_frame(pos, corners):
    """Largest share of the half-picture any corner takes (<= 1: all inside), seen from pos = (cx,cy,cz,tx,ty,tz)."""
    cx, cy, cz, tx, ty, tz = pos
    f = [tx - cx, ty - cy, tz - cz]
    n = math.sqrt(sum(a * a for a in f)); f = [a / n for a in f]
    r = [f[2], 0.0, -f[0]]; n = math.hypot(r[0], r[2]); r = [r[0] / n, 0.0, r[2] / n]
    u = [r[1] * f[2] - r[2] * f[1], r[2] * f[0] - r[0] * f[2], r[0] * f[1] - r[1] * f[0]]
    tan_v = math.tan(math.radians(SS.FOV) / 2); tan_h = tan_v * 16 / 9
    worst = 0
    for i in range(1, len(corners) + 1):
        c = corners[i]
        v = [c[1] - cx, c[2] - cy, c[3] - cz]
        z = sum(a * b for a, b in zip(v, f))
        if z <= 0:
            return 99
        worst = max(worst, abs(sum(a * b for a, b in zip(v, r))) / z / tan_h, abs(sum(a * b for a, b in zip(v, u))) / z / tan_v)
    return worst

def pos_of(t):
    return tuple(t[i] for i in range(1, 7))

corners = SS.boxCorners(SS, T.implement)
view = pos_of(SS.viewOf(SS, T.implement))
fill = in_frame(view, corners)
check(0.8 <= fill <= 0.86, f'the 9 m wide header fills the picture, nothing cut off ({fill:.2f} of the half-width)')
dx, dz = view[0] - 94, view[2] - 50
check(dz > 0 and dx > 0, 'seen from the front three-quarter (35 degrees off the front)')
SS.consoleView(SS, '180')
rear = pos_of(SS.viewOf(SS, T.implement))
check(rear[2] < 50 and in_frame(rear, corners) <= 0.86, 'ssView 180: from behind, still all in')
lua.execute('''
local n = T.newNode(300, 100, 300)
T.roller = { rootNode = n, size = { width = 4.2, length = 6.5, lengthOffset = 1, height = 1.5 }, components = { { node = n } },
    spec_workArea = { workAreas = {
        { start = T.newNode(293.85, 100, 298), width = T.newNode(293.85, 100, 302), height = T.newNode(300, 100, 298) },
        { start = T.newNode(300, 100, 298), width = T.newNode(306.15, 100, 302), height = T.newNode(306.15, 100, 298) } } } }
function T.roller:getName() return "PowerRoll 1230 HD Multi-Roller" end
''')
roller_reach = SS.cornersOf(SS, lua.table_from([G.T.roller]))
box_only = SS.boxCorners(SS, G.T.roller)
rv = pos_of(SS.viewOf(SS, G.T.roller))
check(in_frame(rv, roller_reach) <= 0.86 and in_frame(rv, box_only) < 0.6,
      f'unfolded 12.3 m roller with a 4.2 m size box: the wings are in the picture too ({in_frame(rv, roller_reach):.2f}, box alone {in_frame(rv, box_only):.2f})')
lua.execute('function T.roller:getIsUnfolded() return false end')
folded = pos_of(SS.viewOf(SS, G.T.roller))
check(in_frame(folded, box_only) > 0.75, f'folded: the work areas (still at full width on the frame) do not count, the roller fills the picture ({in_frame(folded, box_only):.2f})')
lua.execute('T.roller.getIsUnfolded = nil')
SS.consoleView(SS, '')
t = SS.getOrbitTarget(SS)
group_corners = SS.cornersOf(SS, SS.getVehicleGroup(SS).list)
fills = [in_frame(pos_of(p), group_corners) for p in lua_list(SS.orbitPositions(SS, t, 8)[0])]
check(len(fills) == 12 and all(0.6 <= f <= 0.86 for f in fills), f"orbit: tractor and header whole in all 12 ({', '.join(f'{f:.2f}' for f in fills)})")
T.date = '20261113_100000'
SS.consoleShot(SS, 'auto')
check(G.g_cameraManager.active == SS.camera and in_frame((T.nodes[SS.camera].x, T.nodes[SS.camera].y, T.nodes[SS.camera].z,
      *pos_of(SS.autoCamera(SS))[3:]), group_corners) <= 0.86, 'ssShot auto: the studio camera frames the whole machine')
run(4)
check(G.g_cameraManager.active != SS.camera, 'then your own camera back')
T.date = '20261112_120000'

# --- something in the way: the framed view moves round it
front = pos_of(SS.viewOf(SS, T.implement))
mid = [(front[i] + front[i + 3]) / 2 for i in range(3)]
lua.execute(f'T.obstacles = {{ {{ id = 501, x = {mid[0]}, y = {mid[1]}, z = {mid[2]}, r = 1.5 }} }}')
T.logs = lua.table_from([])
moved = pos_of(SS.viewOf(SS, T.implement))
check(math.dist(moved[:3], front[:3]) > 3 and SS.isClear(SS, lua.table_from(list(moved)), corners, lua.table_from({})),
      'a pole between camera and header: the view moves to a clear side')
check(any('in the way at 35 degrees' in l for l in lua_list(T.logs)), 'and the log says so')
lua.execute('T.nodeObjects[501] = T.implement')
check(math.dist(pos_of(SS.viewOf(SS, T.implement))[:3], front[:3]) < 0.01, 'a hit on the header itself is not in the way')
lua.execute('T.nodeObjects[501] = nil')
lua.execute('T.obstacles[1].id = g_currentMission.terrainRootNode')
check(math.dist(pos_of(SS.viewOf(SS, T.implement))[:3], front[:3]) < 0.01, 'a hit on the ground is not in the way')
lua.execute('T.obstacles[1].id = 501')
SS.consoleView(SS, '35')
check(math.dist(pos_of(SS.viewOf(SS, T.implement))[:3], front[:3]) < 0.01
      and any('ssView fixed the angle' in l for l in lua_list(T.logs)), 'ssView 35: kept even when blocked, with a note')
SS.consoleView(SS, '')
SS.consoleClear(SS, 'off')
check(math.dist(pos_of(SS.viewOf(SS, T.implement))[:3], front[:3]) < 0.01, 'ssClear off: no looking')
SS.consoleClear(SS, 'on')
t = SS.getOrbitTarget(SS)
lua.execute('T.obstacles = {}')
clear_ring = [pos_of(p) for p in lua_list(SS.orbitPositions(SS, t, 8)[0])]
m0 = [(clear_ring[0][i] + clear_ring[0][i + 3]) / 2 for i in range(3)]
lua.execute(f'T.obstacles = {{ {{ id = 502, x = {m0[0]}, y = {m0[1]}, z = {m0[2]}, r = 1.0 }} }}')
dodged = [pos_of(p) for p in lua_list(SS.orbitPositions(SS, t, 8)[0])]
def elevation_deg(p):
    cx, cy, cz, tx, ty, tz = p
    return math.degrees(math.atan2(cy - ty, math.hypot(cx - tx, cz - tz)))
check(len(dodged) >= 10 and all(elevation_deg(p) <= 31 for p in dodged)
      and all(SS.isClear(SS, lua.table_from(list(p)), group_corners, t.subjects) for p in dodged),
      f'orbit: around the obstacle or left out, never a steep top-down view, all clear ({len(dodged)} of 12)')
real_clear = SS.isClear
lua.execute('function ScreenshotStudio:isClear() return false, "a wall" end')
T.logs = lua.table_from([])
check(SS.consoleOrbit(SS) == 'Orbit started' and SS.session is not None and SS.session.kind == 'orbit'
      and len(lua_list(SS.queue)) == 11 and any('looked blocked from every side (a wall); taken without checking' in l for l in lua_list(T.logs)),
      'blocked all round (more likely a wrong reading): the orbit is taken anyway, and the log says so')
SS.isClear = real_clear
run(40)
lua.execute('T.obstacles = {}')

# --- a building: framed by its placement test area (start node + end node)
lua.execute('''
T.barnStart, T.barnEnd = T.newNode(200, 100, 200), T.newNode(220, 100, 212)
T.alpaca = { rootNode = T.newNode(210, 100, 206), customEnvironment = "FS25_AlpacaPRX500",
             spec_placement = { testAreas = { { startNode = T.barnStart, endNode = T.barnEnd } } } }
function T.alpaca:getName() return "Alpaca Barn" end
''')
bt = SS.placeableTarget(SS, T.alpaca)
bc = bt.corners
ys = sorted({round(bc[i][2], 2) for i in range(1, len(bc) + 1)})
check(len(bc) == 8 and abs(bt.radius - 10) < 0.01 and ys == [100.0, 109.0], f'test area 20 x 12 m, flat: box with 9 m height guess ({bt.radius}, {ys})')
ring = [pos_of(p) for p in lua_list(SS.orbitPositions(SS, bt, 8)[0])]
check(all(in_frame(p, bc) <= 0.86 for p in ring), 'orbit round the barn: all of it in every picture')
SS.consoleRadius(SS, '30')
check(SS.placeableTarget(SS, T.alpaca).corners is None, 'ssRadius set by hand wins over the test area')
SS.consoleRadius(SS, '')

# --- every color: copies in place, vehicle hidden, copies deleted, vehicle back
impl = T.implement
T.loadFails[4] = True     # the Blue copy fails to load: skipped, the rest goes on
T.actions[6](SS)
check(SS.session is not None and SS.session.kind == 'color', 'every color started')
cam = T.nodes[SS.camera]
check(G.g_cameraManager.active == SS.camera
      and in_frame((cam.x, cam.y, cam.z, *pos_of(SS.viewOf(SS, impl))[3:]), SS.boxCorners(SS, impl)) <= 0.86,
      'every color: the studio camera frames the header (your camera can not move it)')
check(T.nodes[impl.rootNode].visible is False and T.nodes[impl.components[2].node].visible is False, 'vehicle hidden')
check(G.g_currentMission.hud.visible is False, 'HUD hidden for the colors')
run(0.7)
copy = T.lastCopy
check(copy is not None and copy.data.configurations.baseColor == 1 and copy.data.configurations.rimColor == 2,
      'first copy: Red, the other options as on the vehicle')
check(copy.data.addToPhysics is False and copy.data.isSaved is False and copy.data.ignoreShopOffset is True,
      'copy without physics, never saved')
check(copy.data.pos[1] == 94 and abs(copy.data.rot[2] - 1.5) < 1e-9, 'copy where the vehicle stands, same rotation')
check(copy.placed is not None and copy.placed[4] is None, 'different component count: placed by the root only')
run(10)
check(SS.session is None, 'every color finished')
color_files = files('FS25_PX150XL/color_')
check(len(color_files) == 2 and color_files[0].endswith('_01_Red.png') and color_files[1].endswith('_02_Green_Metallic.png'),
      f'one picture per selectable color, the failed one skipped ({[os.path.basename(f) for f in color_files]})')
check(lua_list(T.deleted) == [1, 2], f'each copy deleted after its picture ({lua_list(T.deleted)})')
check(T.nodes[impl.rootNode].visible is True and T.nodes[impl.components[2].node].visible is True, 'vehicle shown again')
rows = shots_in(shot_list('color'))
check([r['color'] for r in rows] == ['Red', 'Green Metallic'], f"colors listed by name ({[r['color'] for r in rows]})")
check(SS.consoleColors(SS, 'wheel') == 'Going through the colors', 'ssColors wheel: any option with choices')
run(10)
check(len(files('FS25_PX150XL/color_')) == 4, 'ssColors wheel took 2 more')
check(SS.consoleColors(SS, 'nonsense').startswith('Not possible') and any('Its options' in l for l in lua_list(T.logs)),
      'ssColors with an unknown option lists the options')

# a copy that comes after the batch was stopped is thrown away
T.loadDelay = 100
SS.consoleColors(SS)
run(0.5)
SS.finish(SS)
check(T.nodes[impl.rootNode].visible is True, 'stopping shows the vehicle again')
n_deleted = len(T.deleted)
T.now = T.now + 200
T.tickLoads()
check(len(T.deleted) == n_deleted + 1, 'late copy deleted at once')
T.loadDelay = 0.5

# --- which color option: the one the vehicle's XML calls the body, not the hubs
lua.execute('''
T.storeItem.configurations.designColor = { { name = "Yellow", index = 1 }, { name = "Black", index = 2 } }
T.xmlFiles["px150xl.xml"] = { ["vehicle.baseColorConfigurations#title"] = "$l10n_configuration_hubColor",
                              ["vehicle.designColorConfigurations#title"] = "$l10n_configuration_bodyColor" }
''')
SS.titleCache = None
name, title = SS.pickColorConfig(SS, T.storeItem)
check(name == 'designColor' and 'bodycolor' in title, f'body color wins over hub color ({name}, {title})')
lua.execute('T.xmlFiles["px150xl.xml"] = { ["vehicle.baseColorConfigurations#title"] = "$l10n_configuration_hubColor" }')
SS.titleCache = None
check(SS.pickColorConfig(SS, T.storeItem)[0] == 'designColor', 'hub color passed over even without a body title')
lua.execute('T.xmlFiles["px150xl.xml"] = nil')
SS.titleCache = None
check(SS.pickColorConfig(SS, T.storeItem)[0] == 'baseColor', 'no titles: baseColor first, as before')
check(SS.pickColorConfig(SS, T.storeItem, 'rimColor') == 'rimColor', 'ssColors rimColor still picks that one')
lua.execute('T.storeItem.configurations.designColor = nil')

# --- quiet: other mods' drawing is muted for a batch, and put back after
T.drawn = 0
SS.consoleOrbit(SS)
T.otherModsDraw()
ad = G.FS25_AutoDrive.ADDrawingManager
check(T.drawn == 0 and ad.lines == 0, 'during a batch: nothing drawn, also from copies in mod environments and their lookup tables')
run(40)
T.otherModsDraw()
check(lua.eval('rawget(_G, "drawFilledRect")') is None, 'a metatable function is shadowed, then the shadow removed')
check(T.drawn == 6 and ad.lines == 1 and same(G.renderText, T.originalRenderText) and same(G.FS25_Courseplay.renderText, T.cpRenderText) and SS.muted is None,
      'after the batch: all drawing back')
SS.consoleUi(SS, '1')
T.otherModsDraw()
check(T.drawn == 12, 'UI shot: other mods stay on screen')
run(2)
check(SS.consoleQuiet(SS, 'off').endswith('shown'), 'ssQuiet off')
SS.consoleShot(SS)
T.otherModsDraw()
check(T.drawn == 18, 'ssQuiet off: nothing muted')
run(2)
SS.consoleQuiet(SS, 'on')
SS.consoleShot(SS)
SS.session = None          # a batch that died half-way
run(0.1)
check(SS.muted is None and same(G.renderText, T.originalRenderText), 'never left muted when a batch dies')
SS.state = None

# --- every color: what is hitched changes color with it (a Ropa's header)
lua.execute("""
T.tractorItem = { xmlFilename = "m1240.xml", configurations = {
    baseColor = { { name = "Blue", index = 1 }, { name = "Red", index = 2 }, { name = "Yellow", index = 3 } } } }
T.tractor.configFileName = "m1240.xml"
T.tractor.configurations = { baseColor = 3 }
local get = g_storeManager.getItemByXMLFilename
g_storeManager.getItemByXMLFilename = function(self, f) if f == "m1240.xml" then return T.tractorItem end return get(self, f) end
T.loadLog, T.loadFails = {}, {}
function T.implement:getRootVehicle() return T.tractor end
""")
G.g_localPlayer.vehicle = T.tractor
SS.consoleTarget(SS, '')
check(SS.consoleColors(SS) == 'Going through the colors', 'every color with the tractor hitched')
run(30)
loads = [(l.file, l.cfg[l.config]) for l in lua_list(T.loadLog)]
head = [(f, c) for f, c in loads if f == 'px150xl.xml']
trac = [(f, c) for f, c in loads if f == 'm1240.xml']
check(head == [('px150xl.xml', 1), ('px150xl.xml', 2), ('px150xl.xml', 4)] and trac == [('m1240.xml', 2), ('m1240.xml', 2), ('m1240.xml', 1)],
      f'each color: a copy of the header AND of the tractor, Red as Red, else by place (Green Metallic -> 2nd, Blue -> Blue) ({loads})')
check(SS.session is None and T.nodes[T.tractor.rootNode].visible is True and T.nodes[T.implement.rootNode].visible is True,
      'afterwards both shown again')
lua.execute('T.tractor.configFileName = nil')

# --- ssMove: the machine with its header to an open, flat place, and back
lua.execute("""
T.hitch = { detached = 0, attached = {}, physicsOff = 0, physicsOn = 0 }
T.implement.attachedTo = T.tractor
function T.tractor:getAttachedImplements() return T.implement.attachedTo == self and { { object = T.implement, jointDescIndex = 2 } } or {} end
function T.tractor:detachImplementByObject(o) T.hitch.detached = T.hitch.detached + 1; o.attachedTo = nil end
function T.tractor:attachImplement(o, input, joint, noEvent, index, lowered) table.insert(T.hitch.attached, { input, joint, lowered }); o.attachedTo = self end
T.tractor.spec_attacherJoints = { attacherJoints = { {}, { moveDown = true } } }
function T.implement:getActiveInputAttacherJointDescIndex() return 1 end
function T.implement:getAttacherVehicle() return self.attachedTo end
local function place(v, x, y, z, rx, ry, rz, parts)
    if v.components ~= nil then
        for i, c in ipairs(v.components) do local o = T.nodes[c.node]; o.x, o.y, o.z = parts[i][1][1], parts[i][1][2], parts[i][1][3] end
    else
        local o = T.nodes[v.rootNode]; o.x, o.y, o.z = x, y, z
    end
end
for _, v in ipairs({ T.tractor, T.implement }) do
    v.setAbsolutePosition = place
    v.removeFromPhysics = function() T.hitch.physicsOff = T.hitch.physicsOff + 1 end
    v.addToPhysics = function() T.hitch.physicsOn = T.hitch.physicsOn + 1 end
end
function overlapBox(x, y, z, rx, ry, rz, ex, ey, ez, cb, target, mask)
    local n = 0
    for _, o in ipairs(T.obstacles) do
        if math.abs(o.x - x) < ex + o.r and math.abs(o.z - z) < ez + o.r and math.abs(o.y - y) < ey + o.r then
            n = n + 1; target[cb](target, o.id)
        end
    end
    return n
end
""")
def pos(node):
    o = T.nodes[node]; return (o.x, o.y, o.z)
before = {n: pos(n) for n in (T.tractor.rootNode, T.implement.rootNode, T.implement.components[2].node)}
gap = math.dist(before[T.tractor.rootNode], before[T.implement.rootNode])
# a building where the first place would be (40 m out, straight ahead in +z)
lua.execute('T.obstacles = { { id = 777, x = 96.25, y = 101.5, z = 90, r = 3 } }')
msg = SS.consoleMove(SS)
after = {n: pos(n) for n in before}
moved = math.dist(after[T.tractor.rootNode], before[T.tractor.rootNode])
check(msg.startswith('Moved M1240 with 1 hitched') and 35 < moved < 45 and abs(math.dist(after[T.tractor.rootNode], after[T.implement.rootNode]) - gap) < 1e-6
      and after[T.implement.rootNode][2] - after[T.implement.components[2].node][2] == 0,
      f'ssMove: tractor and header moved together, {moved:.0f} m, still {gap:.1f} m apart ({msg})')
check(abs(after[T.tractor.rootNode][2] - 90) > 1 or abs(after[T.tractor.rootNode][0] - 100) > 1, 'the blocked place (a building) was passed over')
h = G.T.hitch
att = lua_list(h.attached)
check(h.detached == 1 and len(att) == 1 and att[0][1] == 1 and att[0][2] == 2 and att[0][3] is True
      and h.physicsOff == 2 and h.physicsOn == 2 and same(G.T.implement.attachedTo, G.T.tractor),
      'unhitched, physics off, moved, physics on, hitched again on the same hitch, still lowered')
check(SS.consoleMove(SS) == 'Already moved: ssMove back first', 'not twice')
check(SS.consoleMove(SS, 'back').startswith('Back where it was: M1240'), 'ssMove back')
check(all(math.dist(pos(n), before[n]) < 1e-6 for n in before) and same(G.T.implement.attachedTo, G.T.tractor),
      'back exactly where it was, header on')
lua.execute('T.obstacles = {}')
# ssSpot: here, the way you look
lua.execute('T.nodes[999] = { x = 0, y = 0, z = 0, dir = { 1, 0, 0 }, rot = { 0, 0, 0 }, visible = true }')
G.g_cameraManager.active = 999
lua.execute('function g_localPlayer:getPosition() return 300, 100, -200 end')
check(SS.consoleSpot(SS).startswith('Spot for'), 'ssSpot saved')
saved = T.xmlSaved[T.SETTINGS]
check(saved['screenshotStudio.spots.spot(0)#x'] == '300.00' and saved['screenshotStudio.spots.spot(0)#z'] == '-200.00', 'the spot is in settings.xml')
msg = SS.consoleMove(SS)
t_after = pos(T.tractor.rootNode); i_after = pos(T.implement.rootNode)
mid = ((t_after[0] + i_after[0]) / 2, (t_after[2] + i_after[2]) / 2)
check(msg.endswith('to your spot') and math.dist(mid, (300, -200)) < 4, f'ssMove: to the saved spot ({msg}, {mid})')
SS.consoleMove(SS, 'back')
SS.consoleSpot(SS, 'clear')
# trees: rays hit only trunks; a trunk near the line of sight means branches in the picture
lua.execute('T.obstacles = {}')
G.g_localPlayer.vehicle = None
plain = pos_of(SS.viewOf(SS, T.implement))
mid = [(plain[i] + plain[i + 3]) / 2 for i in range(3)]
lua.execute(f'T.obstacles = {{ {{ id = 901, x = {mid[0]}, y = {mid[1] + 3.5}, z = {mid[2]}, r = 0.3 }} }}')
T.logs = lua.table_from([])
real_ray = G.raycastClosest
G.raycastClosest = None                      # only the crown check can see it
moved = pos_of(SS.viewOf(SS, T.implement))
G.raycastClosest = real_ray
check(math.dist(moved[:3], plain[:3]) > 3 and any('trees (' in l for l in lua_list(T.logs)),
      'a tree crown over the line of sight (the rays miss the trunk): the view moves, the log says trees')
lua.execute('T.obstacles = {}')
check(SS.spots[SS.mapId(SS)] is None, 'ssSpot clear')
lua.execute('function g_localPlayer:getPosition() return 0, 100, 0 end')
G.g_cameraManager.active = 999
lua.execute('T.implement.attachedTo = nil; T.implement.getRootVehicle = nil')

# --- on foot: every color of the nearest vehicle; orbit the nearest mod building
G.g_localPlayer.vehicle = None
G.g_currentMission.vehicleSystem.vehicles[1] = impl
check(SS.getColorVehicle(SS) is None, 'on foot, 106 m away: no vehicle for every color')
lua.execute('function g_localPlayer:getPosition() return 90, 100, 60 end')
check(same(SS.getColorVehicle(SS), impl), 'on foot next to it: every color of that vehicle')
node = T.newNode(30, 100, 40)
G.g_currentMission.placeableSystem.placeables[1] = lua.table_from({'rootNode': node, 'customEnvironment': 'FS25_PigBarnWithRobot'})
t = SS.getOrbitTarget(SS)
check(t is not None and t.mod == 'FS25_PigBarnWithRobot' and t.radius == 18, 'on foot: nearest mod building')

# --- ssEnter: on foot, into the nearest vehicle you can sit in, then an outside camera
G.g_currentMission.vehicleSystem.vehicles[2] = T.tractor
check(SS.consoleEnter(SS, 'nothing like it').startswith('No vehicle called'), 'ssEnter with an unknown name')
msg = SS.consoleEnter(SS, 'm12')
check(msg.startswith('Getting into M1240') and same(G.g_localPlayer.vehicle, T.tractor), f'ssEnter m12 ({msg})')
run(2.5)
check(T.tractor.camIndex == 2, 'then the outside camera')
check(T.tractor.motorOn is True, 'and the engine started (no "Please start the engine first!")')

# --- ssTarget / ssList: pick what to photograph by name, wherever it is
lua.execute('''
T.baler = { rootNode = T.newNode(500, 100, 500), customEnvironment = "FS25_KroneBigPack", size = { length = 8, width = 3, height = 3 } }
function T.baler:getName() return "Krone BiG Pack 1290" end
g_currentMission.vehicleSystem.vehicles[3] = T.baler
g_currentMission.vehicleSystem.vehicles[4] = { rootNode = T.newNode(91, 100, 61), isPallet = true }
T.barn = g_currentMission.placeableSystem.placeables[1]
function T.barn:getName() return "Pig Barn" end
function T.implement:getRootVehicle() return T.tractor end
''')
T.logs = lua.table_from([])
msg = SS.consoleList(SS)
listed = [l for l in lua_list(T.logs) if ' m  ' in l]
check(msg.startswith('3 found') and len(listed) == 3 and 'PX150 XL (FS25_PX150XL)  on M1240' in listed[0]
      and 'Pig Barn' in listed[2] and not any('Krone' in l for l in listed),
      f'ssList: what is near, nearest first, no pallets ({msg}; {listed})')
check(SS.consoleList(SS, 'krone').startswith('1 found'), 'ssList krone: the whole map by name')
check(SS.consoleTarget(SS, 'combine').startswith("Nothing called 'combine'"), 'ssTarget with an unknown name')
T.logs = lua.table_from([])
SS.consoleTarget(SS, 'combine')
check(any("Nearest: PX150 XL (FS25_PX150XL" in l for l in lua_list(T.logs)), 'not found: the log names what is nearest')
msg = SS.consoleTarget(SS, 'kronebigpack')
check('Krone BiG Pack 1290' in msg, f'ssTarget by the mod name (FS25_KroneBigPack) when the shop name differs ({msg})')
msg = SS.consoleTarget(SS, 'px150xl.xml')
check('PX150 XL' in msg, f'ssTarget by the XML file name ({msg})')
msg = SS.consoleTarget(SS, 'BiG', 'Pack')
check('Krone BiG Pack 1290 (FS25_KroneBigPack, 601 m)' in msg, f'ssTarget BiG Pack: the baler 601 m away ({msg})')
t = SS.getOrbitTarget(SS)
check(t.what == 'Krone BiG Pack 1290' and t.mod == 'FS25_KroneBigPack' and abs(t.x - 500) < 5 and abs(t.z - 500) < 5,
      'the orbit goes round the target, not what you sit in')
check(SS.getCurrentModName(SS) == 'FS25_KroneBigPack' and same(SS.getColorVehicle(SS), T.baler), 'folder and colors follow the target')
T.date = '20261113_090000'
SS.consoleShot(SS)
check(G.g_cameraManager.active == SS.camera, 'clean shot of a target you are not in: the studio camera')
cam = T.nodes[SS.camera]
d = math.hypot(cam.x - 500, cam.z - 500)
check(7 <= d <= 30 and cam.y > 101, f'a front three-quarter view of it ({d:.1f} m away)')
run(4)
check(len(files('FS25_KroneBigPack/clean_20261113_090000')) == 1 and G.g_cameraManager.active != SS.camera,
      'picture in the target mod folder, own camera back')
G.g_localPlayer.vehicle = None
G.g_localPlayer.vehicle = G.T.tractor
msg = SS.consoleEnter(SS)
tp = G.T.teleported
d = math.hypot(tp[1] - 500, tp[3] - 500) if tp else None
check(msg.startswith('Walking to Krone BiG Pack 1290') and G.g_localPlayer.vehicle is None and d is not None and 55 < d < 65,
      f'ssEnter: the baler has no seat, so out of the tractor and on foot 60 m from it ({msg}; {d})')

msg = SS.consoleTarget(SS, 'px150')
check('on M1240' in msg, f'ssTarget px150: the header on the tractor ({msg})')
SS.consoleEnter(SS)
check(same(G.g_localPlayer.vehicle, T.tractor), 'ssEnter: into the tractor the target hangs on')
check(SS.targetCamera(SS) is None and SS.getCurrentWhat(SS) == 'PX150 XL', 'sitting in the target: your own view, named after the target')

msg = SS.consoleTarget(SS, 'pig')
check(msg.startswith('Target: building Pig Barn'), f'ssTarget pig: a building ({msg})')
check(SS.getOrbitTarget(SS).what == 'Pig Barn' and SS.consoleColors(SS) == 'Not possible (see log)', 'a building: orbit yes, colors no')
SS.consoleTarget(SS, 'krone')
T.baler.isDeleted = True
check(SS.getTarget(SS) is None and any('is gone' in l for l in lua_list(T.logs)), 'a sold target is let go')
check(SS.consoleTarget(SS, '').startswith('Target: what you sit in') and SS.target is None, 'ssTarget empty: back to normal')
T.date = '20261112_120000'
lua.execute('g_currentMission.vehicleSystem.vehicles[4] = nil; g_currentMission.vehicleSystem.vehicles[3] = nil; T.implement.getRootVehicle = nil')

# --- autorun: steps one after the other, only for its save, only fresh, read once
AUTORUN = 'C:/profile/modSettings/FS25_ScreenshotStudio/autorun.xml'
def write_autorun(steps, save='3', created='20261112_115500'):
    values = {'autorun#savegame': save, 'autorun#created': created}
    for i, step in enumerate(steps):
        values[f'autorun.step({i})'] = step
    T.xmlFiles[AUTORUN] = lua.table_from(values)
    SS.autorunChecked = None

write_autorun(['ssShot'], save='5')
run(1)
check(SS.autorun is None and T.xmlFiles[AUTORUN] is not None, 'autorun for another save: not run, left alone')
write_autorun(['ssShot'], created='20261112_110000')
run(1)
check(SS.autorun is None and T.xmlFiles[AUTORUN] is None, 'autorun older than 20 minutes: not run, deleted')
check(SS.stampMinutes('last tuesday') is None and SS.stampMinutes('20270101_000000') - SS.stampMinutes('20261231_235900') == 1,
      'minutes count across the new year')

G.g_localPlayer.vehicle = None
before = len(T.files)
write_autorun(['ssEnter', 'ssLight golden', 'ssShot', 'ssBurst 2 1', 'wait 2', 'bogus step', 'ssLight off', 'quit'])
run(1)
check(SS.autorun is not None and T.xmlFiles[AUTORUN] is None, 'autorun read and deleted at once')
run(8.5)
check(SS.autorun.index == 0, 'first step only after 10 s (the map streams in)')
run(40)
logs = [l for l in lua_list(T.logs) if 'autorun:' in l]
check(SS.autorun is None and T.exited is True, 'autorun finished and quit the game')
check(any('step 1/8 ssEnter -> Getting into M1240' in l for l in logs) and same(G.g_localPlayer.vehicle, T.tractor),
      'step ssEnter got in')
check(any('step 6/8 bogus step -> unknown step' in l for l in logs), 'an unknown step is logged and skipped')
check(any('done, 3 picture(s)' in l for l in logs), f"pictures counted ({[l for l in logs if 'done' in l]})")
check(env.dayTime == 8 * 3600000 and SS.light is None, 'ssLight off ran after the burst was done')
order = [re.search(r'step (\d+/\d+ .*?) ->', l).group(1) for l in logs if ' -> ' in l]
check(order == ['1/8 ssEnter', '2/8 ssLight golden', '3/8 ssShot', '4/8 ssBurst 2 1', '5/8 wait 2', '6/8 bogus step', '7/8 ssLight off'],
      f'steps in order ({order})')

# quit waits while render is on trial: a crash right after the last shot must still count
SS.consoleMethod(SS, 'render_png')
T.exited = None
write_autorun(['ssShot', 'quit'])
run(13)
check(SS.trying == 'render_png' and SS.autorun is not None and T.exited is None, 'quit waits for the render trial')
run(8)
check(SS.trying is None and SS.renderOk and T.exited is True, 'trial over: then it quits')

# --- menus: ssMenu opens a screen, a dialog or an in-game menu page (a mod's page too)
lua.execute("""
InGameMenu = {}
T.gui = { shown = {}, dialogs = {}, page = nil }
T.mapFrame = { name = "InGameMenuMapFrame" }
T.uwm = {}                                  -- Player Trading+'s page: no name of its own
T.menu = { pageFrames = { T.mapFrame, T.uwm } }
function T.menu:goToPage(f) T.gui.page = f end
g_gui = { screenControllers = { [InGameMenu] = T.menu },
          frames = { UWMFrame = { target = T.uwm } },
          guis = { InGameMenu = {}, ShopMenu = {}, UWMOrderDialog = {}, UWMFrame = { target = T.uwm } } }
function g_gui:showGui(n) table.insert(T.gui.shown, n) end
function g_gui:showDialog(n) table.insert(T.gui.dialogs, n) end
""")
T.logs = lua.table_from([])
msg = SS.consoleMenu(SS)
logs = '\n'.join(lua_list(T.logs))
check(msg.startswith('2 menu pages, 4 screens') and '1 InGameMenuMapFrame, 2 UWMFrame' in logs and 'ShopMenu' in logs,
      f'ssMenu lists the menu pages (a mod page named by the GUI it was loaded as) and screens ({msg})')
check(SS.consoleMenu(SS, 'uwm') == 'In-game menu, page UWMFrame' and lua_list(G.T.gui.shown)[-1] == 'InGameMenu' and same(G.T.gui.page, G.T.uwm),
      'ssMenu uwm: the in-game menu on Player Trading+\'s page')
check(SS.consoleMenu(SS, '1') == 'In-game menu, page InGameMenuMapFrame', 'ssMenu 1: a page by number')
check(SS.consoleMenu(SS, 'ShopMenu') == 'Opened ShopMenu' and lua_list(G.T.gui.shown)[-1] == 'ShopMenu', 'ssMenu ShopMenu: a screen')
check(SS.consoleMenu(SS, 'orderdialog') == 'Opened UWMOrderDialog' and lua_list(G.T.gui.dialogs)[-1] == 'UWMOrderDialog', 'a dialog with showDialog')
check(SS.consoleMenu(SS, 'close') == 'Menus closed' and lua_list(G.T.gui.shown)[-1] == '', 'ssMenu close')
check(SS.consoleMenu(SS, 'nothing').startswith('No screen, dialog or menu page called nothing'), 'unknown name')
check(SS.consoleKeys(SS, 'ctrl+f', 'tractor') == 'Keys for the runner to type: ctrl+f tractor', 'ssKeys: a note for the runner')

# an autorun with a menu open: the game pauses the mission's update, the GUI keeps updating
SS.consoleMethod(SS, 'screen')
T.exited = None
T.saveCalls = 0
write_autorun(['ssFolder FS25_PlayerTradingPlus', 'ssMenu uwm', 'ssUi 1', 'ssKeys ctrl+f tractor', 'ssMenu close', 'quit'])
run(11)                                     # read, 10 s, first step
for _ in range(400):                        # 20 s with only the GUI updating
    T.now = T.now + 0.05
    G.Gui.update()
logs = [l for l in lua_list(T.logs) if 'autorun:' in l]
check(T.saveCalls == 1 and len(files('FS25_PlayerTradingPlus/ui_')) == 1 and T.exited is True,
      f'with only the menu updating: page opened, UI shot in the mod folder, quit ({T.saveCalls})')
check(any('ssKeys ctrl+f tractor -> Keys for the runner to type: ctrl+f tractor' in l for l in logs),
      'the keys are in the log for the runner')

SS.deleteMap(SS)
check(SS.camera is None and T.commands['ssShot'] is None, 'deleteMap removes camera and commands')

print()
print('All passed' if not failures else f'{len(failures)} failed')
sys.exit(1 if failures else 0)
