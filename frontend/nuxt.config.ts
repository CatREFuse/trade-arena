export default defineNuxtConfig({
  compatibilityDate: '2024-11-01',
  devtools: { enabled: true },
  ssr: true,
  modules: ['@nuxtjs/tailwindcss'],
  nitro: {
    devProxy: {
      '/api/': {
        target: 'http://localhost:8000/api/',
        changeOrigin: true,
      },
    },
  },
  routeRules: {
    '/api/**': { proxy: 'http://localhost:8000/api/**' },
  },
  app: {
    head: {
      title: 'AI 炒股竞技场',
      meta: [
        { name: 'description', content: '8 大顶级 AI 模型虚拟炒股对决，实时排名' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
      ],
    },
  },
})
