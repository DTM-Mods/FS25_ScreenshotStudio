-- DTM Screenshot Studio: screenshots of a mod for ModHub and dtmmods.com, taken by the game.
--
-- Right Ctrl + 1  Clean shot: the current view without HUD
-- Right Ctrl + 2  Orbit: shots from all around the vehicle you sit in, or the nearest building
-- Right Ctrl + 3  UI shot: waits a few seconds (open the menu meanwhile), then saves the screen
-- Right Ctrl + 4  Light: golden hour, morning mist, midday, overcast, then the old time back
-- Right Ctrl + 5  Burst: a shot every 3 seconds for a minute while you work; again to stop
-- Right Ctrl + 6  Every color: the current view once per color of the vehicle (shop colors)
--
-- What is photographed: what you sit in (an implement from a mod wins), on foot the nearest
-- building (orbit) or vehicle (colors); ssTarget <name> picks any vehicle, implement or building by
-- name wherever it stands, and if you don't sit in it, clean shots and colors get a studio camera
-- view of it. ssList shows the names.
--
-- Pictures go to modSettings/FS25_ScreenshotStudio/<mod name>/. Single player only (modDesc).
-- Each batch also writes _shots_<time>_<kind>.xml next to the pictures: what each one is (kind,
-- HUD or not, light, color), so fs25_screenshots.py can check the ModHub rules.
--
-- How a picture is taken: renderScreenshot renders the 3D view at 1920x1080 whatever the monitor
-- (no HUD; lines other mods draw into the world, like AutoDrive's routes, do show). GIANTS
-- doesn't document it, so the first shot tries its formats one by one and keeps the first that
-- writes a file (settings.xml). If none does: hide the HUD and saveScreenshot, which saves the
-- screen at monitor size; fs25_screenshots.py crops it to 16:9.
-- Crash guard: renderScreenshot can take the whole game down, so before it is first used,
-- settings.xml says "trying"; 10 s later, still alive, that goes away. If the next start still
-- finds it, the game died trying: render is not used again (ssMethod render_png to insist).
--
-- Every color: for each color option a copy of the vehicle is loaded the way the shop and the
-- game's own vehicle reload do it (VehicleLoadingData), without physics, exactly where the
-- vehicle stands, while the vehicle itself is hidden. The copy is never saved and is deleted
-- after its picture; at the end the vehicle is shown again. Nothing about the vehicle changes.

ScreenshotStudio = {}
local SS = ScreenshotStudio

SS.MOD_NAME = g_currentModName
SS.MOD_DIR = g_currentModDirectory

SS.WIDTH, SS.HEIGHT = 1920, 1080
SS.FOV = 40                  -- degrees (vertical) for the orbit camera
SS.SETTLE_MS = 800           -- after moving the camera or hiding the HUD: LODs, shadows, TAA
SS.FIRST_SETTLE_MS = 2000    -- the first orbit position, or a freshly loaded copy: textures stream in
SS.CHECK_MS = 2500           -- how long to wait for a file while finding the method
SS.SURVIVE_MS = 10000        -- still running this long after the first render: render is safe
SS.LOAD_TIMEOUT_MS = 30000   -- loading a color copy
SS.ORBIT_SHOTS = 8
SS.UI_DELAY = 5              -- seconds
SS.BURST_SHOTS = 20
SS.BURST_SECONDS = 3
SS.MAX_COLORS = 60          -- the Apache 1958 has 47 body colors
SS.PLACEABLE_RADIUS = 18     -- metres; buildings don't say how big they are
SS.MAX_PLACEABLE_DISTANCE = 150
SS.MAX_VEHICLE_DISTANCE = 40 -- on foot: every color of the nearest vehicle
SS.LIST_RADIUS = 150         -- ssList without a name: what's this close
SS.MAX_LIST = 40             -- lines ssList prints
SS.HERO_ANGLE = 35           -- degrees off the front: the view of a building target
SS.HERO_ELEVATION = 10
SS.VIEW_ANGLE = 35           -- framed views (colors, ssShot auto, a target): degrees off the front
SS.VIEW_ELEVATION = 12       -- degrees up
SS.FRAME_FILL = 0.85         -- how much of the picture the machine may fill (edge to edge = 1)
SS.MIN_DISTANCE = 4          -- metres
SS.avoidObstacles = true     -- framed views look for walls, poles, cars in the way (ssClear off)
SS.CROWN = 4.5               -- metres a tree's branches reach from its trunk (crowns have no collision)

-- Tried in this order until one writes a file. The last one always works.
SS.METHODS = {
    { id = "render_png", render = true, format = "png", ext = ".png" },
    { id = "render_jpg", render = true, format = "jpg", ext = ".jpg" },
    { id = "screen",     render = false, ext = ".png" },
}
-- renderScreenshot's arguments after the format, exactly as GIANTS' own editor script passes them
-- (GIANTS Editor 10.0.14, scripts/camera/saveBillboards.lua). A guessed list crashed the game.
SS.RENDER_ARGS = { 0, 0.0, 0.0, 0.0, 0.0, 3, 12, false }

-- Right Ctrl + 4 goes through these, then back to the game's own time. Hours are game time; in
-- winter evenings are darker, ssLight golden 16.5 moves it.
SS.LIGHTS = {
    { id = "golden",   hour = 18.5,  weather = "SUN",    text = "golden hour" },
    { id = "morning",  hour = 7.25,  weather = "SUN",    text = "morning mist", fog = true },
    { id = "midday",   hour = 12.5,  weather = "SUN",    text = "midday sun" },
    { id = "overcast", hour = 13.0,  weather = "CLOUDY", text = "overcast, soft light" },
}
-- Ground fog for "morning mist": a light version of what FS25_RealisticWeather sets for real fog
SS.MIST = {
    groundFogCoverageEdge0 = 0.05, groundFogCoverageEdge1 = 0.9, groundFogExtraHeight = 20,
    groundFogGroundLevelDensity = 0.7, heightFogMaxHeight = 600, heightFogGroundLevelDensity = 0.35,
}

-- Color options tried first when ssColors is given no name. The option's title in the vehicle
-- XML decides among them: one called body/paint wins; hubs, rims, seats, lights are passed over
-- (the Apache 1958's baseColor is its hub color, its body is designColor).
SS.COLOR_CONFIGS = { "baseColor", "baseMaterial", "designColor", "designMaterial", "rimColor", "wrappingColor" }
SS.BODY_WORDS = { "body", "paint", "karosserie", "lackierung" }
SS.NOT_BODY_WORDS = { "hub", "rim", "wheel", "tire", "tyre", "felge", "nabe", "seat", "sitz", "interior",
    "innen", "leather", "leder", "light", "beacon", "glass" }

SS.queue = {}        -- shots still to take
SS.session = nil     -- the running batch: camera, HUD state, folder, counters
SS.state = nil       -- nil | "settle" | "check" | "written" | "loading"
SS.stateStart = 0
SS.forcedFolder = nil
SS.light = nil       -- index in SS.LIGHTS while a light preset is on
SS.lightSaved = nil  -- the time (and fog) before the first preset
SS.method = nil      -- method id that works, from settings.xml
SS.renderOk = false  -- render has been used without the game dying
SS.trying = nil      -- render method being tried (settings.xml says so until it survived)
SS.tryingSince = nil
SS.crashed = {}      -- method id -> true: the game died while trying it
SS.target = nil      -- ssTarget: { vehicle = v } or { placeable = p, name = ... }


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

local function vehicleName(v)
    if v ~= nil and v.getName ~= nil then
        local ok, name = pcall(v.getName, v)
        if ok and name ~= nil then return tostring(name) end
    end
    return "vehicle"
end

local function placeableName(p)
    if p ~= nil and p.getName ~= nil then
        local ok, name = pcall(p.getName, p)
        if ok and name ~= nil then return tostring(name) end
    end
    return "building"
end

-- The game's real global table. A mod runs in its own environment, which hides some engine
-- functions (deleteFile) and keeps the mod's own globals; AutoDrive and Courseplay use getfenv(0) too.
local function trueGlobals()
    local ok, g = pcall(getfenv, 0)
    if ok and type(g) == "table" then return g end
    return _G
end

local function removeFile(path)
    local f = trueGlobals().deleteFile or deleteFile
    if f ~= nil then pcall(f, path) end
end

local function isGone(o)
    return o == nil or o.isDeleted == true or o.rootNode == nil
end


-- ------------------------------------------------------------------ settings
function SS:getBaseDir()
    return getUserProfileAppPath() .. "modSettings/" .. self.MOD_NAME .. "/"
end

function SS:loadSettings()
    local path = self:getBaseDir() .. "settings.xml"
    if not fileExists(path) then return end
    local xml = loadXMLFile("ssSettings", path)
    if xml == nil or xml == 0 then return end
    local m = getXMLString(xml, "screenshotStudio.method")
    local trying = getXMLString(xml, "screenshotStudio.trying") or ""
    local crashed = getXMLString(xml, "screenshotStudio.crashed") or ""
    for i = 0, 99 do
        local key = string.format("screenshotStudio.spots.spot(%d)", i)
        local map = getXMLString(xml, key .. "#map")
        if map == nil then break end
        local x, z = tonumber(getXMLString(xml, key .. "#x")), tonumber(getXMLString(xml, key .. "#z"))
        if x ~= nil and z ~= nil then
            self.spots[map] = { x = x, z = z, yaw = tonumber(getXMLString(xml, key .. "#yaw")) or 0 }
        end
    end
    delete(xml)
    if self:getMethod(m) ~= nil then self.method = m end
    for id in crashed:gmatch("[%w_]+") do self.crashed[id] = true end
    if trying ~= "" then
        -- the game ended while a render method was being tried: it's the same engine call for
        -- every format, so none of them is used again
        for _, method in ipairs(self.METHODS) do
            if method.render then self.crashed[method.id] = true end
        end
        if self.method ~= nil and self:getMethod(self.method).render then self.method = nil end
        log("The game ended while trying %s last time: no more render, the screen method instead. " ..
            "ssMethod render_png to try it anyway.", trying)
        self:saveSettings()
    end
    local method = self:getMethod(self.method)
    self.renderOk = method ~= nil and method.render
end

function SS:saveSettings()
    createFolder(getUserProfileAppPath() .. "modSettings/")
    createFolder(self:getBaseDir())
    local xml = createXMLFile("ssSettings", self:getBaseDir() .. "settings.xml", "screenshotStudio")
    if xml ~= nil and xml ~= 0 then
        local crashed = {}
        for _, method in ipairs(self.METHODS) do
            if self.crashed[method.id] then table.insert(crashed, method.id) end
        end
        setXMLString(xml, "screenshotStudio.method", self.method or "")
        setXMLString(xml, "screenshotStudio.trying", self.trying or "")
        setXMLString(xml, "screenshotStudio.crashed", table.concat(crashed, " "))
        local i = 0
        for map, s in pairs(self.spots) do
            local key = string.format("screenshotStudio.spots.spot(%d)", i)
            setXMLString(xml, key .. "#map", map)
            setXMLString(xml, key .. "#x", string.format("%.2f", s.x))
            setXMLString(xml, key .. "#z", string.format("%.2f", s.z))
            setXMLString(xml, key .. "#yaw", string.format("%.4f", s.yaw))
            i = i + 1
        end
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

-- the first method from index i on that hasn't crashed the game (screen never does)
function SS:firstMethod(i)
    for j = i or 1, #self.METHODS do
        if not self.crashed[self.METHODS[j].id] then return j end
    end
    return #self.METHODS
end

function SS:render(path, format)
    return pcall(renderScreenshot, path, self.WIDTH, self.HEIGHT, self.WIDTH / self.HEIGHT, format,
        unpack(self.RENDER_ARGS))
end

-- Written to settings.xml BEFORE the render call: if the game dies, the next start knows.
function SS:startTrying(id)
    if self.trying == nil then
        self.trying = id
        self.tryingSince = nil
        self:saveSettings()
    end
end

function SS:stopTrying()
    if self.trying ~= nil then
        self.trying, self.tryingSince = nil, nil
        self:saveSettings()
    end
end

-- still running SURVIVE_MS after the first render call: render is safe in this game
function SS:checkTrying()
    if self.trying == nil or self.tryingSince == nil or now() - self.tryingSince < self.SURVIVE_MS then return end
    local id = self.trying
    if self.method == id then
        self.renderOk = true
        log("%s works and the game is fine: kept", id)
    end
    self:stopTrying()
end


-- ------------------------------------------------------------------ what's in front of us
-- The vehicle we sit in with everything attached, and the one we photograph: an attached
-- implement from a mod wins over the vehicle (a header on a base-game windrower).
-- ------------------------------------------------------------------ ssTarget / ssList
-- Vehicles (tractors, implements, trailers; not pallets) and buildings whose name contains `text`
-- (any case; nil = all), nearest first: { kind, obj, name, mod, dist, on }
function SS:findObjects(text)
    local player = g_localPlayer
    if player == nil or g_currentMission == nil then return {} end
    local px, _, pz = player:getPosition()
    local want = text ~= nil and text ~= "" and text:lower() or nil
    local list = {}
    local function add(kind, obj, name)
        -- the shop name, the mod name or the XML file name: "PowerRoll" finds the Dalbo roller even
        -- when the game names it differently
        if want ~= nil then
            local file = tostring(obj.configFileName or ""):match("([^/\\]+)$") or ""
            local hay = (name .. " " .. tostring(obj.customEnvironment or "") .. " " .. file):lower()
            if not hay:find(want, 1, true) then return end
        end
        local x, _, z = getWorldTranslation(obj.rootNode)
        local on
        if kind == "vehicle" and obj.getRootVehicle ~= nil then
            local root = obj:getRootVehicle()
            if root ~= nil and root ~= obj then on = vehicleName(root) end
        end
        table.insert(list, { kind = kind, obj = obj, name = name, mod = obj.customEnvironment or "basegame",
            dist = MathUtil.vector2Length(x - px, z - pz), on = on })
    end
    local vehicles = g_currentMission.vehicleSystem
    for _, v in ipairs(vehicles ~= nil and vehicles.vehicles or {}) do
        if not isGone(v) and not v.isPallet then add("vehicle", v, vehicleName(v)) end
    end
    local placeables = g_currentMission.placeableSystem
    for _, p in ipairs(placeables ~= nil and placeables.placeables or {}) do
        if not isGone(p) then add("building", p, placeableName(p)) end
    end
    table.sort(list, function(a, b) return a.dist < b.dist end)
    return list
end

function SS:getTarget()
    local t = self.target
    if t == nil then return nil end
    if isGone(t.vehicle or t.placeable) then
        log("Target %s is gone (sold or deleted): back to what you sit in or stand next to", tostring(t.name))
        self.target = nil
        return nil
    end
    return t
end

-- ssTarget PX150     the nearest vehicle, implement or building with that in its name
-- ssTarget           back to what you sit in or stand next to
function SS:setTarget(text)
    if text == nil or text == "" then
        self.target = nil
        return "Target: what you sit in, or the nearest building/vehicle"
    end
    local found = self:findObjects(text)
    local best = found[1]
    if best == nil then
        local near = {}
        for i, o in ipairs(self:findObjects(nil)) do
            if i > 8 then break end
            table.insert(near, string.format("%s (%s, %.0f m)", o.name, o.mod, o.dist))
        end
        log("ssTarget %s: no vehicle or building with that in its name, mod or file. Nearest: %s", text,
            table.concat(near, "; "))
        return string.format("Nothing called '%s'. ssList shows the names near you.", text)
    end
    self.target = best.kind == "vehicle" and { vehicle = best.obj, name = best.name }
        or { placeable = best.obj, name = best.name }
    local more = #found > 1 and string.format(" (%d more match; the nearest wins: ssList %s)", #found - 1, text) or ""
    return string.format("Target: %s %s (%s, %.0f m%s)%s", best.kind, best.name, best.mod, best.dist,
        best.on ~= nil and (", on " .. best.on) or "", more)
end

-- ssList        everything within LIST_RADIUS
-- ssList krone  everything on the map with "krone" in its name
function SS:listObjects(text)
    local found = self:findObjects(text)
    local shown = 0
    for _, o in ipairs(found) do
        if (text ~= nil and text ~= "") or o.dist <= self.LIST_RADIUS then
            shown = shown + 1
            if shown <= self.MAX_LIST then
                log("%5.0f m  %-8s %s (%s)%s", o.dist, o.kind, o.name, o.mod, o.on ~= nil and ("  on " .. o.on) or "")
            end
        end
    end
    if shown == 0 then
        return (text ~= nil and text ~= "") and ("Nothing called '" .. text .. "'")
            or string.format("Nothing within %d m", self.LIST_RADIUS)
    end
    return string.format("%d found%s; ssTarget <part of a name> picks one", shown,
        shown > self.MAX_LIST and string.format(" (first %d listed)", self.MAX_LIST) or "")
end

-- Sitting in the target (or what it hangs on): the player's own camera shows it
function SS:sittingInTarget()
    local t = self:getTarget()
    local seat = self:getSeatVehicle()
    if t == nil or t.vehicle == nil or seat == nil then return false end
    local root = function(v) return v.getRootVehicle ~= nil and v:getRootVehicle() or v end
    return root(seat) == root(t.vehicle)
end

-- The view for a target you don't sit in: a vehicle framed from ssView's angle, a building from
-- the front three-quarter. nil = player's view.
function SS:targetCamera()
    local target = self:getTarget()
    if target == nil or self:sittingInTarget() then return nil end
    if target.vehicle ~= nil then return self:viewOf(target.vehicle) end
    local t = self:getOrbitTarget()
    if t == nil then return nil end
    if t.corners ~= nil then return self:clearView(t.corners, t.yaw, t.subjects, t.what) end
    return self:orbitPosition(t, t.yaw + math.rad(self.HERO_ANGLE), self.HERO_ELEVATION, math.max(7, t.radius * 2.4))
end

-- ssShot auto: the machine you sit in (everything attached) or the target, framed
function SS:autoCamera()
    local target = self:getTarget()
    if target ~= nil and target.placeable ~= nil then return self:targetCamera() end
    local group = self:getVehicleGroup()
    if group == nil then return nil end
    return self:viewOf(group.root, group.list)
end

-- With ssTarget on a vehicle: that vehicle (with what it's attached to) wherever you are.
function SS:getVehicleGroup()
    local target = self:getTarget()
    if target ~= nil then
        if target.vehicle ~= nil then return self:groupOf(target.vehicle, target.vehicle) end
        return nil      -- a building
    end
    return self:groupOf(self:getSeatVehicle())
end

function SS:getSeatVehicle()
    local player = g_localPlayer
    return player ~= nil and player.getCurrentVehicle ~= nil and player:getCurrentVehicle() or nil
end

-- The vehicle with everything attached; the subject is `subject`, else an implement from a mod.
function SS:groupOf(vehicle, subject)
    if vehicle == nil then return nil end
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
        for k, v in pairs(root:getChildVehicles() or {}) do add(type(v) == "table" and v or (type(k) == "table" and k or nil)) end
    end
    local what = vehicleName(subject or root)
    if subject == nil then
        subject = root
        for _, v in ipairs(list) do
            if v.customEnvironment ~= nil and (subject.customEnvironment == nil or v ~= root) then
                subject = v
            end
        end
    end
    return { root = root, list = list, subject = subject, what = what }
end

-- Returns { x, y, z, radius, yaw, mod, what } or nil.
function SS:getOrbitTarget()
    local player = g_localPlayer
    if player == nil then return nil end

    local group = self:getVehicleGroup()
    if group ~= nil then
        local minX, minZ, maxX, maxZ, sumY, maxH = math.huge, math.huge, -math.huge, -math.huge, 0, 2
        for _, v in ipairs(group.list) do
            local x, y, z = getWorldTranslation(v.rootNode)
            local size = v.size or {}
            local r = math.max(size.length or 4, size.width or 3) / 2
            minX, maxX = math.min(minX, x - r), math.max(maxX, x + r)
            minZ, maxZ = math.min(minZ, z - r), math.max(maxZ, z + r)
            sumY = sumY + y
            maxH = math.max(maxH, size.height or 3)
        end
        local cx, cz = (minX + maxX) / 2, (minZ + maxZ) / 2
        local radius = math.max(maxX - minX, maxZ - minZ) / 2
        local dx, _, dz = localDirectionToWorld(group.root.rootNode, 0, 0, 1)
        local corners = self:cornersOf(group.list)
        local ty = sumY / #group.list + maxH * 0.4
        if #corners > 0 then      -- the middle of the real size boxes, where the framed camera aims
            local lo, hi = { math.huge, math.huge, math.huge }, { -math.huge, -math.huge, -math.huge }
            for _, c in ipairs(corners) do
                for i = 1, 3 do lo[i], hi[i] = math.min(lo[i], c[i]), math.max(hi[i], c[i]) end
            end
            cx, ty, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2, (lo[3] + hi[3]) / 2
        end
        return {
            x = cx, y = ty, z = cz,
            radius = math.max(radius, 2),
            yaw = math.atan2(dx, dz),
            mod = group.subject.customEnvironment or "basegame",
            what = group.what,
            corners = corners,    -- the orbit frames these from every angle
            subjects = SS.subjectSet(group.list),
        }
    end

    local target = self:getTarget()
    if target ~= nil and target.placeable ~= nil then
        return self:placeableTarget(target.placeable)
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
    if best ~= nil then return self:placeableTarget(best) end
    return nil
end

function SS:placeableTarget(p)
    local x, y, z = getWorldTranslation(p.rootNode)
    local dx, _, dz = localDirectionToWorld(p.rootNode, 0, 0, 1)
    local t = {
        x = x, y = y + 3, z = z,
        radius = self.placeableRadius or self.PLACEABLE_RADIUS,
        yaw = math.atan2(dx, dz),
        mod = p.customEnvironment or "basegame",
        what = placeableName(p),
        subjects = { [p] = true },
    }
    -- its placement test areas give a real box (ssRadius set by hand wins)
    local corners = self.placeableRadius == nil and self:placeableCorners(p) or {}
    if #corners > 0 then
        local lo, hi = { math.huge, math.huge, math.huge }, { -math.huge, -math.huge, -math.huge }
        for _, c in ipairs(corners) do
            for i = 1, 3 do lo[i], hi[i] = math.min(lo[i], c[i]), math.max(hi[i], c[i]) end
        end
        t.x, t.y, t.z = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2, (lo[3] + hi[3]) / 2
        t.radius = math.max(hi[1] - lo[1], hi[3] - lo[3]) / 2
        t.corners = corners
    end
    return t
end

function SS:getCurrentModName()
    if self.forcedFolder ~= nil then return self.forcedFolder end
    local group = self:getVehicleGroup()
    if group ~= nil then return group.subject.customEnvironment or "basegame" end
    local target = self:getTarget()
    if target ~= nil and target.placeable ~= nil then return target.placeable.customEnvironment or "basegame" end
    return "misc"
end

function SS:getCurrentWhat()
    local group = self:getVehicleGroup()
    if group ~= nil then return group.what end
    local target = self:getTarget()
    return target ~= nil and target.placeable ~= nil and placeableName(target.placeable) or nil
end

-- Every color: the target, the vehicle we photograph, or on foot the nearest vehicle (mods first).
function SS:getColorVehicle()
    local target = self:getTarget()
    if target ~= nil then return target.vehicle end      -- nil for a building: no colors
    local group = self:getVehicleGroup()
    if group ~= nil then return group.subject end
    local player = g_localPlayer
    if player == nil or g_currentMission == nil then return nil end
    local px, _, pz = player:getPosition()
    local system = g_currentMission.vehicleSystem
    local best, bestDist
    for _, v in ipairs(system ~= nil and system.vehicles or {}) do
        if v.rootNode ~= nil and v.configFileName ~= nil and not v.isPallet then
            local x, _, z = getWorldTranslation(v.rootNode)
            local d = MathUtil.vector2Length(x - px, z - pz)
            local score = d + (v.customEnvironment == nil and 50 or 0)
            if d < self.MAX_VEHICLE_DISTANCE and (bestDist == nil or score < bestDist) then
                best, bestDist = v, score
            end
        end
    end
    return best
end


-- ------------------------------------------------------------------ quiet: other mods' drawing
-- Hiding the HUD leaves what other mods draw themselves: Courseplay's bar, AutoDrive's labels and
-- route lines, the game's hint boxes ("Please start the engine first!"). For a batch (not UI
-- shots) the engine's 2D and debug drawing functions are swapped for nothing in the real global
-- table, where the game and every mod look them up as they draw; AutoDrive's route lines are 3D
-- objects that it hides by itself in a frame where nothing asks for them, so its add*Task
-- functions do nothing meanwhile. Everything is put back when the batch ends.
SS.QUIET_FUNCTIONS = { "renderText", "renderOverlay", "drawFilledRect", "drawDebugLine", "drawDebugPoint",
    "drawDebugTriangle", "drawDebugArrow", "drawDebugAreaRectangle", "renderText3D", "renderTextAtWorldPosition" }
SS.QUIET_AUTODRIVE = { "addLineTask", "addArrowTask", "addSmallSphereTask", "addMarkerTask", "addCrossTask",
    "addSphereTask" }
SS.quietEnabled = true
SS.muted = nil       -- { { table, key, original } } while quiet

local function nothing() end

local function field(t, key)
    local ok, v = pcall(function() return t[key] end)     -- normal lookup: also what a metatable supplies
    if ok then return v end
    return nil
end

-- AutoDrive's drawing manager lives in AutoDrive's own environment, a global named after the mod
local function findAutoDriveDrawing(g)
    local names = {}
    if g_modManager ~= nil and g_modManager.getActiveMods ~= nil then
        local ok, mods = pcall(g_modManager.getActiveMods, g_modManager)
        for _, mod in ipairs(ok and mods or {}) do
            if mod.modName ~= nil then table.insert(names, mod.modName) end
        end
    end
    table.insert(names, "FS25_AutoDrive")
    for _, name in ipairs(names) do
        local env = field(g, name)
        local dm = type(env) == "table" and field(env, "ADDrawingManager") or nil
        if type(dm) == "table" then return dm, name end
    end
    local dm = field(g, "ADDrawingManager")
    if type(dm) == "table" then return dm, "global" end
    return nil
end

function SS:setQuiet(on)
    if on then
        if self.muted ~= nil or not self.quietEnabled then return end
        local g = trueGlobals()
        local muted, count = {}, 0
        -- written straight into the table: shadows a function the table only gets from its metatable
        local function mute(t, key)
            local f = field(t, key)
            if type(f) == "function" then
                table.insert(muted, { t, key, f, rawget(t, key) ~= nil })
                rawset(t, key, nothing)
                count = count + 1
            end
        end
        for _, name in ipairs(self.QUIET_FUNCTIONS) do mute(g, name) end
        -- each mod also has its own environment, which can hold its own copies (Courseplay's bar,
        -- AutoDrive's labels still showed with only the global table muted)
        -- ... or look names up in another table than the global one: follow each __index chain
        local seen = { [g] = true }
        local function muteIn(t, depth)
            if type(t) ~= "table" or seen[t] or depth > 4 then return end
            seen[t] = true
            for _, name in ipairs(self.QUIET_FUNCTIONS) do
                if rawget(t, name) ~= nil then mute(t, name) end
            end
            local ok, mt = pcall(getmetatable, t)
            if ok and type(mt) == "table" and type(rawget(mt, "__index")) == "table" then
                muteIn(rawget(mt, "__index"), depth + 1)
            end
        end
        local envs = 0
        if g_modManager ~= nil and g_modManager.getActiveMods ~= nil then
            local ok, mods = pcall(g_modManager.getActiveMods, g_modManager)
            for _, mod in ipairs(ok and mods or {}) do
                local env = mod.modName ~= nil and field(g, mod.modName) or nil
                if type(env) == "table" and env ~= g then
                    envs = envs + 1
                    muteIn(env, 0)
                end
            end
        end
        muteIn(_G, 0)        -- this mod's own chain too
        local ad, where = findAutoDriveDrawing(g)
        local adCount = count
        if ad ~= nil then
            for _, name in ipairs(self.QUIET_AUTODRIVE) do mute(ad, name) end
        end
        self.muted = muted
        if not self.quietLogged then
            self.quietLogged = true
            local viaGetfenv = pcall(getfenv, 0)
            log("Quiet: %d drawing functions muted (%s, %d mod environments looked at), %s", adCount,
                viaGetfenv and "game's global table" or "no getfenv: this mod's table only, others may still show", envs,
                ad ~= nil and string.format("AutoDrive lines hidden (%s)", where) or "no AutoDrive found")
        end
    elseif self.muted ~= nil then
        for i = #self.muted, 1, -1 do
            local m = self.muted[i]
            rawset(m[1], m[2], m[4] and m[3] or nil)
        end
        self.muted = nil
    end
end

-- ssQuiet off: leave other mods' drawing in the pictures (e.g. to show a mod's own HUD)
function SS:consoleQuiet(state)
    if state == "off" then
        self.quietEnabled = false
    elseif state == "on" then
        self.quietEnabled = true
    else
        self.quietEnabled = not self.quietEnabled
    end
    return "Other mods' drawing during shots: " .. (self.quietEnabled and "hidden" or "shown")
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
-- ------------------------------------------------------------------ framing
-- The camera is placed so the vehicle's whole size box (8 corners, its length, width and
-- height around its root node) fits the 16:9 picture, from any angle: for each corner, how far
-- back must the camera be so the corner is inside the frame; the farthest wins.
function SS:boxCorners(v)
    local s = v.size or {}
    local w, l, h = s.width or 3, s.length or 4, s.height or 3
    local wo, lo, ho = s.widthOffset or 0, s.lengthOffset or 0, s.heightOffset or 0
    local list = {}
    for _, dx in ipairs({ -w / 2, w / 2 }) do
        for _, dz in ipairs({ -l / 2, l / 2 }) do
            for _, dy in ipairs({ 0, h }) do
                local x, y, z = localToWorld(v.rootNode, dx + wo, dy + ho, dz + lo)
                table.insert(list, { x, y, z })
            end
        end
    end
    return list
end

-- The size box is the transport size: an unfolded implement (a 12 m roller with a 4.2 m size box)
-- sticks out of it. Its work areas (start/width/height nodes, on the ground) and its parts
-- (components) show where it really reaches; each is taken at the ground and up to its height.
function SS:reachPoints(v)
    local pts = {}
    local up = math.min(3, (v.size ~= nil and v.size.height) or 2)
    local function add(node)
        if node ~= nil and node ~= 0 then
            local ok, x, y, z = pcall(getWorldTranslation, node)
            if ok and x ~= nil then
                table.insert(pts, { x, y, z })
                table.insert(pts, { x, y + up, z })
            end
        end
    end
    -- folded, the work areas still mark the full working width (their nodes sit on the frame): only
    -- an unfolded machine reaches that far
    local unfolded = true
    if v.getIsUnfolded ~= nil then
        local ok, u = pcall(v.getIsUnfolded, v)
        unfolded = not ok or u ~= false
    end
    local spec = v.spec_workArea
    for _, area in ipairs(unfolded and spec ~= nil and spec.workAreas or {}) do
        add(area.start); add(area.width); add(area.height)
    end
    for _, c in ipairs(v.components or {}) do add(c.node) end
    return pts
end

function SS:cornersOf(vehicles)
    local all = {}
    for _, v in ipairs(vehicles) do
        for _, c in ipairs(self:boxCorners(v)) do table.insert(all, c) end
        for _, p in ipairs(self:reachPoints(v)) do table.insert(all, p) end
    end
    return all
end

-- { cx, cy, cz, tx, ty, tz } framing `corners` from `angle` (world yaw, radians) and `elevation`
-- (degrees), plus the distance
function SS:frameCamera(corners, angle, elevation)
    local minX, minY, minZ, maxX, maxY, maxZ = math.huge, math.huge, math.huge, -math.huge, -math.huge, -math.huge
    for _, c in ipairs(corners) do
        minX, maxX = math.min(minX, c[1]), math.max(maxX, c[1])
        minY, maxY = math.min(minY, c[2]), math.max(maxY, c[2])
        minZ, maxZ = math.min(minZ, c[3]), math.max(maxZ, c[3])
    end
    local tx, ty, tz = (minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2
    local el = math.rad(elevation)
    local sa, ca, se, ce = math.sin(angle), math.cos(angle), math.sin(el), math.cos(el)
    local ux, uy, uz = sa * ce, se, ca * ce            -- from the target to the camera
    local rx, rz = ca, -sa                              -- right (horizontal)
    local vx, vy, vz = -se * sa, ce, -se * ca           -- up, square to both
    local tanV = math.tan(math.rad(self.FOV) / 2) * self.FRAME_FILL
    local tanH = math.tan(math.rad(self.FOV) / 2) * (self.WIDTH / self.HEIGHT) * self.FRAME_FILL
    local d = self.MIN_DISTANCE
    for _, c in ipairs(corners) do
        local px, py, pz = c[1] - tx, c[2] - ty, c[3] - tz
        local along = px * ux + py * uy + pz * uz
        d = math.max(d, along + math.abs(px * rx + pz * rz) / tanH, along + math.abs(px * vx + py * vy + pz * vz) / tanV)
    end
    local cx, cy, cz = tx + ux * d, ty + uy * d, tz + uz * d
    if g_currentMission ~= nil and g_currentMission.terrainRootNode ~= nil then
        cy = math.max(cy, getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, cx, 0, cz) + 1.2)
    end
    return { cx, cy, cz, tx, ty, tz }, d
end

-- ------------------------------------------------------------------ in the way?
-- Rays from the camera to the middle and the 8 corners of the subject's box, each stopping where it
-- enters the box: a hit before that is in the way (a wall, a pole, another car), unless it is part
-- of the subject. raycastClosest calls back at once (AutoDrive relies on that too).
local function rayBoxEntry(ox, oy, oz, dx, dy, dz, lo, hi)
    local tmin, tmax = 0, math.huge
    local o, d = { ox, oy, oz }, { dx, dy, dz }
    for i = 1, 3 do
        if math.abs(d[i]) < 1e-9 then
            if o[i] < lo[i] or o[i] > hi[i] then return nil end
        else
            local t1, t2 = (lo[i] - o[i]) / d[i], (hi[i] - o[i]) / d[i]
            if t1 > t2 then t1, t2 = t2, t1 end
            tmin, tmax = math.max(tmin, t1), math.min(tmax, t2)
            if tmin > tmax then return nil end
        end
    end
    return tmin
end

function SS:rayMask()
    if self.mask == nil then
        local mask = 0
        if CollisionFlag ~= nil then
            -- not TERRAIN: rays to the bottom of the machine graze the ground right in front of it
            for _, name in ipairs({ "DEFAULT", "TREE", "DYNAMIC_OBJECT", "VEHICLE", "BUILDING", "STATIC_OBJECT" }) do
                if type(CollisionFlag[name]) == "number" then mask = mask + CollisionFlag[name] end
            end
        end
        self.mask = mask > 0 and mask or nil
    end
    return self.mask
end

function SS:onViewRay(hitObjectId, x, y, z, distance)
    if hitObjectId ~= nil and hitObjectId ~= 0 then self.rayHit, self.rayDistance = hitObjectId, distance end
end

-- the object a hit node belongs to (a vehicle, a building), or nil
function SS:nodeObject(id)
    if g_currentMission == nil or g_currentMission.getNodeObject == nil then return nil end
    local ok, obj = pcall(g_currentMission.getNodeObject, g_currentMission, id)
    return ok and obj or nil
end

-- true, or false plus what is in the way. subjects: { [object] = true } that may be hit.
function SS:isClear(pos, corners, subjects)
    if not self.avoidObstacles or (raycastClosest == nil and overlapBox == nil) then return true end
    local lo, hi = { math.huge, math.huge, math.huge }, { -math.huge, -math.huge, -math.huge }
    for _, c in ipairs(corners) do
        for i = 1, 3 do lo[i], hi[i] = math.min(lo[i], c[i]), math.max(hi[i], c[i]) end
    end
    -- 27 points: the middle, the 8 corners, the 12 edge middles and 6 face middles of the box
    -- (thin poles slip between fewer rays)
    -- the lowest points a bit above the ground, so no ray grazes it
    local bottom = lo[2] + math.min(0.5, (hi[2] - lo[2]) * 0.2)
    local points = {}
    for _, fx in ipairs({ 0, 0.5, 1 }) do
        for _, fy in ipairs({ 0, 0.5, 1 }) do
            for _, fz in ipairs({ 0, 0.5, 1 }) do
                table.insert(points, { lo[1] + (hi[1] - lo[1]) * fx, bottom + (hi[2] - bottom) * fy, lo[3] + (hi[3] - lo[3]) * fz })
            end
        end
    end
    local terrain = g_currentMission ~= nil and g_currentMission.terrainRootNode or nil
    local cx, cy, cz = pos[1], pos[2], pos[3]
    for _, p in ipairs(points) do
        local dx, dy, dz = p[1] - cx, p[2] - cy, p[3] - cz
        local len = math.sqrt(dx * dx + dy * dy + dz * dz)
        if len > 0.5 then
            dx, dy, dz = dx / len, dy / len, dz / len
            -- stops 0.8 m before the box: parts of the machine sticking out of it don't count
            local reach = math.min(len, rayBoxEntry(cx, cy, cz, dx, dy, dz, lo, hi) or len) - 0.8
            if reach > 0.5 and raycastClosest ~= nil then
                self.rayHit, self.rayDistance = nil, nil
                pcall(raycastClosest, cx, cy, cz, dx, dy, dz, reach, "onViewRay", self, self:rayMask())
                if self.rayHit ~= nil and self.rayHit ~= terrain then
                    local obj = self:nodeObject(self.rayHit)
                    local root = obj ~= nil and obj.getRootVehicle ~= nil and obj:getRootVehicle() or nil
                    if not (obj ~= nil and (subjects[obj] or (root ~= nil and subjects[root]))) then
                        local what
                        if obj == nil then
                            local ok, nodeName = pcall(getName, self.rayHit)
                            what = string.format("something ('%s', %.1f m from the camera)",
                                ok and tostring(nodeName) or "?", self.rayDistance or 0)
                        else
                            what = obj.getRootVehicle ~= nil and vehicleName(obj) or placeableName(obj)
                        end
                        return false, what
                    end
                end
            end
        end
    end
    -- trees: rays only hit the trunk, the crown has no collision. Along the line to the middle,
    -- a trunk within CROWN metres means branches in the picture.
    if overlapBox ~= nil and CollisionFlag ~= nil and type(CollisionFlag.TREE) == "number" then
        local tx, ty, tz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2, (lo[3] + hi[3]) / 2
        local dx, dy, dz = tx - cx, ty - cy, tz - cz
        local len = math.sqrt(dx * dx + dy * dy + dz * dz)
        if len > 1 then
            dx, dy, dz = dx / len, dy / len, dz / len
            local reach = math.min(len, rayBoxEntry(cx, cy, cz, dx, dy, dz, lo, hi) or len) - self.CROWN
            self.spotOwn = subjects
            local t = 1
            while t <= reach do
                self.spotHits = 0
                pcall(overlapBox, cx + dx * t, cy + dy * t, cz + dz * t, 0, 0, 0, self.CROWN, self.CROWN, self.CROWN,
                    "onSpotHit", self, CollisionFlag.TREE, true, true, true, false)
                if self.spotHits > 0 then return false, string.format("trees (%.0f m from the camera)", t) end
                t = t + self.CROWN
            end
        end
    end
    return true
end

-- The framed view from `angleDeg` off `frontYaw`; when that is blocked and the angle wasn't set
-- with ssView, other angles in turn (the other front corner, steeper/shallower, side, rear corners).
SS.ALTERNATIVE_ANGLES = { 1, -1, 1.6, -1.6, 0.45, -0.45, 2.6, -2.6, 4.1, -4.1 }   -- times VIEW_ANGLE
function SS:clearView(corners, frontYaw, subjects, what)
    local fixed = self.viewAngle ~= nil
    local base = self.viewAngle or self.VIEW_ANGLE
    local elevation = self.viewElevation or self.VIEW_ELEVATION
    local tries = fixed and { base } or {}
    if not fixed then
        for _, f in ipairs(self.ALTERNATIVE_ANGLES) do table.insert(tries, base * f) end
    end
    local first, firstBlock
    for i, deg in ipairs(tries) do
        local pos = self:frameCamera(corners, frontYaw + math.rad(deg), elevation)
        local clear, block = self:isClear(pos, corners, subjects)
        if clear then
            if i > 1 then log("View of %s: %s in the way at %g degrees, taken from %g", tostring(what), tostring(firstBlock), tries[1], deg) end
            return pos
        end
        first, firstBlock = first or pos, firstBlock or block
    end
    log("View of %s: %s in the way%s; taken anyway", tostring(what), tostring(firstBlock),
        fixed and " (ssView fixed the angle)" or " from every side")
    return first
end

function SS.subjectSet(list)
    local set = {}
    for _, o in ipairs(list) do
        set[o] = true
        if o.getRootVehicle ~= nil then
            local ok, root = pcall(o.getRootVehicle, o)
            if ok and root ~= nil then set[root] = true end
        end
        if o.getChildVehicles ~= nil then
            -- a list or a table keyed by vehicle (FS25): take every vehicle in it, key or value
            local ok, children = pcall(o.getChildVehicles, o)
            for k, c in pairs(ok and type(children) == "table" and children or {}) do
                if type(c) == "table" then set[c] = true end
                if type(k) == "table" then set[k] = true end
            end
        end
    end
    return set
end

-- The view of a vehicle (with `others` in the frame too) from ssView's angle, clear of obstacles
function SS:viewOf(v, others)
    local dx, _, dz = localDirectionToWorld(v.rootNode, 0, 0, 1)
    local list = { v }
    for _, o in ipairs(others or {}) do if o ~= v then table.insert(list, o) end end
    return self:clearView(self:cornersOf(list), math.atan2(dx, dz), SS.subjectSet(list), vehicleName(v))
end

-- A building's box from its placement test areas (start node + end node: width, height, length in
-- the start node's space). Flat areas get a height of about half their longer side.
function SS:placeableCorners(p)
    local spec = p.spec_placement
    local corners = {}
    for _, area in ipairs(spec ~= nil and spec.testAreas or {}) do
        local s, e = area.startNode, area.endNode
        if s ~= nil and e ~= nil and worldToLocal ~= nil then
            local ex, ey, ez = worldToLocal(s, getWorldTranslation(e))
            if math.abs(ey) < 1 then
                ey = math.min(18, math.max(4, 0.45 * math.max(math.abs(ex), math.abs(ez))))
            end
            for _, x in ipairs({ 0, ex }) do
                for _, y in ipairs({ 0, ey }) do
                    for _, z in ipairs({ 0, ez }) do
                        local wx, wy, wz = localToWorld(s, x, y, z)
                        table.insert(corners, { wx, wy, wz })
                    end
                end
            end
        end
    end
    return corners
end

-- ssClear off: take framed views even with something in the way (no rays)
function SS:consoleClear(state)
    if state == "off" then self.avoidObstacles = false
    elseif state == "on" then self.avoidObstacles = true
    else self.avoidObstacles = not self.avoidObstacles end
    return "Looking for obstacles in framed views: " .. (self.avoidObstacles and "on" or "off")
end

-- ssView 35 12: front three-quarter (default); -35 the other front corner; 180 the rear; 90 side-on
function SS:consoleView(angle, elevation)
    if angle == nil or angle == "" then
        self.viewAngle, self.viewElevation = nil, nil
    else
        self.viewAngle = tonumber(angle) or self.VIEW_ANGLE
        self.viewElevation = tonumber(elevation) or self.viewElevation
    end
    return string.format("View for colors and auto shots: %g degrees off the front, %g degrees up",
        self.viewAngle or self.VIEW_ANGLE, self.viewElevation or self.VIEW_ELEVATION)
end

-- One camera position: `angle` around the target (radians, world), `elevation` degrees up
function SS:orbitPosition(t, angle, elevation, dist)
    local cx = t.x + math.sin(angle) * dist
    local cz = t.z + math.cos(angle) * dist
    local cy = t.y + dist * math.tan(math.rad(elevation))
    local ground = getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, cx, 0, cz)
    cy = math.max(cy, ground + 1.2)
    return { cx, cy, cz, t.x, t.y, t.z }
