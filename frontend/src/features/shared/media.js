export const MEDIA_META = {
  youtube_video: {
    label: "YouTube",
    lane: "video",
    glyph: "YT",
    tone: "video",
  },
  podcast_episode: {
    label: "Podcast",
    lane: "audio",
    glyph: "PD",
    tone: "audio",
  },
  web_article: {
    label: "Article",
    lane: "reading",
    glyph: "AR",
    tone: "reading",
  },
  pdf_document: {
    label: "Document",
    lane: "reading",
    glyph: "PDF",
    tone: "reading",
  },
  book_highlights: {
    label: "Book",
    lane: "reading",
    glyph: "BK",
    tone: "reading",
  },
  social_thread: {
    label: "Thread",
    lane: "reading",
    glyph: "TH",
    tone: "reading",
  },
}

export const LANE_META = {
  video: {
    key: "video",
    title: "Video",
    subtitle: "YouTube and video essays",
  },
  audio: {
    key: "audio",
    title: "Audio",
    subtitle: "Podcasts and spoken content",
  },
  reading: {
    key: "reading",
    title: "Reading",
    subtitle: "Articles, docs, and highlights",
  },
}

export const STATUS_LABELS = {
  ingested: "Ingested",
  processing: "Processing",
  ready: "Ready",
  failed: "Failed",
}

export const LANE_ORDER = ["video", "audio", "reading"]

export function getMediaMeta(mediaType) {
  return (
    MEDIA_META[mediaType] || {
      label: String(mediaType || "Source"),
      lane: "reading",
      glyph: "IT",
      tone: "reading",
    }
  )
}

export function statusClass(status) {
  return String(status || "ingested").toLowerCase()
}

export function laneForItem(item) {
  if (item?.lane) return item.lane
  return getMediaMeta(item?.media_type).lane
}

export function providerLabel(item) {
  const provider = item?.source_provider
  if (!provider) return "manual"
  return String(provider).replaceAll("_", " ")
}

export function formatDateTime(dateString) {
  if (!dateString) return "Recently"
  try {
    const date = new Date(dateString)
    return date.toLocaleString([], {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    })
  } catch (_) {
    return "Recently"
  }
}

export function truncate(text, max = 140) {
  const value = String(text || "").trim()
  if (value.length <= max) return value
  return `${value.slice(0, max - 1)}...`
}
