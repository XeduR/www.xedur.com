$(function() {
    $("a").on('click', function(event) {
        // Only use smooth scroll on the front page.
        if (this.hash !== "" && window.location.pathname == "/") {
            event.preventDefault();
            var target = this.hash,
            $target = $(target);
            
            $('html, body').animate({
                scrollTop: $target.offset().top
            }, 300, function(){
                window.location.hash = target;
            });
        }
    });
});

$(function() {
    $(".toggle").on("click", function() {
        toggleMobileNav();
    });
});

$(function() {
    $(".item").on("click", function() {
        if (window.innerWidth < 420) {
            toggleMobileNav();
        }
    });
});

function toggleMobileNav() {
    $(".bar1").toggleClass("bar1-active");
    $(".bar2").toggleClass("bar2-active");
    $(".bar3").toggleClass("bar3-active");
    $(".item").toggleClass("active");
    event.stopPropagation()
}