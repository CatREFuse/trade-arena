import { shallowRef, readonly } from 'vue'

interface ToastMessage {
  id: number
  message: string
  duration: number
}

const toasts = shallowRef<ToastMessage[]>([])
let toastId = 0

export function useToast() {
  function showToast(message: string, duration = 2000) {
    const id = ++toastId
    const toast: ToastMessage = { id, message, duration }

    toasts.value = [...toasts.value, toast]

    window.setTimeout(() => {
      toasts.value = toasts.value.filter(t => t.id !== id)
    }, duration)
  }

  return {
    toasts: readonly(toasts),
    showToast,
  }
}

export function useToastState() {
  return {
    toasts: readonly(toasts),
  }
}
