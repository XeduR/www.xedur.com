window.mobileCheck = function() {
    return (
        navigator.maxTouchPoints > 0 &&
        window.matchMedia("(hover: none)").matches
    );
};
