"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import "./design/tokens.css"
import "./App.css"

import Sidebar from "./features/layout/Sidebar"
import TopBar from "./features/layout/TopBar"
import MediaLanesBoard from "./features/lanes/MediaLanesBoard"
import DetailDrawer from "./features/detail/DetailDrawer"
import AddSourceModal from "./features/inbox/AddSourceModal"
import IntegrationsModal from "./features/integrations/IntegrationsModal"
import MemoryWorkspace from "./features/memory/MemoryWorkspace"
import { LANE_ORDER, laneForItem } from "./features/shared/media"
import {
  connectReadwise,
  getIntegrationProviders,
  getItems,
  getItemsLanes,
  getSyncJobStatus,
  getTaskStatus,
  ingestSource,
  patchItem,
  queryMemory,
  startReadwiseSync,
  uploadSource,
} from "./services/api"

const EMPTY_LANES = {
  video: [],
  audio: [],
  reading: [],
}

function flattenLanes(lanes) {
  return LANE_ORDER.flatMap((laneKey) => lanes[laneKey] || [])
}

function groupItemsToLanes(items) {
  return items.reduce(
    (accumulator, item) => {
      const lane = laneForItem(item)
      if (accumulator[lane]) accumulator[lane].push(item)
      return accumulator
    },
    { ...EMPTY_LANES }
  )
}

