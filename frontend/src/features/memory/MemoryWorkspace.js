import React from "react"
import { getMediaMeta, truncate } from "../shared/media"

export default function MemoryWorkspace({
  query,
  onQueryChange,
  onSubmit,
  loading,
  result,
  onOpenItem,
}) {
  return (
    <section className="memory-shell shell-surface level-1">
      <header>
        <h2>Ask Memory</h2>
        <p>Grounded answers from your captured content with citations.</p>
      </header>

      <form className="memory-form" onSubmit={onSubmit}>
        <textarea
          value={query}
          onChange={(event) => onQueryChange(event.target.value)}
          placeholder="What did I consume this week about inflation, AI chips, and product strategy?"
        />
        <button type="submit" className="primary-btn" disabled={loading}>
          {loading ? "Thinking..." : "Ask Memory"}
        </button>
      </form>

      {result && (
        <div className="memory-result">
          <section>
            <h3>Answer</h3>
            <p>{result.answer}</p>
          </section>

          <section>
            <h3>Citations</h3>
            <div className="citation-grid">
              {(result.citations || []).map((citation) => {
                const media = getMediaMeta(citation.media_type)
                return (
                  <button key={citation.item_id} className="citation-card" onClick={() => onOpenItem(citation.item_id)}>
                    <div className="citation-head">
                      <span className={`media-glyph ${media.tone}`}>{media.glyph}</span>
                      <div>
                        <strong>{citation.title}</strong>
                        <span>{media.label}</span>
                      </div>
                    </div>
                    <p>{truncate(citation.snippet, 180)}</p>
                  </button>
                )
              })}
            </div>
          </section>
        </div>
      )}
    </section>
  )
}
