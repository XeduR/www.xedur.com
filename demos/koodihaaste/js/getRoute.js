function prepareRoutes( routes ) {
    var busStops = {};
    for (let i = 0; i < routes.pysäkit.length; i++) {
        busStops[routes.pysakit[i]] = {};
    }
    
    let connections = {};
    for (let i in routes.linjastot) {
        connections[i] = {};
        for (let j = 0; j < routes.linjastot.length-1; j++) {
            connections[i][routes.linjastot[i][j] .. routes.linjastot[i][j+1]] = true;
            connections[i][routes.linjastot[i][j+1] .. routes.linjastot[i][j]] = true;
        }
    }
    
    for (let i = 0; i < routes.tiet.length; i++) {
        let duration = routes.tiet[i].kesto;
        let from = routes.tiet[i].mista;
        let to = routes.tiet[i].mihin;
    
        let segment = from + to;
        let isValid = false;
        for (let j in connections) {
            if (typeof j[segment] !== 'undefined') {
                isValid = true;
                break;
            }
        }
        
        if (isValid) {
            busStops[from][to] = duration;
            busStops[to][from] = duration;
        }
    }
    
    return busStops;
}

// -- Luodaan Djikstran algoritmille tarvittava taulukko.
// for i = 1, #data.tiet do
//     local duration = data.tiet[i].kesto
//     local from = data.tiet[i].mista
//     local to = data.tiet[i].mihin
// 
//     local segment, isValid = from .. to
//     for j, k in pairs( busRoutes ) do
//         if k[segment] then
//             isValid = true
//             break
//         end
//     end
// 
//     if isValid then
//         busStops[from][to] = duration
//         busStops[to][from] = duration
//     end
// end
// 
// 
// -- Poimitaan Djikstran algoritmilla laskettu optimaalinen reitti.
// local function getShortestRoute( nodes, destination )
//     local route, next = {}, destination
// 
//     repeat
//         route[#route+1] = { next, nodes[next].d }
//         next = nodes[next].previous
//     until not next
// 
//     return route
// end
// 
// -- Selvitetään reitti määränpäähän Djikstran algoritmilla.
// local function getRoute( map, start, destination )
//     if not busStops[start] or not busStops[destination] then
//         print( "\nVaroitus: pysäkkiä \"" .. (not busStops[start] and start or destination) .. "\" ei ole olemassa." )
//         return false
//     end
// 
//     local path, visited = {}, {}
//     for index, _ in pairs( map ) do
//         path[index] = { d=_huge }
//         visited[index] = false
//     end
//     path[start] = { d=0 }
// 
//     local current = start
// 
//     repeat
//         local nearest, nearestIndex
// 
//         for index, distance in pairs( map[current] ) do
//             if not visited[index] then
//                 local newDistance = path[current].d + distance
//                 if newDistance < path[index].d then
//                     path[index] = { d=newDistance, previous=current }
//                 end
//                 if not nearest then
//                     nearest = path[index].d
//                     nearestIndex = index
//                 elseif path[index].d < nearest then
//                     nearest = path[index].d
//                     nearestIndex = index
//                 end
//             end
//         end
// 
//         if nearest then
//             visited[current] = true
//             current = nearestIndex
//         else
//             nearest = _huge
// 
//             for i, j in pairs( visited ) do
//                 if not j then
//                     if path[i].d < nearest then
//                         nearest = path[i].d
//                         nearestIndex = i
//                     end
//                 end
//             end
// 
//             if nearestIndex then
//                 visited[current] = true
//                 current = nearestIndex
//             else
//                 nearest = nil
//             end
//         end
//     until not nearest
// 
//     -- printSegments( path, true )
//     return getShortestRoute( path, destination )
// end
// -- printSegments( busStops )
// 
// -- Määritä alkupiste ja määränpää tässä:
// local travelRoute = getRoute( busStops, "A", "H" )
// 
// if travelRoute then
//     local stringPath = ""
//     for i = #travelRoute, 1, -1 do
//         stringPath = stringPath .. travelRoute[i][1] .. ", "
//     end
//     stringPath = stringPath:sub(1,-3)
//     print( "\nOptimaalinen reitti on " .. stringPath .. ", kesto on " .. travelRoute[1][2] .. "." )
// end


function getRoute() {
   console.log( "fancy algorithm goes here." );
}
