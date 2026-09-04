/**
 * Muscle heatmap — anatomical front/back figures with primary (red) and
 * secondary (amber) muscle groups plus leader-line set callouts, modelled on
 * the COROS / Garmin strength activity screens.
 *
 * Geometry lives in a 440 x 468 viewBox ("-40 18 440 468"). The figure is
 * centred on x = 180; the 40px bleed on each side is callout label space.
 */

const PRIMARY = '#ef4444'
const SECONDARY = '#f59e0b'
const BODY_FILL = 'color-mix(in srgb, var(--aal-muted) 24%, transparent)'
const BODY_STROKE = 'color-mix(in srgb, var(--aal-muted) 50%, transparent)'
const MUSCLE_IDLE = 'color-mix(in srgb, var(--aal-muted) 36%, transparent)'
const LEADER = 'color-mix(in srgb, var(--aal-muted) 55%, transparent)'

const LABEL_LEFT_X = 92
const LABEL_RIGHT_X = 268

/* ---------------------------------------------------------------- body --- */

const BODY_PARTS = [
  // neck
  'M168 68h24v22c-8 6-16 6-24 0z',
  // torso: broad shoulders tapering to the waist, flaring at the hips
  'M180 86C200 86 218 91 229 100C239 110 243 124 241 140C238 160 230 178 224 196C220 208 218 220 217 230C216 242 208 250 180 250C152 250 144 242 143 230C142 220 140 208 136 196C130 178 122 160 119 140C117 124 121 110 131 100C142 91 160 86 180 86Z',
  // left arm
  'M126 100C112 106 104 122 102 142C100 162 102 180 105 195C104 214 101 238 100 258C99 274 101 288 106 296C112 299 118 296 120 288C120 268 120 246 122 228C124 208 128 190 131 172C135 148 136 118 133 102Z',
  // right arm
  'M234 100C248 106 256 122 258 142C260 162 258 180 255 195C256 214 259 238 260 258C261 274 259 288 254 296C248 299 242 296 240 288C240 268 240 246 238 228C236 208 232 190 229 172C225 148 224 118 227 102Z',
  // left leg
  'M146 232C137 254 133 288 136 322C137 336 141 346 144 354C145 372 142 400 142 424C141 440 142 452 145 458L174 458C175 440 174 418 175 398C177 374 179 358 179 330C179 296 178 262 176 234Z',
  // right leg
  'M214 232C223 254 227 288 224 322C223 336 219 346 216 354C215 372 218 400 218 424C219 440 218 452 215 458L186 458C185 440 186 418 185 398C183 374 181 358 181 330C181 296 182 262 184 234Z',
]

/* ------------------------------------------------------------- muscles --- */

// Deltoid caps, upper-arm bellies and calves are shared by both views.
const DELTS =
  'M144 98C132 93 120 100 115 112C111 124 113 136 118 143C128 145 137 139 142 129C145 119 145 106 144 98Z' +
  'M216 98C228 93 240 100 245 112C249 124 247 136 242 143C232 145 223 139 218 129C215 119 215 106 216 98Z'
const UPPER_ARM =
  'M121 142C113 146 107 157 106 170C106 181 109 190 114 193C119 192 122 185 123 175C124 162 123 149 121 142Z' +
  'M239 142C247 146 253 157 254 170C254 181 251 190 246 193C241 192 238 185 237 175C236 162 237 149 239 142Z'
const CALVES =
  'M147 366C141 374 139 390 140 406C141 418 146 427 152 428C158 427 162 418 162 406C162 388 156 368 147 366Z' +
  'M213 366C219 374 221 390 220 406C219 418 214 427 208 428C202 427 198 418 198 406C198 388 204 368 213 366Z'

// Rectus abdominis drawn as a six-pack grid so it reads as muscle, not a slab.
const ABS = [
  [157, 156, 19],
  [182, 156, 19],
  [157, 178, 19],
  [182, 178, 19],
  [157, 200, 22],
  [182, 200, 22],
]
  .map(
    ([x, y, h]) =>
      `M${x + 4} ${y}h13a4 4 0 0 1 4 4v${h - 8}a4 4 0 0 1-4 4h-13a4 4 0 0 1-4-4v${-(h - 8)}a4 4 0 0 1 4-4z`,
  )
  .join('')

