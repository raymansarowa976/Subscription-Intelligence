const initPasswordStrength = (root = document) => {
    const passwordInput = root.getElementById
        ? root.getElementById("id_password")
        : document.getElementById("id_password");
    const confirmPasswordInput = root.getElementById
        ? root.getElementById("id_confirm_password")
        : document.getElementById("id_confirm_password");
    const strengthBar = document.getElementById("password-strength-bar");
    const strengthLabel = document.getElementById("password-strength-label");
    const confirmPasswordStatus = document.getElementById("confirm-password-status");
    const requirementNodes = {
        length: document.querySelector("[data-password-rule='length']"),
        lowercase: document.querySelector("[data-password-rule='lowercase']"),
        uppercase: document.querySelector("[data-password-rule='uppercase']"),
        number: document.querySelector("[data-password-rule='number']"),
        symbol: document.querySelector("[data-password-rule='symbol']"),
    };

    if (!passwordInput || !strengthBar || !strengthLabel || passwordInput.dataset.strengthBound === "true") {
        return;
    }
    passwordInput.dataset.strengthBound = "true";

    const rules = {
        length: (value) => value.length >= 8,
        lowercase: (value) => /[a-z]/.test(value),
        uppercase: (value) => /[A-Z]/.test(value),
        number: (value) => /[0-9]/.test(value),
        symbol: (value) => /[!@#$%^&*(),.?":{}|<>]/.test(value),
    };

    const strengthState = (score, hasValue) => {
        if (!hasValue) {
            return {
                label: "",
                width: "0%",
                barClass: "bg-stone-200",
            };
        }
        if (score <= 2) {
            return {
                label: "Weak",
                width: "33%",
                barClass: "bg-rose-500",
            };
        }
        if (score <= 4) {
            return {
                label: "Medium",
                width: "66%",
                barClass: "bg-amber-500",
            };
        }
        return {
            label: "Strong",
            width: "100%",
            barClass: "bg-emerald-500",
        };
    };

    const updateStrength = () => {
        const value = passwordInput.value;
        const entries = Object.entries(rules);
        const score = entries.reduce((total, [key, validate]) => {
            const passed = validate(value);
            const node = requirementNodes[key];
            if (node) {
                node.classList.toggle("text-emerald-700", passed);
                node.classList.toggle("text-stone-500", !passed);
                node.classList.toggle("font-semibold", passed);
            }
            return total + (passed ? 1 : 0);
        }, 0);

        const state = strengthState(score, value.length > 0);
        strengthLabel.textContent = state.label;
        strengthBar.className = `h-2 rounded-full transition-all duration-300 ${state.barClass}`;
        strengthBar.style.width = state.width;
    };

    const updatePasswordMatch = () => {
        if (!confirmPasswordInput || !confirmPasswordStatus) {
            return;
        }

        if (!confirmPasswordInput.value) {
            confirmPasswordStatus.textContent = "";
            confirmPasswordStatus.className = "mt-3 hidden text-sm font-semibold";
            return;
        }

        if (confirmPasswordInput.value === passwordInput.value) {
            confirmPasswordStatus.textContent = "Password does match";
            confirmPasswordStatus.className = "mt-3 text-sm font-semibold text-emerald-700";
            return;
        }

        confirmPasswordStatus.textContent = "Password does not match";
        confirmPasswordStatus.className = "mt-3 text-sm font-semibold text-rose-700";
    };

    passwordInput.addEventListener("input", updateStrength);
    passwordInput.addEventListener("input", updatePasswordMatch);
    if (confirmPasswordInput && confirmPasswordInput.dataset.matchBound !== "true") {
        confirmPasswordInput.addEventListener("input", updatePasswordMatch);
        confirmPasswordInput.dataset.matchBound = "true";
    }
    updateStrength();
    updatePasswordMatch();
};

document.addEventListener("DOMContentLoaded", () => {
    initPasswordStrength();
});

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

document.body.addEventListener("htmx:load", (event) => {
    initPasswordStrength(event.target);
});
