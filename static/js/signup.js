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
                label: "Enter a password",
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

document.body.addEventListener("htmx:load", (event) => {
    initPasswordStrength(event.target);
});
