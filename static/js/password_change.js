const initPasswordChangeControls = (root = document) => {
    const scope = root.querySelectorAll ? root : document;
    const toggleButtons = scope.querySelectorAll("[data-password-toggle]");
    const newPasswordInput = document.getElementById("id_new_password");
    const confirmPasswordInput = document.getElementById("id_confirm_password");
    const matchStatus = document.getElementById("change-password-match-status");

    toggleButtons.forEach((button) => {
        if (button.dataset.toggleBound === "true") {
            return;
        }

        const input = document.getElementById(button.dataset.passwordToggle);
        if (!input) {
            return;
        }

        button.addEventListener("click", () => {
            const isHidden = input.type === "password";
            input.type = isHidden ? "text" : "password";
            button.textContent = isHidden ? "Hide" : "Show";
            button.setAttribute("aria-pressed", isHidden ? "true" : "false");
        });
        button.dataset.toggleBound = "true";
    });

    if (!newPasswordInput || !confirmPasswordInput || !matchStatus) {
        return;
    }
    if (confirmPasswordInput.dataset.changeMatchBound === "true") {
        return;
    }

    const updatePasswordMatch = () => {
        if (!confirmPasswordInput.value) {
            matchStatus.textContent = "";
            matchStatus.className = "mt-3 hidden text-sm font-semibold";
            return;
        }

        if (confirmPasswordInput.value === newPasswordInput.value) {
            matchStatus.textContent = "Password does match";
            matchStatus.className = "mt-3 text-sm font-semibold text-emerald-700";
            return;
        }

        matchStatus.textContent = "Password does not match";
        matchStatus.className = "mt-3 text-sm font-semibold text-rose-700";
    };

    newPasswordInput.addEventListener("input", updatePasswordMatch);
    confirmPasswordInput.addEventListener("input", updatePasswordMatch);
    confirmPasswordInput.dataset.changeMatchBound = "true";
    updatePasswordMatch();
};

document.addEventListener("DOMContentLoaded", () => {
    initPasswordChangeControls();
});

document.body.addEventListener("htmx:load", (event) => {
    initPasswordChangeControls(event.target);
});
