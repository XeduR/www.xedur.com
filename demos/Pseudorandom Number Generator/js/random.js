// Pseudorandom number generation using the linear congruential method:

// Initial randomisation parameters (you can leave these as is).
var a = 1664525;
var c = 1013904223;
var m = Math.pow(2, 32);
var seed = 12345;

// Set a new initial random seed.
function randomseed(n) {
    if (typeof(n) == "number") {
        seed = Math.floor(n+0.5)
    }
}

// If only one arguments is passed, then x >= 1. If two arguments are passed, then y >= x.
function random(x,y) {
    seed = (a * seed + c) % m;
    let r = seed / m;
    // With no arguments, return a random number between 0 and 1.
    // With one argument, return a random number between it and 1.
    // With two arguments, return a random number between them.
    return !(typeof(x) == "number") ? r : !(typeof(y) == "number") ? Math.floor((x-1)*r+1.5) : Math.floor((y-x)*r+x+0.5);
}