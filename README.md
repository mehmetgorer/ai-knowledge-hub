# AI Knowledge Hub

Independent, professional AI-powered document intelligence platform.

## Phase 1A — Frontend foundation

This repository is an npm monorepo. The web application lives in `apps/web` (Next.js App Router, TypeScript, Tailwind CSS, ESLint).

## Prerequisites

- Node.js 20+
- npm 10+

## Commands

From the repository root:

| Command        | Description                          |
| -------------- | ------------------------------------ |
| `npm install`  | Install dependencies (uses lockfile)   |
| `npm run dev`  | Start Next.js dev server (`apps/web`) |
| `npm run lint` | Run ESLint                           |
| `npm run typecheck` | Run TypeScript (`tsc --noEmit`) |
| `npm run build` | Production build for `apps/web`     |

The dev server runs at [http://localhost:3000](http://localhost:3000).

## Project layout

```
.
├── apps/
│   └── web/          # Next.js frontend
├── docs/
│   └── HANDOFF.md    # Implementation notes and next steps
├── package.json      # Workspace root
└── package-lock.json
```

See `docs/HANDOFF.md` for what is implemented and what comes next.
