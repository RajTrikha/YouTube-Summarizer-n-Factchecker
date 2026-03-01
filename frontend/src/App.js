"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import "./App.css"

const API_BASE_URL = "http://127.0.0.1:8000"

const MEDIA_TYPES = [
  { value: "youtube_video", label: "YouTube Video", icon: "▶" },
  { value: "podcast_episode", label: "Podcast Episode", icon: "🎙" },
  { value: "web_article", label: "Web Article", icon: "📰" },
  { value: "pdf_document", label: "PDF / Document", icon: "📄" },
  { value: "book_highlights", label: "Book Highlights", icon: "📚" },
  { value: "social_thread", label: "Social Thread", icon: "💬" },
]

const INPUT_MODES = [
  { value: "url", label: "URL" },
  { value: "text", label: "Paste Text" },
  { value: "upload", label: "Upload File" },
]

const STATUS_LABELS = {
  ingested: "Ingested",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
}

function mediaMeta(type) {
  return MEDIA_TYPES.find((m) => m.value === type) || { label: type, icon: "•" }
}

function formatDateGroup(dateString) {
  if (!dateString) return "Recently"
  const date = new Date(dateString)
  const today = new Date()
  const yesterday = new Date(today)
  yesterday.setDate(today.getDate() - 1)

  if (date.toDateString() === today.toDateString()) return "Today"
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday"
  return date.toLocaleDateString()
}