function App() {
  const [activeWorkspace, setActiveWorkspace] = useState("home")
  const [laneFilter, setLaneFilter] = useState("all")
  const [search, setSearch] = useState("")

  const [lanes, setLanes] = useState(EMPTY_LANES)
  const [nextCursor, setNextCursor] = useState(null)
  const [loadingLanes, setLoadingLanes] = useState(false)

  const [selectedItemId, setSelectedItemId] = useState(null)
  const [error, setError] = useState(null)

  const [showAddModal, setShowAddModal] = useState(false)
  const [addSubmitting, setAddSubmitting] = useState(false)
  const [addForm, setAddForm] = useState({
    media_type: "youtube_video",
    input_mode: "url",
    title: "",
    author: "",
    url: "",
    raw_text: "",
  })
  const [addFile, setAddFile] = useState(null)

  const [showIntegrations, setShowIntegrations] = useState(false)
  const [providers, setProviders] = useState([])
  const [loadingProviders, setLoadingProviders] = useState(false)
  const [readwiseToken, setReadwiseToken] = useState("")
  const [connectingReadwise, setConnectingReadwise] = useState(false)
  const [syncingReadwise, setSyncingReadwise] = useState(false)
  const [syncResult, setSyncResult] = useState(null)
  const [syncError, setSyncError] = useState(null)

  const [memoryQueryText, setMemoryQueryText] = useState("")
  const [memoryLoading, setMemoryLoading] = useState(false)
  const [memoryResult, setMemoryResult] = useState(null)

  const allItems = useMemo(() => flattenLanes(lanes), [lanes])

  const selectedItem = useMemo(
    () => allItems.find((item) => item.id === selectedItemId) || null,
    [allItems, selectedItemId]
  )

  const fetchLaneData = useCallback(async () => {
    setLoadingLanes(true)
    try {
      const response = await getItemsLanes({ q: search.trim(), limit: 90 })
      const nextLanes = {
        video: Array.isArray(response?.lanes?.video) ? response.lanes.video : [],
        audio: Array.isArray(response?.lanes?.audio) ? response.lanes.audio : [],
        reading: Array.isArray(response?.lanes?.reading) ? response.lanes.reading : [],
      }
      setLanes(nextLanes)
      setNextCursor(response?.next_cursor || null)
      setError(null)

      if (!selectedItemId) {
        const first = flattenLanes(nextLanes)[0]
        if (first) setSelectedItemId(first.id)
      }
    } catch (laneError) {
      try {
        const items = await getItems({ q: search.trim(), limit: 100 })
        const grouped = groupItemsToLanes(Array.isArray(items) ? items : [])
        setLanes(grouped)
        setError("Lane API unavailable, using fallback feed.")
      } catch (fallbackError) {
        setError(fallbackError instanceof Error ? fallbackError.message : "Unable to load content")
      }
    } finally {
      setLoadingLanes(false)
    }
  }, [search, selectedItemId])

  useEffect(() => {
    fetchLaneData()
    const timer = setInterval(fetchLaneData, 8000)
    return () => clearInterval(timer)
  }, [fetchLaneData])

  const pollTaskUntilDone = async (taskId) => {
    let attempts = 0
    while (attempts < 90) {
      attempts += 1
      try {
        const status = await getTaskStatus(taskId)
        if (status.status === "SUCCESS" || status.status === "FAILURE") {
          await fetchLaneData()
          return
        }
      } catch (_) {
        // Continue polling best effort.
      }
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => setTimeout(resolve, 2500))
    }
    await fetchLaneData()
  }

  const resetAddForm = () => {
    setAddForm({
      media_type: "youtube_video",
      input_mode: "url",
      title: "",
      author: "",
      url: "",
      raw_text: "",
    })
    setAddFile(null)
  }

  const handleAddSource = async (event) => {
    event.preventDefault()
    setAddSubmitting(true)
    setError(null)

    try {
      const metadata = {
        source_provider: "manual",
      }

      const payload = {
        media_type: addForm.media_type,
        input_mode: addForm.input_mode,
        title: addForm.title || null,
        author: addForm.author || null,
        consumed_at: new Date().toISOString(),
        metadata,
      }

      if (addForm.input_mode === "url") {
        payload.url = addForm.url.trim()
      }

      if (addForm.input_mode === "text") {
        payload.raw_text = addForm.raw_text
      }

      if (addForm.input_mode === "upload" || addForm.input_mode === "highlights_file") {
        if (!addFile) throw new Error("Please choose a file first")
        const upload = await uploadSource(addFile)
        payload.metadata.upload_id = upload.upload_id
      }

      const result = await ingestSource(payload)
      setShowAddModal(false)
      resetAddForm()
      await fetchLaneData()

      if (result.task_id) pollTaskUntilDone(result.task_id)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to ingest source")
    } finally {
      setAddSubmitting(false)
    }
  }

  const handlePatchAction = async (itemId, patch) => {
    try {
      await patchItem(itemId, patch)
      await fetchLaneData()
    } catch (patchError) {
      setError(patchError instanceof Error ? patchError.message : "Unable to update item")
    }
  }

  const handlePin = (itemId) => handlePatchAction(itemId, { pinned: true })

  const handleTag = (itemId) => {
    const item = allItems.find((candidate) => candidate.id === itemId)
    const previousTags = Array.isArray(item?.metadata?.tags) ? item.metadata.tags : []
    const nextTags = Array.from(new Set([...previousTags, "review"])).slice(0, 8)
    return handlePatchAction(itemId, { tags: nextTags })
  }

  const handleSaveCollection = (itemId) => {
    const item = allItems.find((candidate) => candidate.id === itemId)
    const previousCollections = Array.isArray(item?.metadata?.collections) ? item.metadata.collections : []
    const nextCollections = Array.from(new Set([...previousCollections, "Learning Queue"])).slice(0, 8)
    return handlePatchAction(itemId, { collections: nextCollections })
  }

  const runMemoryQuery = async (event) => {
    event.preventDefault()
    if (!memoryQueryText.trim()) return

    setMemoryLoading(true)
    try {
      const result = await queryMemory(memoryQueryText.trim(), 5)
      setMemoryResult(result)
    } catch (memoryError) {
      setMemoryResult({
        answer: memoryError instanceof Error ? memoryError.message : "Memory query failed",
        citations: [],
      })
    } finally {
      setMemoryLoading(false)
    }
  }

  const fetchProviders = useCallback(async () => {
    setLoadingProviders(true)
    try {
      const data = await getIntegrationProviders()
      setProviders(Array.isArray(data) ? data : [])
      setSyncError(null)
    } catch (providerError) {
      setSyncError(providerError instanceof Error ? providerError.message : "Failed to load providers")
    } finally {
      setLoadingProviders(false)
    }
  }, [])

  useEffect(() => {
    if (!showIntegrations) return
    fetchProviders()
  }, [showIntegrations, fetchProviders])

  const handleConnectReadwise = async () => {
    setConnectingReadwise(true)
    setSyncError(null)
    try {
      await connectReadwise(readwiseToken)
      await fetchProviders()
    } catch (connectError) {
      setSyncError(connectError instanceof Error ? connectError.message : "Readwise connect failed")
    } finally {
      setConnectingReadwise(false)
    }
  }

  const handleStartReadwiseSync = async (mode) => {
    setSyncingReadwise(true)
    setSyncError(null)
    setSyncResult(null)

    try {
      const start = await startReadwiseSync({ mode })
      let attempts = 0
      while (attempts < 100) {
        attempts += 1
        // eslint-disable-next-line no-await-in-loop
        await new Promise((resolve) => setTimeout(resolve, 1800))
        // eslint-disable-next-line no-await-in-loop
        const status = await getSyncJobStatus(start.job_id)
        setSyncResult(status)
        if (status.status === "ready" || status.status === "failed") {
          await fetchLaneData()
          break
        }
      }
    } catch (syncProcessError) {
      setSyncError(syncProcessError instanceof Error ? syncProcessError.message : "Readwise sync failed")
    } finally {
      setSyncingReadwise(false)
    }
  }

  const handleWorkspaceChange = (workspace) => {
    setActiveWorkspace(workspace)
    if (workspace === "video") setLaneFilter("video")
    if (workspace === "audio") setLaneFilter("audio")
    if (workspace === "reading") setLaneFilter("reading")
    if (workspace === "home" || workspace === "inbox" || workspace === "collections") setLaneFilter("all")
  }

  const openItemFromMemory = (itemId) => {
    setActiveWorkspace("inbox")
    setLaneFilter("all")
    setSelectedItemId(itemId)
  }

  return (
    <div className="app-frame">
      <div className="ambient-glow" aria-hidden="true" />

      <Sidebar
        activeWorkspace={activeWorkspace}
        onWorkspaceChange={handleWorkspaceChange}
        onQuickCapture={() => setShowAddModal(true)}
      />

      <main className="app-main">
        <TopBar
          search={search}
          onSearchChange={setSearch}
          laneFilter={laneFilter}
          onLaneFilterChange={setLaneFilter}
          onOpenIntegrations={() => setShowIntegrations(true)}
          onOpenAddSource={() => setShowAddModal(true)}
        />

        {error && <div className="global-error">{error}</div>}

        {activeWorkspace === "memory" ? (
          <MemoryWorkspace
            query={memoryQueryText}
            onQueryChange={setMemoryQueryText}
            onSubmit={runMemoryQuery}
            loading={memoryLoading}
            result={memoryResult}
            onOpenItem={openItemFromMemory}
          />
        ) : (
          <section className="workspace-shell">
            <header className="workspace-head shell-surface level-1">
              <h2>Cross-Media Intake</h2>
              <div>
                <span>{allItems.length} items</span>
                {nextCursor && <span className="next-cursor">cursor {nextCursor}</span>}
                {loadingLanes && <span className="loading-flag">Refreshing...</span>}
              </div>
            </header>

            <MediaLanesBoard
              lanes={lanes}
              laneFilter={laneFilter}
              selectedItemId={selectedItemId}
              onSelectItem={setSelectedItemId}
              onPin={handlePin}
              onTag={handleTag}
              onSaveCollection={handleSaveCollection}
            />
          </section>
        )}
      </main>

      <DetailDrawer item={selectedItem} isOpen={Boolean(selectedItem)} onClose={() => setSelectedItemId(null)} />

      <AddSourceModal
        isOpen={showAddModal}
        form={addForm}
        setForm={setAddForm}
        file={addFile}
        setFile={setAddFile}
        submitting={addSubmitting}
        error={null}
        onClose={() => setShowAddModal(false)}
        onSubmit={handleAddSource}
      />

      <IntegrationsModal
        isOpen={showIntegrations}
        onClose={() => setShowIntegrations(false)}
        providers={providers}
        loadingProviders={loadingProviders}
        onRefresh={fetchProviders}
        readwiseToken={readwiseToken}
        onTokenChange={setReadwiseToken}
        onConnectReadwise={handleConnectReadwise}
        connectingReadwise={connectingReadwise}
        onStartSync={handleStartReadwiseSync}
        syncingReadwise={syncingReadwise}
        syncResult={syncResult}
        syncError={syncError}
      />
    </div>
  )
}

export default App
