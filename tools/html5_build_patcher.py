#!/usr/bin/env python3
"""
Solar2D HTML5 Build - Post-Build Patcher (WASM builds)

.bin patches:
  1. Removes the blur callback registration to prevent HTML5 builds from freezing when user clicks outside of the app.

index.html patches:
  2. Comments out the alert() in printErr to prevent blocking popups on non-fatal WASM errors.
  3. Adds cross-browser vendor prefixes and styling fixes to the progress bar CSS.
  4. Replaces statusElement.innerHTML with textContent to prevent XSS.
  5. Prevents arrow keys from scrolling the page.
  6. Adds pointer capture and edge projection for mouse/cursor drag handling outside the canvas.

Cleanup:
  7. Deletes index-debug.html and index-nosplash.html (unused in production).
"""

import zipfile
import os
import sys
import shutil
import re
from pathlib import Path

line_length = 60

def remove_blur_callback(js_content):
    """
    Remove the blur callback registration from _emscripten_set_blur_callback_on_thread.
    """
    pattern = r'(function _emscripten_set_blur_callback_on_thread\([^)]*\)\{)registerFocusEventCallback\([^)]*\);(return 0\})'

    modified_content = re.sub(pattern, r'\1\2', js_content)

    if modified_content != js_content:
        print("Successfully removed blur callback registration")
        return modified_content, True

    print("Warning: Could not find the expected function pattern.")
    print("This file may already be modified or have a different structure.")
    return js_content, False