const FRONT_MUSCLES = [
  { id: 'shoulders', d: DELTS },
  {
    id: 'chest',
    d:
      'M177 103C164 101 150 105 143 114C138 124 139 138 145 146C155 152 168 150 175 142C178 132 178 114 177 103Z' +
      'M183 103C196 101 210 105 217 114C222 124 221 138 215 146C205 152 192 150 185 142C182 132 182 114 183 103Z',
  },
  { id: 'biceps', d: UPPER_ARM },
  { id: 'abs', d: ABS },
  {
    id: 'obliques',
    d:
      'M152 162C146 164 143 170 143 178v34c0 8 4 14 10 15c3-1 4-4 4-9v-56c0-4-2-5-5-4z' +
      'M208 162C214 164 217 170 217 178v34c0 8-4 14-10 15c-3-1-4-4-4-9v-56c0-4 2-5 5-4z',
  },
  {
    id: 'hip_flexors',
    d:
      'M152 236C161 233 170 233 176 235C177 242 176 250 174 254C167 252 159 253 153 256C150 252 149 241 152 236Z' +
      'M208 236C199 233 190 233 184 235C183 242 184 250 186 254C193 252 201 253 207 256C210 252 211 241 208 236Z',
  },
  {
    id: 'quads',
    d:
      'M158 258C148 262 141 278 140 300C139 320 143 336 149 344C156 343 161 334 162 318C163 298 162 274 158 258Z' +
      'M202 258C212 262 219 278 220 300C221 320 217 336 211 344C204 343 199 334 198 318C197 298 198 274 202 258Z',
  },
  {
    id: 'adductors',
    d:
      'M172 260C167 268 165 286 166 304C167 316 170 322 173 322C175 320 176 312 176 300v-40z' +
      'M188 260C193 268 195 286 194 304C193 316 190 322 187 322C185 320 184 312 184 300v-40z',
  },
  { id: 'calves', d: CALVES },
]

const BACK_MUSCLES = [
  { id: 'shoulders', d: DELTS },
  {
    id: 'upper_back',
    d: 'M180 92C198 92 214 97 224 106C228 122 226 142 220 160C214 178 204 190 196 194L164 194C156 190 146 178 140 160C134 142 132 122 136 106C146 97 162 92 180 92Z',
  },
  { id: 'triceps', d: UPPER_ARM },
  {
    id: 'lower_back',
    d: 'M167 198h26a8 8 0 0 1 8 8v26a8 8 0 0 1-8 8h-26a8 8 0 0 1-8-8v-26a8 8 0 0 1 8-8z',
  },
  {
    id: 'glutes',
    d:
      'M178 234C166 232 152 236 147 246C143 258 145 272 153 278C164 281 176 276 178 266Z' +
      'M182 234C194 232 208 236 213 246C217 258 215 272 207 278C196 281 184 276 182 266Z',
  },
  {
    id: 'hamstrings',
    d:
      'M158 284C148 288 141 304 140 324C139 338 142 348 148 352C155 351 160 342 161 326C162 308 161 292 158 284Z' +
      'M202 284C212 288 219 304 220 324C221 338 218 348 212 352C205 351 200 342 199 326C198 308 199 292 202 284Z',
  },
  { id: 'calves', d: CALVES },
]

/* Leader lines. `from` is where the dotted line leaves the muscle; entries are
   ordered top-to-bottom per side so the lines never cross. */
const FRONT_CALLOUTS = [
  { id: 'shoulders', side: 'left', y: 112, from: 118 },
  { id: 'chest', side: 'left', y: 134, from: 146 },
  { id: 'abs', side: 'left', y: 190, from: 160 },
  { id: 'quads', side: 'left', y: 300, from: 142 },
  { id: 'biceps', side: 'right', y: 168, from: 252 },
  { id: 'obliques', side: 'right', y: 202, from: 216 },
  { id: 'hip_flexors', side: 'right', y: 246, from: 208 },
  { id: 'adductors', side: 'right', y: 296, from: 192 },
  { id: 'calves', side: 'right', y: 400, from: 216 },
]

