// Pseudorandom number generation using the middle-square method:

////////////////////////////////////////////////////////////////////////
// NB! If you need a pseudorandom number generator, then you should   //
// use random.js instead. The file is located in the same repository. //
////////////////////////////////////////////////////////////////////////

// Initial randomisation parameters.
var numCount = 10;
var beg = Math.floor(numCount*0.5);
var end = beg + numCount;
var seed = 12345;

// Set a new initial random seed.
function randomseedMS(n) {
    if (typeof(n) == "number") {
        seed = Math.floor(n+0.5)
    }
}

// Calculate and return a random number between between 0 and 1.
function randomMS() {
    let n = (seed*seed).toString();
    while (n.length < numCount*2) {
        n = "0".concat(n);
    }
    seed = n.substring(beg, end);
    return seed / 9999999999;
}