"use strict";
function escapeAttr(value) {
return value
.replace(/&/g, "&amp;")
.replace(/</g, "&lt;")
.replace(/>/g, "&gt;")
.replace(/"/g, "&quot;");
}
function loadVideos() {
const placeholders = document.querySelectorAll(".video-placeholder");
placeholders.forEach((placeholder) => {
const videoId = placeholder.getAttribute("data-video-id");
const rawTitle = placeholder.getAttribute("data-video-title") || "YouTube video player";
const title = escapeAttr(rawTitle);
placeholder.innerHTML = '<iframe src="https://www.youtube-nocookie.com/embed/' + videoId + '?rel=0" title="' + title + '" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>';
});
}
function readConsent() {
try {
return localStorage.getItem("videosAccepted") === "true";
} catch (error) {
return false;
}
}
function storeConsent() {
try {
localStorage.setItem("videosAccepted", "true");
} catch (error) {
console.warn("Video consent could not be saved:", error);
}
}
function acceptVideos() {
storeConsent();
loadVideos();
}
document.addEventListener("DOMContentLoaded", () => {
const placeholders = document.querySelectorAll(".video-placeholder");
placeholders.forEach((placeholder) => {
const videoId = placeholder.getAttribute("data-video-id");
const probe = new Image();
probe.addEventListener("load", () => {
placeholder.style.backgroundImage = "url('https://img.youtube.com/vi/" + videoId + "/maxresdefault.jpg')";
});
probe.addEventListener("error", () => {
placeholder.style.backgroundImage = "url('https://img.youtube.com/vi/" + videoId + "/hqdefault.jpg')";
});
probe.src = "https://img.youtube.com/vi/" + videoId + "/maxresdefault.jpg";
const button = placeholder.querySelector(".video-consent");
if (button) {
button.addEventListener("click", acceptVideos);
}
});
if (readConsent()) {
loadVideos();
}
});