const BACK_CALLOUTS = [
  { id: 'shoulders', side: 'left', y: 112, from: 118 },
  { id: 'upper_back', side: 'left', y: 150, from: 140 },
  { id: 'lower_back', side: 'left', y: 218, from: 160 },
  { id: 'hamstrings', side: 'left', y: 318, from: 142 },
  { id: 'triceps', side: 'right', y: 168, from: 252 },
  { id: 'glutes', side: 'right', y: 258, from: 211 },
  { id: 'calves', side: 'right', y: 400, from: 216 },
]

function BodyFigure({ side, regions }) {
  const muscles = side === 'front' ? FRONT_MUSCLES : BACK_MUSCLES
  const callouts = (side === 'front' ? FRONT_CALLOUTS : BACK_CALLOUTS).filter(
    (c) => regions?.[c.id],
  )

  return (
    <figure className="m-0 flex flex-col items-center">
      <svg
        viewBox="-40 18 440 468"
        className="w-full max-w-[430px]"
        role="img"
        aria-label={`${side} muscle heatmap`}
      >
        <g fill={BODY_FILL} stroke={BODY_STROKE} strokeWidth="1.5" strokeLinejoin="round">
          <ellipse cx="180" cy="52" rx="21" ry="26" />
          {BODY_PARTS.map((d) => (
            <path key={d.slice(0, 12)} d={d} />
          ))}
          <ellipse cx="158" cy="461" rx="13" ry="7" />
          <ellipse cx="202" cy="461" rx="13" ry="7" />
        </g>

        <g>
          {muscles.map((m) => {
            const info = regions?.[m.id]
            const fill = !info ? MUSCLE_IDLE : info.role === 'primary' ? PRIMARY : SECONDARY
            return (
              <path
                key={`${side}-${m.id}`}
                d={m.d}
                fill={fill}
                opacity={info ? 0.95 : 0.5}
                stroke={info ? 'rgba(255,255,255,0.3)' : 'none'}
                strokeWidth="0.8"
              >
                <title>
                  {info ? `${info.label}: ${info.sets} set(s)` : m.id.replace(/_/g, ' ')}
                </title>
              </path>
            )
          })}
        </g>

        <g>
          {callouts.map((c) => {
            const info = regions[c.id]
            const isLeft = c.side === 'left'
            const labelX = isLeft ? LABEL_LEFT_X : LABEL_RIGHT_X
            return (
              <g key={`${side}-cal-${c.id}`}>
                <line
                  x1={c.from}
                  y1={c.y}
                  x2={isLeft ? labelX + 6 : labelX - 6}
                  y2={c.y}
                  stroke={LEADER}
                  strokeWidth="1"
                  strokeDasharray="3 3"
                />
                <circle
                  cx={c.from}
                  cy={c.y}
                  r="2.6"
                  fill={info.role === 'primary' ? PRIMARY : SECONDARY}
                />
                <text
                  x={labelX}
                  y={c.y + 4}
                  textAnchor={isLeft ? 'end' : 'start'}
                  style={{ fontSize: '12.5px', fontVariantNumeric: 'tabular-nums' }}
                >
                  <tspan fill="var(--aal-ink)" fontWeight="600">
                    {info.label}
                  </tspan>
                  <tspan fill="var(--aal-muted)" dx="5">
                    {info.sets}
                  </tspan>
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      <figcaption className="mt-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--aal-muted)]">
        {side}
      </figcaption>
    </figure>
  )
}

export default function MuscleHeatmap({ muscleMap }) {
  const regions = muscleMap?.regions
  if (!regions || !Object.keys(regions).length) return null

  return (
    <section className="overflow-hidden rounded-xl border border-[var(--aal-line)] bg-[var(--aal-card)]">
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-[var(--aal-line)] px-4 py-2.5">
        <div>
          <h3 className="text-sm font-semibold text-[var(--aal-ink)]">Muscle heatmap</h3>
          <p className="text-[11px] text-[var(--aal-muted)]">Sets per muscle group</p>
        </div>
        <div className="flex items-center gap-4 text-[11px] text-[var(--aal-muted)]">
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: PRIMARY }} />
            Primary
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: SECONDARY }} />
            Secondary
          </span>
        </div>
      </header>

      <div className="grid grid-cols-2 gap-2 px-2 py-3 sm:gap-6 sm:px-5">
        <BodyFigure side="front" regions={regions} />
        <BodyFigure side="back" regions={regions} />
      </div>
    </section>
  )
}
