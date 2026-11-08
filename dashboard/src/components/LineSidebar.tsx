import { useState } from "react"

interface LineSidebarProps {
  items: string[]
  accentColor?: string
  textColor?: string
  markerColor?: string
  showIndex?: boolean
  showMarker?: boolean
  proximityRadius?: number
  maxShift?: number
  falloff?: "linear" | "smooth"
  markerLength?: number
  markerGap?: number
  tickScale?: number
  scaleTick?: boolean
  itemGap?: number
  fontSize?: number
  smoothing?: number
  defaultActive?: number
  onItemClick?: (index: number, label: string) => void
}

export default function LineSidebar({
  items,
  accentColor = "#a855f7",
  textColor = "#c4c4c4",
  markerColor = "#6c6c6c",
  showIndex = true,
  showMarker = true,
  proximityRadius = 100,
  maxShift = 30,
  falloff = "smooth",
  markerLength = 60,
  markerGap = 0,
  tickScale = 0.5,
  scaleTick = true,
  itemGap = 20,
  fontSize = 1.1,
  smoothing = 100,
  defaultActive = 0,
  onItemClick,
}: LineSidebarProps) {
  const [active, setActive] = useState(defaultActive)
  const [pointerY, setPointerY] = useState<number | null>(null)

  function getShift(element: HTMLButtonElement) {
    if (pointerY === null) return 0
    const distance = Math.abs(pointerY - (element.offsetTop + element.offsetHeight / 2))
    const progress = Math.max(0, 1 - distance / proximityRadius)
    const eased = falloff === "smooth" ? progress * progress * (3 - 2 * progress) : progress
    return eased * maxShift
  }

  return (
    <aside
      className="relative flex min-h-svh w-72 shrink-0 flex-col border-r border-white/10 bg-black/45 px-8 py-10 backdrop-blur-xl"
      onMouseMove={(event) => {
        const bounds = event.currentTarget.getBoundingClientRect()
        setPointerY(event.clientY - bounds.top)
      }}
      onMouseLeave={() => setPointerY(null)}
      style={{ ["--sidebar-smoothing" as string]: `${smoothing}ms` }}
    >
      <div className="mb-16">
        <p className="font-mono text-xl font-semibold uppercase tracking-[0.3em]" style={{ color: accentColor }}>
          CodeDNA
        </p>
        <p className="mt-2 text-xs" style={{ color: textColor }}>
          Repository map
        </p>
      </div>

      <nav aria-label="Repository sections" className="relative">
        {showMarker && (
          <div
            aria-hidden="true"
            className="absolute left-0 top-0 transition-transform"
            style={{
              height: markerLength,
              marginTop: markerGap,
              borderLeft: `1px solid ${markerColor}`,
              transform: `translateY(${active * (markerLength + itemGap)}px)`,
              transitionDuration: "var(--sidebar-smoothing)",
            }}
          />
        )}
        <div className="flex flex-col" style={{ gap: itemGap }}>
          {items.map((label, index) => {
            const isActive = index === active
            return (
              <button
                key={label}
                type="button"
                onClick={() => {
                  setActive(index)
                  onItemClick?.(index, label)
                }}
                onMouseEnter={(event) => {
                  event.currentTarget.style.transform = `translateX(${getShift(event.currentTarget)}px)`
                }}
                onMouseMove={(event) => {
                  event.currentTarget.style.transform = `translateX(${getShift(event.currentTarget)}px)`
                }}
                onMouseLeave={(event) => {
                  event.currentTarget.style.transform = "translateX(0)"
                }}
                className="group flex h-[60px] w-full items-center gap-3 pl-5 text-left transition-transform"
                style={{
                  color: isActive ? accentColor : textColor,
                  fontSize: `${fontSize}rem`,
                  transitionDuration: "var(--sidebar-smoothing)",
                }}
              >
                {showIndex && (
                  <span className="w-6 font-mono text-[10px] opacity-50">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                )}
                <span className="tracking-tight">{label}</span>
                {scaleTick && (
                  <span
                    aria-hidden="true"
                    className="ml-auto h-px origin-left transition-all group-hover:w-8"
                    style={{
                      width: `${markerLength * tickScale}px`,
                      backgroundColor: isActive ? accentColor : markerColor,
                    }}
                  />
                )}
              </button>
            )
          })}
        </div>
      </nav>
    </aside>
  )
}
