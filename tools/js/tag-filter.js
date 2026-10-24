"use strict";

// Sort menu, search field, and reset button for the Tangents tag chips. The
// choice is kept in sessionStorage so it carries over to tag and pagination pages.

const TAG_FILTER_KEY = "tangentsTagFilter";
const TAG_SORT_DEFAULT = "count-desc";

function readTagFilter() {
    try {
        const stored = JSON.parse(sessionStorage.getItem(TAG_FILTER_KEY));
        if (stored && typeof stored.sort === "string" && typeof stored.search === "string") {
            return stored;
        }
    } catch (error) {
        console.warn("Tag filter settings could not be read:", error);
    }
    return { sort: TAG_SORT_DEFAULT, search: "" };
}

function saveTagFilter(settings) {
    try {
        sessionStorage.setItem(TAG_FILTER_KEY, JSON.stringify(settings));
    } catch (error) {
        console.warn("Tag filter settings could not be saved:", error);
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const tools = document.querySelector(".tag-tools");
    const list = document.querySelector(".tag-filter-list");
    if (!tools || !list) {
        return;
    }

    const sortMenu = document.getElementById("tag-sort");
    const searchField = document.getElementById("tag-search");
    const resetButton = tools.querySelector(".tag-reset");
    const emptyNote = document.querySelector(".tag-empty");
    const items = Array.from(list.querySelectorAll("li[data-tag]"));
    const indexUrl = list.querySelector("li:not([data-tag]) a").href;
    const onIndex = window.location.href.split(/[?#]/)[0] === indexUrl;
    const collator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });

    const byName = (first, second) => collator.compare(first.dataset.tag, second.dataset.tag);
    const byCount = (first, second) => Number(first.dataset.count) - Number(second.dataset.count);
    const comparers = {
        "count-desc": (first, second) => byCount(second, first) || byName(first, second),
        "count-asc": (first, second) => byCount(first, second) || byName(first, second),
        "name-asc": byName,
        "name-desc": (first, second) => byName(second, first),
    };

    const apply = () => {
        const settings = { sort: sortMenu.value, search: searchField.value };
        saveTagFilter(settings);

        items.sort(comparers[settings.sort]).forEach((item) => list.appendChild(item));

        const query = settings.search.trim().toLocaleLowerCase();
        let shown = 0;
        items.forEach((item) => {
            // The tag whose page this is stays visible whatever the search says.
            const matches = item.dataset.tag.toLocaleLowerCase().includes(query) || item.querySelector("a.active") !== null;
            item.hidden = !matches;
            if (matches) {
                shown += 1;
            }
        });
        emptyNote.hidden = shown > 0;
        resetButton.disabled = onIndex && settings.sort === TAG_SORT_DEFAULT && settings.search === "";
    };

    // Clearing also drops the selected tag, so anywhere but the first index page it returns there.
    const reset = () => {
        sortMenu.value = TAG_SORT_DEFAULT;
        searchField.value = "";
        apply();
        if (!onIndex) {
            window.location.href = indexUrl;
        }
    };

    const settings = readTagFilter();
    sortMenu.value = settings.sort in comparers ? settings.sort : TAG_SORT_DEFAULT;
    searchField.value = settings.search;
    tools.hidden = false;
    apply();

    sortMenu.addEventListener("change", apply);
    searchField.addEventListener("input", apply);
    resetButton.addEventListener("click", reset);
});
