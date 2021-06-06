--[[
    Tekijä: Eetu Rantanen, 2020

    Ratkaisu käyttää Djikstran algoritmia. Ratkaisussa käytetty apuna: https://www.youtube.com/watch?v=pVfj6mxhdMw

    Päätin aloittaa koodihaasteen kirjoittamalla konsolipohjaisen ratkaisun Lua:lla
    käyttäen Solar2D pelimoottoria (https://solar2d.com/), jotta saisin logiikan
    nopeasti kuntoon ja sen jälkeen käänsin kyseisen koodin JavaScriptiin.
]]

local json = require( "json" )
local _huge = math.huge
local _sort = table.sort
local _concat = table.concat

local function compare( a, b )
    return a < b
end

local function load( filename )
    local path = system.pathForFile( filename )

    if path then
        local file, errorString = io.open( path, "r" )

        if not file then
            print( "File error: " .. errorString )
        else
            local contents = file:read( "*a" )
            local t = json.decode( contents )
            io.close( file )
            return t
        end
    end
end

local data = load( "reittiopas.json" )
local busStops = {}

for i = 1, #data.pysakit do
    busStops[data.pysakit[i]] = {}
end

-- Luodaan taulukko vierekkäisistä bussipysäkeistä joiden välillä kulkee linja.
local busRoutes = {}
for i, j in pairs( data.linjastot ) do
    busRoutes[i] = {}
    for k = 1, #data.linjastot[i]-1 do
        busRoutes[i][data.linjastot[i][k] .. data.linjastot[i][k+1]] = true
        busRoutes[i][data.linjastot[i][k+1] .. data.linjastot[i][k]] = true
    end
end

-- Luodaan Djikstran algoritmille tarvittava taulukko.
for i = 1, #data.tiet do
    local duration = data.tiet[i].kesto
    local from = data.tiet[i].mista
    local to = data.tiet[i].mihin

    local segment, isValid = from .. to
    for j, k in pairs( busRoutes ) do
        if k[segment] then
            isValid = true
            break
        end
    end

    if isValid then
        busStops[from][to] = duration
        busStops[to][from] = duration
    end
end

-- Debuggauksessa käytetty funktio joka tulostaa konsoliin kaikki vierekkäiset
-- pysäkit ja niiden väliset kestot, tai pienimmät kestot pysäkkeihin (djikstra).
local function printSegments( map, djikstra )
    print( "" )
    print( "-------------------------------------------------------" )
    if djikstra then
        print( "Pienimmät kestot pysäkkeihin ja niitä edeltävä pysäkit:" )
    else
        print( "Pysäkkien väliset yhteydet ja niiden kestot:" )
    end
    print( "-------------------------------------------------------" )

    local t = {}
    for i, j in pairs( map ) do
        local sub = {}

        for k, l in pairs( j ) do
            sub[#sub+1] = k .. "=" .. l
        end
        _sort( sub, compare )

        t[#t+1] = i .. " = { " .. _concat( sub, ", " ) .. " }"
    end
    _sort( t, compare )

    for i = 1, #t do
        print( t[i] )
    end
    print( "-------------------------------------------------------" )
end

-- Poimitaan Djikstran algoritmilla laskettu optimaalinen reitti.
local function getShortestRoute( nodes, destination )
    local route, next = {}, destination
     
    repeat
        route[#route+1] = { next, nodes[next].d }
        next = nodes[next].previous
    until not next
    
    return route
end

-- Selvitetään reitti määränpäähän Djikstran algoritmilla.
local function getRoute( map, start, destination )
    if not busStops[start] or not busStops[destination] then
        print( "\nVaroitus: pysäkkiä \"" .. (not busStops[start] and start or destination) .. "\" ei ole olemassa." )
        return false
    end
    
    local path, visited = {}, {}
    for index, _ in pairs( map ) do
        path[index] = { d=_huge }
        visited[index] = false
    end
    path[start] = { d=0 }

    local current = start

    repeat
        local nearest, nearestIndex

        for index, distance in pairs( map[current] ) do
            if not visited[index] then
                local newDistance = path[current].d + distance
                if newDistance < path[index].d then
                    path[index] = { d=newDistance, previous=current }
                end
                if not nearest then
                    nearest = path[index].d
                    nearestIndex = index
                elseif path[index].d < nearest then
                    nearest = path[index].d
                    nearestIndex = index
                end
            end
        end

        if nearest then
            visited[current] = true
            current = nearestIndex
        else
            nearest = _huge

            for i, j in pairs( visited ) do
                if not j then
                    if path[i].d < nearest then
                        nearest = path[i].d
                        nearestIndex = i
                    end
                end
            end

            if nearestIndex then
                visited[current] = true
                current = nearestIndex
            else
                nearest = nil
            end
        end
    until not nearest
    
    -- printSegments( path, true )
    return getShortestRoute( path, destination )
end
-- printSegments( busStops )

-- Määritä alkupiste ja määränpää tässä:
local travelRoute = getRoute( busStops, "A", "H" )

if travelRoute then
    local stringPath = ""
    for i = #travelRoute, 1, -1 do
        stringPath = stringPath .. travelRoute[i][1] .. ", "
    end
    stringPath = stringPath:sub(1,-3)
    print( "\nOptimaalinen reitti on " .. stringPath .. ", kesto on " .. travelRoute[1][2] .. "." )
end
