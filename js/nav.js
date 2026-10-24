var CONTACT_ID = "contact";
var FLASH_CLASS = "contact-flash";
var SEEK_MS_PER_ROOT_PX = 10;
var SEEK_MAX_MS = 900;
var SEEK_CANCEL_EVENTS = ["wheel", "touchstart", "pointerdown", "keydown", "popstate"];
var cancelSeek = null;
document.addEventListener("DOMContentLoaded", function() {
var contactAnchor = document.getElementById(CONTACT_ID);
document.querySelectorAll("a").forEach(function(link) {
link.addEventListener("click", function(event) {
if (this.classList.contains("heading-link")) return;
if (this.hash !== "" && this.href.split("#")[0] === location.href.split("#")[0]) {
var target = document.getElementById(this.hash.slice(1));
if (target) {
event.preventDefault();
if (location.hash !== this.hash) history.pushState(null, "", this.hash);
if (target === contactAnchor) {
showContactPanel(contactAnchor);
} else {
target.scrollIntoView({ behavior: scrollBehavior() });
}
}
}
});
});
if (contactAnchor) {
var panel = contactAnchor.closest("section");
panel.addEventListener("animationend", function(event) {
if (event.target === panel) panel.classList.remove(FLASH_CLASS);
});
var navigation = performance.getEntriesByType("navigation")[0];
if (location.hash === "#" + CONTACT_ID && navigation && navigation.type === "navigate") {
showContactPanel(contactAnchor);
}
}
document.querySelectorAll(".heading-link").forEach(function(link) {
link.addEventListener("click", function(event) {
event.preventDefault();
event.stopPropagation();
var url = this.href;
navigator.clipboard.writeText(url);
this.classList.add("copied");
var el = this;
setTimeout(function() { el.classList.remove("copied"); }, 1500);
});
});
document.querySelector(".toggle").addEventListener("click", function(event) {
toggleMobileNav(event);
});
document.querySelectorAll(".item").forEach(function(item) {
item.addEventListener("click", function(event) {
if (getComputedStyle(document.getElementById("mobile-nav")).display !== "none") {
toggleMobileNav(event);
}
});
});
});
function scrollBehavior() {
return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}
function showContactPanel(anchor) {
var panel = anchor.closest("section");
var root = document.scrollingElement;
function targetY() {
return Math.min(root.scrollHeight - window.innerHeight, anchor.getBoundingClientRect().top + window.scrollY);
}
seekScroll(targetY, function() {
panel.classList.remove(FLASH_CLASS);
void panel.offsetWidth;
panel.classList.add(FLASH_CLASS);
});
}
function seekScroll(targetY, onArrive) {
if (cancelSeek) cancelSeek();
var smooth = scrollBehavior() === "smooth";
var start = window.scrollY;
var written = start;
var lastTarget = start;
var segments = [];
var frame = 0;
var arrived = false;
var observer = new ResizeObserver(function() {
if (!frame) frame = requestAnimationFrame(step);
});
function stop() {
cancelAnimationFrame(frame);
observer.disconnect();
SEEK_CANCEL_EVENTS.forEach(function(type) {
window.removeEventListener(type, stop);
});
cancelSeek = null;
}
function step(now) {
frame = 0;
var drift = window.scrollY - written;
if (Math.abs(drift) < 1) drift = 0;
start += drift;
var target = targetY();
var distance = target - lastTarget - drift;
lastTarget = target;
if (Math.abs(distance) >= 1) {
var duration = smooth ? Math.min(Math.sqrt(Math.abs(distance)) * SEEK_MS_PER_ROOT_PX, SEEK_MAX_MS) : 0;
segments.push({ start: now, distance: distance, duration: duration });
}
var position = start;
var running = false;
segments.forEach(function(segment) {
var progress = segment.duration > 0 ? Math.min((now - segment.start) / segment.duration, 1) : 1;
running = running || progress < 1;
position += segment.distance * easeInOut(progress);
});
window.scrollTo(0, position);
written = window.scrollY;
if (running) {
frame = requestAnimationFrame(step);
return;
}
start = position;
segments = [];
if (!arrived) {
arrived = true;
onArrive();
}
}
SEEK_CANCEL_EVENTS.forEach(function(type) {
window.addEventListener(type, stop, { passive: true });
});
observer.observe(document.body);
cancelSeek = stop;
frame = requestAnimationFrame(step);
}
function easeInOut(progress) {
return progress < 0.5 ? 4 * progress * progress * progress : 1 - Math.pow(2 - 2 * progress, 3) / 2;
}
function toggleMobileNav(event) {
document.querySelector(".bar1").classList.toggle("bar1-active");
document.querySelector(".bar2").classList.toggle("bar2-active");
document.querySelector(".bar3").classList.toggle("bar3-active");
document.querySelectorAll(".item").forEach(function(item) {
item.classList.toggle("active");
});
event.stopPropagation();
}