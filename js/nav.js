$(function() {
    $("a").on('click', function(event) {
        // TODO: If links are clicked from a subpage, then they don't have offset.
        if (this.hash !== "" && window.location.href === "https://www.xedur.com/") {
            event.preventDefault();
            var hash = this.hash;
            $('html, body').animate({
                scrollTop: $(hash).offset().top-100
            }, 300, function(){
                window.location.hash = hash-100;
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
    if ($(".item").hasClass("active")) {
        $(".item").removeClass("active");
    } else {
        $(".item").addClass("active");
    }
}