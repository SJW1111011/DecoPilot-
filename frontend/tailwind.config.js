/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // 业主模式 - 优雅蓝色系
        owner: {
          50: '#f0f7ff',
          100: '#e0efff',
          200: '#b9dfff',
          300: '#7cc4ff',
          400: '#36a5ff',
          500: '#0c87f2',
          600: '#0068cf',
          700: '#0052a7',
          800: '#04468a',
          900: '#0a3c72',
          950: '#07254b',
        },
        // 商家模式 - 翡翠绿色系
        merchant: {
          50: '#edfcf5',
          100: '#d4f7e6',
          200: '#aceed1',
          300: '#76dfb6',
          400: '#3ec896',
          500: '#1aad7c',
          600: '#0d8c64',
          700: '#0b7053',
          800: '#0c5943',
          900: '#0b4938',
          950: '#052920',
        },
        // 思考过程 - 柔和紫色系
        thinking: {
          50: '#faf5ff',
          100: '#f3e8ff',
          200: '#e9d5ff',
          300: '#d8b4fe',
          400: '#c084fc',
          500: '#a855f7',
          600: '#9333ea',
          700: '#7c3aed',
        },
        // 界面中性色
        slate: {
          25: '#fcfcfd',
          50: '#f8fafc',
          100: '#f1f5f9',
          150: '#e9eef4',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          'PingFang SC',
          'Microsoft YaHei',
          'system-ui',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'sans-serif',
        ],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.625rem', { lineHeight: '0.875rem' }],
      },
      spacing: {
        '4.5': '1.125rem',
        '13': '3.25rem',
        '15': '3.75rem',
        '18': '4.5rem',
        '22': '5.5rem',
        '68': '17rem',
      },
      borderRadius: {
        '4xl': '2rem',
        '5xl': '2.5rem',
      },
      boxShadow: {
        'xs': '0 1px 2px 0 rgb(0 0 0 / 0.03)',
        'soft': '0 2px 8px -2px rgb(0 0 0 / 0.05), 0 4px 12px -4px rgb(0 0 0 / 0.05)',
        'soft-md': '0 4px 16px -4px rgb(0 0 0 / 0.08), 0 8px 24px -8px rgb(0 0 0 / 0.06)',
        'soft-lg': '0 8px 32px -8px rgb(0 0 0 / 0.1), 0 16px 48px -16px rgb(0 0 0 / 0.08)',
        'soft-xl': '0 16px 48px -12px rgb(0 0 0 / 0.12), 0 24px 64px -24px rgb(0 0 0 / 0.1)',
        'inner-soft': 'inset 0 2px 4px 0 rgb(0 0 0 / 0.03)',
        // 新增浮动阴影系统
        'float': '0 2px 12px -3px rgb(0 0 0 / 0.08), 0 1px 4px -2px rgb(0 0 0 / 0.04)',
        'float-md': '0 4px 20px -4px rgb(0 0 0 / 0.1), 0 2px 8px -3px rgb(0 0 0 / 0.06)',
        'float-lg': '0 8px 32px -6px rgb(0 0 0 / 0.12), 0 4px 16px -4px rgb(0 0 0 / 0.08)',
        'input-focus': '0 0 0 3px rgb(12 135 242 / 0.08), 0 2px 12px -3px rgb(0 0 0 / 0.06)',
        'input-focus-merchant': '0 0 0 3px rgb(26 173 124 / 0.08), 0 2px 12px -3px rgb(0 0 0 / 0.06)',
        'glow-owner': '0 0 24px -4px rgb(12 135 242 / 0.25)',
        'glow-owner-lg': '0 0 40px -8px rgb(12 135 242 / 0.35)',
        'glow-merchant': '0 0 24px -4px rgb(26 173 124 / 0.25)',
        'glow-merchant-lg': '0 0 40px -8px rgb(26 173 124 / 0.35)',
        'glow-thinking': '0 0 24px -4px rgb(168 85 247 / 0.25)',
        'ring': '0 0 0 3px rgb(12 135 242 / 0.1)',
        'ring-merchant': '0 0 0 3px rgb(26 173 124 / 0.1)',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'gradient-conic': 'conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))',
        'mesh-owner': 'radial-gradient(at 40% 20%, rgb(12 135 242 / 0.08) 0px, transparent 50%), radial-gradient(at 80% 0%, rgb(12 135 242 / 0.06) 0px, transparent 50%), radial-gradient(at 0% 50%, rgb(12 135 242 / 0.04) 0px, transparent 50%)',
        'mesh-merchant': 'radial-gradient(at 40% 20%, rgb(26 173 124 / 0.08) 0px, transparent 50%), radial-gradient(at 80% 0%, rgb(26 173 124 / 0.06) 0px, transparent 50%), radial-gradient(at 0% 50%, rgb(26 173 124 / 0.04) 0px, transparent 50%)',
        'shimmer': 'linear-gradient(90deg, transparent 0%, rgb(255 255 255 / 0.4) 50%, transparent 100%)',
        // 欢迎页渐变
        'welcome-owner': 'linear-gradient(135deg, rgb(12 135 242 / 0.06) 0%, rgb(12 135 242 / 0.02) 50%, transparent 100%)',
        'welcome-merchant': 'linear-gradient(135deg, rgb(26 173 124 / 0.06) 0%, rgb(26 173 124 / 0.02) 50%, transparent 100%)',
        // 底部渐变遮罩
        'fade-bottom': 'linear-gradient(to top, rgb(248 250 252) 0%, transparent 100%)',
        'fade-bottom-white': 'linear-gradient(to top, white 0%, transparent 100%)',
      },
      animation: {
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in-up': 'fadeInUp 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'fade-in-down': 'fadeInDown 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-left': 'slideInLeft 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-in-right': 'slideInRight 0.5s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up': 'slideUp 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in-bounce': 'scaleInBounce 0.6s cubic-bezier(0.34, 1.56, 0.64, 1)',
        'pulse-soft': 'pulseSoft 2.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'shimmer': 'shimmer 2s linear infinite',
        'typing-1': 'typing 1.4s ease-in-out infinite',
        'typing-2': 'typing 1.4s ease-in-out 0.2s infinite',
        'typing-3': 'typing 1.4s ease-in-out 0.4s infinite',
        'spin-slow': 'spin 3s linear infinite',
        'float': 'float 6s ease-in-out infinite',
        'expand': 'expand 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
        'collapse': 'collapse 0.3s cubic-bezier(0.16, 1, 0.3, 1)',
        // 新增消息动画
        'message-in': 'messageIn 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-up-fade': 'slideUpFade 0.4s cubic-bezier(0.16, 1, 0.3, 1)',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        fadeInDown: {
          '0%': { opacity: '0', transform: 'translateY(-16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-24px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideInRight: {
          '0%': { opacity: '0', transform: 'translateX(24px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.95)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        scaleInBounce: {
          '0%': { opacity: '0', transform: 'scale(0.8)' },
          '50%': { transform: 'scale(1.02)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
        pulseSoft: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.6' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
        typing: {
          '0%, 60%, 100%': { transform: 'translateY(0)', opacity: '0.4' },
          '30%': { transform: 'translateY(-6px)', opacity: '1' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        expand: {
          '0%': { opacity: '0', height: '0', paddingTop: '0', paddingBottom: '0' },
          '100%': { opacity: '1', height: 'var(--expand-height, auto)' },
        },
        collapse: {
          '0%': { opacity: '1', height: 'var(--expand-height, auto)' },
          '100%': { opacity: '0', height: '0', paddingTop: '0', paddingBottom: '0' },
        },
        // 新增消息进入动画
        messageIn: {
          '0%': { opacity: '0', transform: 'translateY(8px) scale(0.98)' },
          '100%': { opacity: '1', transform: 'translateY(0) scale(1)' },
        },
        slideUpFade: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      transitionTimingFunction: {
        'smooth': 'cubic-bezier(0.16, 1, 0.3, 1)',
        'bounce': 'cubic-bezier(0.34, 1.56, 0.64, 1)',
      },
      transitionDuration: {
        '250': '250ms',
        '350': '350ms',
        '400': '400ms',
      },
    },
  },
  plugins: [],
}
