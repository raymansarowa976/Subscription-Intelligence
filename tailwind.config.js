/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./users/**/*.py",
    "./subscriptions/**/*.py",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#1d1b19",
        sand: "#f4efe7",
        clay: "#c96f3b",
        pine: "#0e5a52",
        pineDeep: "#0a403a",
      },
      fontFamily: {
        sans: ["Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 24px 60px rgba(48, 38, 26, 0.14)",
      },
    },
  },
  plugins: [
    require("@tailwindcss/forms"),
    require("@tailwindcss/typography"),
  ],
};
