"use client"

import { useState, useEffect } from "react"

const SummaryReport = ({ summary }) => {
  const [activeTab, setActiveTab] = useState("overall")
  const [expandedChapter, setExpandedChapter] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [modalContent, setModalContent] = useState(null)
  const [isVisible, setIsVisible] = useState(false)
  const [animateChapters, setAnimateChapters] = useState(false)

  // Trigger entrance animation
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 100)
    return () => clearTimeout(timer)
  }, [])

  // Handle both old and new data structures
  const overallSummary =
    typeof summary === "string" ? summary : summary?.overall || summary?.summary || "No summary could be generated."
  const chapterSummary = summary?.chapters || summary?.detailed || []

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return ""

    if (typeof timestamp === "string") {
      if (timestamp.includes(":")) return timestamp
      const seconds = Number.parseInt(timestamp)
      if (!isNaN(seconds)) {
        const minutes = Math.floor(seconds / 60)
        const remainingSeconds = seconds % 60
        return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`
      }
    }

    if (typeof timestamp === "number") {
      const minutes = Math.floor(timestamp / 60)
      const remainingSeconds = timestamp % 60
      return `${minutes}:${remainingSeconds.toString().padStart(2, "0")}`
    }

    return timestamp
  }

  const handleTabSwitch = (tab) => {
    setActiveTab(tab)
    if (tab === "chapters") {
      setTimeout(() => setAnimateChapters(true), 200)
    } else {
      setAnimateChapters(false)
    }
  }

  const toggleChapter = (index) => {
    setExpandedChapter(expandedChapter === index ? null : index)
  }

  const openModal = (content, type) => {
    setModalContent({ content, type })
    setShowModal(true)
    document.body.style.overflow = "hidden"
  }

  const closeModal = () => {
    setShowModal(false)
    setModalContent(null)
    document.body.style.overflow = "auto"
  }

  const handleKeyPress = (e, callback) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault()
      callback()
    }
  }

  return (
    <>
      <div className={`summary-report popup-card interactive-card enhanced-summary ${isVisible ? "card-visible" : ""}`}>
        <div className="popup-header interactive-header">
          <div className="popup-icon animated-icon">📝</div>
          <h2 className="animated-title">Video Summary</h2>
          <button className="expand-button" onClick={() => openModal(overallSummary, "summary")} title="Expand Summary">
            <span className="expand-icon">🔍</span>
          </button>
        </div>

        {/* Interactive Tab Navigation */}
        <div className="tab-navigation interactive-tabs">
          <button
            className={`tab-button interactive-tab enhanced-tab ${activeTab === "overall" ? "active" : ""}`}
            onClick={() => handleTabSwitch("overall")}
            onKeyPress={(e) => handleKeyPress(e, () => handleTabSwitch("overall"))}
          >
            <span className="tab-icon pulse-icon">📋</span>
            <span className="tab-text">Overall Summary</span>
            <div className="tab-indicator"></div>
          </button>
          {chapterSummary.length > 0 && (
            <button
              className={`tab-button interactive-tab ${activeTab === "chapters" ? "active" : ""}`}
              onClick={() => handleTabSwitch("chapters")}
              onKeyPress={(e) => handleKeyPress(e, () => handleTabSwitch("chapters"))}
            >
              <span className="tab-icon pulse-icon">📚</span>
              <span className="tab-text">Chapter Breakdown</span>
              <span className="chapter-count">{chapterSummary.length}</span>
              <div className="tab-indicator"></div>
            </button>
          )}
        </div>

        <div className="popup-content animated-content">
          {activeTab === "overall" && (
            <div className="overall-summary slide-in-left">
              <div className="summary-badge floating-badge enhanced-badge">
                <span className="badge-icon rotating-icon">🎯</span>
                <span>Key Insights</span>
              </div>
              <div className="summary-text-container enhanced-text-container">
                <p className="summary-text enhanced-summary-text">{overallSummary}</p>
                <button className="read-more-btn" onClick={() => openModal(overallSummary, "summary")}>
                  <span className="btn-icon">📖</span>
                  Read Full Summary
                </button>
              </div>
            </div>
          )}

          {activeTab === "chapters" && chapterSummary.length > 0 && (
            <div className="chapter-summary slide-in-right">
              <div className="summary-badge floating-badge">
                <span className="badge-icon rotating-icon">⏱️</span>
                <span>Timestamped Breakdown</span>
              </div>
              <div className="chapters-container">
                {chapterSummary.map((chapter, index) => (
                  <div
                    key={index}
                    className={`chapter-item popup-item interactive-chapter ${
                      animateChapters ? "chapter-animate" : ""
                    } ${expandedChapter === index ? "expanded" : ""}`}
                    style={{ animationDelay: `${index * 0.1}s` }}
                  >
                    <div
                      className="chapter-header clickable-header"
                      onClick={() => toggleChapter(index)}
                      onKeyPress={(e) => handleKeyPress(e, () => toggleChapter(index))}
                      tabIndex={0}
                      role="button"
                      aria-expanded={expandedChapter === index}
                    >
                      <div className="chapter-number bouncing-number">
                        <span className="chapter-index">{index + 1}</span>
                      </div>
                      <div className="chapter-info">
                        {chapter.timestamp && (
                          <div className="timestamp-badge glowing-badge">
                            <span className="timestamp-icon blinking-icon">🕐</span>
                            <span className="timestamp-text">{formatTimestamp(chapter.timestamp)}</span>
                          </div>
                        )}
                        {chapter.title && <h3 className="chapter-title">{chapter.title}</h3>}
                      </div>
                      <div className={`expand-arrow ${expandedChapter === index ? "rotated" : ""}`}>▼</div>
                    </div>

                    <div
                      className={`chapter-content collapsible-content ${expandedChapter === index ? "expanded" : ""}`}
                    >
                      <div className="content-inner">
                        <p className="chapter-text fade-in-text">
                          {chapter.chapter_summary ||
                            chapter.summary ||
                            chapter.content ||
                            chapter.description ||
                            "No content available."}
                        </p>
                        {chapter.key_points && chapter.key_points.length > 0 && (
                          <div className="key-points animated-points">
                            <h4 className="key-points-title">
                              <span className="key-points-icon sparkling-icon">💡</span>
                              Key Points
                            </h4>
                            <ul className="key-points-list">
                              {chapter.key_points.map((point, pointIndex) => (
                                <li
                                  key={pointIndex}
                                  className="key-point-item slide-in-point"
                                  style={{ animationDelay: `${pointIndex * 0.1}s` }}
                                >
                                  <span className="point-bullet">✨</span>
                                  {point}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        <button
                          className="chapter-action-btn"
                          onClick={(e) => {
                            e.stopPropagation()
                            openModal(chapter, "chapter")
                          }}
                        >
                          <span className="btn-icon">🔍</span>
                          View Details
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeTab === "chapters" && chapterSummary.length === 0 && (
            <div className="no-chapters-message bounce-in">
              <div className="no-content-icon floating-icon">📄</div>
              <p>
                No chapter breakdown available. The video may be too short or the content couldn't be segmented into
                chapters.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Interactive Modal */}
      {showModal && (
        <div className="modal-overlay" onClick={closeModal}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {modalContent?.type === "summary"
                  ? "📝 Full Summary"
                  : modalContent?.type === "chapter"
                    ? `📚 Chapter ${chapterSummary.indexOf(modalContent.content) + 1}`
                    : "Details"}
              </h3>
              <button className="modal-close" onClick={closeModal}>
                <span className="close-icon">✕</span>
              </button>
            </div>
            <div className="modal-body">
              {modalContent?.type === "summary" && (
                <div className="modal-summary">
                  <p className="modal-text">{modalContent.content}</p>
                </div>
              )}
              {modalContent?.type === "chapter" && (
                <div className="modal-chapter">
                  {modalContent.content.timestamp && (
                    <div className="modal-timestamp">
                      <span className="timestamp-icon">🕐</span>
                      {formatTimestamp(modalContent.content.timestamp)}
                    </div>
                  )}
                  {modalContent.content.title && <h4 className="modal-chapter-title">{modalContent.content.title}</h4>}
                  <p className="modal-text">
                    {modalContent.content.chapter_summary ||
                      modalContent.content.summary ||
                      modalContent.content.content ||
                      modalContent.content.description}
                  </p>
                  {modalContent.content.key_points && modalContent.content.key_points.length > 0 && (
                    <div className="modal-key-points">
                      <h5>Key Points:</h5>
                      <ul>
                        {modalContent.content.key_points.map((point, index) => (
                          <li key={index}>{point}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default SummaryReport
