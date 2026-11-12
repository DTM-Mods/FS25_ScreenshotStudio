-- DTM Screenshot Studio: screenshots of a mod for ModHub and dtmmods.com, taken by the game.
--
-- Right Ctrl + 1  Clean shot: the current view without HUD
-- Right Ctrl + 2  Orbit: shots from all around the vehicle you sit in, or the nearest building
-- Right Ctrl + 3  UI shot: waits a few seconds (open the menu meanwhile), then saves the screen
-- Right Ctrl + 4  Golden hour: evening light and sun, press again for the old time back
--
-- Pictures go to modSettings/FS25_ScreenshotStudio/<mod name>/. Single player only (modDesc).
--
-- How a picture is taken: renderScreenshot renders the 3D view at 1920x1080 whatever the monitor
-- (no HUD, no mod overlays). Its formats aren't documented, so the first shot tries them one by
-- one and keeps the first that writes a file (settings.xml). If none does: hide the HUD and
-- saveScreenshot, which saves the screen at monitor size; fs25_screenshots.py crops it to 16:9.

ScreenshotStudio = {}
local SS = ScreenshotStudio

SS.MOD_NAME = g_currentModName
SS.MOD_DIR = g_currentModDirectory

SS.WIDTH, SS.HEIGHT = 1920, 1080
SS.FOV = 40                  -- degrees (vertical) for the orbit camera
SS.SETTLE_MS = 800           -- after moving the camera or hiding the HUD: LODs, shadows, TAA
SS.FIRST_SETTLE_MS = 2000    -- the first orbit position also streams in textures
SS.CHECK_MS = 2500           -- how long to wait for a file while finding the method
SS.ORBIT_SHOTS = 8
SS.UI_DELAY = 5              -- seconds
SS.GOLDEN_HOUR = 18.5
SS.PLACEABLE_RADIUS = 18     -- metres; buildings don't say how big they are
SS.MAX_PLACEABLE_DISTANCE = 150

-- Tried in this order until one writes a file. The last one always works.
SS.METHODS = {
    { id = "render_png", render = true, format = "png", ext = ".png" },
    { id = "render_jpg", render = true, format = "jpg", ext = ".jpg" },
    { id = "screen",     render = false, ext = ".png" },
}

SS.queue = {}        -- shots still to take
SS.session = nil     -- the running batch: camera, HUD state, folder, counters
SS.state = nil       -- nil | "settle" | "check" | "countdown"
SS.stateStart = 0
SS.forcedFolder = nil
SS.golden = nil      -- the time before golden hour, while it's on
SS.method = nil      -- method id that works, from settings.xml


local function log(fmt, ...)
    print(string.format("[ScreenshotStudio] " .. fmt, ...))
end

local function now()
    return getTimeSec() * 1000     -- real time: g_time stands still while a menu pauses the game
end

local function notify(text)
    if g_currentMission ~= nil and g_currentMission.addIngameNotification ~= nil then
        pcall(g_currentMission.addIngameNotification, g_currentMission, FSBaseMission.INGAME_NOTIFICATION_OK, text)
    end
end

-- "FS25_RopaTiger6S_ProEdition" stays; spaces and odd characters become "_"
local function safeName(name)
    name = tostring(name or "misc"):gsub("[^%w%-_]", "_")
    if name == "" then name = "misc" end
    return name
end


-- ------------------------------------------------------------------ settings
function SS:getBaseDir()
    return getUserProfileAppPath() .. "modSettings/" .. self.MOD_NAME .. "/"
end

function SS:loadSettings()
    local path = self:getBaseDir() .. "settings.xml"
    if not fileExists(path) then return end
    local xml = loadXMLFile("ssSettings", path)
    if xml ~= nil and xml ~= 0 then
        local m = getXMLString(xml, "screenshotStudio.method")
        for _, method in ipairs(self.METHODS) do
            if method.id == m then self.method = m end
        end
        delete(xml)
    end
end

