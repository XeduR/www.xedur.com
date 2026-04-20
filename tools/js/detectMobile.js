// Detect touch-capable devices, but filter out filter out
// laptops with touchscreens (which still have a mouse).
window.mobileCheck = function() {
    return (
        navigator.maxTouchPoints > 0 &&
        window.matchMedia("(hover: none)").matches
    );
};
