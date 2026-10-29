var CONTACT_ID = "contact";
var FLASH_CLASS = "contact-flash";

// Speed of the scroll to the contact panel: milliseconds per square root of the distance in pixels, and the longest one scroll may take.
var SEEK_MS_PER_ROOT_PX = 10;
var SEEK_MAX_MS = 900;

// Visitor input and history moves that take the scroll back from a seek.
var SEEK_CANCEL_EVENTS = ["wheel", "touchstart", "pointerdown", "keydown", "popstate"];

var cancelSeek = null;

document.addEventListener("DOMContentLoaded", function() {
    var contactAnchor = document.getElementById(CONTACT_ID);

    document.querySelectorAll("a").forEach(function(link) {
        link.addEventListener("click", function(event) {
            // Skip heading-link elements (handled separately for clipboard copy).
            if (this.classList.contains("heading-link")) return;
            // Use smooth scroll if the anchor target exists on the current page.
            if (this.hash !== "" && this.origin === location.origin && pagePath(this.pathname) === pagePath(location.pathname)) {
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

        // A Contact link from another page lands and flashes the same way; reloads and Back keep their restored position.
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
            // The mobile nav is only displayed below the CSS breakpoint.
            if (getComputedStyle(document.getElementById("mobile-nav")).display !== "none") {
                toggleMobileNav(event);
            }
        });
    });
});

// The query string and a trailing index.html still address the same page.
function pagePath(pathname) {
    return pathname.replace(/index\.html$/, "");
}

function scrollBehavior() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

// The contact panel always closes the page, so the page end shows all of it.
// A panel taller than the space under the nav stops at its anchor instead, which keeps the heading in view.
function showContactPanel(anchor) {
    var panel = anchor.closest("section");
    var root = document.scrollingElement;

    function targetY() {
        return Math.min(root.scrollHeight - window.innerHeight, anchor.getBoundingClientRect().top + window.scrollY);
    }

    seekScroll(targetY, function() {
        panel.classList.remove(FLASH_CLASS);
        // Reading layout between the two class changes restarts a flash that is still playing.
        void panel.offsetWidth;
        panel.classList.add(FLASH_CLASS);
    });
}

// Lazy images can grow the page during and after the scroll, which a native smooth scroll misses or answers by restarting from rest.
// Each target move eases in here on top of the motion so far, and the page stays on target until the visitor takes over.
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

        // Scroll anchoring has already moved the view for growth above it, so that part needs no scrolling.
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
    var open = document.querySelector(".bar1").classList.toggle("bar1-active");
    document.querySelector(".toggle button").setAttribute("aria-expanded", String(open));
    document.querySelector(".bar2").classList.toggle("bar2-active");
    document.querySelector(".bar3").classList.toggle("bar3-active");
    document.querySelectorAll(".item").forEach(function(item) {
        item.classList.toggle("active");
    });
    event.stopPropagation();
}