function App() {
  const [items, setItems] = useState([])
  const [selectedItemId, setSelectedItemId] = useState(null)
  const [search, setSearch] = useState("")
  const [mediaFilter, setMediaFilter] = useState("all")
  const [loadingItems, setLoadingItems] = useState(false)
  const [error, setError] = useState(null)

  const [showAddModal, setShowAddModal] = useState(false)
  const [addSubmitting, setAddSubmitting] = useState(false)
  const [addForm, setAddForm] = useState({
    media_type: "youtube_video",
    input_mode: "url",
    title: "",
    author: "",
    url: "",
    raw_text: "",
  })
  const [addFile, setAddFile] = useState(null)

  const [memoryQuery, setMemoryQuery] = useState("")
  const [memoryLoading, setMemoryLoading] = useState(false)
  const [memoryResult, setMemoryResult] = useState(null)
  const [activeWorkspace, setActiveWorkspace] = useState("inbox")

  const selectedItem = useMemo(() => items.find((i) => i.id === selectedItemId) || null, [items, selectedItemId])

  const groupedItems = useMemo(() => {
    const filtered = items.filter((item) => {
      if (mediaFilter !== "all" && item.media_type !== mediaFilter) return false
      if (!search.trim()) return true
      const text = `${item.title || ""} ${item.author || ""} ${item.summary || ""}`.toLowerCase()
      return text.includes(search.toLowerCase())
    })

    return filtered.reduce((acc, item) => {
      const key = formatDateGroup(item.created_at || item.consumed_at)
      if (!acc[key]) acc[key] = []
      acc[key].push(item)
      return acc
    }, {})
  }, [items, mediaFilter, search])

  const groupOrder = useMemo(() => Object.keys(groupedItems), [groupedItems])

  const fetchItems = useCallback(async () => {
    setLoadingItems(true)
    try {
      const params = new URLSearchParams({ limit: "100" })
      if (mediaFilter !== "all") params.set("media_type", mediaFilter)
      if (search.trim()) params.set("q", search.trim())

      const res = await fetch(`${API_BASE_URL}/items?${params.toString()}`)
      if (!res.ok) throw new Error("Unable to load items")
      const data = await res.json()
      setItems(Array.isArray(data) ? data : [])
      setSelectedItemId((prev) => {
        if (prev) return prev
        if (Array.isArray(data) && data.length > 0) return data[0].id
        return prev
      })
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load items")
    } finally {
      setLoadingItems(false)
    }
  }, [mediaFilter, search])

  useEffect(() => {
    fetchItems()
    const timer = setInterval(fetchItems, 7000)
    return () => clearInterval(timer)
  }, [fetchItems])

  const pollTaskUntilDone = async (taskId) => {
    let attempts = 0
    const maxAttempts = 90

    while (attempts < maxAttempts) {
      attempts += 1
      try {
        const res = await fetch(`${API_BASE_URL}/status/${taskId}`)
        if (res.ok) {
          const data = await res.json()
          if (data.status === "SUCCESS" || data.status === "FAILURE") {
            await fetchItems()
            return
          }
        }
      } catch (_) {
        // Keep polling
      }
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => setTimeout(resolve, 2500))
    }
    await fetchItems()
  }

  const resetAddForm = () => {
    setAddForm({
      media_type: "youtube_video",
      input_mode: "url",
      title: "",
      author: "",
      url: "",
      raw_text: "",
    })
    setAddFile(null)
  }

  const submitAddSource = async (e) => {
    e.preventDefault()
    setAddSubmitting(true)
    setError(null)

    try {
      let metadata = {}
      let payload = {
        media_type: addForm.media_type,
        input_mode: addForm.input_mode,
        title: addForm.title || null,
        author: addForm.author || null,
        consumed_at: new Date().toISOString(),
        metadata,
      }

      if (addForm.input_mode === "url") {
        if (!addForm.url.trim()) throw new Error("URL is required")
        payload.url = addForm.url.trim()
      }

      if (addForm.input_mode === "text") {
        if (!addForm.raw_text.trim()) throw new Error("Text is required")
        payload.raw_text = addForm.raw_text
      }

      if (addForm.input_mode === "upload") {
        if (!addFile) throw new Error("File is required")
        const uploadData = new FormData()
        uploadData.append("file", addFile)
        const uploadRes = await fetch(`${API_BASE_URL}/uploads`, {
          method: "POST",
          body: uploadData,
        })
        if (!uploadRes.ok) throw new Error("Upload failed")
        const upload = await uploadRes.json()
        metadata = { upload_id: upload.upload_id }
        payload.metadata = metadata
      }

      const ingestRes = await fetch(`${API_BASE_URL}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })

      if (!ingestRes.ok) {
        const body = await ingestRes.json().catch(() => ({}))
        throw new Error(body.detail || "Ingestion failed")
      }

      const ingest = await ingestRes.json()
      setShowAddModal(false)
      resetAddForm()
      await fetchItems()

      if (ingest.task_id) {
        pollTaskUntilDone(ingest.task_id)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add source")
    } finally {
      setAddSubmitting(false)
    }
  }

  const patchItem = async (itemId, patch) => {
    try {
      const res = await fetch(`${API_BASE_URL}/items/${itemId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      })
      if (!res.ok) return
      await fetchItems()
    } catch (_) {
      // Best-effort UI action
    }
  }

  const runMemoryQuery = async (e) => {
    e.preventDefault()
    if (!memoryQuery.trim()) return

    setMemoryLoading(true)
    try {
      const res = await fetch(`${API_BASE_URL}/memory/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: memoryQuery.trim(), limit: 5 }),
      })
      if (!res.ok) throw new Error("Memory query failed")
      const data = await res.json()
      setMemoryResult(data)
    } catch (err) {
      setMemoryResult({ answer: err instanceof Error ? err.message : "Failed", citations: [] })
    } finally {
      setMemoryLoading(false)
    }
  }

  return (
    <div className="tom-app">
      <aside className="tom-sidebar">
        <div className="brand-block">
          <div className="brand-glyph">T</div>
          <div>
            <h1>Tom</h1>
            <p>Personal Consumption OS</p>
          </div>
        </div>

        <button
          className={`nav-btn ${activeWorkspace === "inbox" ? "active" : ""}`}
          onClick={() => setActiveWorkspace("inbox")}
        >
          <span>◻</span>
          Inbox
        </button>
        <button
          className={`nav-btn ${activeWorkspace === "memory" ? "active" : ""}`}
          onClick={() => setActiveWorkspace("memory")}
        >
          <span>◎</span>
          Ask Memory
        </button>

        <div className="sidebar-foot">
          <p>Capture everything you watch, listen, and read.</p>
        </div>
      </aside>

      <main className="tom-main">
        <header className="top-bar">
          <div className="top-search">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search your consumed content"
            />
          </div>
          <div className="top-actions">
            <select value={mediaFilter} onChange={(e) => setMediaFilter(e.target.value)}>
              <option value="all">All Sources</option>
              {MEDIA_TYPES.map((m) => (
                <option key={m.value} value={m.value}>
                  {m.label}
                </option>
              ))}
            </select>
            <button className="add-source-btn" onClick={() => setShowAddModal(true)}>
              + Add Source
            </button>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        {activeWorkspace === "inbox" && (
          <section className="workspace-grid">
            <div className="inbox-panel glass">
              <div className="panel-heading">
                <h2>Unified Inbox</h2>
                <span>{items.length} items</span>
              </div>

              {loadingItems && <p className="subtle">Refreshing feed...</p>}

              {groupOrder.length === 0 && <div className="empty-card">No content yet. Add your first source.</div>}

              {groupOrder.map((group) => (
                <div key={group} className="group-block">
                  <h3>{group}</h3>
                  {groupedItems[group].map((item) => {
                    const meta = mediaMeta(item.media_type)
                    const statusClass = (item.item_status || "ingested").toLowerCase()

                    return (
                      <button
                        type="button"
                        key={item.id}
                        className={`content-card ${selectedItemId === item.id ? "selected" : ""}`}
                        onClick={() => setSelectedItemId(item.id)}
                      >
                        <div className="card-top">
                          <span className="card-icon">{meta.icon}</span>
                          <span className="card-type">{meta.label}</span>
                          <span className={`status-pill ${statusClass}`}>
                            {STATUS_LABELS[item.item_status] || item.item_status}
                          </span>
                        </div>
                        <h4>{item.title || "Untitled Source"}</h4>
                        <p>{item.summary || "Processing or summary not ready yet."}</p>
                        <div className="card-actions" onClick={(e) => e.stopPropagation()}>
                          <button onClick={() => patchItem(item.id, { pinned: true })}>Pin</button>
                          <button onClick={() => patchItem(item.id, { archived: true })}>Archive</button>
                        </div>
                      </button>
                    )
                  })}
                </div>
              ))}
            </div>

            <div className="detail-panel glass">
              {!selectedItem && <div className="empty-card">Select an item to inspect its insights.</div>}

              {selectedItem && (
                <>
                  <div className="panel-heading detail-head">
                    <div>
                      <h2>{selectedItem.title || "Untitled"}</h2>
                      <p>{mediaMeta(selectedItem.media_type).label}</p>
                    </div>
                    <span className={`status-pill ${(selectedItem.item_status || "ingested").toLowerCase()}`}>
                      {STATUS_LABELS[selectedItem.item_status] || selectedItem.item_status}
                    </span>
                  </div>

                  <div className="detail-section">
                    <h3>Summary</h3>
                    <p>{selectedItem.summary || "Summary not available yet."}</p>
                  </div>

                  <div className="detail-section">
                    <h3>Key Points</h3>
                    {selectedItem.key_points?.length ? (
                      <ul>
                        {selectedItem.key_points.map((point, idx) => (
                          <li key={`${selectedItem.id}-kp-${idx}`}>{point}</li>
                        ))}
                      </ul>
                    ) : (
                      <p className="subtle">No key points extracted yet.</p>
                    )}
                  </div>

                  <div className="detail-section">
                    <h3>Moments</h3>
                    {selectedItem.moments?.length ? (
                      <div className="moments-grid">
                        {selectedItem.moments.map((moment, idx) => (
                          <div key={`${selectedItem.id}-moment-${idx}`} className="moment-card">
                            <span>{moment.label || `Moment ${idx + 1}`}</span>
                            <p>{moment.text || "No detail"}</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="subtle">No moments available yet.</p>
                    )}
                  </div>

                  <div className="detail-section">
                    <h3>Source</h3>
                    {selectedItem.source_url ? (
                      <a href={selectedItem.source_url} target="_blank" rel="noreferrer">
                        Open original source
                      </a>
                    ) : (
                      <p className="subtle">No external source URL.</p>
                    )}
                  </div>
                </>
              )}
            </div>
          </section>
        )}

        {activeWorkspace === "memory" && (
          <section className="memory-workspace glass">
            <div className="panel-heading">
              <h2>Ask Memory</h2>
              <span>Cited answers from your personal library</span>
            </div>

            <form className="memory-form" onSubmit={runMemoryQuery}>
              <textarea
                value={memoryQuery}
                onChange={(e) => setMemoryQuery(e.target.value)}
                placeholder="What did I consume this week about inflation, AI chips, and product strategy?"
              />
              <button type="submit" disabled={memoryLoading}>
                {memoryLoading ? "Thinking..." : "Ask"}
              </button>
            </form>

            {memoryResult && (
              <div className="memory-result">
                <h3>Answer</h3>
                <p>{memoryResult.answer}</p>

                <h3>Citations</h3>
                <div className="citation-list">
                  {memoryResult.citations?.map((c) => (
                    <button key={c.item_id} className="citation-card" onClick={() => setSelectedItemId(c.item_id)}>
                      <strong>{c.title}</strong>
                      <span>{mediaMeta(c.media_type).label}</span>
                      <p>{c.snippet}</p>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}
      </main>

      {showAddModal && (
        <div className="modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Add Source</h2>
              <button onClick={() => setShowAddModal(false)}>✕</button>
            </div>

            <form onSubmit={submitAddSource} className="add-form">
              <div className="field-row">
                <label>Media Type</label>
                <select
                  value={addForm.media_type}
                  onChange={(e) => setAddForm((p) => ({ ...p, media_type: e.target.value }))}
                >
                  {MEDIA_TYPES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-row">
                <label>Input Mode</label>
                <select
                  value={addForm.input_mode}
                  onChange={(e) => setAddForm((p) => ({ ...p, input_mode: e.target.value }))}
                >
                  {INPUT_MODES.map((m) => (
                    <option key={m.value} value={m.value}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="field-row">
                <label>Title</label>
                <input
                  value={addForm.title}
                  onChange={(e) => setAddForm((p) => ({ ...p, title: e.target.value }))}
                  placeholder="Optional title"
                />
              </div>

              <div className="field-row">
                <label>Author</label>
                <input
                  value={addForm.author}
                  onChange={(e) => setAddForm((p) => ({ ...p, author: e.target.value }))}
                  placeholder="Optional author"
                />
              </div>

              {addForm.input_mode === "url" && (
                <div className="field-row">
                  <label>URL</label>
                  <input
                    value={addForm.url}
                    onChange={(e) => setAddForm((p) => ({ ...p, url: e.target.value }))}
                    placeholder="https://..."
                    required
                  />
                </div>
              )}

              {addForm.input_mode === "text" && (
                <div className="field-row">
                  <label>Text</label>
                  <textarea
                    value={addForm.raw_text}
                    onChange={(e) => setAddForm((p) => ({ ...p, raw_text: e.target.value }))}
                    placeholder="Paste article, notes, highlights, or thread text..."
                    required
                  />
                </div>
              )}

              {addForm.input_mode === "upload" && (
                <div className="field-row">
                  <label>File</label>
                  <input type="file" onChange={(e) => setAddFile(e.target.files?.[0] || null)} required />
                </div>
              )}

              <button type="submit" className="submit-add" disabled={addSubmitting}>
                {addSubmitting ? "Adding..." : "Add to Inbox"}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
