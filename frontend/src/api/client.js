// Panel backend ile aynı adreste yayınlandığı için yol göreli: /api/...
// Kimlik doğrulama HttpOnly çerezle yapılır — JS paketinde gizli anahtar YOKTUR.
const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')

/** Oturum düştüğünde App'in giriş ekranına dönmesi için yayınlanan olay */
export const UNAUTHORIZED_EVENT = 'prism:unauthorized'

export class AuthError extends Error {
  constructor(message = 'Oturum sona erdi, tekrar giriş yap') {
    super(message)
    this.name = 'AuthError'
  }
}

/**
 * Üstteki geçiş menüsüyle seçilen kişi (null = kendisi).
 *
 * Sadece GET isteklerine `?kisi=` olarak ekleniyor. Yazma isteklerine BİLEREK
 * eklenmiyor: yazma her zaman giriş yapan kişinin kendi verisine gider, sunucu
 * da başkasınınkine dokunmayı 403 ile reddediyor. Parametreyi yazmaya da
 * taşısaydık "başkası adına kaydet" diye bir şey uydurmuş olurduk.
 */
let bakilanKisi = null

export function setBakilanKisi(id) {
  bakilanKisi = id ?? null
}

function kisiEkle(path) {
  if (bakilanKisi == null || path.startsWith('/api/auth/')) return path
  return `${path}${path.includes('?') ? '&' : '?'}kisi=${bakilanKisi}`
}

async function request(path, options = {}) {
  const yontem = (options.method || 'GET').toUpperCase()
  if (yontem === 'GET') path = kisiEkle(path)

  const res = await fetch(`${BASE_URL}${path}`, {
    credentials: 'same-origin', // oturum çerezi gitsin
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (res.status === 401) {
    // Giriş uçlarında 401 "parola yanlış" demek — orada giriş ekranına atmaya gerek yok
    if (!path.startsWith('/api/auth/')) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
    }
    const err = await res.json().catch(() => ({}))
    throw new AuthError(err.detail || undefined)
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
  // ── Oturum ──────────────────────────────────────────────────────────────
  me: () => request('/api/auth/me'),
  login: (password) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  konumBildir: (enlem, boylam) =>
    request('/api/auth/konum', { method: 'POST', body: JSON.stringify({ enlem, boylam }) }),

  getReminders: (includeCompleted = false) =>
    request(`/api/reminders/?include_completed=${includeCompleted}`),
  createReminder: (data) =>
    request('/api/reminders/', { method: 'POST', body: JSON.stringify(data) }),
  completeReminder: (id) =>
    request(`/api/reminders/${id}/complete`, { method: 'PUT' }),
  snoozeReminder: (id, minutes) =>
    request(`/api/reminders/${id}/snooze/${minutes}`, { method: 'PUT' }),
  updateReminder: (id, data) =>
    request(`/api/reminders/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteReminder: (id) =>
    request(`/api/reminders/${id}`, { method: 'DELETE' }),

  getNotes: (category) =>
    request(`/api/notes/${category ? `?category=${encodeURIComponent(category)}` : ''}`),
  searchNotes: (q, category) =>
    request(`/api/notes/search?q=${encodeURIComponent(q)}${category ? `&category=${encodeURIComponent(category)}` : ''}`),
  updateNote: (id, data) =>
    request(`/api/notes/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  createNote: (data) =>
    request('/api/notes/', { method: 'POST', body: JSON.stringify(data) }),
  deleteNote: (id) =>
    request(`/api/notes/${id}`, { method: 'DELETE' }),

  getExpenses: (month, category) => {
    const p = new URLSearchParams()
    if (month) p.set('month', month)
    if (category) p.set('category', category)
    const qs = p.toString()
    return request(`/api/expenses/${qs ? `?${qs}` : ''}`)
  },
  getExpenseSummary: (month) =>
    request(`/api/expenses/summary${month ? `?month=${month}` : ''}`),
  createExpense: (data) =>
    request('/api/expenses/', { method: 'POST', body: JSON.stringify(data) }),
  deleteExpense: (id) =>
    request(`/api/expenses/${id}`, { method: 'DELETE' }),

  getBudgets: () => request('/api/budget/'),
  setBudget: (data) =>
    request('/api/budget/', { method: 'PUT', body: JSON.stringify(data) }),
  deleteBudget: (category) =>
    request(`/api/budget/${encodeURIComponent(category)}`, { method: 'DELETE' }),

  // Sohbet: yanıt gövdesi FormData olduğu için Content-Type'ı tarayıcı koysun
  // (sınır dizesini o üretiyor) — bu yüzden request() değil doğrudan fetch.
  sohbet: (message) =>
    request('/api/chat/', { method: 'POST', body: JSON.stringify({ message }) }),
  sohbetGorsel: async (dosya, message = '') => {
    const fd = new FormData()
    fd.append('file', dosya)
    fd.append('message', message)
    const res = await fetch(`${BASE_URL}/api/chat/image`, {
      method: 'POST', credentials: 'same-origin', body: fd,
    })
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || `HTTP ${res.status}`)
    }
    return res.json()
  },

  // Seslendirme: gövde JSON değil ses dosyası, o yüzden request() değil fetch.
  // Dönen adresi çağıran taraf URL.revokeObjectURL ile bırakmalı, yoksa
  // her dinlemede bir blob bellekte kalır.
  seslendir: async (metin) => {
    const res = await fetch(`${BASE_URL}/api/chat/ses`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ metin }),
    })
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent(UNAUTHORIZED_EVENT))
      throw new AuthError()
    }
    if (!res.ok) {
      const e = await res.json().catch(() => ({}))
      throw new Error(e.detail || `HTTP ${res.status}`)
    }
    return URL.createObjectURL(await res.blob())
  },

  getWeather: () => request('/api/weather/'),
  getSummary: () => request('/api/summary/'),
}
