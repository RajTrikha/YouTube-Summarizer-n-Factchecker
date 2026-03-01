import React from "react"

const WORKSPACES = [
  { key: "home", label: "Home" },
  { key: "inbox", label: "Inbox" },
  { key: "reading", label: "Reading" },
  { key: "audio", label: "Audio" },
  { key: "video", label: "Video" },
  { key: "collections", label: "Collections" },
  { key: "memory", label: "Ask Memory" },
]

export default function Sidebar({ activeWorkspace, onWorkspaceChange, onQuickCapture }) {
  return (
    <aside className="app-sidebar shell-surface level-2">
      <div className="brand-block">
        <div className="brand-mark" aria-hidden="true">
          <span />
          <span />
          <span />
        </div>
        <div>
          <h1>Tom</h1>
          <p>Cross-Media Learning OS</p>
        </div>
      </div>

      <button className="quick-capture" onClick={onQuickCapture}>
        Add Source
      </button>

      <nav className="workspace-nav" aria-label="Primary navigation">
        {WORKSPACES.map((workspace) => {
          const isActive = activeWorkspace === workspace.key
          return (
            <button
              key={workspace.key}
              className={`workspace-btn ${isActive ? "active" : ""}`}
              onClick={() => onWorkspaceChange(workspace.key)}
              aria-pressed={isActive}
            >
              <span className="workspace-dot" aria-hidden="true" />
              <span>{workspace.label}</span>
            </button>
          )
        })}
      </nav>

      <footer className="sidebar-footnote">
        <p>Capture, synthesize, revisit. Built for serious learners.</p>
      </footer>
    </aside>
  )
}