end

-- In the way: a little to either side first, then a bit higher (looking steeply down at the roof
-- makes a poor picture); still blocked: left out. Returns the positions and what was skipped.
SS.ORBIT_DODGES = { { 15, 0 }, { -15, 0 }, { 30, 0 }, { -30, 0 }, { 0, 15 }, { 15, 15 }, { -15, 15 } }

function SS:orbitPositions(t, count, distance, unchecked)
    local list, skipped = {}, {}
    local dist = distance or math.max(7, t.radius * 2.4)
    local function at(angle, elevation)
        if t.corners ~= nil and #t.corners > 0 and distance == nil then
            local pos = self:frameCamera(t.corners, angle, elevation)     -- the whole machine
            local clear, block = true, nil
            if not unchecked then clear, block = self:isClear(pos, t.corners, t.subjects or {}) end
            if not clear then
                pos = nil
                for _, try in ipairs(self.ORBIT_DODGES) do
                    local p = self:frameCamera(t.corners, angle + math.rad(try[1]), elevation + try[2])
                    if self:isClear(p, t.corners, t.subjects or {}) then pos = p; break end
                end
                if pos == nil then table.insert(skipped, tostring(block)) end
            end
            if pos ~= nil then table.insert(list, pos) end
        else
            table.insert(list, self:orbitPosition(t, angle, elevation, dist))
        end
    end
    local start = t.yaw + math.rad(35)          -- front three-quarter first
    for i = 0, count - 1 do
        at(start + i * 2 * math.pi / count, 15)
    end
    for _, a in ipairs({ 35, -35, 145, -145 }) do  -- low hero shots
        at(t.yaw + math.rad(a), 3)
    end
    return list, skipped
