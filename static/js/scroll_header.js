(function () {
    const header = document.querySelector("[data-scroll-header]");

    if (!header) {
        return;
    }

    let lastScrollY = window.scrollY;
    let ticking = false;
    const minimumDelta = 8;

    function updateHeader() {
        const currentScrollY = Math.max(window.scrollY, 0);
        const delta = currentScrollY - lastScrollY;

        if (currentScrollY <= 0) {
            header.classList.remove("app-scroll-header--hidden");
            lastScrollY = 0;
            ticking = false;
            return;
        }

        if (Math.abs(delta) < minimumDelta) {
            ticking = false;
            return;
        }

        if (delta > 0 && currentScrollY > header.offsetHeight) {
            header.classList.add("app-scroll-header--hidden");
        } else {
            header.classList.remove("app-scroll-header--hidden");
        }

        lastScrollY = currentScrollY;
        ticking = false;
    }

    window.addEventListener("scroll", function () {
        if (!ticking) {
            window.requestAnimationFrame(updateHeader);
            ticking = true;
        }
    }, { passive: true });
})();
