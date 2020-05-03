// Luodaan taulukko vierekkäisistä pysäkeistä, joiden välillä on bussiyhteys.
function getConnections( routes ) {
    let connections = {};
    for (let i in routes.linjastot) {
        connections[i] = {};
        for (let j = 0; j < routes.linjastot[i].length-1; j++) {
            connections[i][routes.linjastot[i][j] + routes.linjastot[i][j+1]] = true;
            connections[i][routes.linjastot[i][j+1] + routes.linjastot[i][j]] = true;
        }
    }
    return connections;
}

// Valmistellaan reittioppaan data Djikstran algoritmia varten.
function prepareRoutes( routes ) {
    var busStops = {};
    for (let i = 0; i < routes.pysakit.length; i++) {
        busStops[routes.pysakit[i]] = {};
    }
    
    for (let i = 0; i < routes.tiet.length; i++) {
        let duration = routes.tiet[i].kesto;
        let from = routes.tiet[i].mista;
        let to = routes.tiet[i].mihin;
    
        let segment = from + to;
        let isValid = false;
        for (let j in connections) {
            if (typeof connections[j][segment] !== 'undefined') {
                isValid = true;
                break;
            }
        }
    
        if (isValid) {
            busStops[from][to] = duration;
            busStops[to][from] = duration;
        }
    }
    
    // console.log( busStops );
    return busStops;
}

// Djiksan algoritmia käyttäen, määritetään nopein reitti jokaiselle pysäkille
// annetun lähtöpysäkin ja määränpään perusteella.
function getRoute( map, start, destination ) {    
    let path = {};
    let visited = {};
    
    for (let index in map) {
        path[index] = {};
        path[index].d = Infinity;
        visited[index] = false;
    }
    path[start].d = 0;
    
    let current = start;
    
    // Käydään jokainen pysäkki ja niiden naapurit läpi ja selvitetään nopein reitti jokaiselle pysäkille.
    while (true) {
        let nearest, nearestIndex;
        
        for (let index in map[current]) {
            if (visited[index] === false) {
                let newDistance = path[current].d + map[current][index];                
                
                if (newDistance < path[index].d) {
                    path[index].d = newDistance;
                    path[index].previous = current;
                }
                
                if (typeof nearest === 'undefined' || path[index].d < nearest) {
                    nearest = path[index].d;
                    nearestIndex = index;
                }
            }
        }
    
        if (typeof nearest !== 'undefined') {
            visited[current] = true;
            current = nearestIndex;
        } else {
            // Huom! Tätä voisi parantaa jonkun verran, jos algoritmiä ei ajettaisi pysäkkien
            // kohdalla jos määränpää on jo saavutettu ja kyseiselle pysäkille on pidempi kesto
            // kuin jo saavutettuun määränpäähän. Tämän koodihaasteen kohdalla kyseinen parannus
            // jäi tekemättä.
            nearest = Infinity;
            
            for (let index in visited) {
                if (visited[index] == false) {
                    if (path[index].d < nearest) {
                        nearest = path[index].d;
                        nearestIndex = index;
                    }
                }
            }

            if (typeof nearestIndex !== 'undefined') {
                visited[current] = true;
                current = nearestIndex;
            } else {
                break;
            }
        }
    }
    
    // Kun nopein reitti määränpäähän on tiedossa, niin selvitetään
    // vielä reitti takaisin alkupisteeseen. Tämän jälkeen reitti
    // käännetään vielä takaisin "alku -> loppu" järjestykseen.
    let stops = [];
    let durations = [];
    let next = destination;
    let n = 0;
    
    while (true) {
        stops[n] = next;
        durations[n] = path[next].d;
        next = path[next].previous;
        n++;
        if (!next) {break};
    }
    let shortestRoute = {};
    shortestRoute.stops = stops.reverse();
    shortestRoute.duration = durations.reverse();
    // console.log( shortestRoute );
    
    return shortestRoute;
}