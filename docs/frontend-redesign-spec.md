# Skill2Job Frontend Redesign — Design System Specification

> Single source of truth for the "Futuristic AI Premium + Clean SaaS + Subtle
> Glassmorphism" redesign. Every page and component must follow this spec.

## 1. Vision

- **Look:** premium SaaS (Linear / Vercel / Stripe quality) with a blue-violet
  brand identity, subtle frosted-glass surfaces, layered soft shadows,
  generous spacing, and quiet micro-interactions.
- **Feel:** calm, spacious, high-contrast text, low-noise chrome, consistent
  rhythm (4/8px grid).
- **Motion:** short (150–400ms), eased (`ease-smooth`), never bouncy. Loading
  uses skeletons, not spinners, on page level.

## 2. Design tokens (already configured in `tailwind.config.js`)

### Colors
| Token | Use |
|---|---|
| `primary-50..950` | Brand blue-violet. `primary-600` (#5557e6) is the primary action color. |
| `gray-50..950` | Cool slate neutrals. `gray-900` headings, `gray-700` body, `gray-500` muted, `gray-400` subtle, `gray-200` borders, `gray-100` subtle fills. |
| `ink` / `ink-muted` / `ink-subtle` | Semantic aliases of gray-900/600/400 for text. |
| Status colors | `emerald` (success), `amber` (warning), `red`/`rose` (danger), `sky`/`blue` (info), `violet`/`purple` (AI features). Use at 50/100 backgrounds, 600/700 text. |

### Gradients (`backgroundImage` tokens)
- `bg-brand-gradient` — the signature blue→violet diagonal gradient (buttons, hero, active nav).
- `bg-brand-gradient-strong` — darker variant for large hero surfaces.
- `bg-brand-gradient-soft` — 14% opacity tint (soft panels).
- `bg-surface-mesh` — already applied to `<body>`; do not re-add.

### Typography
- Body: **Inter** (already global). Headings: `font-display` = **Sora**.
  Use `font-display` for page titles and big numbers only.
- Page title: `page-title` class (or `font-display text-2xl sm:text-3xl font-bold tracking-tight`).
- Muted copy: `text-sm text-gray-500`.
- Overlines/labels: `section-label` class.

### Shadows (indigo-tinted, layered)
`shadow-xs`, `shadow` , `shadow-soft`, `shadow-md`, `shadow-lg`, `shadow-xl`,
`shadow-card`, `shadow-elevated`, `shadow-glow`, `shadow-glow-sm`.
Cards use `shadow-card`/`shadow-soft`; hover states may upgrade to `shadow-lg`.

### Radii
`rounded-lg` = 0.75rem (default for controls), `rounded-xl` = 1rem (cards),
`rounded-2xl` = 1.25rem (modals/hero), `rounded-full` for pills.

### Motion
Utilities: `animate-fade-up`, `animate-fade-in`, `animate-scale-in`,
`animate-entrance`, `animate-shimmer`, `animate-pulse-soft`, `animate-float`.
Use `transition-all duration-200` (or duration-300) on interactive elements.
Respect `prefers-reduced-motion` (global CSS already does).

## 3. Component classes (defined in `src/index.css`)

### Surfaces
- `card` — standard frosted white card (`card p-6`, add `card-hover` for lift).
- `card-solid` — opaque white for tables/dropdowns/modals.
- `glass` — more transparent frosted surface.
- `panel-brand` — soft brand-tinted callout panel.
- `panel-dark` — brand-gradient panel with white text.

### Page structure
- `.page-header` + `.page-title` + `.page-subtitle` — the canonical page head:
  ```tsx
  <div className="page-header">
    <div>
      <h1 className="page-title">Jobs</h1>
      <p className="page-subtitle">Manage your open roles</p>
    </div>
    <div className="flex gap-2">{/* actions */}</div>
  </div>
  ```
- `.section-title`, `.section-label`, `.divider`, `.kpi-value`, `.text-gradient`.

### Buttons
Raw usage on any `<button>`/`<Link>`: `btn-primary`, `btn-secondary`,
`btn-ghost`, `btn-danger` + size `btn-sm|btn-md|btn-lg`.
The shared `<Button>` component (components/ui/Button) uses the same tokens —
prefer it inside existing pages that already import it.

### Forms
- `field-label` for labels; `field` on `input`/`select`/`textarea`;
  add `field-error` when invalid; `field-hint` for helper text.
- Page-local forms that don't use the shared Input must still use `field` /
  `field-label` so focus rings and borders match.

### Badges & chips
`badge-primary | badge-success | badge-warning | badge-danger | badge-info |
badge-neutral` (status pills), `chip` (interactive/filter pills).

### Tables
```tsx
<div className="table-wrap">
  <table className="data-table">
    <thead><tr><th>Name</th><th>Status</th></tr></thead>
    <tbody><tr><td>…</td><td>…</td></tr></tbody>
  </table>
</div>
```
Never leave tables as raw `bg-white` blocks — always wrap.

### States
- Loading: `.skeleton h-4 w-40` blocks (or keep `LoadingSpinner` for inline).
- Empty: `.empty-state` container (icon + title + description + action).
- Errors: `.error-banner`; success: `.success-banner`; info: `.info-banner`.

### Navigation
`.nav-link` (+ `.nav-link-active`) for tabs/in-page nav.

## 4. Layout conventions

- Page root: `<div className="space-y-6 animate-fade-up">`.
- Grids: `grid gap-4 sm:gap-6 grid-cols-1 md:grid-cols-2 xl:grid-cols-3`
  (responsive, always: 1 column on mobile).
- Stat tiles: `card p-5` with icon in `rounded-xl p-2.5 bg-primary-50 text-primary-600`
  tinted well (rotate tint: emerald/amber/red/sky/violet per meaning).
- Max content width is enforced by AppLayout (`max-w-[1400px]`); do not add
  page-level max-width.
- Header/Sidebar are frosted (`bg-white/70 backdrop-blur-xl`) — do not add
  page chrome that duplicates them (no extra top bars).

## 5. Hard rules (NON-NEGOTIABLE)

1. **Preserve all functionality.** Only change JSX structure + classNames.
   Never change: props, state, effects, API calls, event handlers, form
   `onSubmit` logic, validation logic, `navigate()` targets, route paths,
   data-testid attributes, aria-labels, or exported names.
2. **Preserve all user-visible text** (headings, labels, messages, buttons
   copy). You may *add* decorative elements (icons, dividers) but never remove
   information.
3. **Do not edit files outside your assigned list.** Shared components and
   other groups are owned by others; editing them creates conflicts.
4. **Keep TypeScript strict-clean**: no unused imports/locals (`noUnusedLocals`
   is on), no implicit any. Verify with `npx tsc --noEmit` and fix errors only
   in your files (other groups may be mid-flight; ignore their errors).
5. **Run your group's tests** at the end:
   `npx vitest run <path/to/your.test.tsx> …` — all must pass. If a test
   asserts on rendered structure you changed, adapt the *styling* (not the
   assertion); tests are the spec.
6. **Only use tokens/classes from this spec.** If you need a new utility,
   compose existing tokens (e.g., `bg-gradient-to-br from-primary-500 to-violet-500`)
   instead of inventing names. `slate-*` palette is tolerated but prefer `gray-*`.
7. **No new dependencies.** `lucide-react` is available for icons — prefer it
   for empty states and feature icons; keep existing inline SVGs working.
8. **Loading, empty, error, validation, hover, focus and disabled states** all
   must be styled per this spec (requirement #5 of the redesign brief).

## 6. Recipe examples

### Card with header + action
```tsx
<div className="card p-6">
  <div className="mb-4 flex items-center justify-between">
    <h2 className="section-title">Recent Activity</h2>
    <Link className="text-sm font-medium text-primary-600 hover:text-primary-700" to="…">View all</Link>
  </div>
  …
</div>
```

### Stat tile
```tsx
<div className="card card-hover p-5">
  <div className="flex items-start justify-between">
    <div className="min-w-0">
      <p className="text-sm font-medium text-gray-500">Applications</p>
      <p className="mt-1.5 font-display text-2xl font-bold text-gray-900">128</p>
      <p className="mt-1 text-xs text-emerald-600">+12% this week</p>
    </div>
    <div className="rounded-xl bg-primary-50 p-2.5 text-primary-600"><Icon className="h-5 w-5" /></div>
  </div>
</div>
```

### Page loading / empty / error
```tsx
if (loading) return (
  <div className="space-y-4">
    <div className="skeleton h-8 w-56" />
    <div className="skeleton h-40 w-full" />
  </div>
);
if (error) return <div className="error-banner">{error}</div>;
if (!data.length) return (
  <div className="empty-state">
    <FileText className="mb-3 h-10 w-10 text-gray-300" />
    <h3 className="text-base font-semibold text-gray-900">No applications yet</h3>
    <p className="mt-1 text-sm text-gray-500">Apply to jobs to see them here.</p>
  </div>
);
```

### Modal
```tsx
<div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-950/40 p-4 backdrop-blur-sm">
  <div className="card-solid w-full max-w-lg animate-scale-in p-6">
    <h2 className="section-title">Confirm</h2>
    …
  </div>
</div>
```
