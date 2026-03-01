import React from "react"
import MediaLane from "./MediaLane"
import { LANE_META, LANE_ORDER } from "../shared/media"

export default function MediaLanesBoard({
  lanes,
  laneFilter,
  selectedItemId,
  onSelectItem,
  onPin,
  onTag,
  onSaveCollection,
}) {
  return (
    <section className="media-lanes-grid">
      {LANE_ORDER.map((laneKey) => {
        const lane = LANE_META[laneKey]
        const dimmed = laneFilter !== "all" && laneFilter !== laneKey
        const laneItems = Array.isArray(lanes[laneKey]) ? lanes[laneKey] : []

        return (
          <MediaLane
            key={laneKey}
            lane={lane}
            items={laneItems}
            dimmed={dimmed}
            selectedItemId={selectedItemId}
            onSelectItem={onSelectItem}
            onPin={onPin}
            onTag={onTag}
            onSaveCollection={onSaveCollection}
          />
        )
      })}
    </section>
  )
}
