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
var unit = 1/(mapSize-borders);
var entryCount = mapSize*mapSize;
var y;
var randomMethod;

function draw() {
    // Draw the random bitmap line by line.
    for (var x = borders; x < mapSize; x++) {
        let r = randomMethod();
        entries[Math.floor(r/unit)] += 1;
        let c = r*255;
        context.fillStyle = "rgb("+c+","+c+","+c+")";
        context.fillRect(x, y, 1, 1);
    }
    y++;
    if (y < canvas.height-borders) {
        draw();
    } else if (y == canvas.height-borders) {
        // Find rarest and most common random variables and their frequencies (up to 2 decimals).
        let max = Math.max(...entries);
        let maxFreq = Math.floor(max/entryCount*10000)/100+"%";;
        let min = Math.min(...entries);
        let minFreq = Math.floor(min/entryCount*10000)/100+"%";;
        let range = max-min;
        
        // Draw the histogram and axes information.
        context.fillStyle = "black";
        for (var i = 0; i < entries.length; i++) {
            let h = (entries[i]-min)/range*histogramHeight;
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

// Start drawing a new random bitmap.
function start(mode) {
    if (!drawing) {
        if (mode == "middle-square") {
            randomMethod = randomMS;
            seed = document.getElementById("seed2").value;
        } else {
            randomMethod = random;
            seed = document.getElementById("seed1").value;
        }
        if (seed) {
            drawing = true;
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