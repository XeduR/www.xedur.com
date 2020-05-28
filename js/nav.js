$(window).on("load", function(){
    console.log( "nav loaded" );
    $("a").on('click', function(event) {
        console.log( "nav clicked" );
        if (this.hash !== "") {
            event.preventDefault();
            var hash = this.hash;
            console.log( "nav hash: " + hash );
            $('html, body').animate({
                scrollTop: $(hash).offset().top-100
            }, 300, function(){
                window.location.hash = hash-100;
            });
        }
    });
});

function toggleMobileNav() {
    if ($("item").hasClass("active")) {
        $("item").removeClass("active");
    } else {
        $("item").addClass("active");
    }
}

$(function() {
    console.log( "toggle loaded" );
    $("toggle").on("click", function() {
        console.log( "toggle clicked" );
        toggleMobileNav();
    });
});

$(function() {
    $("item").on("click", function() {
        if (window.innerWidth < 420) {
            toggleMobileNav();
        }
    });
});