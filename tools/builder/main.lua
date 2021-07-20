--[[
    ---------------------------------------------------------------------------
    Program for automating the creation of static page files for www.xedur.com.
    ---------------------------------------------------------------------------
    
    The front page, as well as most of the demo pages share a few common elements,
    such as 1) header, 2) footer, and 3) Ko-fi buttons. Most of the demo pages
    also have identical structure with 1) back button, 2) title and description,
    both visible and in meta data, 3) the links, and 4) the app itself.
    
    This program will load the source files for the three common elements and
    add them to home.html, then saving it the resulting file as index.html in
    the root of dst folder.
    
    It will then load the demos.json file, which contains all of the relevant
    information mentioned above for each project and use them to create a page
    for each individual demo. The actual app files will need to manually added,
    because there is no need to store them twice in the system given that they
    will not be edited in any way by this program.
    ---------------------------------------------------------------------------
]]--
local lfs = require( "lfs" )
local json = require("json")
local demoPath, demoContent = system.pathForFile( "src/demos.json", system.ResourceDirectory )
if not demoPath then
    print( "Path error: demos.json not found." )
else
    local file, errorString = io.open( demoPath, "r" )
    if not file then
        print( "File error: " .. errorString )
    else
        local contents = file:read( "*a" )
        demoContent = json.decode( contents )
        io.close( file )
    end
end

local progress = display.newText( "Build starting...", display.contentCenterX, display.contentCenterY, native.systemFontBold, 32 )