function SS:saveSettings()
    createFolder(getUserProfileAppPath() .. "modSettings/")
    createFolder(self:getBaseDir())
    local xml = createXMLFile("ssSettings", self:getBaseDir() .. "settings.xml", "screenshotStudio")
    if xml ~= nil and xml ~= 0 then
        setXMLString(xml, "screenshotStudio.method", self.method or "")
        saveXMLFile(xml)
        delete(xml)
    end
end

function SS:getMethod(id)
    for i, method in ipairs(self.METHODS) do
        if method.id == id then return method, i end
    end
    return nil, nil
end


-- ------------------------------------------------------------------ what's in front of us
-- The vehicle we sit in plus everything attached, or the nearest building.
-- Returns { x, y, z, radius, yaw, mod } or nil.
function SS:getOrbitTarget()
    local player = g_localPlayer
    if player == nil then return nil end

    local vehicle = player.getCurrentVehicle ~= nil and player:getCurrentVehicle() or nil
    if vehicle ~= nil then
        local root = vehicle.getRootVehicle ~= nil and vehicle:getRootVehicle() or vehicle
        local list, seen = {}, {}
        local function add(v)
            if v ~= nil and not seen[v] and v.rootNode ~= nil then
                seen[v] = true
                table.insert(list, v)
            end
        end
        add(root)
        if root.getChildVehicles ~= nil then
            for _, v in pairs(root:getChildVehicles()) do add(v) end
        end

        local minX, minZ, maxX, maxZ, sumY, maxH = math.huge, math.huge, -math.huge, -math.huge, 0, 2
        local modName
        for _, v in ipairs(list) do
            local x, y, z = getWorldTranslation(v.rootNode)
            local size = v.size or {}
            local r = math.max(size.length or 4, size.width or 3) / 2
            minX, maxX = math.min(minX, x - r), math.max(maxX, x + r)
            minZ, maxZ = math.min(minZ, z - r), math.max(maxZ, z + r)
            sumY = sumY + y
            maxH = math.max(maxH, size.height or 3)
            -- The mod we're photographing: prefer an attached implement from a mod (a header on a
            -- base-game windrower), else the vehicle itself.
            if v.customEnvironment ~= nil and (modName == nil or v ~= root) then
                modName = v.customEnvironment
            end
        end
        local cx, cz = (minX + maxX) / 2, (minZ + maxZ) / 2
        local radius = math.max(maxX - minX, maxZ - minZ) / 2
        local dx, _, dz = localDirectionToWorld(root.rootNode, 0, 0, 1)
        return {
            x = cx, y = sumY / #list + maxH * 0.4, z = cz,
            radius = math.max(radius, 2),
            yaw = math.atan2(dx, dz),
            mod = modName or "basegame",
            what = root.getName ~= nil and root:getName() or "vehicle",
        }
    end

    -- On foot: the nearest building, mods first.
    local px, _, pz = player:getPosition()
    local best, bestDist
    local system = g_currentMission ~= nil and g_currentMission.placeableSystem or nil
    for _, p in ipairs(system ~= nil and system.placeables or {}) do
        if p.rootNode ~= nil then
            local x, _, z = getWorldTranslation(p.rootNode)
            local d = MathUtil.vector2Length(x - px, z - pz)
            if p.customEnvironment == nil then d = d + 50 end
            if d < self.MAX_PLACEABLE_DISTANCE and (bestDist == nil or d < bestDist) then
                best, bestDist = p, d
            end
        end
    end
    if best ~= nil then
        local x, y, z = getWorldTranslation(best.rootNode)
        local dx, _, dz = localDirectionToWorld(best.rootNode, 0, 0, 1)
        return {
            x = x, y = y + 3, z = z,
            radius = self.placeableRadius or self.PLACEABLE_RADIUS,
            yaw = math.atan2(dx, dz),
            mod = best.customEnvironment or "basegame",
            what = best.getName ~= nil and best:getName() or "building",
        }
    end
    return nil
end

function SS:getCurrentModName()
    if self.forcedFolder ~= nil then return self.forcedFolder end
    local player = g_localPlayer
    local vehicle = player ~= nil and player.getCurrentVehicle ~= nil and player:getCurrentVehicle() or nil
    if vehicle ~= nil then
        local t = self:getOrbitTarget()
        if t ~= nil then return t.mod end
    end
    return "misc"
