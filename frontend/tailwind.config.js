/** @type {import('tailwindcss').Config} */
export default {
  content: [],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        arena: {
          green: '#16a34a',
          'green-bg': '#f0fdf4',
          red: '#dc2626',
          'red-bg': '#fef2f2',
          blue: '#2563eb',
          'blue-bg': '#eff6ff',
          gold: '#ca8a04',
          purple: '#7c3aed',
          'purple-bg': '#f5f3ff',
        },
      },
      fontFamily: {
        sans: ['Inter', 'Noto Sans SC', 'system-ui', 'sans-serif'],
        mono: ['Fira Code', 'JetBrains Mono', 'monospace'],
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.5rem',
      },
    },
  },
}