end


-- ------------------------------------------------------------------ the queue
function SS:isBusy()
    return self.session ~= nil
end

function SS:start(kind, shots, folder, opts)
    opts = opts or {}
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
        mod = opts.mod or folder,
        what = opts.what,
        stamp = getDate("%Y%m%d_%H%M%S"),
        index = 0,
        saved = {},          -- { file, kind, hud, light, color }
        prevCamera = g_cameraManager:getActiveCamera(),
        hudWasVisible = hud ~= nil and (hud.getIsVisible == nil or hud:getIsVisible()),
        keepHud = opts.keepHud,
        delayMs = opts.delayMs,
        colorVehicle = opts.colorVehicle,
        colorExtras = opts.colorExtras,
        storeItem = opts.storeItem,
    }
    if hud ~= nil and hud.setIsVisible ~= nil and not self.session.keepHud then
        hud:setIsVisible(false)
    end
    if opts.colorVehicle ~= nil then
        self:setVehicleVisible(self.session, false)
    end
    if not opts.keepHud then self:setQuiet(true) end   -- UI shots and render bursts keep everything
    self.queue = shots
    self:nextShot()
    return true
end

function SS:nextShot()
    local s = self.session
    if s == nil then return end
    self:deleteCopies(s)
    local shot = table.remove(self.queue, 1)
    if shot == nil then
        self:finish()
        return
    end
    s.index = s.index + 1
    s.shot = shot
    s.methodIndex = select(2, self:getMethod(self.method)) or self:firstMethod(1)
    if shot.camera ~= nil then
        self:placeCamera(unpack(shot.camera))
        if g_cameraManager:getActiveCamera() ~= self.camera then
            g_cameraManager:setActiveCamera(self.camera)
        end
    end
    s.settleMs = (s.index == 1 and shot.camera ~= nil) and self.FIRST_SETTLE_MS or self.SETTLE_MS
    if shot.waitMs ~= nil and s.index > 1 then
        s.settleMs = math.max(0, shot.waitMs - (now() - (s.lastCapture or now())))   -- from the last picture
    end
    if s.index == 1 and s.delayMs ~= nil then
        s.settleMs = s.delayMs
    end
    if shot.configId ~= nil then
        self:loadCopy(s, shot)     -- settles once the copy is there
        return
    end
    self:setState("settle")
