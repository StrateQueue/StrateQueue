/******************************
 * TailwindCSS config for StrateQueue Web UI
 ******************************/
module.exports = {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {},
  },
  plugins: [require('tailwindcss-animate')],
}; 