end


-- ------------------------------------------------------------------ camera
function SS:getCamera()
    if self.camera == nil then
        self.camera = createCamera("screenshotStudioCamera", math.rad(self.FOV), 0.15, 10000)
        link(getRootNode(), self.camera)
        if setFastShadowUpdate ~= nil then setFastShadowUpdate(self.camera, true) end
        g_cameraManager:addCamera(self.camera, nil, false)
    end
    return self.camera
end

-- Camera at (cx, cy, cz) looking at (tx, ty, tz). Cameras look along their -Z.
function SS:placeCamera(cx, cy, cz, tx, ty, tz)
    local cam = self:getCamera()
    setWorldTranslation(cam, cx, cy, cz)
    setDirection(cam, cx - tx, cy - ty, cz - tz, 0, 1, 0)
end

-- Positions around the target: a ring at about 15 degrees, then low three-quarter views.
function SS:orbitPositions(t, count, distance)
    local list = {}
    local dist = distance or math.max(7, t.radius * 2.4)
    local function at(angle, elevation)
        local cx = t.x + math.sin(angle) * dist
        local cz = t.z + math.cos(angle) * dist
        local cy = t.y + dist * math.tan(math.rad(elevation))
        local ground = getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, cx, 0, cz)
        cy = math.max(cy, ground + 1.2)
        table.insert(list, { cx, cy, cz, t.x, t.y, t.z })
    end
    local start = t.yaw + math.rad(35)          -- front three-quarter first
    for i = 0, count - 1 do
        at(start + i * 2 * math.pi / count, 15)
    end
    for _, a in ipairs({ 35, -35, 145, -145 }) do  -- low hero shots
        at(t.yaw + math.rad(a), 3)
    end
    return list
end


-- ------------------------------------------------------------------ the queue
function SS:isBusy()
    return self.session ~= nil
end

function SS:start(kind, shots, folder, opts)
    if self:isBusy() then
        log("Still busy with the last batch")
        return false
    end
    if g_currentMission == nil then return false end
    local info = g_currentMission.missionDynamicInfo
    if info ~= nil and info.isMultiplayer then
        log("Single player only")
        return false
    end

    folder = safeName(folder)
    local dir = self:getBaseDir() .. folder .. "/"
    createFolder(getUserProfileAppPath() .. "modSettings/")
    createFolder(self:getBaseDir())
    createFolder(dir)

    local hud = g_currentMission.hud
    self.session = {
        kind = kind,
        dir = dir,
        folder = folder,
        stamp = getDate("%Y%m%d_%H%M%S"),
        index = 0,
        saved = {},
        prevCamera = g_cameraManager:getActiveCamera(),
        hudWasVisible = hud ~= nil and (hud.getIsVisible == nil or hud:getIsVisible()),
        keepHud = opts ~= nil and opts.keepHud,
        delayMs = opts ~= nil and opts.delayMs or nil,
    }
    if hud ~= nil and hud.setIsVisible ~= nil and not self.session.keepHud then
        hud:setIsVisible(false)
    end
    self.queue = shots
    self:nextShot()
    return true
end

function SS:nextShot()
    local s = self.session
    local shot = table.remove(self.queue, 1)
    if shot == nil then
        self:finish()
        return
    end
    s.index = s.index + 1
    s.shot = shot
    s.methodIndex = select(2, self:getMethod(self.method)) or 1
    if shot.camera ~= nil then
        self:placeCamera(unpack(shot.camera))
        if g_cameraManager:getActiveCamera() ~= self.camera then
            g_cameraManager:setActiveCamera(self.camera)
        end
    end
    s.settleMs = (s.index == 1 and shot.camera ~= nil) and self.FIRST_SETTLE_MS or self.SETTLE_MS
    if s.index == 1 and s.delayMs ~= nil then
        s.settleMs = s.delayMs
    end
    self:setState("settle")
end

function SS:setState(state)
    self.state = state
    self.stateStart = now()
