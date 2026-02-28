var canvas = document.getElementById("canvas");
var context = canvas.getContext("2d");

// Canvas & histogram visual customisation variables:
var borders = 40;
var textOffset = 10;
var histogramHeight = 60;
var mapSize = canvas.width-borders;
var mapStartY = canvas.height-mapSize;
var drawing = false;
var entries = [];
// Width of each histogram bucket (maps [0,1) range to pixel columns)
var unit = 1/(mapSize-borders);
var entryCount = mapSize*mapSize;
var y;
var randomMethod;

function draw() {
    // Draw the random bitmap line by line using a loop.
    while (y < canvas.height-borders) {
        for (var x = borders; x < mapSize; x++) {
            var r = randomMethod();
            entries[Math.floor(r/unit)] += 1;
            var c = r*255;
            context.fillStyle = "rgb("+c+","+c+","+c+")";
            context.fillRect(x, y, 1, 1);
        }
        y++;
    }

    if (y == canvas.height-borders) {
        // Find rarest and most common random variables and their frequencies (up to 2 decimals).
        var max = Math.max(...entries);
        // Truncate (not round) to 2 decimal places
        var maxFreq = Math.floor(max/entryCount*10000)/100+"%";
        var min = Math.min(...entries);
        var minFreq = Math.floor(min/entryCount*10000)/100+"%";
        var range = max-min;

        // Draw the histogram and axes information.
        context.fillStyle = "black";
        for (var i = 0; i < entries.length; i++) {
            var h = (entries[i]-min)/range*histogramHeight;
            context.fillRect( borders+i, borders+histogramHeight-h, 1, h);
        }
        context.fillStyle = "red";
        context.fillRect(borders, borders, mapSize-borders, 1);
        context.fillRect(borders, borders+histogramHeight*0.5, mapSize-borders, 1);
        context.fillRect(borders, borders+histogramHeight, mapSize-borders, 1);
        context.font = "bold 10px Arial";
        context.textAlign = "right";
        context.textBaseline = "middle";
        context.fillText(maxFreq, borders-4, borders);
        context.fillText(minFreq, borders-4, borders+histogramHeight);
        context.textAlign = "left";
        context.fillText("x", mapSize+4, borders+histogramHeight);
        context.textAlign = "center";
        context.textBaseline = "bottom";
        context.fillText("freq", borders, borders-12);
        context.textBaseline = "top";
        context.fillText("0", borders, borders+histogramHeight+8);
        context.fillText("1", mapSize, borders+histogramHeight+8);

        drawing = false;
    }
}

function start(mode) {
    if (!drawing) {
        var seedValue;
        if (mode == "middle-square") {
            randomMethod = randomMS;
            seedValue = document.getElementById("seed2").value;
        } else {
            randomMethod = random;
            seedValue = document.getElementById("seed1").value;
        }
        if (seedValue) {
            drawing = true;
            // Seed the RNG via the proper function instead of setting a global.
            if (mode == "middle-square") {
                randomseedMS(Number(seedValue));
            } else {
                randomseed(Number(seedValue));
            }
            // Reset the canvas and the entries.
            for (var i = 0; i < (mapSize-borders); i++) {
                entries[i] = 0;
            }
            y = mapStartY;
            context.clearRect(0, 0, canvas.width, canvas.height);
            context.fillStyle = "rgb(255,255,255)";
            context.fillRect(0, 0, canvas.width, canvas.height);
            draw();
        } else {
            alert("You must set a seed.");
        }
    }
}

start();
