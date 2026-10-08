# Wontology UI

The UI uses Wagner Design System V1, **The Score**, in its light manuscript register. Its source is `wagner_frontend/app/globals.css` and `components/diagram/estate-canvas.tsx`, extracted for this standalone application.

| Role | Token | Value |
| --- | --- | --- |
| Canvas | `--score-pitch` | `#F7F6FA` |
| Surface | `--score-surface` | `#FFFFFF` |
| Hover | `--score-surface-2` | `#F1EFF8` |
| Primary text | `--score-frost` | `#0A0A14` |
| Body text | `--score-muted` | `#2A2D33` |
| Metadata | `--score-whisper` | `#6B6E75` |
| Accent | `--score-violet` | `#6A35FF` |
| Rules | `--score-rule` | `rgba(10,10,20,.12)` |
| Confirmed success | `--score-resolve` | `#2C7A4D` |

Inter carries UI and labels, Space Grotesk the wordmark, and Instrument Serif page and dialog titles. Fonts are bundled locally under the SIL Open Font License; no font service is contacted. Monospace is reserved for code and identifiers.

The default canvas preserves Wagner's region → network → service → resource navigation, breadcrumbs, relationship curves, resource search and atlas. Small toolbar controls use 6px corners; graph nodes use 2px corners. The optional full topology view supports pan, zoom, filters and exported SVG diagrams. Both views share the resource evidence inspector.

The canvas groups only observed resources. Network placement follows explicit containment, deployment and attachment evidence; ambiguous membership has its own bucket. Shared network placement never creates an application dependency. Gray means health unassessed. Service edges aggregate observed relationships; the inspector and JSON preserve their kinds and evidence.
