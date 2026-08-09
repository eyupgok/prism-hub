/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        // Başlıklar için geometrik sans — index.css'te h1/h2/h3'e otomatik uygulanır,
        // başka yerde istersen font-display sınıfıyla çağır
        display: ['Space Grotesk', 'Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