end

function SS:capture()
    local s = self.session
    local method = self.METHODS[s.methodIndex]
    local path = string.format("%s%s_%s_%02d%s", s.dir, s.shot.kind, s.stamp, s.index, method.ext)
    -- UI shots show menus, which only the screen has.
    if s.shot.kind == "ui" then
        method = self:getMethod("screen")
        path = string.format("%s%s_%s_%02d%s", s.dir, s.shot.kind, s.stamp, s.index, method.ext)
    end
    s.path = path

    local ok, err
    if method.render then
        ok, err = pcall(renderScreenshot, path, self.WIDTH, self.HEIGHT, self.WIDTH / self.HEIGHT,
            method.format, 1, 0, 0, 0, 0, 0, 15, false, 4)
    else
        ok, err = pcall(saveScreenshot, path)
    end
    if not ok then
        log("%s failed: %s", method.id, tostring(err))
    end

    if self.method ~= nil or s.shot.kind == "ui" then
        table.insert(s.saved, path)
        self:setState("written")
    else
        self:setState("check")     -- finding out which method works
    end
end

function SS:tick()
    if self.session == nil then return end
    local s = self.session
    local elapsed = now() - self.stateStart

    if self.state == "settle" and elapsed >= s.settleMs then
        self:capture()
    elseif self.state == "written" and elapsed >= 150 then
        self:nextShot()
    elseif self.state == "check" then
        local method = self.METHODS[s.methodIndex]
        if fileExists(s.path) then
            self.method = method.id
            self:saveSettings()
            log("Screenshot method: %s (saved in settings.xml)", method.id)
            table.insert(s.saved, s.path)
            self:nextShot()
        elseif elapsed >= self.CHECK_MS then
            log("%s wrote no file, trying the next method", method.id)
            if s.methodIndex < #self.METHODS then
                s.methodIndex = s.methodIndex + 1
                self:capture()
            else
                log("No method wrote a file. Look for errors above in the log.")
                self:finish()
            end
        end
    end
end

