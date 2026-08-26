import { useLayoutEffect, useRef, useState } from 'react'

/**
 * Gmail-style scrollable table shell: sticky header, body scrolls inside.
 *
 * - fill: grow/shrink inside a flex parent (preferred for full-page tables)
 * - autoHeight: cap height to remaining viewport below this element (nested tables)
 */
export default function ScrollableTable({
  children,
  fill = false,
  autoHeight = false,
  bottomOffset = 20,
  minHeight = 160,
  maxHeightClass = '',
  className = '',
}) {
  const ref = useRef(null)
  const [height, setHeight] = useState(null)

  useLayoutEffect(() => {
    if (!autoHeight || fill) return undefined
    const el = ref.current
    if (!el) return undefined

    const update = () => {
      const top = el.getBoundingClientRect().top
      const available = Math.floor(window.innerHeight - top - bottomOffset)
      setHeight(Math.max(minHeight, available))
    }

    update()
    const onResize = () => requestAnimationFrame(update)
    window.addEventListener('resize', onResize)
    const ro = new ResizeObserver(onResize)
    if (el.parentElement) ro.observe(el.parentElement)

    return () => {
      window.removeEventListener('resize', onResize)
      ro.disconnect()
    }
  }, [autoHeight, fill, bottomOffset, minHeight])

  const style =
    autoHeight && !fill && height != null ? { height, maxHeight: height } : undefined

  return (
    <div
      ref={ref}
      className={[
        'overflow-auto',
        fill ? 'min-h-0 flex-1' : null,
        !fill && !autoHeight ? maxHeightClass : null,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      style={style}
    >
      {children}
    </div>
  )
}

export const stickyTheadClass =
  'sticky top-0 z-10 bg-slate-50 text-[var(--aal-muted)] shadow-[0_1px_0_0_var(--aal-line)] dark:bg-[#1a1f2e]'
