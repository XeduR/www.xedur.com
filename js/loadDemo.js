$("button").click(function() {
    const $iframe = $("#app");
    const $but = $(this);
    $iframe.on("load",function() {
        $but.hide();
    });
    $iframe.attr( "src", "./app/index.html" );
});