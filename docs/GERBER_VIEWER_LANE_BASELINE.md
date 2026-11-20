# Gerber viewer lane functional baseline

Adopted by the user on 2026-11-21. This narrative is the foundation for functionality definitions in this new lane. Architecture choices must support these interactions. This records the agreed direction; it does not establish implementation or qualification.

## Viewer experience

One Gerber canvas shows the current result. Preserve zoom and position across slice updates and briefly highlight the affected region.

- Layer visibility controls and an active layer.
- Click selection with a highlighted boundary and a small collapsible inspector for identity, layer and dimensions. Preserve source identities; component, pin and net labels require qualified mappings.
- A Show changes toggle: green additions and pink removals; switching it off restores the clean current result.
- Fit board and Fit latest change actions.
- A compact status strip showing slice, revision and Preview, Verified or Failed status. Verification remains scoped to its retained evidence.
- Follow latest change controls automatic camera movement. With it disabled, incoming updates preserve the inspection viewport.
- Previous and Current revisions toggle within the same canvas.
- Logs and evidence remain behind a Details control.

The first version enables seeing the result, locating changes, inspecting objects and understanding status. Geometry editing is a separate scope.

## Coding chat integration

Use a versioned project-local ABI rather than MCP. The chat publishes slice-result bundles; a native host validates them and updates the canvas. Selection messages can return through the ABI for the chat to read on its next tool call.

Begin with recoverable snapshots and affected-region updates. Bundles bind job, slice, revision, parent revision, stable object identities, geometry, affected bounds, layers, source hashes, evidence paths and verification status. Publish complete payloads before atomically publishing their manifest. Redraw affected underlying geometry as well as changed objects, including removal and polarity effects.

## Application foundation

Retain ResearchWorkspace's current application framework and extensibility for Apple Intelligence and future local models. Reuse appropriate Mac/iOS lifecycle, concurrency, state ownership, platform integration and model-provider interfaces after a bounded read-only architecture review. The current implementation and extraction feasibility remain to be verified.

Create a separate Gerber viewer identity and data model. Research content, databases, prompts, account state and unrelated services are outside the reuse scope. A native host with a reusable web rendering canvas is the initial architectural direction; renderer performance must be measured on representative boards.

Rendering and inspection operate independently of model availability. Future models can explain selected geometry or propose structured operations; engineering execution and verification govern geometry changes and verified results.

## Scope and custody

The user subsequently authorized a viewer branch and implementation on 2026-11-21; see GERBER_VIEWER_IMPLEMENTATION.md. Cross-project modification and new CAM engineering qualification remain outside this lane. Preserve existing PCB acceptance and frozen evidence. All future engineering artifacts, caches and tests follow the project's LaCie storage policy.
