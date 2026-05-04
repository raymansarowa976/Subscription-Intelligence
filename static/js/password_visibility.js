document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-password-toggle]");
    if (!button) {
        return;
    }

    const input = document.getElementById(button.dataset.passwordToggle);
    if (!input) {
        return;
    }

    const isHidden = input.type === "password";
    const baseLabel = button.getAttribute("aria-label") || "password";
    const fieldLabel = baseLabel.replace(/^Show\s+/i, "").replace(/^Hide\s+/i, "");
    const openIcon = button.querySelector("[data-eye-open]");
    const closedIcon = button.querySelector("[data-eye-closed]");

    input.type = isHidden ? "text" : "password";
    button.setAttribute("aria-pressed", isHidden ? "true" : "false");
    button.setAttribute("aria-label", `${isHidden ? "Hide" : "Show"} ${fieldLabel}`);
    if (openIcon && closedIcon) {
        openIcon.classList.toggle("hidden", isHidden);
        closedIcon.classList.toggle("hidden", !isHidden);
    }
});
