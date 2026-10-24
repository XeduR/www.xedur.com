"use strict";
document.addEventListener("DOMContentLoaded", () => {
document.querySelectorAll(".page-jump-input").forEach((input) => {
const current = Number(input.dataset.current);
const total = Number(input.dataset.total);
const firstPage = input.dataset.first;
let leaving = false;
const restore = () => {
input.value = String(current);
};
const commit = () => {
if (leaving) {
return;
}
const typed = input.value.trim();
if (!/^[0-9]+$/.test(typed) || Number(typed) < 1) {
restore();
return;
}
const target = Math.min(Number(typed), total);
input.value = String(target);
if (target !== current) {
leaving = true;
window.location.href = target === 1 ? firstPage : firstPage + target + "/";
}
};
input.addEventListener("focus", () => {
input.select();
});
input.addEventListener("keydown", (event) => {
if (event.key === "Enter") {
event.preventDefault();
commit();
} else if (event.key === "Escape") {
restore();
input.blur();
}
});
input.addEventListener("blur", commit);
window.addEventListener("pageshow", (event) => {
if (event.persisted) {
leaving = false;
restore();
}
});
});
});