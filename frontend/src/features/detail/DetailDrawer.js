import React, { useMemo, useState } from "react"
import { formatDateTime, getMediaMeta, providerLabel, truncate } from "../shared/media"

const TABS = ["summary", "highlights", "moments", "source"]

export default function DetailDrawer({ item, isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState("summary")

  const highlights = useMemo(() => {
    const fromMetadata = item?.metadata?.highlights
    if (Array.isArray(fromMetadata) && fromMetadata.length) return fromMetadata
    if (Array.isArray(item?.key_points) && item.key_points.length) return item.key_points
    return []
  }, [item])

  if (!item) return null

  const media = getMediaMeta(item.media_type)

  return (
    <aside className={`detail-drawer ${isOpen ? "open" : ""}`} aria-hidden={!isOpen}>
      <div className="drawer-header">
        <div>
          <span className={`media-glyph ${media.tone}`}>{media.glyph}</span>
          <h3>{item.title || "Untitled source"}</h3>
          <p>
            {media.label} / {providerLabel(item)} / {formatDateTime(item.created_at || item.consumed_at)}
          </p>
        </div>
        <button className="icon-close" onClick={onClose} aria-label="Close detail drawer">
          Close
        </button>
      </div>

      <div className="drawer-tabs" role="tablist" aria-label="Detail tabs">
        {TABS.map((tab) => (
          <button
            key={tab}
            className={activeTab === tab ? "active" : ""}
            onClick={() => setActiveTab(tab)}
            role="tab"
            aria-selected={activeTab === tab}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="drawer-body">
        {activeTab === "summary" && (
          <section>
            <h4>Summary</h4>
            <p>{item.summary || "Summary still processing."}</p>
          </section>
        )}

        {activeTab === "highlights" && (
          <section>
            <h4>Highlights</h4>
            {highlights.length === 0 && <p>No highlights saved yet.</p>}
            {highlights.length > 0 && (
              <div className="drawer-list">
                {highlights.slice(0, 12).map((highlight, index) => (
                  <article key={`${item.id}-hl-${index}`}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <p>{typeof highlight === "string" ? highlight : truncate(JSON.stringify(highlight), 180)}</p>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}

        {activeTab === "moments" && (
          <section>
            <h4>Moments</h4>
            {Array.isArray(item.moments) && item.moments.length > 0 ? (
              <div className="drawer-list">
                {item.moments.map((moment, index) => (
                  <article key={`${item.id}-moment-${index}`}>
                    <span>{moment.label || `M${index + 1}`}</span>
                    <p>{moment.text || "No detail available."}</p>
                  </article>
                ))}
              </div>
            ) : (
              <p>No moments extracted yet.</p>
            )}
          </section>
        )}

        {activeTab === "source" && (
          <section>
            <h4>Source</h4>
            <div className="source-grid">
              <div>
                <span>Media Type</span>
                <p>{media.label}</p>
              </div>
              <div>
                <span>Status</span>
                <p>{item.item_status}</p>
              </div>
              <div>
                <span>Provider</span>
                <p>{providerLabel(item)}</p>
              </div>
              <div>
                <span>Input Mode</span>
                <p>{item.input_mode}</p>
              </div>
            </div>

            {item.source_url ? (
              <a className="source-link" href={item.source_url} target="_blank" rel="noreferrer">
                Open Original Source
              </a>
            ) : (
              <p>No external URL available for this item.</p>
            )}
          </section>
        )}
      </div>
    </aside>
  )
}
