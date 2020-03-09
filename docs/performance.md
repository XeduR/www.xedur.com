# Performance

## Overview
A simple performance meter UI to keep track of FPS, texture memory and memory usage in Corona apps.

You can try out the plugin's HTML5 demo at [https://xedur.com/demos/spyricPerformance/](https://xedur.com/demos/spyricPerformance/).

## Setting up
In order to set up Spyric Performance plugin, all you need to do is to add it to your project folder and then require it. You can download Spyric Performance from [GitHub](https://github.com/XeduR/spyricPerformance).

```lua
local performance = require( "spyric.performance" )
```

## Syntax
After requiring Spyric Performance, all you need to do is to start it.

```lua
performance:start( [startVisible] )
```

**startVisible** (optional)
- *Boolean*. You can optionally start the performance meter so that it isn't visible. Default value is true.

## Customisation
You can customise the performance meter's appearance and change its location on the screen by simply modifying these variables within the plugin file.

```lua
local x = display.contentCenterX
local y = display.screenOriginY
local paddingHorizontal = 20
local paddingVertical = 10
local fontColor = { 1 }
local bgColor = { 0 }
local fontSize = 28
local font = "Helvetica"
```
