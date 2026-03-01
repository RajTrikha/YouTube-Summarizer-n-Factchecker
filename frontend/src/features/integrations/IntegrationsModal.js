import React from "react"

function ProviderCard({ provider }) {
  return (
    <article className="provider-card">
      <header>
        <h4>{provider.provider.replaceAll("_", " ")}</h4>
        <span className={`provider-status ${provider.status}`}>{provider.status}</span>
      </header>
      <p>{provider.limitations}</p>
      <div className="provider-meta">
        <span>Media: {provider.supported_media_types.join(", ")}</span>
        <span>Methods: {provider.ingestion_methods.join(", ")}</span>
      </div>
    </article>
  )
}

export default function IntegrationsModal({
  isOpen,
  onClose,
  providers,
  loadingProviders,
  onRefresh,
  readwiseToken,
  onTokenChange,
  onConnectReadwise,
  connectingReadwise,
  onStartSync,
  syncingReadwise,
  syncResult,
  syncError,
}) {
  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card shell-surface level-3" onClick={(event) => event.stopPropagation()}>
        <header className="modal-head">
          <h2>Integrations</h2>
          <div className="modal-actions">
            <button className="ghost-btn" onClick={onRefresh}>
              Refresh
            </button>
            <button className="ghost-btn" onClick={onClose}>
              Close
            </button>
          </div>
        </header>

        <section className="integrations-grid">
          <div className="provider-list">
            {loadingProviders && <div className="lane-empty">Loading providers...</div>}
            {!loadingProviders && providers.map((provider) => <ProviderCard key={provider.provider} provider={provider} />)}
          </div>

          <div className="readwise-panel">
            <h3>Readwise Bridge</h3>
            <p>Connect your token, then import highlights or reader documents.</p>

            <label>
              <span>Readwise Token</span>
              <input
                value={readwiseToken}
                type="password"
                placeholder="Paste token"
                onChange={(event) => onTokenChange(event.target.value)}
              />
            </label>

            <button className="primary-btn" onClick={onConnectReadwise} disabled={connectingReadwise || !readwiseToken.trim()}>
              {connectingReadwise ? "Connecting..." : "Connect Readwise"}
            </button>

            <div className="sync-actions">
              <button className="ghost-btn" disabled={syncingReadwise} onClick={() => onStartSync("highlights_export")}>
                Sync Highlights
              </button>
              <button className="ghost-btn" disabled={syncingReadwise} onClick={() => onStartSync("reader_documents")}>
                Sync Reader Docs
              </button>
            </div>

            {syncResult && (
              <div className="sync-status">
                <h4>Sync Status</h4>
                <p>Status: {syncResult.status}</p>
                <p>Imported: {syncResult.imported_count}</p>
                <p>Failed: {syncResult.failed_count}</p>
              </div>
            )}

            {syncError && <div className="inline-error">{syncError}</div>}
          </div>
        </section>
      </div>
    </div>
  )
}