function SS:finish()
    local s = self.session
    if s == nil then return end
    if s.prevCamera ~= nil and g_cameraManager:getActiveCamera() ~= s.prevCamera then
        g_cameraManager:setActiveCamera(s.prevCamera)
    end
    local hud = g_currentMission ~= nil and g_currentMission.hud or nil
    if hud ~= nil and hud.setIsVisible ~= nil and s.hudWasVisible then
        hud:setIsVisible(true)
    end
    self.session, self.state, self.queue = nil, nil, {}
    log("%d picture(s) in %s", #s.saved, s.dir)
    for _, p in ipairs(s.saved) do log("  %s", p) end
    notify(string.format("Screenshot Studio: %d picture(s) in modSettings/%s/%s", #s.saved, self.MOD_NAME, s.folder))
end


-- ------------------------------------------------------------------ the four actions
function SS:cleanShot()
    return self:start("clean", { { kind = "clean" } }, self:getCurrentModName())
end

function SS:orbit(count, distance)
    local t = self:getOrbitTarget()
    if t == nil then
        notify("Screenshot Studio: get in a vehicle or stand near a building")
        log("Orbit: no vehicle and no building within %d m", self.MAX_PLACEABLE_DISTANCE)
        return false
    end
    local shots = {}
    for _, cam in ipairs(self:orbitPositions(t, count or self.ORBIT_SHOTS, distance)) do
        table.insert(shots, { kind = "orbit", camera = cam })
    end
    log("Orbit around %s (%s): %d shots, radius %.1f m", tostring(t.what), t.mod, #shots, t.radius)
    return self:start("orbit", shots, self.forcedFolder or t.mod)
end

function SS:uiShot(seconds)
    local delay = (tonumber(seconds) or self.UI_DELAY) * 1000
    log("UI shot in %.0f s: open the menu now", delay / 1000)
    return self:start("ui", { { kind = "ui" } }, self.forcedFolder or "ui", { keepHud = true, delayMs = delay })
end

function SS:toggleGolden(hour)
    local env = g_currentMission ~= nil and g_currentMission.environment or nil
    if env == nil then return "No environment" end
    if self.golden == nil then
        self.golden = { env.currentMonotonicDay, env.currentDay, env.dayTime, env.daysPerPeriod }
        local h = tonumber(hour) or self.GOLDEN_HOUR
        local ok, err = pcall(env.setEnvironmentTime, env, env.currentMonotonicDay, env.currentDay,
            math.floor(h * 3600000), env.daysPerPeriod, false)
        if ok and env.lighting ~= nil and env.lighting.update ~= nil then pcall(env.lighting.update, env.lighting, 1, true) end
        if env.weather ~= nil and env.weather.consoleCommandWeatherSet ~= nil then
            pcall(env.weather.consoleCommandWeatherSet, env.weather, "SUN")
        end
        local msg = ok and string.format("Golden hour: %.2f h, sunny. Again for the old time.", h)
            or ("Golden hour failed: " .. tostring(err))
        notify("Screenshot Studio: " .. msg)
        return msg
    else
        local g = self.golden
        self.golden = nil
        local ok, err = pcall(env.setEnvironmentTime, env, g[1], g[2], g[3], g[4], false)
        if ok and env.lighting ~= nil and env.lighting.update ~= nil then pcall(env.lighting.update, env.lighting, 1, true) end
        local msg = ok and "Time is back to where it was (the weather stays sunny)." or ("Restore failed: " .. tostring(err))
        notify("Screenshot Studio: " .. msg)
        return msg
    end
end


-- ------------------------------------------------------------------ keys
function SS.onKeyClean() SS:cleanShot() end
function SS.onKeyOrbit() SS:orbit() end
function SS.onKeyUi() SS:uiShot() end
function SS.onKeyGolden() SS:toggleGolden() end

PlayerInputComponent.registerGlobalPlayerActionEvents = Utils.appendedFunction(
    PlayerInputComponent.registerGlobalPlayerActionEvents, function(self)
        for _, a in ipairs({
            { InputAction.SS_CLEAN_SHOT, SS.onKeyClean },
            { InputAction.SS_ORBIT, SS.onKeyOrbit },
            { InputAction.SS_UI_SHOT, SS.onKeyUi },
            { InputAction.SS_GOLDEN_HOUR, SS.onKeyGolden },
        }) do
            if a[1] ~= nil then
                local _, id = g_inputBinding:registerActionEvent(a[1], SS, a[2], false, true, false, true)
                if id ~= nil then g_inputBinding:setActionEventTextVisibility(id, false) end
            end
        end
    end)


-- ------------------------------------------------------------------ console
function SS:consoleShot() return self:cleanShot() and "Taking a clean shot" or "Busy or not possible" end

function SS:consoleOrbit(count, distance)
    return self:orbit(tonumber(count), tonumber(distance)) and "Orbit started" or "Orbit not possible (see log)"
end

function SS:consoleUi(seconds) return self:uiShot(seconds) and "UI shot coming, open the menu" or "Busy or not possible" end

function SS:consoleGolden(hour) return self:toggleGolden(hour) end

function SS:consoleFolder(name)
    if name == nil or name == "" then
        self.forcedFolder = nil
        return "Folder: automatic (the mod of the vehicle or building)"
    end
    self.forcedFolder = safeName(name)
    return "Folder: modSettings/" .. self.MOD_NAME .. "/" .. self.forcedFolder
end

function SS:consoleRadius(radius)
    self.placeableRadius = tonumber(radius)
    return string.format("Building orbit radius: %.1f m", self.placeableRadius or self.PLACEABLE_RADIUS)
end

-- Tries every renderScreenshot format plus saveScreenshot, so the log shows what this game
-- version can do. Files go to modSettings/FS25_ScreenshotStudio/probe/.
function SS:consoleProbe()
    local dir = self:getBaseDir() .. "probe/"
    createFolder(getUserProfileAppPath() .. "modSettings/")
    createFolder(self:getBaseDir())
    createFolder(dir)
    local tries = {}
    for _, f in ipairs({ "png", "jpg", "tga", "bmp", "dds", "raw_ldr", "raw_hdr" }) do
        local path = dir .. "render_" .. f .. "." .. (f:match("^raw_(%w+)") or f)
        local ok, err = pcall(renderScreenshot, path, self.WIDTH, self.HEIGHT, self.WIDTH / self.HEIGHT,
            f, 1, 0, 0, 0, 0, 0, 15, false, 4)
        table.insert(tries, { path = path, call = "renderScreenshot " .. f, ok = ok, err = err })
    end
    for _, ext in ipairs({ "png", "jpg" }) do
        local path = dir .. "save." .. ext
        local ok, err = pcall(saveScreenshot, path)
        table.insert(tries, { path = path, call = "saveScreenshot ." .. ext, ok = ok, err = err })
    end
    self.probe = { tries = tries, start = now() }
    return "Probing; results in the log in 3 seconds"
end

function SS:checkProbe()
    if self.probe == nil or now() - self.probe.start < 3000 then return end
    for _, t in ipairs(self.probe.tries) do
        log("probe %-28s call %s, file %s%s", t.call, t.ok and "ok" or "ERROR",
            fileExists(t.path) and "written" or "missing", t.err ~= nil and (" (" .. tostring(t.err) .. ")") or "")
    end
    self.probe = nil
end

-- ssMethod            the next shot finds the method again
-- ssMethod screen     always hide the HUD and save the screen (e.g. if render_png looks wrong)
function SS:consoleMethod(id)
    if id == nil or id == "" then
        self.method = nil
        self:saveSettings()
        return "The next shot finds the screenshot method again"
    end
    if self:getMethod(id) == nil then
        local ids = {}
        for _, m in ipairs(self.METHODS) do table.insert(ids, m.id) end
        return "Unknown method. Use one of: " .. table.concat(ids, ", ")
    end
    self.method = id
    self:saveSettings()
    return "Screenshot method: " .. id
end


-- ------------------------------------------------------------------ mod events
function SS:loadMap()
    self:loadSettings()
    addConsoleCommand("ssShot", "Clean shot of the current view, no HUD", "consoleShot", self)
    addConsoleCommand("ssOrbit", "Shots all around the vehicle or nearest building [count] [distance]", "consoleOrbit", self)
    addConsoleCommand("ssUi", "Screenshot with menus after a delay [seconds]", "consoleUi", self)
    addConsoleCommand("ssGolden", "Golden hour on/off [hour]", "consoleGolden", self)
    addConsoleCommand("ssFolder", "Folder name for the next shots, empty = automatic", "consoleFolder", self)
    addConsoleCommand("ssRadius", "Orbit radius around buildings in metres", "consoleRadius", self)
    addConsoleCommand("ssProbe", "Tests which screenshot calls work (see log)", "consoleProbe", self)
    addConsoleCommand("ssMethod", "Screenshot method: render_png, render_jpg, screen; empty = find again", "consoleMethod", self)
    log("Loaded. Right Ctrl + 1 clean shot, 2 orbit, 3 UI shot, 4 golden hour. Method: %s", self.method or "not found yet")
end

function SS:deleteMap()
    if self.session ~= nil then self:finish() end
    for _, c in ipairs({ "ssShot", "ssOrbit", "ssUi", "ssGolden", "ssFolder", "ssRadius", "ssProbe", "ssMethod" }) do
        removeConsoleCommand(c)
    end
    if self.camera ~= nil then
        g_cameraManager:removeCamera(self.camera)
        delete(self.camera)
        self.camera = nil
    end
    self.golden = nil
end

function SS:update(dt)
    self:tick()
    self:checkProbe()
end

function SS:draw()
    self:tick()
end

-- An open menu can stop the mission's update and draw, but the GUI updates every frame: the UI
-- shot's countdown runs from there too. tick() only acts when its time has come, so being called
-- more than once a frame does nothing extra.
if Gui ~= nil and Gui.update ~= nil then
    Gui.update = Utils.appendedFunction(Gui.update, function()
        SS:tick()
    end)
end

addModEventListener(SS)
