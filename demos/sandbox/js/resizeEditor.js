// Match the code editor's height with the app's height.
var maxSize = false;
function resizeEditor(){
    var width = document.documentElement.clientWidth;
    if (!maxSize || width < 1920) {
        if (width >= 1920) {
            maxSize = true;
        } else {
            maxSize = false;
        }
        width = width*0.5*0.6666;
        editor.setSize(null, Math.min(width,960));
    }
}
window.addEventListener("resize", resizeEditor);