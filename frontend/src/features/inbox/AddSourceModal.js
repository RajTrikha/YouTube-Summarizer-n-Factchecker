import React from "react"

const MEDIA_TYPES = [
  { value: "youtube_video", label: "YouTube Video" },
  { value: "podcast_episode", label: "Podcast Episode" },
  { value: "web_article", label: "Web Article" },
  { value: "pdf_document", label: "PDF / Document" },
  { value: "book_highlights", label: "Book Highlights" },
  { value: "social_thread", label: "Social Thread" },
]

const INPUT_MODES = [
  { value: "url", label: "URL" },
  { value: "text", label: "Paste Text" },
  { value: "upload", label: "Upload File" },
  { value: "highlights_file", label: "Highlights File" },
]

export default function AddSourceModal({
  isOpen,
  form,
  setForm,
  file,
  setFile,
  submitting,
  error,
  onClose,
  onSubmit,
}) {
  if (!isOpen) return null

  const requiresFile = form.input_mode === "upload" || form.input_mode === "highlights_file"

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card shell-surface level-3" onClick={(event) => event.stopPropagation()}>
        <header className="modal-head">
          <h2>Add Source</h2>
          <button className="ghost-btn" onClick={onClose}>
            Close
          </button>
        </header>

        {error && <div className="inline-error">{error}</div>}

        <form className="source-form" onSubmit={onSubmit}>
          <label>
            <span>Media Type</span>
            <select
              value={form.media_type}
              onChange={(event) => setForm((previous) => ({ ...previous, media_type: event.target.value }))}
            >
              {MEDIA_TYPES.map((mediaType) => (
                <option key={mediaType.value} value={mediaType.value}>
                  {mediaType.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Input Mode</span>
            <select
              value={form.input_mode}
              onChange={(event) => setForm((previous) => ({ ...previous, input_mode: event.target.value }))}
            >
              {INPUT_MODES.map((inputMode) => (
                <option key={inputMode.value} value={inputMode.value}>
                  {inputMode.label}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Title</span>
            <input
              value={form.title}
              placeholder="Optional title"
              onChange={(event) => setForm((previous) => ({ ...previous, title: event.target.value }))}
            />
          </label>

          <label>
            <span>Author</span>
            <input
              value={form.author}
              placeholder="Optional author"
              onChange={(event) => setForm((previous) => ({ ...previous, author: event.target.value }))}
            />
          </label>

          {form.input_mode === "url" && (
            <label>
              <span>URL</span>
              <input
                required
                value={form.url}
                placeholder="https://..."
                onChange={(event) => setForm((previous) => ({ ...previous, url: event.target.value }))}
              />
            </label>
          )}

          {form.input_mode === "text" && (
            <label>
              <span>Text</span>
              <textarea
                required
                value={form.raw_text}
                placeholder="Paste article text, notes, or highlights"
                onChange={(event) => setForm((previous) => ({ ...previous, raw_text: event.target.value }))}
              />
            </label>
          )}

          {requiresFile && (
            <label>
              <span>File</span>
              <input required type="file" onChange={(event) => setFile(event.target.files?.[0] || null)} />
              {file && <small>{file.name}</small>}
            </label>
          )}

          <button type="submit" className="primary-btn" disabled={submitting}>
            {submitting ? "Adding..." : "Add to Inbox"}
          </button>
        </form>
      </div>
    </div>
  )
}