def process_bin_file(bin_path):
    """
    Process the .bin file (zip archive):
    1. Extract it
    2. Modify the .js file (same name as .bin)
    3. Re-zip it
    """
    bin_path = Path(bin_path)

    if not bin_path.exists():
        print(f"Error: File '{bin_path}' not found!")
        return False

    print(f"Processing: {bin_path}")

    temp_dir = bin_path.parent / f"{bin_path.stem}_temp"

    try:
        # .bin is a zip archive containing the JS app and WASM module
        print("Extracting files...")
        with zipfile.ZipFile(bin_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Find the .js file (same name as .bin file)
        js_filename = bin_path.stem + ".js"
        js_file = temp_dir / js_filename

        if not js_file.exists():
            print(f"Error: {js_filename} not found in the archive!")
            print("Looking for any .js files in the archive...")
            js_files = list(temp_dir.glob("*.js"))
            if js_files:
                print(f"Found: {[f.name for f in js_files]}")
                print(f"Expected: {js_filename}")
            return False

        print(f"Found: {js_file.name}")

        with open(js_file, 'r', encoding='utf-8') as f:
            js_content = f.read()

        print("Modifying blur callback function...")
        modified_content, was_modified = remove_blur_callback(js_content)

        if not was_modified:
            print("No modifications made. The file may already be modified.")
            user_input = input("Continue anyway? (y/n): ").strip().lower()
            if user_input != 'y':
                return False

        with open(js_file, 'w', encoding='utf-8') as f:
            f.write(modified_content)

        # Repack the archive with the patched JS file
        print("Re-creating archive...")
        with zipfile.ZipFile(bin_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(temp_dir)
                    zip_ref.write(file_path, arcname)

        print(f"Successfully processed {bin_path.name}")
        return True

    except Exception as e:
        print(f"Error: {e}")
        return False

    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print("Cleaned up temporary files")


def patch_printErr_alert(content):
    """
    Comment out the alert() call in printErr.
    The Solar2D-generated printErr calls alert() for any error containing 'ERROR',
    which blocks the UI thread and can cause cascading WASM crashes.
    """
    pattern = r'''if\(\s*typeof\(text\)\s*===\s*"string"\s*&&\s*text\.toUpperCase\(\)\.indexOf\("ERROR"\)\s*>=\s*0\)\s*alert\(text\);'''
    modified = re.sub(pattern, r'// Commented out: blocking alert() on errors causes WASM crashes and freezes the UI\n            // \g<0>', content)
    return modified, modified != content


def patch_progress_css(content):
    """
    Add cross-browser vendor prefixes and styling fixes to the progress bar.
    - Adds -webkit-appearance and -moz-appearance prefixes
    - Replaces border-radius with border: none
    - Improves box-shadow depth
    """
    modified = content

    # Add vendor prefixes for appearance (match indentation of surrounding CSS)
    modified = re.sub(
        r'(\n)([ \t]*)(appearance:\s*none;)',
        r'\1\2-webkit-appearance: none;\1\2-moz-appearance: none;\1\2appearance: none;',
        modified,
        count=1
    )

    # Replace border-radius with border: none
    modified = modified.replace('border-radius: 3px;', 'border: none;', 1)

    # Improve box-shadow depth
    modified = modified.replace('0 2px 3px rgba', '0 4px 4px rgba', 1)

    return modified, modified != content


def patch_textContent(content):
    """Replace statusElement.innerHTML with textContent to prevent XSS."""
    modified = content.replace('statusElement.innerHTML', 'statusElement.textContent', 1)
    return modified, modified != content


# The enhanced script block that replaces Solar2D's default event listeners.
# Adds arrow key scroll prevention and pointer capture with edge projection.
ENHANCED_SCRIPT_BLOCK = '''\t<script>
\t\t// Solar2D's default listeners.
\t\twindow.addEventListener('load',function(){window.focus()});
\t\twindow.addEventListener('mousedown', function () {
\t\t\tdocument.activeElement.blur();
\t\t\twindow.focus();
\t\t}, true);

\t\t// Prevent arrow keys from scrolling the page.
\t\twindow.addEventListener("keydown", function(event) {
\t\t\tif (["ArrowLeft","ArrowUp","ArrowRight","ArrowDown"].indexOf(event.key) > -1 || (event.keyCode !== undefined && [37, 38, 39, 40].indexOf(event.keyCode) > -1)) {
\t\t\t\tevent.preventDefault();
\t\t\t}
\t\t}, false);

\t\t// Pointer capture: track drags outside the canvas by projecting
\t\t// the drag vector onto the nearest canvas edge (preserves angle).
\t\tvar canvas = document.getElementById('canvas');
\t\tvar emscriptenMousemove = null;
\t\tvar dragging = false;
\t\tvar outsideCanvas = false;
\t\tvar startX = 0, startY = 0;
\t\tvar lastX = 0, lastY = 0;

\t\t// Project line from start to cursor onto the nearest canvas edge.
\t\tfunction edgeProject(sx, sy, ex, ey, r) {
\t\t\tvar dx = ex - sx, dy = ey - sy;
\t\t\tvar t, tMin = 1, c;
\t\t\tif (dx > 0) {
\t\t\t\tt = (r.right - 1 - sx) / dx;
\t\t\t\tif (t > 0 && t < tMin) { c = sy + t * dy; if (c >= r.top && c < r.bottom) tMin = t; }
\t\t\t} else if (dx < 0) {
\t\t\t\tt = (r.left - sx) / dx;
\t\t\t\tif (t > 0 && t < tMin) { c = sy + t * dy; if (c >= r.top && c < r.bottom) tMin = t; }
\t\t\t}
\t\t\tif (dy > 0) {
\t\t\t\tt = (r.bottom - 1 - sy) / dy;
\t\t\t\tif (t > 0 && t < tMin) { c = sx + t * dx; if (c >= r.left && c < r.right) tMin = t; }
\t\t\t} else if (dy < 0) {
\t\t\t\tt = (r.top - sy) / dy;
\t\t\t\tif (t > 0 && t < tMin) { c = sx + t * dx; if (c >= r.left && c < r.right) tMin = t; }
\t\t\t}
\t\t\treturn {
\t\t\t\tx: Math.max(r.left, Math.min(r.right - 1, sx + tMin * dx)),
\t\t\t\ty: Math.max(r.top, Math.min(r.bottom - 1, sy + tMin * dy))
\t\t\t};
\t\t}

\t\t// Intercept Emscripten's mousemove handler on the canvas and
\t\t// block it during outside-canvas drags (only projected coords pass).
\t\tvar _origAdd = EventTarget.prototype.addEventListener;
\t\tcanvas.addEventListener = function(type, fn, opt) {
\t\t\tif (type === 'mousemove' && !emscriptenMousemove) {
\t\t\t\temscriptenMousemove = fn;
\t\t\t\t_origAdd.call(canvas, type, function(e) {
\t\t\t\t\tif (dragging && outsideCanvas) return;
\t\t\t\t\temscriptenMousemove.call(canvas, e);
\t\t\t\t}, opt);
\t\t\t} else {
\t\t\t\t_origAdd.call(this, type, fn, opt);
\t\t\t}
\t\t};
\t\tcanvas.addEventListener('pointerdown', function(e) {
\t\t\tdragging = true;
\t\t\toutsideCanvas = false;
\t\t\tstartX = e.clientX;
\t\t\tstartY = e.clientY;
\t\t\tlastX = e.clientX;
\t\t\tlastY = e.clientY;
\t\t\ttry { canvas.setPointerCapture(e.pointerId); } catch (err) {}
\t\t}, true);
\t\tdocument.addEventListener('pointerup', function() {
\t\t\tdragging = false;
\t\t\toutsideCanvas = false;
\t\t});
\t\tdocument.addEventListener('pointercancel', function() {
\t\t\tdragging = false;
\t\t\toutsideCanvas = false;
\t\t});

\t\t// When dragging outside the canvas, project onto the nearest
\t\t// edge (Solar2D's HTML5 layer ignores out-of-bounds values).
\t\tcanvas.addEventListener('pointermove', function(e) {
\t\t\tif (!dragging) return;
\t\t\tvar rect = canvas.getBoundingClientRect();
\t\t\tvar isOutside = e.clientX < rect.left || e.clientX >= rect.right ||
\t\t\t\t\t\t\te.clientY < rect.top || e.clientY >= rect.bottom;
\t\t\toutsideCanvas = isOutside;
\t\t\tif (isOutside) {
\t\t\t\tlastX += e.movementX;
\t\t\t\tlastY += e.movementY;
\t\t\t\tif (emscriptenMousemove) {
\t\t\t\t\tvar p = edgeProject(startX, startY, lastX, lastY, rect);
\t\t\t\t\temscriptenMousemove.call(canvas, new MouseEvent('mousemove', {
\t\t\t\t\t\tclientX: p.x,
\t\t\t\t\t\tclientY: p.y,
\t\t\t\t\t\tscreenX: e.screenX,
\t\t\t\t\t\tscreenY: e.screenY,
\t\t\t\t\t\tmovementX: e.movementX,
\t\t\t\t\t\tmovementY: e.movementY,
\t\t\t\t\t\tbutton: e.button,
\t\t\t\t\t\tbuttons: e.buttons,
\t\t\t\t\t\tctrlKey: e.ctrlKey,
\t\t\t\t\t\tshiftKey: e.shiftKey,
\t\t\t\t\t\taltKey: e.altKey,
\t\t\t\t\t\tmetaKey: e.metaKey
\t\t\t\t\t}));
\t\t\t\t}
\t\t\t} else {
\t\t\t\tlastX = e.clientX;
\t\t\t\tlastY = e.clientY;
\t\t\t}
\t\t}, true);

\t\t// Forward parent-document moves into the iframe with projected coords.
\t\tvar iframe;
\t\ttry { iframe = window.frameElement; } catch (e) {}
\t\tif (iframe) {
\t\t\twindow.parent.document.addEventListener('mousemove', function(e) {
\t\t\t\tif (dragging && emscriptenMousemove) {
\t\t\t\t\tvar iRect = iframe.getBoundingClientRect();
\t\t\t\t\tvar cRect = canvas.getBoundingClientRect();
\t\t\t\t\tvar mx = e.clientX - iRect.left;
\t\t\t\t\tvar my = e.clientY - iRect.top;
\t\t\t\t\tif (mx < cRect.left || mx >= cRect.right || my < cRect.top || my >= cRect.bottom) {
\t\t\t\t\t\toutsideCanvas = true;
\t\t\t\t\t\tvar p = edgeProject(startX, startY, mx, my, cRect);
\t\t\t\t\t\temscriptenMousemove.call(canvas, new MouseEvent('mousemove', {
\t\t\t\t\t\t\tclientX: p.x,
\t\t\t\t\t\t\tclientY: p.y,
\t\t\t\t\t\t\tscreenX: e.screenX,
\t\t\t\t\t\t\tscreenY: e.screenY,
\t\t\t\t\t\t\tmovementX: e.movementX,
\t\t\t\t\t\t\tmovementY: e.movementY,
\t\t\t\t\t\t\tbutton: e.button,
\t\t\t\t\t\t\tbuttons: e.buttons,
\t\t\t\t\t\t\tctrlKey: e.ctrlKey,
\t\t\t\t\t\t\tshiftKey: e.shiftKey,
\t\t\t\t\t\t\taltKey: e.altKey,
\t\t\t\t\t\t\tmetaKey: e.metaKey
\t\t\t\t\t\t}));
\t\t\t\t\t}
\t\t\t\t}
\t\t\t});
\t\t\twindow.parent.document.addEventListener('mouseup', function() {
\t\t\t\tdragging = false;
\t\t\t\toutsideCanvas = false;
\t\t\t});
\t\t}
\t</script>'''


def patch_inject_scripts(content):
    """
    Replace the default event listener script block with an enhanced version
    that includes arrow key scroll prevention and pointer capture with edge projection.
    """
    # Match the last <script> block containing the default window event listeners
    pattern = r'<script>\s*window\.addEventListener\(\'load\'.*?</script>'
    modified = re.sub(pattern, ENHANCED_SCRIPT_BLOCK, content, count=1, flags=re.DOTALL)
    return modified, modified != content


def patch_index_html(bin_dir):
    """
    Apply all patches to bin/index.html:
    - Remove alert() from printErr
    - Fix lang attribute
    - Fix progress bar CSS
    - Use textContent instead of innerHTML
    - Inject arrow key prevention + pointer capture
    """
    index_path = bin_dir / "index.html"

    if not index_path.exists():
        print(f"Warning: {index_path} not found, skipping index.html patches")
        return False

    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    patches = [
        ("Remove printErr alert", patch_printErr_alert),
        ("Fix progress bar CSS", patch_progress_css),
        ("Use textContent over innerHTML", patch_textContent),
        ("Add arrow key prevention + pointer capture", patch_inject_scripts),
    ]

    any_applied = False
    for name, fn in patches:
        content, applied = fn(content)
        status = "applied" if applied else "skipped (already patched or pattern not found)"
        print(f"  {name}: {status}")
        if applied:
            any_applied = True

    if any_applied:
        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print("index.html patched successfully")
    else:
        print("Note: No patches were applied (file may already be patched)")

    return any_applied


def delete_unused_html(bin_dir):
    """
    Delete index-debug.html and index-nosplash.html from the bin directory.
    These are generated by Solar2D but not used in production.
    """
    files_to_delete = ["index-debug.html", "index-nosplash.html"]
    deleted = []

    for filename in files_to_delete:
        file_path = bin_dir / filename
        if file_path.exists():
            file_path.unlink()
            print(f"Deleted {filename}")
            deleted.append(filename)

    if not deleted:
        print("Note: No unused HTML files found to delete")

    return len(deleted) > 0


def clean_path(raw_path):
    """
    Clean up a path string from terminal input.
    Handles VS Code/PowerShell drag-and-drop artifacts and surrounding quotes.
    """
    path = raw_path.strip()

    # VS Code adds "& '" at the beginning when drag-dropping
    if path.startswith("& '") or path.startswith('& "'):
        path = path[2:].strip()

    # Remove surrounding quotes (from drag and drop)
    path = path.strip('"').strip("'")

    return path


def find_bin_in_dir(directory):
    """
    Find a single .bin file in a directory.
    Returns the path if exactly one .bin file is found, otherwise None.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None

    bin_files = list(directory.glob("*.bin"))

    if len(bin_files) == 1:
        return bin_files[0]
    elif len(bin_files) > 1:
        print(f"Error: Multiple .bin files found in '{directory}':")
        for f in bin_files:
            print(f"  - {f.name}")
        print("Please specify which file to process.")

    return None


def resolve_bin_path(user_path):
    """
    Resolve user input to a .bin file path.
    Accepts a direct .bin file path or a folder containing a .bin file.
    """
    path = Path(user_path)

    if path.is_file() and path.suffix == '.bin':
        return path

    if path.is_dir():
        result = find_bin_in_dir(path)
        if result:
            return result
        print(f"Error: No .bin file found in '{path}'")
        return None

    if not path.exists():
        print(f"Error: '{path}' does not exist!")
        return None

    print(f"Error: '{path}' is not a .bin file or directory")
    return None


def auto_detect_bin():
    """
    Auto-detect .bin file in the script's directory or its 'bin' subdirectory.
    """
    script_dir = Path(__file__).parent

    result = find_bin_in_dir(script_dir)
    if result:
        return result

    bin_dir = script_dir / "bin"
    result = find_bin_in_dir(bin_dir)
    if result:
        return result

    print(f"Error: No .bin file found in '{script_dir}' or '{bin_dir}'")
    return None


def main():
    print("=" * line_length)
    print("Solar2D HTML5 - Post-Build Patcher (WASM)")
    print("Patches .bin + index.html + cleanup")
    print("=" * line_length)
    print()

    bin_path = None

    if len(sys.argv) > 1:
        bin_path = resolve_bin_path(clean_path(sys.argv[1]))
    else:
        print("Provide the path to your .bin file or its folder by:")
        print("  - Typing or pasting a path to the .bin file or its folder")
        print("  - Dragging and dropping the file or its folder into this window")
        print("  - Pressing Enter to auto-detect the file in the current folder")
        print()

        try:
            user_input = input("> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            return

        if user_input:
            bin_path = resolve_bin_path(clean_path(user_input))
        else:
            print("Auto-detecting .bin file...")
            bin_path = auto_detect_bin()

    if not bin_path:
        input("\nPress Enter to exit...")
        return

    print(f"Found: {bin_path}")
    print()

    bin_dir = bin_path.parent
    bin_success = process_bin_file(bin_path)

    print()
    print("-" * line_length)
    print("Patching index.html...")
    html_success = patch_index_html(bin_dir)

    print()
    print("-" * line_length)
    print("Cleaning up unused HTML files...")
    delete_unused_html(bin_dir)

    print()
    print("=" * line_length)

    if bin_success and html_success:
        print("SUCCESS! Your HTML5 build has been patched.")
        print("- Blur callback removed from .bin (no freeze on click outside)")
        print("- index.html patches applied (see details above)")
        print("- Unused HTML files cleaned up")
    elif bin_success:
        print("Blur callback removed successfully.")
        print("Note: index.html patches were skipped (see above).")
    elif html_success:
        print("index.html patches applied successfully.")
        print("Note: .bin processing had issues (see above).")
    else:
        print("Process completed with warnings or errors.")
        print("Please check the messages above.")

    print("=" * line_length)
    input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()