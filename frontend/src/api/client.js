const BASE_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '')
const API_KEY = import.meta.env.VITE_API_KEY || ''

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
      ...options.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export const api = {
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

  getWeather: () => request('/api/weather/'),
  getSummary: () => request('/api/summary/'),
}
