import axios from 'axios'

export function getApiErrorMessage(error: unknown, fallback = 'Something went wrong. Please try again.') {
  if (!axios.isAxiosError(error)) {
    return fallback
  }

  if (!error.response) {
    return error.message || fallback
  }

  const detail = error.response.data?.detail

  if (typeof detail === 'string') {
    return detail
  }

  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item?.msg === 'string' ? item.msg : null))
      .filter(Boolean)
      .join('. ')
  }

  return fallback
}
