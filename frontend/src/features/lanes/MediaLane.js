import React from "react"
import ContentCard from "./ContentCard"

export default function MediaLane({
  lane,
  items,
  selectedItemId,
  onSelectItem,
  onPin,
  onTag,
  onSaveCollection,
  dimmed = false,
}) {
  return (
    <section className={`media-lane shell-surface level-1 ${dimmed ? "dimmed" : ""}`}>
      <header className="lane-header">
        <div>
          <h3>{lane.title}</h3>
          <p>{lane.subtitle}</p>
        </div>
        <span>{items.length}</span>
      </header>

      <div className="lane-scroll">
        {items.length === 0 && <div className="lane-empty">No items in this lane yet.</div>}
        {items.map((item, index) => (
          <div key={item.id} className="lane-card-wrap" style={{ animationDelay: `${40 + index * 24}ms` }}>
            <ContentCard
              item={item}
              selected={selectedItemId === item.id}
              onSelect={onSelectItem}
              onPin={onPin}
              onTag={onTag}
              onSaveCollection={onSaveCollection}
              laneKey={lane.key}
              index={index}
            />
          </div>
        ))}
      </div>
    </section>
  )
}
