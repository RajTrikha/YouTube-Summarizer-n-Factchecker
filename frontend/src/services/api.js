const API_BASE_URL = "http://127.0.0.1:8000"

async function parseJsonOrThrow(response, fallbackMessage) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    const message = body?.detail || fallbackMessage
    throw new Error(message)
  }
  return response.json()
}

export async function getItemsLanes({ q = "", limit = 90, cursor = null } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q.trim()) params.set("q", q.trim())
  if (cursor) params.set("cursor", cursor)

  const response = await fetch(`${API_BASE_URL}/items/lanes?${params.toString()}`)
  return parseJsonOrThrow(response, "Unable to load lane items")
}

export async function getItems({ q = "", mediaType = "", limit = 100 } = {}) {
  const params = new URLSearchParams({ limit: String(limit) })
  if (q.trim()) params.set("q", q.trim())
  if (mediaType) params.set("media_type", mediaType)

  const response = await fetch(`${API_BASE_URL}/items?${params.toString()}`)
  return parseJsonOrThrow(response, "Unable to load items")
}

export async function getTaskStatus(taskId) {
  const response = await fetch(`${API_BASE_URL}/status/${taskId}`)
  return parseJsonOrThrow(response, "Unable to load task status")
}

export async function uploadSource(file) {
  const uploadData = new FormData()
  uploadData.append("file", file)

  const response = await fetch(`${API_BASE_URL}/uploads`, {
    method: "POST",
    body: uploadData,
  })
  return parseJsonOrThrow(response, "Upload failed")
}

export async function ingestSource(payload) {
  const response = await fetch(`${API_BASE_URL}/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  return parseJsonOrThrow(response, "Ingestion failed")
}

export async function patchItem(itemId, patch) {
  const response = await fetch(`${API_BASE_URL}/items/${itemId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  })
  return parseJsonOrThrow(response, "Unable to update item")
}

export async function queryMemory(query, limit = 5) {
  const response = await fetch(`${API_BASE_URL}/memory/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit }),
  })
  return parseJsonOrThrow(response, "Memory query failed")
}

export async function getIntegrationProviders() {
  const response = await fetch(`${API_BASE_URL}/integrations/providers`)
  return parseJsonOrThrow(response, "Unable to load integrations")
}

export async function connectReadwise(accessToken) {
  const response = await fetch(`${API_BASE_URL}/integrations/readwise/connect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ access_token: accessToken }),
  })
  return parseJsonOrThrow(response, "Readwise connection failed")
}

export async function startReadwiseSync({ mode, updatedAfter = null }) {
  const response = await fetch(`${API_BASE_URL}/integrations/readwise/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      mode,
      updated_after: updatedAfter,
    }),
  })
  return parseJsonOrThrow(response, "Readwise sync failed to start")
}

export async function getSyncJobStatus(jobId) {
  const response = await fetch(`${API_BASE_URL}/integrations/sync-jobs/${jobId}`)
  return parseJsonOrThrow(response, "Unable to read sync status")
}
