// Pseudorandom number generation using the linear congruential method:
///////////////////////////////////////////////////////////////////////

// An interactive online tool demonstrating the random distribution is available at:
// https://www.xedur.com/demos/Pseudorandom%20Number%20Generator/

// A pure Lua implementation of this same linear congruential method is available at:
// https://github.com/XeduR/Solar2D-Projects/blob/master/Pseudorandom%20Number%20Generator/rng.lua

// Initial randomisation parameters (you can leave these as is).
var a = 1664525;
var c = 1013904223;
var m = Math.pow(2, 32);
var seed = 12345;

// Set a new initial random seed.
function randomseed(n) {
    if (typeof(n) == "number") {
        seed = Math.floor(Math.abs(n+0.5));
    }
}

// Generate a pseudorandom number.
function random(x,y) {
    seed = (a * seed + c) % m;
    let r = seed / m;
    // With no arguments,  return a pseudorandom number (fraction) between 0 and 1.
    // With one argument,  return a pseudorandom number (integer)  between 1 and x.
    // With two arguments, return a pseudorandom number (integer)  between x and y.
    return !(typeof(x) == "number") ? r : !(typeof(y) == "number") ? Math.floor((x-1)*r+1.5) : Math.floor((y-x)*r+x+0.5);
}
