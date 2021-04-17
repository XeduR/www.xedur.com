# Static Page Builder for www.xedur.com
A Lua/Solar2D based simple program for dynamically creating a series of static files for [www.xedur.com](https://www.xedur.com/)'s main pages and most demos.

## How to use
- Just run Builder/main.lua using Solar2D Simulator and copy the outputs from the Builder/dst/ folder.
- Make any needed changes to the source files in Builder/src/.
- The website builder only creates the static web pages for the site. It doesn't actually build and copy the demo apps, so they need to be moved manually.
- TO BE ADDED: Verifier - run the verifier after having copied the files to www.xedur.com site files to verify that the Demo apps names match with their index.html names, or if they don't then change them to match to avoid errors on live site.

Note: If you are using another Lua based engine or terminal, you'll need to change `system.pathForFile()` API call to work with your setup.  


## Why?
Because I want to keep my portfolio site running entirely without a backend, i.e. using only static pages and because I don't wish to use jQuery or other trickery to load common elements to all pages and subpages. Using this static page builder lets me change one of the source files and then run the program once and that change gets applied to all corresponding pages. In other words, simplicty and maximum gains for minimum effort. 
