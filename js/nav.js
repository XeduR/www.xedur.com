$(function() {
    $("a").on('click', function(event) {
        if (this.hash !== "") {
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
    if ($(".item").hasClass("active")) {
        $(".item").removeClass("active");
    } else {
        $(".item").addClass("active");
    }
}