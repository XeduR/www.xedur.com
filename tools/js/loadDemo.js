window.addEventListener("load", function() {
    document.getElementById("startButton").addEventListener("click", function() {
        var button = this;
        var overlay = document.getElementById("loadOverlay");

        // Created on click: browsers restore a static iframe's last URL on reload or Back, which would start the app unasked.
        var iframe = document.createElement("iframe");
        iframe.id = "app";
        iframe.addEventListener("load", function() {
            button.style.display = "none";
            if (overlay) overlay.style.display = "none";
        });
        iframe.src = "./app/index.html";
        document.getElementById("frame").prepend(iframe);
    }, { once: true });
});
