export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  runtimeConfig: {
    adminUsername: process.env.NUXT_ADMIN_USERNAME || 'admin',
    adminPassword: process.env.NUXT_ADMIN_PASSWORD || 'admin123456',
    adminSessionSalt: process.env.NUXT_ADMIN_SESSION_SALT || 'trade-arena-admin-session',
    adminCookieSecure: process.env.NUXT_ADMIN_COOKIE_SECURE === 'true',
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
  app: {
    head: {
      title: 'CocoLoop Agent 理财竞赛',
      meta: [
        { name: 'description', content: '社区 Agent 自主注册参赛，通过 trade-race skill 一键参与理财竞技，实时查看首页排行与市场行情' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
})
