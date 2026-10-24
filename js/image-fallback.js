"use strict";
const FALLBACK_SELECTOR = ".feature-image img, .post-item-image img, .md-figure img";
const MISSING_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/><line x1="2" y1="2" x2="22" y2="22"/></svg>';
function showMissing(image) {
const panel = document.createElement("span");
panel.className = "image-missing";
panel.setAttribute("role", "img");
const alt = image.getAttribute("alt") || "";
panel.setAttribute("aria-label", alt ? "Image unavailable: " + alt : "Image unavailable");
panel.innerHTML = MISSING_ICON;
const label = document.createElement("span");
label.className = "image-missing-label";
label.textContent = "Image unavailable";
panel.appendChild(label);
if (alt) {
const altText = document.createElement("span");
altText.className = "image-missing-alt";
altText.textContent = alt;
panel.appendChild(altText);
}
image.replaceWith(panel);
}
document.addEventListener("DOMContentLoaded", () => {
document.querySelectorAll(FALLBACK_SELECTOR).forEach((image) => {
if (image.complete && image.naturalWidth === 0) {
showMissing(image);
return;
}
image.addEventListener("error", () => showMissing(image), { once: true });
});
});