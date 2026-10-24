"use strict";

// GDPR-friendly YouTube loader: nothing is embedded until the visitor consents.
// Consent is stored in localStorage so the site itself sets no cookie.  The
// thumbnail is a single image from img.youtube.com (no cookie); it is loaded
// before consent as a deliberate trade-off for a useful placeholder.

function escapeAttr(value) {
    // The engine already entity-escaped data-video-title, but getAttribute
    // returns the decoded value, so re-escape before it goes back into markup.
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

// Blocked site storage makes the localStorage getter itself throw, so every
// access is guarded; consent then lasts only until the page reloads.
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

        // CSS background images fire no error event, so probe with an Image()
        // to pick maxres when it exists and fall back to hq when it does not.
        // A missing maxres is a 404 that still decodes as a 120x90 grey image.
        const useHq = () => {
            placeholder.style.backgroundImage = "url('https://img.youtube.com/vi/" + videoId + "/hqdefault.jpg')";
        };
        const probe = new Image();
        probe.addEventListener("load", () => {
            if (probe.naturalWidth <= 120) {
                useHq();
                return;
            }
            placeholder.style.backgroundImage = "url('https://img.youtube.com/vi/" + videoId + "/maxresdefault.jpg')";
        });
        probe.addEventListener("error", useHq);
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