end

function SS:setState(state)
    self.state = state
    self.stateStart = now()
end

function SS:shotPath(s, ext)
    local tag = s.shot.tag ~= nil and ("_" .. s.shot.tag) or ""
    return string.format("%s%s_%s_%02d%s%s", s.dir, s.shot.kind, s.stamp, s.index, tag, ext)
end

function SS:capture()
    local s = self.session
    local method = self.METHODS[s.methodIndex]
    -- UI shots show menus, which only the screen has.
    if s.shot.kind == "ui" then
        method = self:getMethod("screen")
    end
    local path = self:shotPath(s, method.ext)
    s.path = path
    s.lastCapture = now()

    local ok, err
    if method.render then
        if not self.renderOk then self:startTrying(method.id) end
        ok, err = self:render(path, method.format)
        if self.trying ~= nil and self.tryingSince == nil then self.tryingSince = now() end
    else
        ok, err = pcall(saveScreenshot, path)
    end
    if not ok then
        log("%s failed: %s", method.id, tostring(err))
    end

    if self.method ~= nil or s.shot.kind == "ui" then
        self:recordShot(s, path)
        self:setState("written")
    else
        self:setState("check")     -- finding out which method works
    end
end

function SS:recordShot(s, path)
    local light = self.light ~= nil and self.LIGHTS[self.light].id or "game"
    table.insert(s.saved, {
        file = path:match("([^/\\]+)$") or path,
        path = path,
        kind = s.shot.kind,
        hud = s.shot.kind == "ui",     -- everything else is taken with the HUD hidden or rendered without it
        light = light,
        color = s.shot.color,
    })
end

function SS:tick()
    if self.session == nil then return end
    local s = self.session
    local elapsed = now() - self.stateStart

    if self.state == "settle" and elapsed >= s.settleMs then
        self:capture()
    elseif self.state == "written" and elapsed >= 150 then
        self:nextShot()
    elseif self.state == "loading" and elapsed >= self.LOAD_TIMEOUT_MS then
        log("Color %s: the copy didn't load in %d s, skipped", tostring(s.shot.color), self.LOAD_TIMEOUT_MS / 1000)
        self:nextShot()
    elseif self.state == "check" then
        local method = self.METHODS[s.methodIndex]
        if fileExists(s.path) then
            self.method = method.id
            self:saveSettings()
            log("Screenshot method: %s (saved in settings.xml)", method.id)
            self:recordShot(s, s.path)
            self:nextShot()
        elseif elapsed >= self.CHECK_MS then
            log("%s wrote no file, trying the next method", method.id)
            if self.trying == method.id then self:stopTrying() end
            if s.methodIndex < #self.METHODS then
                s.methodIndex = self:firstMethod(s.methodIndex + 1)
                self:capture()
            else
                log("No method wrote a file. Look for errors above in the log.")
                self:finish()
            end
        end
    end
end

-- _shots_<stamp>_<kind>.xml: one <shot> per picture of the batch
function SS:writeShotList(s)
    if #s.saved == 0 then return end
    local path = string.format("%s_shots_%s_%s.xml", s.dir, s.stamp, s.kind)
    local xml = createXMLFile("ssShots", path, "shots")
    if xml == nil or xml == 0 then return end
    setXMLString(xml, "shots#mod", tostring(s.mod or ""))
    if s.what ~= nil then setXMLString(xml, "shots#what", tostring(s.what)) end
    for i, shot in ipairs(s.saved) do
        local key = string.format("shots.shot(%d)", i - 1)
        setXMLString(xml, key .. "#file", shot.file)
        setXMLString(xml, key .. "#kind", shot.kind)
        setXMLString(xml, key .. "#hud", shot.hud and "true" or "false")
        setXMLString(xml, key .. "#light", shot.light)
        if shot.color ~= nil then setXMLString(xml, key .. "#color", tostring(shot.color)) end
    end
    saveXMLFile(xml)
    delete(xml)
end

