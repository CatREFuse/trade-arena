/** @type {import('tailwindcss').Config} */
export default {
  content: [],
  theme: {
    extend: {
      colors: {
        arena: {
          bg: '#080b12',
          surface: '#0d1117',
          card: '#151b23',
          'card-hover': '#1c2433',
          border: '#21262d',
          'border-light': '#30363d',
          green: '#3fb950',
          'green-dim': '#122117',
          red: '#f85149',
          'red-dim': '#2d1215',
          blue: '#58a6ff',
          'blue-dim': '#0c2d6b',
          gold: '#e3b341',
          purple: '#bc8cff',
          'purple-dim': '#1b1230',
        },
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.4s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
}
