// 前端 API 服务
// 所有数据请求统一从这里走，方便切换后端地址

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error')
    throw new Error(`API ${path} -> ${res.status}: ${text}`)
  }

  if (res.status === 204) return null
  return res.json()
}

// ─── 报告 API ───

export async function fetchReports() {
  return request('/reports')
}

export async function fetchReport(id) {
  return request(`/reports/${encodeURIComponent(id)}`)
}

export async function updateReport(id, data) {
  return request(`/reports/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// ─── 统计 API ───

export async function fetchStats() {
  return request('/stats')
}

// ─── 字典 API ───

export async function fetchQcItems() {
  return request('/qc-items')
}

export async function fetchSeverityMap() {
  return request('/severity-map')
}

// ─── 健康检查 ───

export async function healthCheck() {
  try {
    const res = await fetch(`${API_BASE}/stats`, { signal: AbortSignal.timeout(3000) })
    return res.ok
  } catch {
    return false
  }
}