function SS:finish()
    local s = self.session
    if s == nil then return end
    self:setQuiet(false)
    self:deleteCopies(s)
    if s.colorVehicle ~= nil then
        self:setVehicleVisible(s, true)
    end
    if s.prevCamera ~= nil and g_cameraManager:getActiveCamera() ~= s.prevCamera then
        g_cameraManager:setActiveCamera(s.prevCamera)
    end
    local hud = g_currentMission ~= nil and g_currentMission.hud or nil
    if hud ~= nil and hud.setIsVisible ~= nil and s.hudWasVisible then
        hud:setIsVisible(true)
    end
    self.session, self.state, self.queue = nil, nil, {}
    if self.autorun ~= nil then self.autorun.pictures = self.autorun.pictures + #s.saved end
    self:writeShotList(s)
    log("%d picture(s) in %s", #s.saved, s.dir)
    for _, p in ipairs(s.saved) do log("  %s", p.path) end
    notify(string.format("Screenshot Studio: %d picture(s) in modSettings/%s/%s", #s.saved, self.MOD_NAME, s.folder))
end


-- ------------------------------------------------------------------ every color
function SS:setVehicleVisible(s, visible)
    if not visible then
        s.hidden = {}
        local list = { s.colorVehicle }
        for _, e in ipairs(s.colorExtras or {}) do table.insert(list, e.vehicle) end
        for _, v in ipairs(list) do
            for _, c in ipairs(v.components or {}) do
                if c.node ~= nil and (getVisibility == nil or getVisibility(c.node)) then
                    setVisibility(c.node, false)
                    table.insert(s.hidden, c.node)
                end
            end
        end
    else
        for _, node in ipairs(s.hidden or {}) do setVisibility(node, true) end
        s.hidden = nil
    end
end

-- Which option to go through: the given name, else the first color option with more than one choice.
-- "$l10n_configuration_hubColor" plus its translation, lower case: from <xxxConfigurations title="...">
function SS:configTitle(storeItem, name)
    local path = storeItem ~= nil and storeItem.xmlFilename or nil
    if path == nil then return "" end
    self.titleCache = self.titleCache or {}
    local key = path .. "|" .. name
    if self.titleCache[key] ~= nil then return self.titleCache[key] end
    local title = ""
    local ok, xml = pcall(loadXMLFile, "ssVehicle", path)
    if ok and xml ~= nil and xml ~= 0 then
        title = getXMLString(xml, "vehicle." .. name .. "Configurations#title") or ""
        delete(xml)
    end
    local text = title
    if title:sub(1, 6) == "$l10n_" and g_i18n ~= nil and g_i18n.getText ~= nil then
        local tok, translated = pcall(g_i18n.getText, g_i18n, title:sub(7), storeItem.customEnvironment)
        if tok and translated ~= nil then text = title .. " " .. tostring(translated) end
    end
    self.titleCache[key] = text:lower()
    return self.titleCache[key]
end

function SS:titleHas(title, words)
    for _, w in ipairs(words) do
        if title:find(w, 1, true) then return true end
    end
    return false
end

function SS:pickColorConfig(storeItem, name)
    local configs = storeItem.configurations or {}
    local function choices(n)
        local count = 0
        for _, item in ipairs(configs[n] or {}) do
            if item.isSelectable ~= false then count = count + 1 end
        end
        return count
    end
    if name ~= nil and name ~= "" then
        return configs[name] ~= nil and name or nil
    end
    -- what the option is called in the vehicle's XML decides: the body paint, not the hubs
    local candidates = {}
    for _, n in ipairs(self.COLOR_CONFIGS) do
        if choices(n) > 1 then table.insert(candidates, n) end
    end
    if #candidates > 0 then
        local fallback
        for _, n in ipairs(candidates) do
            local title = self:configTitle(storeItem, n)
            if self:titleHas(title, self.BODY_WORDS) then return n, title end
            if fallback == nil and not self:titleHas(title, self.NOT_BODY_WORDS) then fallback = n end
        end
        return fallback or candidates[1], self:configTitle(storeItem, fallback or candidates[1])
    end
    local manager = g_vehicleConfigurationManager
    local names = {}
    for n in pairs(configs) do table.insert(names, n) end
    table.sort(names)
    for _, n in ipairs(names) do
        local isColor = false
        if manager ~= nil and manager.getConfigurationSelectorType ~= nil and ConfigurationUtil ~= nil
            and ConfigurationUtil.SELECTOR_COLOR ~= nil then
            local ok, sel = pcall(manager.getConfigurationSelectorType, manager, n)
            isColor = ok and sel == ConfigurationUtil.SELECTOR_COLOR
        else
            isColor = n:lower():find("color") ~= nil
        end
        if isColor and choices(n) > 1 then return n end
    end
    if choices("design") > 1 then return "design" end
    return nil
end

function SS:listOptions(storeItem)
    local list = {}
    for n, items in pairs(storeItem.configurations or {}) do
        if #items > 1 then table.insert(list, string.format("%s (%d)", n, #items)) end
    end
    table.sort(list)
    return table.concat(list, ", ")
end

function SS:colors(configName)
    local v = self:getColorVehicle()
    if v == nil and self:getTarget() ~= nil then
        log("Every color: the target %s is a building, it has no colors", tostring(self.target.name))
        return false
    end
    if v == nil then
        notify("Screenshot Studio: sit in the vehicle or stand next to it")
        log("Every color: no vehicle (sit in it, or stand within %d m)", self.MAX_VEHICLE_DISTANCE)
        return false
    end
    local storeItem = v.configFileName ~= nil and g_storeManager ~= nil
        and g_storeManager:getItemByXMLFilename(v.configFileName) or nil
    if storeItem == nil or VehicleLoadingData == nil then
        log("Every color: %s has no shop entry", vehicleName(v))
        return false
    end
    local name, title = self:pickColorConfig(storeItem, configName)
    if name == nil then
        log("Every color: %s has no color option%s. Its options: %s", vehicleName(v),
            configName ~= nil and (" called " .. configName) or "", self:listOptions(storeItem))
        notify("Screenshot Studio: no color options on " .. vehicleName(v))
        return false
    end

    local shots = {}
    -- framed with what it's hitched to (a beet harvester with its header), the same for every color:
    -- nothing can move it
    local group = self:groupOf(v)
    local camera = self:viewOf(v, group ~= nil and group.list or nil)
    -- what's hitched to it changes color with it (the header on a Ropa): same option, else its own
    -- body color; the color matched by name, else by its place in the list
    local extras = {}
    for _, o in ipairs(group ~= nil and group.list or {}) do
        if o ~= v and o.configFileName ~= nil then
            local item = g_storeManager:getItemByXMLFilename(o.configFileName)
            local cfg = item ~= nil and ((item.configurations or {})[name] ~= nil and #item.configurations[name] > 1 and name
                or self:pickColorConfig(item)) or nil
            if cfg ~= nil then table.insert(extras, { vehicle = o, storeItem = item, config = cfg }) end
        end
    end
    local function match(e, label, i)
        local list = e.storeItem.configurations[e.config]
        for j, it in ipairs(list) do
            if it.name ~= nil and tostring(it.name):lower() == label:lower() then return it.index or j end
        end
        local it = list[i]
        return it ~= nil and (it.index or i) or nil
    end
    for i, item in ipairs(storeItem.configurations[name]) do
        if item.isSelectable ~= false and #shots < self.MAX_COLORS then
            local label = item.name ~= nil and tostring(item.name) or string.format("%s %d", name, i)
            local extraIds = {}
            for k, e in ipairs(extras) do extraIds[k] = match(e, label, i) end
            table.insert(shots, { kind = "color", config = name, configId = item.index or i, extraIds = extraIds,
                color = label, tag = safeName(label):sub(1, 32), camera = camera })
        end
    end
    local mod = v.customEnvironment or "basegame"
    local withText = ""
    if #extras > 0 then
        local names = {}
        for _, e in ipairs(extras) do table.insert(names, vehicleName(e.vehicle) .. " (" .. e.config .. ")") end
        withText = ", with " .. table.concat(names, ", ")
    end
    log("Every color of %s: %d x %s%s%s (other options: %s; ssColors <option> picks one)", vehicleName(v), #shots, name,
        (title ~= nil and title ~= "") and (" \"" .. title .. "\"") or "", withText, self:listOptions(storeItem))
    return self:start("color", shots, self.forcedFolder or mod,
        { mod = mod, what = vehicleName(v), colorVehicle = v, storeItem = storeItem, colorExtras = extras })
end

-- One copy per colored vehicle (the main one and what's hitched to it); the picture waits for all.
function SS:loadCopy(s, shot)
    local loads = { { vehicle = s.colorVehicle, storeItem = s.storeItem, config = shot.config, id = shot.configId, main = true } }
    for k, e in ipairs(s.colorExtras or {}) do
        local id = shot.extraIds ~= nil and shot.extraIds[k] or nil
        if id ~= nil then table.insert(loads, { vehicle = e.vehicle, storeItem = e.storeItem, config = e.config, id = id }) end
    end
    s.copies, s.pendingLoads, s.mainFailed = {}, #loads, false
    -- The callbacks can come at once (on an error), so the state is set first.
    self:setState("loading")
    for _, l in ipairs(loads) do
        local v = l.vehicle
        local configs = {}
        for k, id in pairs(v.configurations or {}) do configs[k] = id end
        configs[l.config] = l.id
        local x, y, z = getWorldTranslation(v.rootNode)
        local rx, ry, rz = getWorldRotation(v.rootNode)
        local data = VehicleLoadingData.new()
        data:setStoreItem(l.storeItem)
        data:setConfigurations(configs)
        data:setPosition(x, y, z)
        data:setRotation(rx, ry, rz)
        if data.setIgnoreShopOffset ~= nil then data:setIgnoreShopOffset(true) end
        data:setAddToPhysics(false)     -- stays exactly where it's put, touches nothing
        data:setIsSaved(false)
        if v.getOwnerFarmId ~= nil then data:setOwnerFarmId(v:getOwnerFarmId()) end
        local ok, err = pcall(data.load, data, self.onCopyLoaded, self,
            { session = s, shot = shot, like = v, main = l.main, config = l.config })
        if not ok then
            log("Color %s: loading %s failed: %s", tostring(shot.color), vehicleName(v), tostring(err))
            self:copyDone(s, l.main)
        end
    end
end

function SS:copyDone(s, failedMain)
    if failedMain then s.mainFailed = true end
    s.pendingLoads = (s.pendingLoads or 1) - 1
    if s.pendingLoads > 0 or self.session ~= s then return end
    if s.mainFailed then
        self:nextShot()
    else
        s.settleMs = self.FIRST_SETTLE_MS
        self:setState("settle")
    end
end

function SS:onCopyLoaded(vehicles, loadingState, args)
    local s = args.session
    if self.session ~= s or s.shot ~= args.shot then
        -- too late (timed out or stopped): throw it away
        for _, v in ipairs(vehicles or {}) do pcall(v.delete, v) end
        return
    end
    local okState = VehicleLoadingState == nil or loadingState == VehicleLoadingState.OK
    if not okState or vehicles == nil or vehicles[1] == nil then
        log("Color %s: the copy of %s didn't load (%s)", tostring(args.shot.color), vehicleName(args.like), tostring(loadingState))
        for _, v in ipairs(vehicles or {}) do pcall(v.delete, v) end
        self:copyDone(s, args.main)
        return
    end
    for _, v in ipairs(vehicles) do table.insert(s.copies, v) end
    self:placeLikeOriginal(vehicles[1], args.like)
    self:copyDone(s, false)
end

-- ------------------------------------------------------------------ moving to a better place
-- ssMove takes the machine (the target, else what you sit in) with everything hitched to it to a
-- flat, open place, and ssMove back returns it. Like the game's own teleport: unhitch, move every
-- part of every vehicle with physics off, physics on, hitch again (a Ropa's header stays on).
SS.SPOT_RADII = { 40, 70, 100, 140, 190, 250, 320 }   -- metres from the machine, nearest first
SS.SPOT_ANGLES = 16
SS.SPOT_FLAT = 0.8          -- metres up or down allowed over the place
SS.SPOT_CLEARANCE = 8       -- free metres around the machine, for the camera
SS.spots = {}               -- map id -> { x, z, yaw }: ssSpot
SS.moved = nil              -- { vehicles, combos, poses, name } while moved

function SS:mapId()
    local info = g_currentMission ~= nil and g_currentMission.missionInfo or nil
    return tostring(info ~= nil and (info.mapId or info.mapTitle) or "map")
end

-- the vehicle and all hitched to it (and to those), with how each is hitched
function SS:comboOf(root)
    local vehicles, combos, seen = {}, {}, {}
    local function walk(v)
        if seen[v] then return end
        seen[v] = true
        table.insert(vehicles, v)
        if v.getAttachedImplements == nil then return end
        local ok, list = pcall(v.getAttachedImplements, v)
        for _, impl in pairs(ok and list or {}) do
            local obj = type(impl) == "table" and impl.object or nil
            if type(obj) == "table" then
                local input
                if obj.getActiveInputAttacherJointDescIndex ~= nil then
                    local iok, i = pcall(obj.getActiveInputAttacherJointDescIndex, obj)
                    input = iok and i or nil
                end
                local spec = v.spec_attacherJoints
                local joint = spec ~= nil and spec.attacherJoints ~= nil and spec.attacherJoints[impl.jointDescIndex] or nil
                table.insert(combos, { vehicle = v, object = obj, joint = impl.jointDescIndex, input = input,
                    lowered = joint ~= nil and joint.moveDown or false })
                walk(obj)
            end
        end
    end
    walk(root)
    return vehicles, combos
end

-- where every part of every vehicle is: poses[v] = { { x, y, z, rx, ry, rz }, ... } per component
function SS:posesOf(vehicles)
    local poses = {}
    for _, v in ipairs(vehicles) do
        local list = {}
        local nodes = {}
        for _, c in ipairs(v.components or {}) do table.insert(nodes, c.node) end
        if #nodes == 0 then nodes = { v.rootNode } end
        for _, n in ipairs(nodes) do
            local x, y, z = getWorldTranslation(n)
            local rx, ry, rz = getWorldRotation(n)
            table.insert(list, { x, y, z, rx, ry, rz })
        end
        poses[v] = list
    end
    return poses
end

local function ground(x, z)
    return getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, x, 0, z)
end

-- the same poses turned by dYaw round (cx, cz) and set down at (x, z), each part as high above the
-- ground there as it was here
function SS:movedPoses(poses, cx, cz, x, z, dYaw)
    local c, s = math.cos(dYaw), math.sin(dYaw)
    local out = {}
    for v, list in pairs(poses) do
        local moved = {}
        for i, p in ipairs(list) do
            local dx, dz = p[1] - cx, p[3] - cz
            local nx, nz = x + dx * c + dz * s, z - dx * s + dz * c
            local ny = p[2] - ground(p[1], p[3]) + ground(nx, nz) + 0.05
            moved[i] = { nx, ny, nz, p[4], p[5] + dYaw, p[6] }
        end
        out[v] = moved
    end
    return out
end

function SS:placeVehicles(vehicles, combos, poses)
    for i = #combos, 1, -1 do
        local cmb = combos[i]
        if cmb.vehicle.detachImplementByObject ~= nil then pcall(cmb.vehicle.detachImplementByObject, cmb.vehicle, cmb.object, true) end
    end
    for _, v in ipairs(vehicles) do
        if v.removeFromPhysics ~= nil then pcall(v.removeFromPhysics, v) end
    end
    for _, v in ipairs(vehicles) do
        local p = poses[v]
        if p ~= nil and p[1] ~= nil and v.setAbsolutePosition ~= nil then
            local parts = {}
            for i, q in ipairs(p) do parts[i] = { { q[1], q[2], q[3] }, { q[4], q[5], q[6] } } end
            local ok, err = pcall(v.setAbsolutePosition, v, p[1][1], p[1][2], p[1][3], p[1][4], p[1][5], p[1][6], parts)
            if not ok then log("Moving %s: %s", vehicleName(v), tostring(err)) end
        end
    end
    for _, v in ipairs(vehicles) do
        if v.addToPhysics ~= nil then pcall(v.addToPhysics, v) end
    end
    local lost = {}
    for _, cmb in ipairs(combos) do
        if cmb.vehicle.attachImplement ~= nil then
            pcall(cmb.vehicle.attachImplement, cmb.vehicle, cmb.object, cmb.input, cmb.joint, true, nil, cmb.lowered, false)
        end
        local on = cmb.object.getAttacherVehicle ~= nil and select(2, pcall(cmb.object.getAttacherVehicle, cmb.object)) or nil
        if cmb.object.getAttacherVehicle ~= nil and on ~= cmb.vehicle then table.insert(lost, vehicleName(cmb.object)) end
    end
    return lost
end

function SS:onSpotHit(hitObjectId)
    if hitObjectId ~= nil and hitObjectId ~= 0 and hitObjectId ~= g_currentMission.terrainRootNode then
        local obj = self:nodeObject(hitObjectId)
        if obj == nil or not (self.spotOwn or {})[obj] then self.spotHits = (self.spotHits or 0) + 1 end
    end
    return true
end

-- a flat, open place for the machine: the ssSpot of this map, else the nearest that fits
function SS:findSpot(vehicles, cx, cz, radius, yaw)
    local saved = self.spots[self:mapId()]
    if saved ~= nil then return { x = saved.x, z = saved.z, yaw = saved.yaw, saved = true } end
    local need = radius + self.SPOT_CLEARANCE
    self.spotOwn = SS.subjectSet(vehicles)
    local mask = self:rayMask()
    for _, r in ipairs(self.SPOT_RADII) do
        for i = 0, self.SPOT_ANGLES - 1 do
            local a = i * 2 * math.pi / self.SPOT_ANGLES
            local x, z = cx + math.sin(a) * r, cz + math.cos(a) * r
            local h0 = ground(x, z)
            local lo, hi, fits = h0, h0, true
            for k = 0, 7 do
                local b = k * math.pi / 4
                for _, f in ipairs({ 0.5, 1 }) do
                    local h = ground(x + math.sin(b) * need * f, z + math.cos(b) * need * f)
                    lo, hi = math.min(lo, h), math.max(hi, h)
                end
            end
            fits = hi - lo <= self.SPOT_FLAT + need * 0.02
            if fits and g_currentMission.environmentAreaSystem ~= nil and g_currentMission.environmentAreaSystem.getWaterYAtWorldPosition ~= nil then
                local ok, wy = pcall(g_currentMission.environmentAreaSystem.getWaterYAtWorldPosition,
                    g_currentMission.environmentAreaSystem, x, h0, z)
                if ok and wy ~= nil and wy > h0 - 0.2 then fits = false end
            end
            if fits and overlapBox ~= nil then
                self.spotHits = 0
                pcall(overlapBox, x, h0 + 3, z, 0, 0, 0, need, 2.6, need, "onSpotHit", self, mask, true, true, true, false)
                fits = self.spotHits == 0
            end
            if fits then return { x = x, z = z, yaw = yaw, distance = r } end
        end
    end
    return nil
end

-- ssSpot: here (where you stand, the way you look) is where ssMove puts machines on this map
-- ssSpot clear: back to finding a place by itself
function SS:consoleSpot(arg)
    local map = self:mapId()
    if arg == "clear" then
        self.spots[map] = nil
        self:saveSettings()
        return "No spot on this map: ssMove finds an open, flat place by itself"
    end
    local player = g_localPlayer
    if player == nil then return "No player" end
    local x, _, z = player:getPosition()
    local yaw = 0
    local cam = g_cameraManager ~= nil and g_cameraManager:getActiveCamera() or nil
    if cam ~= nil then
        local ok, dx, _, dz = pcall(localDirectionToWorld, cam, 0, 0, -1)     -- cameras look along -Z
        if ok and dx ~= nil then yaw = math.atan2(dx, dz) end
    end
    self.spots[map] = { x = x, z = z, yaw = yaw }
    self:saveSettings()
    return string.format("Spot for %s saved: ssMove puts machines here, facing the way you look", map)
end

-- ssMove: the machine to the spot (or an open, flat place); ssMove back: where it was
function SS:consoleMove(arg)
    if arg == "back" then return self:moveBack() end
    if self.moved ~= nil then return "Already moved: ssMove back first" end
    local target = self:getTarget()
    if target ~= nil and target.placeable ~= nil then return "Buildings stay where they are" end
    local v = target ~= nil and target.vehicle or self:getSeatVehicle()
    if v == nil then return "Nothing to move: sit in it or ssTarget it" end
    local root = v.getRootVehicle ~= nil and v:getRootVehicle() or v
    local vehicles, combos = self:comboOf(root)
    local corners = self:cornersOf(vehicles)
    local lo, hi = { math.huge, math.huge }, { -math.huge, -math.huge }
    for _, c in ipairs(corners) do
        lo[1], hi[1] = math.min(lo[1], c[1]), math.max(hi[1], c[1])
        lo[2], hi[2] = math.min(lo[2], c[3]), math.max(hi[2], c[3])
    end
    local cx, cz = (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2
    local radius = math.sqrt((hi[1] - lo[1]) ^ 2 + (hi[2] - lo[2]) ^ 2) / 2
    local dx, _, dz = localDirectionToWorld(root.rootNode, 0, 0, 1)
    local yaw = math.atan2(dx, dz)
    local spot = self:findSpot(vehicles, cx, cz, radius, yaw)
    if spot == nil then
        return string.format("No open, flat place within %d m: stand somewhere nice and ssSpot", self.SPOT_RADII[#self.SPOT_RADII])
    end
    local poses = self:posesOf(vehicles)
    local lost = self:placeVehicles(vehicles, combos, self:movedPoses(poses, cx, cz, spot.x, spot.z, spot.yaw - yaw))
    self.moved = { vehicles = vehicles, combos = combos, poses = poses, name = vehicleName(root) }
    local seated = self:getSeatVehicle()
    local inIt = false
    for _, o in ipairs(vehicles) do if o == seated then inIt = true end end
    if not inIt and target ~= nil then self:walkToTarget(target) end
    local msg = string.format("Moved %s%s %s", vehicleName(root),
        #vehicles > 1 and string.format(" with %d hitched", #vehicles - 1) or "",
        spot.saved and "to your spot" or string.format("%.0f m to an open, flat place", spot.distance or 0))
    if #lost > 0 then msg = msg .. "; NOT hitched again: " .. table.concat(lost, ", ") end
    log("%s. ssMove back returns it", msg)
    return msg
end

function SS:moveBack()
    local m = self.moved
    if m == nil then return "Nothing moved" end
    local lost = self:placeVehicles(m.vehicles, m.combos, m.poses)
    self.moved = nil
    local msg = "Back where it was: " .. m.name
    if #lost > 0 then msg = msg .. "; NOT hitched again: " .. table.concat(lost, ", ") end
    log("%s", msg)
    return msg
end

-- Every part of the copy where the same part of the vehicle is (articulated vehicles, raised arms)
function SS:placeLikeOriginal(copy, v)
    if copy.setAbsolutePosition == nil then return end
    local x, y, z = getWorldTranslation(v.rootNode)
    local rx, ry, rz = getWorldRotation(v.rootNode)
    local positions
    if copy.components ~= nil and v.components ~= nil and #copy.components == #v.components then
        positions = {}
        for i, c in ipairs(v.components) do
            positions[i] = { { getWorldTranslation(c.node) }, { getWorldRotation(c.node) } }
        end
    end
    local ok, err = pcall(copy.setAbsolutePosition, copy, x, y, z, rx, ry, rz, positions)
    if not ok then log("Placing the copy: %s", tostring(err)) end
end

function SS:deleteCopies(s)
    for _, v in ipairs(s.copies or {}) do
        local ok, err = pcall(v.delete, v)
        if not ok then log("Deleting the copy: %s", tostring(err)) end
    end
    s.copies = nil
end


-- ------------------------------------------------------------------ light
function SS:getEnv()
    return g_currentMission ~= nil and g_currentMission.environment or nil
end

function SS:setTime(env, md, day, dayTime, dpp)
    local ok, err = pcall(env.setEnvironmentTime, env, md, day, dayTime, dpp, false)
    if ok and env.lighting ~= nil and env.lighting.update ~= nil then pcall(env.lighting.update, env.lighting, 1, true) end
    return ok, err
end

function SS:setWeather(env, typeName)
    local w = env.weather
    if w == nil or w.consoleCommandWeatherSet == nil then return false end
    if WeatherType ~= nil and WeatherType[typeName] == nil then
        log("Weather type %s doesn't exist here, keeping the weather", typeName)
        return false
    end
    local ok, msg = pcall(w.consoleCommandWeatherSet, w, typeName)
    if msg ~= nil then log("Weather %s: %s", typeName, tostring(msg)) end
    return ok
end

-- Morning mist on or off. Remembers the fog the game had, for switching it back.
function SS:setMist(env, on)
    local w = env.weather
    local updater = w ~= nil and w.fogUpdater or nil
    if updater == nil or updater.setTargetFog == nil then return false end
    if on then
        local template = w.seasonToFog ~= nil and w.seasonToFog[env.currentSeason] or nil
        if template == nil or template.createFromTemplate == nil then return false end
        local ok, fog = pcall(template.createFromTemplate, template)
        if not ok or fog == nil then return false end
        for k, value in pairs(self.MIST) do fog[k] = value end
        fog.groundFogStartDayTimeMinutes, fog.groundFogEndDayTimeMinutes = 0, 1439
        fog.groundFogWeatherTypes = fog.groundFogWeatherTypes or {}
        if WeatherType ~= nil and WeatherType.SUN ~= nil then fog.groundFogWeatherTypes[WeatherType.SUN] = true end
        if self.lightSaved ~= nil and not self.lightSaved.fogSaved then
            self.lightSaved.fog, self.lightSaved.fogSaved = updater.targetFog, true
        end
        return (pcall(updater.setTargetFog, updater, fog, 1000))
    elseif self.lightSaved ~= nil and self.lightSaved.fogSaved then
        pcall(updater.setTargetFog, updater, self.lightSaved.fog, 1000)
        self.lightSaved.fog, self.lightSaved.fogSaved = nil, false
    end
    return true
end

-- Preset i (index in SS.LIGHTS), optionally at another hour
function SS:setLight(i, hour)
    local env = self:getEnv()
    if env == nil then return "No environment" end
    local preset = self.LIGHTS[i]
    if self.lightSaved == nil then
        self.lightSaved = { env.currentMonotonicDay, env.currentDay, env.dayTime, env.daysPerPeriod }
    end
    local h = tonumber(hour) or preset.hour
    local ok, err = self:setTime(env, env.currentMonotonicDay, env.currentDay, math.floor(h * 3600000), env.daysPerPeriod)
    if not ok then
        local msg = "Light failed: " .. tostring(err)
        notify("Screenshot Studio: " .. msg)
        return msg
    end
    self.light = i
    self:setWeather(env, preset.weather)
    local mist = self:setMist(env, preset.fog == true)
    local msg = string.format("Light %d/%d: %s, %02d:%02d%s. Again for the next.", i, #self.LIGHTS, preset.text,
        math.floor(h), math.floor((h % 1) * 60 + 0.5), (preset.fog and not mist) and " (no fog in this game)" or "")
    notify("Screenshot Studio: " .. msg)
    return msg
end

function SS:restoreLight()
    local env = self:getEnv()
    if env == nil or self.lightSaved == nil then
        self.light = nil
        return "Light: the game's own"
    end
    local g = self.lightSaved
    self:setMist(env, false)
    local ok, err = self:setTime(env, g[1], g[2], g[3], g[4])
    self.light, self.lightSaved = nil, nil
    local msg = ok and "Time is back to where it was (the weather stays as it is)." or ("Restore failed: " .. tostring(err))
    notify("Screenshot Studio: " .. msg)
    return msg
end

function SS:nextLight()
    local i = (self.light or 0) + 1
    if i > #self.LIGHTS then return self:restoreLight() end
    return self:setLight(i)
end

function SS:getLightIndex(id)
    for i, preset in ipairs(self.LIGHTS) do
        if preset.id == id then return i end
    end
    return nil
end

-- ssGolden: golden hour on, or everything back
function SS:toggleGolden(hour)
    if self.light ~= nil then return self:restoreLight() end
    return self:setLight(self:getLightIndex("golden"), hour)
end


-- ------------------------------------------------------------------ the actions
-- The current view; with an ssTarget you don't sit in, a framed view of it; auto: always framed
function SS:cleanShot(auto)
    local camera = auto and self:autoCamera() or self:targetCamera()
    if auto and camera == nil then
        log("ssShot auto: nothing to frame (sit in a vehicle or ssTarget something): your own view instead")
    end
    return self:start("clean", { { kind = "clean", camera = camera } }, self:getCurrentModName(),
        { what = self:getCurrentWhat() })
end

function SS:orbit(count, distance)
    local t = self:getOrbitTarget()
    if t == nil then
        notify("Screenshot Studio: get in a vehicle or stand near a building")
        log("Orbit: no vehicle and no building within %d m", self.MAX_PLACEABLE_DISTANCE)
        return false
    end
    local shots = {}
    local positions, skipped = self:orbitPositions(t, count or self.ORBIT_SHOTS, distance)
    if #positions == 0 then
        -- blocked all round is more likely a wrong reading than a real wall on every side: take
        -- the plain positions, and say so
        log("Orbit around %s: looked blocked from every side (%s); taken without checking", tostring(t.what),
            skipped[1] or "?")
        positions, skipped = self:orbitPositions(t, count or self.ORBIT_SHOTS, distance, true)
    end
    for _, cam in ipairs(positions) do
        table.insert(shots, { kind = "orbit", camera = cam })
    end
    log("Orbit around %s (%s): %d shots, radius %.1f m%s", tostring(t.what), t.mod, #shots, t.radius,
        #skipped > 0 and string.format("; %d left out, blocked by: %s", #skipped, table.concat(skipped, ", ")) or "")
    return self:start("orbit", shots, self.forcedFolder or t.mod, { mod = t.mod, what = t.what })
end

function SS:uiShot(seconds)
    local delay = (tonumber(seconds) or self.UI_DELAY) * 1000
    log("UI shot in %.0f s: open the menu now", delay / 1000)
    return self:start("ui", { { kind = "ui" } }, self.forcedFolder or "ui", { keepHud = true, delayMs = delay })
end

-- A clean shot every few seconds of the current view, while you drive or work. The render
-- methods leave the HUD out by themselves, so the HUD only goes away with the screen method.
function SS:burst(count, seconds)
    if self.session ~= nil and self.session.kind == "burst" then
        return self:stopBurst()
    end
    count = math.max(1, math.floor(tonumber(count) or self.BURST_SHOTS))
    local waitMs = math.max(0.5, tonumber(seconds) or self.BURST_SECONDS) * 1000
    local shots = {}
    local camera = self:targetCamera()      -- a target you don't sit in: its framed view, else yours
    for _ = 1, count do table.insert(shots, { kind = "burst", waitMs = waitMs, camera = camera }) end
    local method = self:getMethod(self.method)
    local ok = self:start("burst", shots, self:getCurrentModName(),
        { what = self:getCurrentWhat(), keepHud = method ~= nil and method.render })
    if ok then
        notify(string.format("Screenshot Studio: burst, %d shots, one every %.0f s. Right Ctrl + 5 again to stop.",
            count, waitMs / 1000))
    end
    return ok
end

function SS:stopBurst()
    self.queue = {}
    if self.state == "settle" then self:finish() end   -- else it ends after the picture it's taking
    return true
end


-- ------------------------------------------------------------------ keys
function SS.onKeyClean() SS:cleanShot() end
function SS.onKeyOrbit() SS:orbit() end
function SS.onKeyUi() SS:uiShot() end
function SS.onKeyLight() SS:nextLight() end
function SS.onKeyBurst() SS:burst() end
function SS.onKeyColors() SS:colors() end

PlayerInputComponent.registerGlobalPlayerActionEvents = Utils.appendedFunction(
    PlayerInputComponent.registerGlobalPlayerActionEvents, function(self)
        for _, a in ipairs({
            { InputAction.SS_CLEAN_SHOT, SS.onKeyClean },
            { InputAction.SS_ORBIT, SS.onKeyOrbit },
            { InputAction.SS_UI_SHOT, SS.onKeyUi },
            { InputAction.SS_GOLDEN_HOUR, SS.onKeyLight },
            { InputAction.SS_BURST, SS.onKeyBurst },
            { InputAction.SS_COLORS, SS.onKeyColors },
        }) do
            if a[1] ~= nil then
                local _, id = g_inputBinding:registerActionEvent(a[1], SS, a[2], false, true, false, true)
                if id ~= nil then g_inputBinding:setActionEventTextVisibility(id, false) end
            end
        end
    end)


-- ------------------------------------------------------------------ console
-- ssShot: your view; ssShot auto: the machine framed from ssView's angle
function SS:consoleShot(mode)
    local auto = mode == "auto"
    return self:cleanShot(auto) and (auto and "Taking a framed shot" or "Taking a clean shot") or "Busy or not possible"
end

function SS:consoleOrbit(count, distance)
    return self:orbit(tonumber(count), tonumber(distance)) and "Orbit started" or "Orbit not possible (see log)"
end

function SS:consoleUi(seconds)
    -- in an autorun, a picture of the wrong page is worse than none
    if self.autorun ~= nil and self.menuFailed ~= nil then
        log("UI shot skipped: the page %s didn't open", self.menuFailed)
        return "Skipped: the page " .. self.menuFailed .. " didn't open"
    end
    return self:uiShot(seconds) and "UI shot coming, open the menu" or "Busy or not possible"
end

function SS:consoleGolden(hour) return self:toggleGolden(hour) end

-- ssLight              next preset (like Right Ctrl + 4)
-- ssLight midday 11    that preset, at another hour
-- ssLight off          the old time back
function SS:consoleLight(name, hour)
    if name == nil or name == "" then return self:nextLight() end
    if name == "off" then return self:restoreLight() end
    local i = self:getLightIndex(name)
    if i == nil then
        local ids = {}
        for _, p in ipairs(self.LIGHTS) do table.insert(ids, p.id) end
        return "Unknown light. Use one of: " .. table.concat(ids, ", ") .. ", off"
    end
    return self:setLight(i, hour)
end

function SS:consoleBurst(count, seconds)
    if self.session ~= nil and self.session.kind == "burst" then
        self:stopBurst()
        return "Burst stopped"
    end
    return self:burst(count, seconds) and "Burst started" or "Busy or not possible"
end

function SS:consoleColors(configName)
    return self:colors(configName) and "Going through the colors" or "Not possible (see log)"
end

-- ------------------------------------------------------------------ menus
-- ssMenu UWMFrame opens the in-game menu on that page (a mod's page too: Player Trading+ adds one),
-- ssMenu ShopMenu a screen, ssMenu xyzDialog a dialog, ssMenu close closes them; ssMenu lists all.
-- A UI shot (ssUi) then takes the screen with the menu.
function SS:inGameMenu()
    if g_gui == nil or g_gui.screenControllers == nil or InGameMenu == nil then return nil end
    return g_gui.screenControllers[InGameMenu]
end

-- the in-game menu's pages: { index, frame, name }; the name from the frame, else from the GUI
-- it was loaded as (g_gui.frames / g_gui.guis), else "page N"
function SS:menuPages()
    local menu = self:inGameMenu()
    local list = {}
    if menu == nil then return list, nil end
    local known = {}
    for _, t in ipairs({ g_gui.frames or {}, g_gui.guis or {} }) do
        for n, gui in pairs(t) do
            if type(gui) == "table" then
                known[gui] = known[gui] or n
                if type(gui.target) == "table" then known[gui.target] = known[gui.target] or n end
            end
        end
    end
    local frames = menu.pageFrames
    if frames == nil and menu.pagingElement ~= nil then frames = menu.pagingElement.pages end
    for i, f in ipairs(frames or {}) do
        local frame = type(f) == "table" and f.element ~= nil and f.element or f
        local name = known[frame] or (type(frame) == "table" and (frame.name or frame.pageName)) or nil
        table.insert(list, { index = i, frame = frame, name = tostring(name or ("page " .. i)) })
    end
    return list, menu
end

-- after ssMenu <page>: goToPage until the menu shows it (from the GUI update, a few frames)
function SS:checkPendingPage()
    local pp = self.pendingPage
    if pp == nil then return end
    pp.tries = pp.tries + 1
    local menu = pp.menu
    if menu.currentPage == pp.frame then
        self.pendingPage = nil
        log("In-game menu on page %s", pp.name)
        return
    end
    if menu.goToPage ~= nil then pcall(menu.goToPage, menu, pp.frame) end
    if pp.tries >= 30 then
        self.pendingPage = nil
        self.menuFailed = pp.name
        -- why not: the page's own "enabled" check, wherever the menu keeps it
        local enabled = "?"
        for _, v in pairs(menu) do
            if type(v) == "table" and type(rawget(v, pp.frame)) == "function" then
                local ok, e = pcall(rawget(v, pp.frame))
                enabled = ok and tostring(e) or "error"
            end
        end
        log("In-game menu: page %s didn't open (its enabled check says %s; a mod's page may only be on in some cases)",
            pp.name, enabled)
    end
end

function SS:screenNames()
    local names = {}
    for n in pairs(g_gui ~= nil and g_gui.guis or {}) do
        if type(n) == "string" then table.insert(names, n) end
    end
    table.sort(names)
    return names
end

function SS:consoleMenu(...)
    local name = table.concat({ ... }, " ")
    if g_gui == nil then return "No GUI" end
    if name == "" then
        local pages = {}
        for _, p in ipairs(self:menuPages()) do table.insert(pages, p.index .. " " .. p.name) end
        local screens = self:screenNames()
        log("In-game menu pages: %s", #pages > 0 and table.concat(pages, ", ") or "none")
        log("Screens and dialogs: %s", table.concat(screens, ", "))
        return string.format("%d menu pages, %d screens/dialogs: listed in the log", #pages, #screens)
    end
    self.menuFailed = nil
    if name == "close" then
        self.pendingPage = nil
        pcall(g_gui.showGui, g_gui, "")
        return "Menus closed"
    end
    local want, num = name:lower(), tonumber(name)
    local pages, menu = self:menuPages()
    for _, p in ipairs(pages) do
        if (num ~= nil and p.index == num) or (num == nil and p.name:lower():find(want, 1, true)) then
            local ok, err = pcall(g_gui.showGui, g_gui, "InGameMenu")
            if not ok then return "Opening the menu failed: " .. tostring(err) end
            -- the menu picks its own page as it opens: go to ours over the next frames, and check
            self.pendingPage = { menu = menu, frame = p.frame, name = p.name, tries = 0 }
            self.menuFailed = nil
            return "In-game menu, going to page " .. p.name
        end
    end
    local hit
    for _, n in ipairs(self:screenNames()) do
        if n:lower() == want then hit = n end
    end
    if hit == nil then
        for _, n in ipairs(self:screenNames()) do
            if hit == nil and n:lower():find(want, 1, true) then hit = n end
        end
    end
    if hit == nil then return "No screen, dialog or menu page called " .. name .. ": ssMenu lists them" end
    local isDialog = hit:find("Dialog") ~= nil
    local ok, err = pcall(isDialog and g_gui.showDialog or g_gui.showGui, g_gui, hit)
    return ok and ("Opened " .. hit) or ("Opening " .. hit .. " failed: " .. tostring(err))
end

-- ssType tractor: the text straight into a text field of the open screen or dialog, no keyboard (a
-- search box like Searchables' reads its field every frame, so it searches at once). One whose id has
-- "search" in it wins, else the first visible one; a dialog before the screen under it.
function SS:findTextFields()
    local found, seen, roots = {}, {}, {}
    if g_gui == nil then return found end
    local dialogs = g_gui.dialogs or {}
    for i = #dialogs, 1, -1 do table.insert(roots, dialogs[i]) end
    if g_gui.currentGui ~= nil then table.insert(roots, g_gui.currentGui) end
    local function walk(e, depth)
        if type(e) ~= "table" or seen[e] or depth > 30 then return end
        seen[e] = true
        if type(e.setText) == "function" and type(e.getText) == "function" and type(e.setForcePressed) == "function" then
            local visible = true
            if e.getIsVisible ~= nil then
                local ok, v = pcall(e.getIsVisible, e)
                visible = not ok or v ~= false
            end
            if visible then table.insert(found, e) end
        end
        for _, c in ipairs(e.elements or {}) do walk(c, depth + 1) end
    end
    for _, r in ipairs(roots) do walk(r, 0) end
    return found
end

function SS:consoleType(...)
    local text = table.concat({ ... }, " ")
    local fields = self:findTextFields()
    if #fields == 0 then return "No text field on this screen" end
    local field = fields[1]
    for _, f in ipairs(fields) do
        if tostring(f.id or ""):lower():find("search", 1, true) then field = f; break end
    end
    local ok, err = pcall(field.setText, field, text)
    if not ok then return "Writing into the text field failed: " .. tostring(err) end
    return string.format("Typed '%s' into %s", text, tostring(field.id or "a text field"))
end

-- ssKeys ctrl+f tractor enter: the game can't press its own keys, so in an autorun this is a note for
-- fs25_run_game.py, which reads it in the log and types the keys into the game window (a key name
-- or a chord with +, else the word is typed). Typed by hand it does nothing.
function SS:consoleKeys(...)
    local keys = table.concat({ ... }, " ")
    if keys == "" then return "ssKeys <keys>: e.g. ctrl+f tractor enter" end
    return "Keys for the runner to type: " .. keys
end

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
    if not self.renderOk then self:startTrying("render_png") end
    for _, f in ipairs({ "png", "jpg", "tga", "bmp", "dds", "raw_ldr", "raw_hdr" }) do
        local path = dir .. "render_" .. f .. "." .. (f:match("^raw_(%w+)") or f)
        local ok, err = self:render(path, f)
        table.insert(tries, { path = path, call = "renderScreenshot " .. f, ok = ok, err = err })
    end
    if self.trying ~= nil and self.tryingSince == nil then self.tryingSince = now() end
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

-- ssMethod            the next shot finds the method again (not render if it crashed the game)
-- ssMethod screen     always hide the HUD and save the screen (e.g. if render_png looks wrong)
-- ssMethod render_png render again, even after a crash (still guarded: a crash goes back to screen)
function SS:consoleMethod(id)
    if id == nil or id == "" then
        self.method, self.renderOk = nil, false
        self:saveSettings()
        if self.crashed.render_png then
            return "The next shot finds the screenshot method again (without render: it crashed the game)"
        end
        return "The next shot finds the screenshot method again"
    end
    local method = self:getMethod(id)
    if method == nil then
        local ids = {}
        for _, m in ipairs(self.METHODS) do table.insert(ids, m.id) end
        return "Unknown method. Use one of: " .. table.concat(ids, ", ")
    end
    self.method = id
    if method.render then
        self.crashed, self.renderOk = {}, false
        self:saveSettings()
        return "Screenshot method: " .. id .. ". If the game crashes on the next shot, it goes back to screen."
    end
    self:saveSettings()
    return "Screenshot method: " .. id
end


-- ------------------------------------------------------------------ getting in
-- ssEnter [name]: into the vehicle whose name contains `name`, else the nearest one, then an
-- outside camera. For autorun, where the save starts you on foot.
function SS:getEnterableVehicles()
    local list = {}
    local system = g_currentMission ~= nil and g_currentMission.vehicleSystem or nil
    for _, v in ipairs(system ~= nil and system.vehicles or {}) do
        local ok, enterable = false, false
        if v.getIsEnterable ~= nil then ok, enterable = pcall(v.getIsEnterable, v) end
        if ok and enterable and v.rootNode ~= nil then table.insert(list, v) end
    end
    return list
end

function SS:enter(name)
    local player = g_localPlayer
    if player == nil or player.requestToEnterVehicle == nil then return false, "No player" end
    local current = player.getCurrentVehicle ~= nil and player:getCurrentVehicle() or nil
    local px, _, pz = player:getPosition()
    local best, bestDist
    -- no name and a target on a vehicle: into the target, or the tractor it hangs on
    local target = self:getTarget()
    if (name == nil or name == "") and target ~= nil and target.vehicle ~= nil then
        local root = target.vehicle.getRootVehicle ~= nil and target.vehicle:getRootVehicle() or target.vehicle
        for _, v in ipairs(self:getEnterableVehicles()) do
            if v == root then
                local x, _, z = getWorldTranslation(v.rootNode)
                best, bestDist = v, MathUtil.vector2Length(x - px, z - pz)
            end
        end
    end
    -- no name, a target without a seat (an implement on its own, a building): walk over to it, so the
    -- game loads the detail around it (from far away it shows rough stand-ins)
    if best == nil and (name == nil or name == "") and target ~= nil then
        return self:walkToTarget(target)
    end
    for _, v in ipairs(best == nil and self:getEnterableVehicles() or {}) do
        local x, _, z = getWorldTranslation(v.rootNode)
        local d = MathUtil.vector2Length(x - px, z - pz)
        local fits = name == nil or name == "" or vehicleName(v):lower():find(name:lower(), 1, true) ~= nil
        if fits and (bestDist == nil or d < bestDist) then best, bestDist = v, d end
    end
    if best == nil then return false, "No vehicle" .. (name ~= nil and name ~= "" and (" called " .. name) or "") end
    if best ~= current then
        local ok, err = pcall(player.requestToEnterVehicle, player, best)
        if not ok then return false, "Getting in failed: " .. tostring(err) end
    end
    self.pendingCamera = { vehicle = best, at = now() + 2000 }
    return true, string.format("Getting into %s (%.0f m)", vehicleName(best), bestDist)
end

-- The first outside camera of the vehicle, once we sit in it
function SS:checkPendingCamera()
    local p = self.pendingCamera
    if p == nil or now() < p.at then return end
    self.pendingCamera = nil
    self:startEngine(p.vehicle)
    local spec = p.vehicle.spec_enterable
    if spec == nil or p.vehicle.setActiveCameraIndex == nil then return end
    for i, cam in ipairs(spec.cameras or {}) do
        if not cam.isInside then
            pcall(p.vehicle.setActiveCameraIndex, p.vehicle, i)
            return
        end
    end
end

-- On foot, WALK_DISTANCE metres out on the side of the main view: behind that camera, and only a
-- speck in the orbit's rear views. Out of a vehicle the way AdvancedFarmManager does it.
SS.WALK_DISTANCE = 60
function SS:walkToTarget(target)
    local player = g_localPlayer
    local t = self:getOrbitTarget()
    if player == nil or t == nil then return false, "Can't get to the target" end
    local angle = t.yaw + math.rad(self.viewAngle or self.VIEW_ANGLE)
    local x = t.x + math.sin(angle) * self.WALK_DISTANCE
    local z = t.z + math.cos(angle) * self.WALK_DISTANCE
    local y = getTerrainHeightAtWorldPos(g_currentMission.terrainRootNode, x, 0, z) + 0.2
    local inVehicle = player.getCurrentVehicle ~= nil and player:getCurrentVehicle() ~= nil
    local ok, err
    if inVehicle and player.leaveVehicle ~= nil then pcall(player.leaveVehicle, player) end
    if inVehicle and g_currentMission.controlledVehicle ~= nil and g_currentMission.onLeaveVehicle ~= nil then
        ok, err = pcall(g_currentMission.onLeaveVehicle, g_currentMission, x, y, z, false, false)
    elseif player.teleportTo ~= nil then
        ok, err = pcall(player.teleportTo, player, x, y, z, false, false)
    else
        ok, err = false, "no teleportTo"
    end
    if not ok then return false, "Getting to the target failed: " .. tostring(err) end
    return true, string.format("Walking to %s: on foot %d m from it (it has no seat), so its detail loads",
        tostring(target.name), self.WALK_DISTANCE)
end

-- An engine that is off makes the game (and AutoDrive/Courseplay) show "Please start the engine
-- first!" over the vehicle; ssEnter starts it, the way Courseplay does (vehicle:startMotor()).
function SS:startEngine(v)
    if v == nil or v.startMotor == nil or v.getIsMotorStarted == nil then return false end
    local ok, started = pcall(v.getIsMotorStarted, v)
    if ok and not started then
        return (pcall(v.startMotor, v))
    end
    return false
end

function SS:consoleTarget(...) return self:setTarget(table.concat({ ... }, " ")) end

function SS:consoleList(...) return self:listObjects(table.concat({ ... }, " ")) end

function SS:consoleEnter(...)
    local name = table.concat({ ... }, " ")
    local _, msg = self:enter(name)
    return msg
end


-- ------------------------------------------------------------------ autorun
-- tools/fs25_run_game.py writes modSettings/FS25_ScreenshotStudio/autorun.xml, starts the game with
-- that save and reads the log:
--   <autorun savegame="3" created="20261112_183000"><step>ssLight golden</step>...<step>quit</step></autorun>
-- Steps are console commands (ssShot, ssOrbit 8, ssColors, ssEnter, ...), "wait <seconds>" or
-- "quit". Each one starts when the one before is done. The file is only used in the save it names,
-- only if it's less than 20 minutes old, and it's deleted once read, so a normal game never runs it.
SS.AUTORUN_FILE = "autorun.xml"
SS.AUTORUN_MAX_AGE = 20       -- minutes
SS.AUTORUN_START_S = 10       -- after the save is running: let the map stream in
SS.AUTORUN_PAUSE = { ssLight = 3, ssGolden = 3, ssEnter = 8, ssMove = 6, ssMenu = 2, ssKeys = 4, ssType = 2 }   -- seconds after these steps; others 1

-- "20261112_183000" -> minutes since a fixed day (only differences matter)
local function stampMinutes(stamp)
    local y, mo, d, h, mi = tostring(stamp or ""):match("^(%d%d%d%d)(%d%d)(%d%d)_(%d%d)(%d%d)")
    if y == nil then return nil end
    y, mo, d, h, mi = tonumber(y), tonumber(mo), tonumber(d), tonumber(h), tonumber(mi)
    if mo <= 2 then y = y - 1 end
    local era = math.floor(y / 400)
    local yoe = y - era * 400
    local doy = math.floor((153 * ((mo + 9) % 12) + 2) / 5) + d - 1
    local days = era * 146097 + yoe * 365 + math.floor(yoe / 4) - math.floor(yoe / 100) + doy
    return days * 1440 + h * 60 + mi
end
SS.stampMinutes = stampMinutes

function SS:readAutorun()
    local path = self:getBaseDir() .. self.AUTORUN_FILE
    if not fileExists(path) then return nil end
    local xml = loadXMLFile("ssAutorun", path)
    if xml == nil or xml == 0 then return nil end
    local save = getXMLString(xml, "autorun#savegame")
    local created = getXMLString(xml, "autorun#created")
    local steps, i = {}, 0
    while true do
        local step = getXMLString(xml, string.format("autorun.step(%d)", i))
        if step == nil then break end
        step = step:match("^%s*(.-)%s*$")
        if step ~= "" then table.insert(steps, step) end
        i = i + 1
    end
    delete(xml)

    local info = g_currentMission ~= nil and g_currentMission.missionInfo or nil
    local here = info ~= nil and tostring(info.savegameIndex) or "?"
    if save ~= here then
        log("autorun: %s is for savegame %s, this is %s: not run", self.AUTORUN_FILE, tostring(save), here)
        return nil
    end
    local age = (stampMinutes(getDate("%Y%m%d_%H%M%S")) or 0) - (stampMinutes(created) or -math.huge)
    if age < 0 or age > self.AUTORUN_MAX_AGE then
        log("autorun: %s is old (%s), not run", self.AUTORUN_FILE, tostring(created))
        removeFile(path)
        return nil
    end
    removeFile(path)
    return steps
end

function SS:checkAutorun()
    if self.autorunChecked then return end
    local info = g_currentMission ~= nil and g_currentMission.missionInfo or nil
    if info == nil or g_localPlayer == nil or g_currentMission.gameStarted == false then return end
    self.autorunChecked = true
    local steps = self:readAutorun()
    if steps == nil then return end
    self.autorun = { steps = steps, index = 0, nextAt = now() + self.AUTORUN_START_S * 1000, pictures = 0 }
    log("autorun: started, %d steps, first in %d s", #steps, self.AUTORUN_START_S)
end

function SS:runStep(step)
    local words = {}
    for w in step:gmatch("%S+") do table.insert(words, w) end
    local name = table.remove(words, 1)
    if name == "wait" then
        return tonumber(words[1]) or 1, "waiting"
    end
    if name == "quit" then
        return 0, "quit"
    end
    for _, c in ipairs(self.COMMANDS) do
        if c[1] == name then
            local ok, result = pcall(self[c[3]], self, unpack(words))
            return self.AUTORUN_PAUSE[name] or 1, ok and tostring(result) or ("ERROR " .. tostring(result))
        end
    end
    return 0, "unknown step"
end

function SS:tickAutorun()
    local a = self.autorun
    if a == nil or self:isBusy() or now() < a.nextAt then return end
    local step = a.steps[a.index + 1]
    -- don't quit while render is still on trial: a crash then must still be noticed next start
    if (step == nil or step == "quit") and self.trying ~= nil then return end
    a.index = a.index + 1
    if step == nil or step == "quit" then
        self.autorun = nil
        log("autorun: done, %d picture(s)", a.pictures)
        if step == "quit" then
            log("autorun: quitting")
            if doExit ~= nil then pcall(doExit) end
        end
        return
    end
    local pause, result = self:runStep(step)
    log("autorun: step %d/%d %s -> %s", a.index, #a.steps, step, result)
    a.nextAt = now() + pause * 1000
end


-- ------------------------------------------------------------------ mod events
SS.COMMANDS = {
    { "ssShot", "Clean shot of the current view, no HUD; [auto] = the machine framed by itself", "consoleShot" },
    { "ssClear", "Framed views move around walls, poles and cars in the way: on/off", "consoleClear" },
    { "ssView", "Angle for framed shots and colors: [degrees off the front, 35] [degrees up, 12]; 180 = rear", "consoleView" },
    { "ssOrbit", "Shots all around the vehicle or nearest building [count] [distance]", "consoleOrbit" },
    { "ssUi", "Screenshot with menus after a delay [seconds]", "consoleUi" },
    { "ssBurst", "A shot every few seconds while you work [count] [seconds]; again to stop", "consoleBurst" },
    { "ssColors", "The current view once per color of the vehicle [option name, e.g. baseColor]", "consoleColors" },
    { "ssLight", "Light preset: golden, morning, midday, overcast, off [hour]; empty = next", "consoleLight" },
    { "ssGolden", "Golden hour on/off [hour]", "consoleGolden" },
    { "ssTarget", "What to photograph: the nearest vehicle, implement or building with [name] in its name; empty = what you sit in", "consoleTarget" },
    { "ssList", "Vehicles, implements and buildings near you, or all with [name] in their name", "consoleList" },
    { "ssSpot", "Here (where you stand, the way you look) is where ssMove puts machines on this map; [clear]", "consoleSpot" },
    { "ssMove", "The machine with what is hitched to it to your spot or an open, flat place; [back] = where it was", "consoleMove" },
    { "ssEnter", "Get into the target, the nearest vehicle, or the one whose name contains [name]; outside camera", "consoleEnter" },
    { "ssMenu", "Open a screen, dialog or in-game menu page by (part of) its name: [name]; empty = list them; close", "consoleMenu" },
    { "ssType", "Write [text] into the text field of the open screen (a search box), no keyboard", "consoleType" },
    { "ssKeys", "For the runner: keys to type into the game, e.g. ctrl+f tractor enter (the runner types them)", "consoleKeys" },
    { "ssFolder", "Folder name for the next shots, empty = automatic", "consoleFolder" },
    { "ssQuiet", "Hide other mods' drawing (Courseplay, AutoDrive, hints) during shots: on/off", "consoleQuiet" },
    { "ssRadius", "Orbit radius around buildings in metres", "consoleRadius" },
    { "ssProbe", "Tests which screenshot calls work (see log)", "consoleProbe" },
    { "ssMethod", "Screenshot method: render_png, render_jpg, screen; empty = find again", "consoleMethod" },
}

function SS:loadMap()
    self:loadSettings()
    for _, c in ipairs(self.COMMANDS) do addConsoleCommand(c[1], c[2], c[3], self) end
    log("Loaded. Right Ctrl + 1 clean shot, 2 orbit, 3 UI shot, 4 light, 5 burst, 6 every color. Method: %s%s",
        self.method or "not found yet", self.crashed.render_png and " (render crashed the game once: not used)" or "")
end

function SS:deleteMap()
    if self.session ~= nil then self:finish() end
    self:stopTrying()     -- leaving the game normally: whatever was being tried didn't crash it
    if self.moved ~= nil then self:moveBack() end
    self:setQuiet(false)
    for _, c in ipairs(self.COMMANDS) do removeConsoleCommand(c[1]) end
    if self.camera ~= nil then
        g_cameraManager:removeCamera(self.camera)
        delete(self.camera)
        self.camera = nil
    end
    self.light, self.lightSaved = nil, nil
    self.autorun, self.autorunChecked, self.pendingCamera = nil, nil, nil
    self.target = nil
end

function SS:update(dt)
    if self.muted ~= nil and self.session == nil then self:setQuiet(false) end   -- never left muted
    self:tick()
    self:checkTrying()
    self:checkProbe()
    self:checkPendingCamera()
    self:checkAutorun()
    self:tickAutorun()
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
        SS:checkPendingPage()
        SS:tickAutorun()     -- an open menu pauses the mission's update: the steps go on from here
    end)
end

addModEventListener(SS)