if demoContent then
    -- Create and select "dst" folder to build the website to.
    local rootPath = system.pathForFile( nil, system.ResourceDirectory )
    lfs.chdir( rootPath )
    lfs.mkdir( "dst" )
    local buildPath = lfs.currentdir() .. "/dst"
    
    -- Load all source files for the common elements.
    local function getSource( filepath )
        local path = system.pathForFile( filepath, system.ResourceDirectory )
        if not path then
            print( "Path error: " .. filepath )
        else
            local file, errorString = io.open( path, "r" )
            if not file then
                print( "File error: " .. errorString )
            else
                local contents = file:read( "*a" )
                io.close( file )
                return contents
            end
        end
    end
    local srcFrontpage = getSource( "src/frontpage.html" )
    local srcDemopage = getSource( "src/demopage.html" )
    local srcIframe = getSource( "src/iframe.html" )
    local srcOptimisation = getSource( "src/optimisation.html" )
    local srcHeader = getSource( "src/header.html" )
    local srcFooter = getSource( "src/footer.html" )
    local srcContact = getSource( "src/contact.html" )
    local srcKofi = getSource( "src/kofi.html" )

    -- Add the common elements to top level pages and output them to dst folder root.
    local function createPage( filename, data )
        local file, errorString = io.open( buildPath .. "/" .. filename, "w" )
        if not file then
            print( "File error: " .. errorString )
        else
            data = data:gsub( "###INSERT_HEADER###", srcHeader )
            data = data:gsub( "###INSERT_FOOTER###", srcFooter )
            data = data:gsub( "###INSERT_CONTACT###", srcContact )
            data = data:gsub( "###INSERT_KOFI###", srcKofi )
            -- Create a demo panel for the front page.
            if filename == "index.html" then
                local demo = {}
                for i = 1, #demoContent do
                    local t = demoContent[i].frontpage
                    if not demo[t.type] then demo[t.type] = {} end
                    local s = ''
                    s = s .. '<div class="project-container">'
                    s = s ..    '<a href="'..(t.link or "")..'">'
                    s = s ..        '<h2>'..(t.title or "")..'</h2>'
                    s = s ..        '<div class="image-container">'
                    s = s ..            '<img src="'..(t.image or "")..'">'
                    s = s ..        '</div>'
                    s = s ..        '<p>'..(t.desc or "")..'</p>'
                    s = s ..    '</a>'
                    s = s .. '</div>'
                    if t.tech then
                        s = s .. '<p class="tech"><b>Tech:</b> '..t.tech..'</p>'
                    end
                    demo[t.type][#demo[t.type]+1] = s
                end
                data = data:gsub( "###INSERT_PLUGINS###", table.concat( demo["plugins"], "\n" ) )
                data = data:gsub( "###INSERT_UNASSORTED###", table.concat( demo["unassorted"], "\n" ) )
                data = data:gsub( "###INSERT_GAMES###", table.concat( demo["games"], "\n" ) )
                data = data:gsub( "###INSERT_OTHER###", table.concat( demo["other"], "\n" ) )
            end
            file:write( data )
            io.close( file )
        end
    end
    createPage( "index.html", srcFrontpage )
    createPage( "optimisation.html", srcOptimisation )
    
    -- Create demo pages using the common elements and the data in the demos.json.
    -- NB! Some non-Solar2D demos are manually generated and need manual updating.
    local function createDemoPage( demoData )
        -- Ensure that demo page exists on the domain and isn't an external link.
        local t, link = demoData.demo, demoData.frontpage.link
        local _, startIndex =  link:find( "https://www.xedur.com/demos/" )
        if not t or not startIndex then return end
        
        -- Create the demo's folder name based on the front page's link for it.
        local endIndex = link:find( "/", startIndex+1 )
        local folder = link:sub( startIndex+1, endIndex and endIndex-1 )
        
        local success = lfs.chdir( buildPath )
        local demoPath = buildPath .. "/" .. folder
        if success then
            lfs.mkdir( demoPath )
        else
            return
        end
        
        -- Create the index.html page where the demo will reside.
        local path = system.pathForFile( "", system.ResourceDirectory )
        if not path then
            print( "Path error: " .. filename )
        else
            local file, errorString = io.open( demoPath .. "/index.html", "w" )
            if not file then
                print( "File error: " .. errorString )
            else
                local data = srcDemopage
                data = data:gsub( "###INSERT_HEADER###", srcHeader )
                data = data:gsub( "###INSERT_FOOTER###", srcFooter )
                data = data:gsub( "###INSERT_KOFI###", srcKofi )
                data = data:gsub( "###INSERT_DEMO_TITLE_META###", (t.heading or "") )
                data = data:gsub( "###INSERT_DEMO_DESCRIPTION_META###", (demoData.frontpage.desc or "") )
                
                local s = ''
                s = s .. '<h1 class="title-demo">'
                s = s ..    (t.heading or "")
                s = s .. '</h1>'
                data = data:gsub( "###INSERT_DEMO_TITLE###", s )
                
                s = ''
                s = s .. '<div class="demo-panel">'
                s = s ..    '<p>'
                s = s ..        (t.desc or "")
                s = s ..    '</p>'
                s = s .. '</div>'
                data = data:gsub( "###INSERT_DEMO_DESCRIPTION###", s )
                
                if t.links and #t.links > 0 then
                    s = ''
                    s = s .. '<div class="demo-panel dark">'
                    s = s ..    '<ul>'
                    for i = 1, #t.links do
                        s = s ..    '<a class="list" href="' .. t.links[i].url .. '">'
                        s = s ..        '<li>'
                        s = s ..            '<span style="color:white;">' .. t.links[i].text .. ':</span> ' .. t.links[i].url
                        s = s ..        '</li>'
                        s = s ..    '</a>'
                    end
                    s = s ..    '</ul>'
                    s = s .. '</div>'
                    data = data:gsub( "###INSERT_DEMO_LINKS###", s )
                end
                file:write( data )
                io.close( file )
                
                -- Create a a subfolder for where the app's Iframe content will reside.
                local success = lfs.chdir( demoPath )
                local appPath = demoPath .. "/app"
                if success then
                    lfs.mkdir( appPath )
                else
                    return
                end
                
                local path = system.pathForFile( "", system.ResourceDirectory )
                if not path then
                    print( "Path error: " .. filename )
                else
                    local file, errorString = io.open( appPath .. "/index.html", "w" )
                    if not file then
                        print( "File error: " .. errorString )
                    else
                        local data = srcIframe
                        data = data:gsub( "###INSERT_DEMO_TITLE_META###", (t.heading or "") )
                        file:write( data )
                        io.close( file )
                    end
                end
            end
        end
    end
    
    for _, demoData in pairs( demoContent ) do
        createDemoPage( demoData )
    end
    -- Return to root directory in order to release the current folder from Solar2D's control,
    -- so that the build folder can be moved or removed without the files being locked by OS.
    lfs.chdir( rootPath )
    
    progress.text = "Build done."
    progress:setFillColor( 0.2, 0.9, 0 )
end