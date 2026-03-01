import React from "react"

const LANE_FILTERS = [
  { key: "all", label: "All" },
  { key: "video", label: "Video" },
  { key: "audio", label: "Audio" },
  { key: "reading", label: "Reading" },
]

export default function TopBar({
  search,
  onSearchChange,
  laneFilter,
  onLaneFilterChange,
  onOpenIntegrations,
  onOpenAddSource,
}) {
  return (
    <header className="top-bar shell-surface level-1">
      <div className="search-shell">
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search ideas, moments, quotes, themes"
          aria-label="Search content"
        />
      </div>

      <div className="chip-row" role="tablist" aria-label="Lane filters">
        {LANE_FILTERS.map((filter) => {
          const isActive = laneFilter === filter.key
          return (
            <button
              key={filter.key}
              className={`filter-chip ${isActive ? "active" : ""}`}
              onClick={() => onLaneFilterChange(filter.key)}
              role="tab"
              aria-selected={isActive}
            >
              {filter.label}
            </button>
          )
        })}
      </div>

      <div className="top-actions">
        <button className="ghost-btn" onClick={onOpenIntegrations}>
          Connect Sources
        </button>
        <button className="primary-btn" onClick={onOpenAddSource}>
          Add Source
        </button>
      </div>
    </header>
  )
}
