"use client"

import { useState, useEffect } from "react"

const FactCheckReport = ({ result }) => {
  const [factCheckItems, setFactCheckItems] = useState([])
  const [reportMessage, setReportMessage] = useState("")
  const [overallRating, setOverallRating] = useState(null)
  const [activeFilter, setActiveFilter] = useState("all")
  const [expandedClaim, setExpandedClaim] = useState(null)
  const [showModal, setShowModal] = useState(false)
  const [modalContent, setModalContent] = useState(null)
  const [isVisible, setIsVisible] = useState(false)
  const [animateItems, setAnimateItems] = useState(false)

  // Trigger entrance animation
  useEffect(() => {
    const timer = setTimeout(() => setIsVisible(true), 300)
    return () => clearTimeout(timer)
  }, [])

  useEffect(() => {
    if (!result) {
      setReportMessage("No fact-check could be generated.")
      setFactCheckItems([])
      setOverallRating(null)
      return
    }

    const fact_check_results = result.fact_check_results || result.fact_checks || result.claims || []
    const overall_rating = result.overall_credibility || result.credibility_rating || result.overall_rating

    setOverallRating(overall_rating)

    if (!fact_check_results || fact_check_results.length === 0) {
      setReportMessage("No claims could be extracted for fact-checking.")
      setFactCheckItems([])
      return
    }

    const processed_results = fact_check_results.map((res, index) => {
      const score = res.false_confidence_score || res.confidence_score || res.score || 0.0
      const accuracy = res.accuracy || res.verdict || res.status

      let verdict = ""
      let verdictClass = ""

      if (accuracy) {
        verdict = accuracy
        verdictClass = accuracy.toLowerCase().replace(/\s+/g, "-")
      } else {
        if (score >= 0.8) {
          verdict = "False"
          verdictClass = "false"
        } else if (score >= 0.6) {
          verdict = "Possibly False"
          verdictClass = "possibly-false"
        } else if (score >= 0.4) {
          verdict = "Uncertain"
          verdictClass = "uncertain"
        } else {
          verdict = "Likely True"
          verdictClass = "likely-true"
        }
      }

      return {
        ...res,
        verdict,
        verdictClass,
        confidence_score: score,
        id: index,
      }
    })

    setFactCheckItems(processed_results)

    const problematicClaims = processed_results.filter(
      (item) => item.verdict === "False" || item.verdict === "Possibly False" || item.verdict === "Misleading",
    )

    if (problematicClaims.length === 0) {
      setReportMessage("✅ No false or misleading claims were detected.")
    } else {
      setReportMessage("")
    }

    // Trigger item animations
    setTimeout(() => setAnimateItems(true), 500)
  }, [result])

  const getFilteredItems = () => {
    if (activeFilter === "all") return factCheckItems
    if (activeFilter === "problematic") {
      return factCheckItems.filter(
        (item) => item.verdict === "False" || item.verdict === "Possibly False" || item.verdict === "Misleading",
      )
    }
    if (activeFilter === "verified") {
      return factCheckItems.filter(
        (item) => item.verdict === "True" || item.verdict === "Likely True" || item.verdict === "Verified",
      )
    }
    return factCheckItems
  }

  const getVerdictEmoji = (verdict) => {
    switch (verdict.toLowerCase()) {
      case "false":
      case "misleading":
        return "❌"
      case "possibly false":
      case "uncertain":
        return "🤔"
      case "true":
      case "likely true":
      case "verified":
        return "✅"
      default:
        return "❓"
    }
  }

  const getCredibilityColor = (rating) => {
    if (!rating) return "medium"
    const lowerRating = rating.toLowerCase()
    if (lowerRating.includes("high") || lowerRating.includes("good")) return "high"
    if (lowerRating.includes("low") || lowerRating.includes("poor")) return "low"
    return "medium"
  }

  const handleFilterChange = (filter) => {
    setActiveFilter(filter)
    setExpandedClaim(null)
    setAnimateItems(false)
    setTimeout(() => setAnimateItems(true), 200)
  }

  const toggleClaim = (index) => {
    setExpandedClaim(expandedClaim === index ? null : index)
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

  const filteredItems = getFilteredItems()

  return (
    <>
      <div className={`fact-check-report popup-card interactive-card ${isVisible ? "card-visible" : ""}`}>
        <div className="popup-header interactive-header">
          <div className="popup-icon animated-icon">🔎</div>
          <h2 className="animated-title">Fact-Check Report</h2>
          {overallRating && (
            <div className={`credibility-badge credibility-${getCredibilityColor(overallRating)} pulsing-badge`}>
              <span className="credibility-icon rotating-icon">🎯</span>
              <span>Overall: {overallRating}</span>
            </div>
          )}
          <button
            className="expand-button"
            onClick={() => openModal(filteredItems, "all-claims")}
            title="View All Claims"
          >
            <span className="expand-icon">📊</span>
          </button>
        </div>

        {factCheckItems.length > 0 && (
          <div className="filter-navigation interactive-filters">
            <button
              className={`filter-button interactive-filter ${activeFilter === "all" ? "active" : ""}`}
              onClick={() => handleFilterChange("all")}
              onKeyPress={(e) => handleKeyPress(e, () => handleFilterChange("all"))}
            >
              <span className="filter-icon pulse-icon">📊</span>
              <span className="filter-text">All Claims</span>
              <span className="filter-count">{factCheckItems.length}</span>
              <div className="filter-indicator"></div>
            </button>
            <button
              className={`filter-button interactive-filter ${activeFilter === "problematic" ? "active" : ""}`}
              onClick={() => handleFilterChange("problematic")}
              onKeyPress={(e) => handleKeyPress(e, () => handleFilterChange("problematic"))}
            >
              <span className="filter-icon pulse-icon">⚠️</span>
              <span className="filter-text">Problematic</span>
              <span className="filter-count">
                {
                  factCheckItems.filter(
                    (item) =>
                      item.verdict === "False" || item.verdict === "Possibly False" || item.verdict === "Misleading",
                  ).length
                }
              </span>
              <div className="filter-indicator"></div>
            </button>
            <button
              className={`filter-button interactive-filter ${activeFilter === "verified" ? "active" : ""}`}
              onClick={() => handleFilterChange("verified")}
              onKeyPress={(e) => handleKeyPress(e, () => handleFilterChange("verified"))}
            >
              <span className="filter-icon pulse-icon">✅</span>
              <span className="filter-text">Verified</span>
              <span className="filter-count">
                {
                  factCheckItems.filter(
                    (item) => item.verdict === "True" || item.verdict === "Likely True" || item.verdict === "Verified",
                  ).length
                }
              </span>
              <div className="filter-indicator"></div>
            </button>
          </div>
        )}

        <div className="popup-content animated-content">
          {filteredItems.length > 0 ? (
            <div className="fact-check-items">
              {filteredItems.map((item, index) => (
                <div
                  key={item.id || index}
                  className={`fact-check-item popup-item interactive-claim ${
                    animateItems ? "claim-animate" : ""
                  } ${expandedClaim === index ? "expanded" : ""}`}
                  style={{ animationDelay: `${index * 0.1}s` }}
                >
                  <div
                    className="fact-check-item-content clickable-content"
                    onClick={() => toggleClaim(index)}
                    onKeyPress={(e) => handleKeyPress(e, () => toggleClaim(index))}
                    tabIndex={0}
                    role="button"
                    aria-expanded={expandedClaim === index}
                  >
                    <span className="fact-check-emoji bouncing-emoji">{getVerdictEmoji(item.verdict)}</span>
                    <div className="fact-check-details">
                      <div className="fact-check-claim">
                        <span className="claim-text">{item.claim || item.statement || item.text || "N/A"}</span>
                        <span className={`verdict-badge verdict-${item.verdictClass} glowing-verdict`}>
                          {item.verdict}
                        </span>
                      </div>

                      {item.confidence_score > 0 && (
                        <div className="confidence-meter animated-meter">
                          <span className="confidence-label">Confidence:</span>
                          <div className="confidence-bar">
                            <div
                              className="confidence-fill animated-fill"
                              style={{
                                width: `${item.confidence_score * 100}%`,
                                animationDelay: `${index * 0.2}s`,
                              }}
                            ></div>
                          </div>
                          <span className="confidence-value pulsing-value">
                            {Math.round(item.confidence_score * 100)}%
                          </span>
                        </div>
                      )}
                    </div>
                    <div className={`expand-arrow ${expandedClaim === index ? "rotated" : ""}`}>▼</div>
                  </div>

                  <div className={`claim-details collapsible-content ${expandedClaim === index ? "expanded" : ""}`}>
                    <div className="details-inner">
                      <p className="fact-check-explanation fade-in-text">
                        {item.explanation || item.reasoning || item.details || "No explanation provided."}
                      </p>

                      {item.sources && item.sources.length > 0 && (
                        <div className="sources-section animated-sources">
                          <h4 className="sources-title">
                            <span className="sources-icon sparkling-icon">📚</span>
                            Sources
                          </h4>
                          <ul className="sources-list">
                            {item.sources.map((source, sourceIndex) => (
                              <li
                                key={sourceIndex}
                                className="source-item slide-in-source"
                                style={{ animationDelay: `${sourceIndex * 0.1}s` }}
                              >
                                <span className="source-bullet">🔗</span>
                                {typeof source === "string" ? source : source.title || source.url || "Unknown source"}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      <button
                        className="claim-action-btn"
                        onClick={(e) => {
                          e.stopPropagation()
                          openModal(item, "claim")
                        }}
                      >
                        <span className="btn-icon">🔍</span>
                        View Full Analysis
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : factCheckItems.length > 0 ? (
            <div className="no-results-message bounce-in">
              <div className="no-content-icon floating-icon">🔍</div>
              <p>No claims match the current filter.</p>
              <button className="reset-filter-btn" onClick={() => handleFilterChange("all")}>
                Show All Claims
              </button>
            </div>
          ) : (
            <div className="popup-success bounce-in">
              <div className="success-icon pulsing-success">✅</div>
              <p>{reportMessage}</p>
            </div>
          )}
        </div>
      </div>

      {/* Interactive Modal */}
      {showModal && (
        <div className="modal-overlay modal-fade-in" onClick={closeModal}>
          <div className="modal-content modal-slide-up" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">
                {modalContent?.type === "claim"
                  ? "🔍 Detailed Analysis"
                  : modalContent?.type === "all-claims"
                    ? "📊 All Claims Overview"
                    : "Details"}
              </h3>
              <button className="modal-close rotating-close" onClick={closeModal}>
                <span className="close-icon">✕</span>
              </button>
            </div>
            <div className="modal-body">
              {modalContent?.type === "claim" && (
                <div className="modal-claim">
                  <div className="modal-claim-header">
                    <span className="modal-emoji">{getVerdictEmoji(modalContent.content.verdict)}</span>
                    <span className={`modal-verdict verdict-${modalContent.content.verdictClass}`}>
                      {modalContent.content.verdict}
                    </span>
                  </div>
                  <div className="modal-claim-text">
                    <strong>Claim:</strong>{" "}
                    {modalContent.content.claim || modalContent.content.statement || modalContent.content.text}
                  </div>
                  <div className="modal-explanation">
                    <strong>Analysis:</strong>{" "}
                    {modalContent.content.explanation || modalContent.content.reasoning || modalContent.content.details}
                  </div>
                  {modalContent.content.sources && modalContent.content.sources.length > 0 && (
                    <div className="modal-sources">
                      <strong>Sources:</strong>
                      <ul>
                        {modalContent.content.sources.map((source, index) => (
                          <li key={index}>
                            {typeof source === "string" ? source : source.title || source.url || "Unknown source"}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
              {modalContent?.type === "all-claims" && (
                <div className="modal-overview">
                  <div className="overview-stats">
                    <div className="stat-item">
                      <span className="stat-number">{modalContent.content.length}</span>
                      <span className="stat-label">Total Claims</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-number">
                        {
                          modalContent.content.filter(
                            (item) =>
                              item.verdict === "False" ||
                              item.verdict === "Possibly False" ||
                              item.verdict === "Misleading",
                          ).length
                        }
                      </span>
                      <span className="stat-label">Problematic</span>
                    </div>
                    <div className="stat-item">
                      <span className="stat-number">
                        {
                          modalContent.content.filter(
                            (item) =>
                              item.verdict === "True" || item.verdict === "Likely True" || item.verdict === "Verified",
                          ).length
                        }
                      </span>
                      <span className="stat-label">Verified</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  )
}

export default FactCheckReport
