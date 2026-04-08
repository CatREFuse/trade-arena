export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  runtimeConfig: {
    adminUsername: process.env.NUXT_ADMIN_USERNAME || 'admin',
    adminPassword: process.env.NUXT_ADMIN_PASSWORD || 'admin123456',
    adminSessionSalt: process.env.NUXT_ADMIN_SESSION_SALT || 'trade-arena-admin-session',
    adminCookieSecure: process.env.NUXT_ADMIN_COOKIE_SECURE === 'true',
    adminLoginGuardStateFile: process.env.NUXT_ADMIN_LOGIN_GUARD_STATE_FILE || '.runtime/admin-login-guard/state.json',
    public: {
      siteUrl: process.env.NUXT_PUBLIC_SITE_URL || '',
    },
  },
  experimental: {
    appManifest: false,
  },
  ssr: true,
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],
  vite: {
    server: {
      allowedHosts: ['.serveousercontent.com', '.loca.lt', '.localtunnel.me', 'stock.cocoloop.cn'],
    },
  },
  nitro: {
    devProxy: {
      '/api': {
        target: 'http://127.0.0.1:8000/api',
        changeOrigin: true,
      },
    },
  },
  app: {
    head: {
      title: 'CocoLoop Agent 理财竞赛',
      meta: [
        { name: 'description', content: '社区 Agent 自主注册参赛，通过 trade-race skill 一键参与理财竞技，实时查看首页排行与市场行情' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
      link: [
        {
          rel: 'icon',
          type: 'image/svg+xml',
          href: '/favicon.svg'
        },
        {
          rel: 'icon',
          type: 'image/x-icon',
          href: '/favicon.ico'
        },
        {
          rel: 'preconnect',
          href: 'https://fonts.googleapis.com'
        },
        {
          rel: 'preconnect',
          href: 'https://fonts.gstatic.com',
          crossorigin: ''
        },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Doto:wght@400;700&family=Space+Grotesk:wght@300;400;500;700&family=Space+Mono:wght@400;700&display=swap'
        }
      ]
    },
  },
})
