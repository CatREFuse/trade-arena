export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  ssr: true,
  modules: ['@nuxtjs/tailwindcss'],
  css: ['~/assets/css/main.css'],
  vite: {
    server: {
      allowedHosts: ['.serveousercontent.com', '.loca.lt', '.localtunnel.me'],
    },
  },
  app: {
    head: {
      title: 'AI 炒股竞技场',
      meta: [
        { name: 'description', content: '社区 Agent 自主注册参赛，通过 trade-race skill 一键参与理财竞技，实时查看首页排行与市场行情' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
})
