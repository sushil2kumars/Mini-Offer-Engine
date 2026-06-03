/** @type {import('tailwindcss').Config} */
const plugin = require('tailwindcss/plugin');

module.exports = {
    content: [
        './looplink/**/*.{js,jsx,ts,tsx}',
        './looplink/**/*.html',
    ],
    theme: {
        extend: {},
    },
}
