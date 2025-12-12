export function getCsrfToken() {
  const name = 'csrftoken='
  const cookies = document.cookie.split(';')
  for (let c of cookies) {
    c = c.trim()
    if (c.startsWith(name)) {
      return decodeURIComponent(c.substring(name.length))
    }
  }
  return null
}
