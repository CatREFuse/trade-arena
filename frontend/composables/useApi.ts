export function useApi() {
  const fetchApi = async <T>(path: string, options?: any): Promise<T> => {
    const data = await $fetch<T>(path, {
      ...options,
    })
    return data
  }

  return { fetchApi }
}
