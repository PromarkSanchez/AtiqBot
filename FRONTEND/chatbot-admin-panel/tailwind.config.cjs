// tailwind.config.js o tailwind.config.cjs
module.exports = {
  darkMode: 'media', // o 'class' si quieres controlarlo manualmente con JS
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      animation: {
        'spin-slow': 'spin 3s linear infinite',
      }
    },
  },
  plugins: [],
}