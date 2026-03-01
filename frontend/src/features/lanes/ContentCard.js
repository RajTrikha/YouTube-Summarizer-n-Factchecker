import React, { useMemo, useState } from "react"
import { formatDateTime, getMediaMeta, providerLabel, statusClass, STATUS_LABELS, truncate } from "../shared/media"

export default function ContentCard({
  item,
  selected,
  onSelect,
  onPin,
  onTag,
  onSaveCollection,
  laneKey,
  index,
}) {
  const [isHovered, setIsHovered] = useState(false)
  const media = useMemo(() => getMediaMeta(item.media_type), [item.media_type])
  const cardStatus = statusClass(item.item_status)
  const quickPoints = Array.isArray(item.key_points) ? item.key_points.slice(0, 3) : []

  const focusByCoordinate = (targetLane, targetIndex) => {
    const selector = `[data-lane="${targetLane}"][data-index="${targetIndex}"]`
    const next = document.querySelector(selector)
    if (next && typeof next.focus === "function") next.focus()
  }

  return (
    <article
      className={`lane-card ${media.tone} ${selected ? "selected" : ""}`}
      tabIndex={0}
      data-lane={laneKey}
      data-index={index}
      onClick={() => onSelect(item.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onSelect(item.id)
        }
        if (event.key === "ArrowDown") {
          event.preventDefault()
          focusByCoordinate(laneKey, index + 1)
        }
        if (event.key === "ArrowUp") {
          event.preventDefault()
          focusByCoordinate(laneKey, Math.max(index - 1, 0))
        }
        if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
          event.preventDefault()
          const laneOrder = ["video", "audio", "reading"]
          const lanePosition = laneOrder.indexOf(laneKey)
          const offset = event.key === "ArrowRight" ? 1 : -1
          const targetLane = laneOrder[lanePosition + offset]
          if (targetLane) focusByCoordinate(targetLane, index)
        }
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      aria-label={item.title || "Untitled source"}
    >
      <div className="lane-card-head">
        <span className={`media-glyph ${media.tone}`}>{media.glyph}</span>
        <div className="lane-card-meta">
          <span>{media.label}</span>
          <span className="dot-sep">/</span>
          <span>{providerLabel(item)}</span>
        </div>
        <span className={`status-pill ${cardStatus}`}>{STATUS_LABELS[cardStatus] || cardStatus}</span>
      </div>

      <h4>{item.title || "Untitled source"}</h4>
      <p className="card-summary">{truncate(item.summary || "Summary is still processing.", 170)}</p>

      <div className="lane-card-foot">
        <span>{formatDateTime(item.created_at || item.consumed_at)}</span>
        {item.metadata?.collections?.length ? <span>{item.metadata.collections[0]}</span> : <span>Inbox</span>}
      </div>

      {isHovered && (
        <section className="hover-peek" onClick={(event) => event.stopPropagation()}>
          <header>
            <h5>Quick Peek</h5>
            <span>{media.label}</span>
          </header>

          <p>{truncate(item.summary || "Summary pending.", 190)}</p>

          <div className="peek-points">
            {quickPoints.length ? (
              quickPoints.map((point, index) => <div key={`${item.id}-peek-${index}`}>{truncate(point, 110)}</div>)
            ) : (
              <div>No key points yet.</div>
            )}
          </div>

          <div className="peek-actions">
            <button onClick={() => onPin(item.id)}>Pin</button>
            <button onClick={() => onTag(item.id)}>Tag</button>
            <button onClick={() => onSaveCollection(item.id)}>Save</button>
            {item.source_url ? (
              <a href={item.source_url} target="_blank" rel="noreferrer">
                Open
              </a>
            ) : (
              <span className="disabled-link">Open</span>
            )}
          </div>
        </section>
      )}
    </article>
  )
}
