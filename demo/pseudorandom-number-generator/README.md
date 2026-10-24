Pseudorandom Number Generator
----

[Interactive online demo](https://www.xedur.com/demo/pseudorandom-number-generator/) that demonstrates pseudorandom number generation methods and their distribution (with source code).

If you just need the **JavaScript implementation** for generating pseudorandom numbers without any of the interactive demo hassle, then all you need to do is copy the [random.js from inside the js folder of this repo](https://github.com/XeduR/www.xedur.com/blob/master/demo/pseudorandom-number-generator/js/random.js) and place it in your project.

You can also find a **Lua implementation** for generating pseudorandom numbers using the linear congruential generation method in my [other repository](https://github.com/XeduR/Solar2D-Projects/blob/master/Pseudorandom%20Number%20Generator/rng.lua). You may find this useful if you are using game engines like Solar2D, Defold or Löve and you need to be able to generate pseudorandom numbers that are platform independent (since Lua's math.random isn't).
