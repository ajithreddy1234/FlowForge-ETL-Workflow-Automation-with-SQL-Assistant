export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: {
          bg: '#0A0A0A',
          deep: '#060606',
          panel: '#171717',
          panel2: '#111111',
          elevated: '#1C1C1C',
        },
        accent: {
          DEFAULT: '#8B5CF6',
          hover: '#7C3AED',
          light: '#A78BFA',
        },
      },
      fontFamily: {
        sans: ['"Plus Jakarta Sans"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        'glow-accent': '0 0 0 1px rgba(139, 92, 246, 0.4), 0 0 24px rgba(139, 92, 246, 0.35)',
        'glow-accent-sm': '0 0 0 1px rgba(139, 92, 246, 0.35), 0 0 12px rgba(139, 92, 246, 0.25)',
        'glow-success': '0 0 0 1px rgba(16, 185, 129, 0.4), 0 0 16px rgba(16, 185, 129, 0.25)',
        'glow-error': '0 0 0 1px rgba(239, 68, 68, 0.4), 0 0 16px rgba(239, 68, 68, 0.25)',
      },
      backdropBlur: {
        void: '32px',
      },
      keyframes: {
        'fade-up': {
          '0%': { opacity: 0, transform: 'translateY(12px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'pulse-glow': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.55 },
        },
        'dash-flow': {
          to: { strokeDashoffset: -24 },
        },
        blink: {
          '0%, 49%': { opacity: 1 },
          '50%, 100%': { opacity: 0 },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-6px)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.5s ease-out both',
        'pulse-glow': 'pulse-glow 1.8s ease-in-out infinite',
        'dash-flow': 'dash-flow 1s linear infinite',
        blink: 'blink 1s step-start infinite',
        float: 'float 4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
