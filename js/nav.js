document.addEventListener("DOMContentLoaded", function() {
document.querySelectorAll("a").forEach(function(link) {
link.addEventListener("click", function(event) {
if (this.classList.contains("heading-link")) return;
if (this.hash !== "") {
var target = document.querySelector(this.hash);
if (target) {
event.preventDefault();
var hash = this.hash;
target.scrollIntoView({ behavior: "smooth" });
history.pushState(null, "", hash);
}
}
});
});
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
if (window.innerWidth < 420) {
toggleMobileNav(event);
}
});
});
});
function toggleMobileNav(event) {
document.querySelector(".bar1").classList.toggle("bar1-active");
document.querySelector(".bar2").classList.toggle("bar2-active");
document.querySelector(".bar3").classList.toggle("bar3-active");
document.querySelectorAll(".item").forEach(function(item) {
item.classList.toggle("active");
});
event.stopPropagation();
}