// Pseudorandom number generation using the middle-square method.
// NB! For production use, prefer random.js (linear congruential) over this method.

(function() {
	// Initial randomisation parameters.
	var numCount = 10;
	var beg = Math.floor(numCount*0.5);
	var end = beg + numCount;
	var seed = 12345;

	window.randomseedMS = function(n) {
		if (typeof(n) == "number") {
			seed = Math.floor(n+0.5);
		}
	};

	window.randomMS = function() {
		var n = (seed*seed).toString();
		// Pad to 2*numCount digits so the middle extraction always has consistent width
		while (n.length < numCount*2) {
			n = "0".concat(n);
		}
		seed = n.substring(beg, end);
		return seed / 9999999999;
	};
})();
