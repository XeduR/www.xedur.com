window.addEventListener("load", function() {
document.getElementById("startButton").addEventListener("click", function() {
var iframe = document.getElementById("app");
var button = this;
var overlay = document.getElementById("loadOverlay");
iframe.addEventListener("load", function() {
button.style.display = "none";
if (overlay) overlay.style.display = "none";
});
iframe.src = "./app/index.html";
});
});