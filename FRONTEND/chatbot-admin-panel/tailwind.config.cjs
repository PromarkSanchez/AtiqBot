// Archivo: tailwind.config.cjs
module.exports = {
  darkMode: 'class', // <--- Clave: Usar 'class' nos da control total.
  content: [
    "./index.html",
    "./chatbot.html",
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