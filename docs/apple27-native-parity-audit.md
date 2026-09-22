# Apple-27 native-parity audit (A0)

Date: 22 September 2026. Repository: `wenn-id/beeloftone`.
Baseline: **`7a76b415e6750fc06a80a050fe801ec3a5c46613`** (`origin/main`, fetched during this audit).
Branch: `docs/apple27-native-parity-a0`.
Scope: current-state evidence and integration design. No A1 implementation.

## 1. Baseline, method, and limits

The supplied baseline is still the latest fetched main. The original checkout was clean and 47 commits behind; this branch was created directly from `origin/main`, without resetting local main or discarding work. `gh pr list --state open` returned no open PRs. Recent main includes business-readiness documentation/tests through PR #86. Relevant merged frontend history is navigation A-G through `0efb111` (#17), M1 `65fb288` (#19), M2 `31447f6` (#20), M3 `49addbb` (#21), M4 `50b44a3` (#22), M5 `6806338` (#23), M6 `f8921e7` (#25), and the first-paint test correction `97815b8` (#69). These are history observations, not claims that old CI verifies this audit.

| Fact | Evidence |
|---|---|
| App 0.97.0, Python >=3.12 | [pyproject.toml](../pyproject.toml), project metadata |
| Protected main | GitHub branch API returned `protected: true` and the same full baseline SHA during A0 |
| Schema 55 | [rework_completions.sql](../beeloft/rework_completions.sql), final `PRAGMA user_version=55`; migration dispatch in `Store.__init__` |
| FastAPI + vanilla HTML/CSS/ES modules | [api.py](../beeloft/api.py), the four static files below; no frontend framework/runtime dependency added |
| Existing design direction | [DESIGN.md](../DESIGN.md): Shopeers-derived operations workspace, 20px cards, smaller controls, real data, light/dark and reduced motion |
| Runtime isolation | Existing `tests/run_browser.py` creates a temporary demo SQLite database and loopback server, then removes them. Browser runs and the A0 measurement use this path; Python acceptance tests use their own disposable fixtures. No operational database was inspected. |

Evidence notation below uses baseline line numbers plus stable names. Source files: [app.mjs](../beeloft/static/app.mjs), [style.css](../beeloft/static/style.css), [index.html](../beeloft/static/index.html), [client.mjs](../beeloft/static/client.mjs). The [baseline tree](https://github.com/wenn-id/beeloftone/tree/7a76b415e6750fc06a80a050fe801ec3a5c46613) preserves those line references after later edits. Historical [navigation inventory](workspace-navigation-inventory.md), [navigation architecture](workspace-navigation-architecture.md), and [motion inventory](motion-interaction-inventory.md) were cross-checked against implementation; their historical assertions are not automatically current facts.

“Apple-27” is the product programme's target name here. This document recommends perceptual behavior for this web application; it does not assert access to Apple implementation details or exact native spring constants. The existing DESIGN.md remains unchanged in A0. A1 must explicitly reconcile its current radius/type/reference rules with the new direction.

## 2. Navigation truth and complete activation lifecycle

`workspaceDestinations` (`app.mjs:127`) maps 27 nav ids to 16 primary section hosts. `workspaceSections` (`:164`) includes those hosts plus internal `detail-view`, for 17 sections. The twelve analytics children account for the shared host. **Every persistent primary destination is a workspace page; no exception was found.** Backup activation does not download, and scanner activation does not open a dialog.

1. Direct sidebar `onclick` calls the feature's `show*` function or inline handler. `guardPending()` precedes activation in Command Center, the business queues, utilities, AI, integrations and audit. It is **not** a universal check inside `activateWorkspace()`: board/materials/people/products/activity and the twelve analytics show functions activate without this check. Native modal focus ordinarily blocks sidebar interaction during dialog recovery, while pending inline AI state is a distinct case. Preserve the actual call-site contract rather than claiming the router itself protects mutations; audit any future programmatic navigation against pending inline work. No guard changes are made in A0.
2. `activateWorkspace(navId, sectionId=workspaceDestinations[navId])` (`:227`) synchronously invalidates **every non-target section's** feature counters and sets its `hidden=true`, including sections already hidden. It reveals the target, sets module-level `view`, then calls `activeNavigation(navId)`.
3. `activeNavigation()` (`:119`) removes all sidebar `aria-current` attributes and sets the selected element's `aria-current="page"`. There is no separate active-nav model. `view` is the async workspace context; the attribute is the authoritative selected destination exposed to presentation/accessibility. Analytics additionally requires `analyticsReport` because `view==='analytics'` alone cannot distinguish reports. Internal order detail uses `view==='detail'` while retaining `board-home` selection.
4. When `enteredSection` is nonempty and differs from the target, `playEntryMotion(section)` runs. The first activation after login, same-section refresh, and analytics-to-analytics switching skip page entry. `enteredSection` is presentation history, not navigation truth.
5. If `body.nav-open` is set, `sidebar(false)` closes the drawer immediately, synchronizes `aria-expanded` and `inert`, and removes drawer entry state. The target `h1` gets `tabIndex=-1` and focus. If a dialog is open, focus is remembered on `menu-toggle` through `dialogReturnFocus` instead. Desktop activation does not move focus into the page.
6. The feature starts its data request after activation. For example, `showCommandCenter()` captures `epoch` and increments `commandCenterRequest`, requests `/api/command-center`, then checks epoch, request and `view` before rendering. Motion scheduling occurs before the fetch in this path; the comment above `motionMs()` should not be interpreted as an ordering guarantee that fetching already started.
7. `activateAnalyticsReport()` (`:263`) increments `analyticsRequest` even when the host did not change, sets `analyticsReport`, updates heading/eyebrow and replaces `analytics-body`. Each report's current predicate includes epoch, request, view and report identity; paged loaders also use local generation guards. Invalidation prevents stale painting; it does not abort the underlying fetch. `client.mjs` owns a separate 15-second AbortController deadline, unrelated to presentation timing.
8. Successful rendering clears the appropriate loading/busy state. Motion classes settle separately. Errors and stale responses follow existing feature paths; no request waits for transition completion.

Visibility belongs to `activateWorkspace()` for navigation; logout owns whole-workspace teardown. Entry presentation belongs to `playEntryMotion()` and CSS. Focus, invalidation, view, `aria-current`, request dispatch, recovery checks and committed results must never await a lens or spring. A lens can observe the selected id at the end of `activeNavigation()` without writing any of them.

## 3. All 27 primary destinations

Legend used in every row: **E** = section entry only after a different previously entered section; first login and same-section activation skip it. **EA** = E on entry from another host, no section entry between analytics children. **F** = mobile drawer selection focuses h1; desktop preserves control focus. **R** = shared shell: sticky sidebar above 980px, in-flow display-driven drawer at <=980px, wrapping headings/forms and contained tables at narrow widths. Role column describes destination access and representative mutation controls, not a replacement authorization specification; server permissions remain authoritative.

| Nav id | Label | Section id | Renderer / loader | Request counter | Analytics shared host | Entry | Responsive | Roles | Focus |
|---|---|---|---|---|---|---|---|---|---|
| `command-center` | Command center | `command-center-view` | `showCommandCenter` | `commandCenterRequest` | No | E | R; business/operations grids collapse at 980, rails 760 | All; read-only dashboard | F |
| `board-home` | Produksi | `board-view` | `showBoard` / `loadBoard` | `boardRequest` | No | E | R; bounded 1360px container; 48/30/19rem container queries govern rows/filters/KPIs | All; new order admin, mutations follow role | F; detail Back focuses `search` |
| `materials` | Bahan baku | `materials-view` | `showMaterials` / `loadMaterials` | `materialsRequest` | No | E | R; wrapping batch cards/paging | All; receive hidden for viewer | F |
| `workforce` | People | `people-view` | `showPeople` / `loadPeople` | `peopleRequest` | No | E | R; summary auto-fit min118px (104px <=650); rows stack at 650 | All; add employee admin, attendance non-viewer | F |
| `scan-bundle` | Scan bundle | `bundle-scan-view` | `showScanner('bundle')` | `scanRequest` (shared scanners) | No | E | R; scan form/result reflow | All; read lookup | F; desktop code input; result selects code |
| `scan-finished-goods` | Scan barang jadi | `finished-goods-scan-view` | `showScanner('finished-goods')` | `scanRequest` | No | E | R; scan form/result reflow | All; read lookup | F; desktop code input; result selects code |
| `products` | Master SKU | `products-view` | `showProducts` / `loadProducts` / `paintProducts` | `productsRequest` | No | E | R; wrapping product actions | All; SKU/BOM/mapping writes admin | F; per-keystroke local search does not animate |
| `wip-ageing-insights` | WIP ageing | `analytics-view` | `showWipAgeingInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `capacity-plan` | Kapasitas produksi | `analytics-view` | `showCapacityPlan` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All; capacity master edits admin | F |
| `production-quality-insights` | Kualitas produksi | `analytics-view` | `showProductionQualityInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `supplier-performance-insights` | Kinerja supplier | `analytics-view` | `showSupplierPerformanceInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `material-price-insights` | Harga bahan | `analytics-view` | `showMaterialPriceInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `purchase-commitment-insights` | Komitmen PO | `analytics-view` | `showPurchaseCommitmentInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `demand-forecast` | Forecast demand | `analytics-view` | `showDemandForecast` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `replenishment` | Rekomendasi stok | `analytics-view` | `showReplenishment` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `size-demand-insights` | Analisis ukuran | `analytics-view` | `showSizeDemandInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `return-insights` | Analisis retur | `analytics-view` | `showReturnInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `dead-stock-insights` | Dead stock | `analytics-view` | `showDeadStockInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `stock-adjustment-insights` | Audit adjustment | `analytics-view` | `showStockAdjustmentInsights` | `analyticsRequest` | Yes | EA | R; shared report forms/results | All | F |
| `ai-brain` | Tanya Beeloft | `ai-view` | `showAi` / `loadAiHistory`; investigation submit | `aiRequest`, `aiHistoryRequest` | No | E | R; form, disclosure and result/history blocks | All read; viewer cannot submit investigation | F; history jump scrolls/focuses history input |
| `integrations` | Integrasi | `integrations-view` | `showIntegrations` / `loadIntegrations` | `integrationsRequest` | No | E | R; wrapping status cards | All read; source operations retain own restrictions | F |
| `activity` | Laporan aktivitas | `activity-view` | inline `activity.onclick` / `loadActivity` | `activityRequest` | No | E | R; activity rows stack at 600 | All; authenticated export | F |
| `audit-trail` | Audit trail | `audit-view` | `showAuditEvents` / `loadAuditEvents` | `auditRequest` | No | E | R; filter/list/cursor paging | Admin nav; server guards audit reads | F |
| `backup` | Cadangan data | `backup-view` | inline `backup.onclick`, then `download-backup.onclick` | `backupRequest` | No | E | R; wrapping download control | Admin; handler also checks admin | F |
| `purchase-requests` | Permintaan pembelian | `purchase-requests-view` | `showPurchaseRequests` / `loadPurchaseRequests` | `purchaseRequestsRequest` | No | E | R; filter/list/cursor paging | All read; create non-viewer; decisions retain domain rules | F |
| `marketing-budgets` | Budget marketing | `marketing-budgets-view` | `showMarketingBudgets` / `loadMarketingBudgets` | `marketingBudgetsRequest` | No | E | R; filter/list/cursor paging | All read; create non-viewer; decisions retain domain rules | F |
| `approvals` | Inbox approval | `approvals-view` | `showApprovals` / `loadApprovals` | `approvalsRequest` | No | E | R; offset paging; nav is sticky CTA child | All read; decisions retain role/actor rules | F |

Inventory evidence: static sidebar markup, registries at `app.mjs:127-182`, handlers at `:617`, `:747`, `:1015`, `:1315`, `:1670`, `:1742`, `:1963`, `:3125`, `:3527`, analytics registry `:4590`, business loaders `:4659-4818`, backup `:5334`. `browser_navigation_foundation.cjs` compares the sidebar button ids with the destination set and sweeps admin/operator/viewer, including hidden audit/backup for non-admins. Exact label/id agreement is also encoded in `browser_motion_consistency.cjs:11-39`.

## 4. Confirmed current gaps

Scope of negative search: all `beeloft/static` files, then inspection of shell, navigation and dialog code. Absence is scoped to the merged web frontend, not external Apple technology.

| Proposed gap | Status | Evidence / distinction |
|---|---|---|
| Backdrop-filter glass system | CONFIRMED_ABSENT | No `backdrop-filter`, blur/filter declarations in static assets; shell surfaces are opaque token colors. |
| Formal glass/material tokens | PARTIAL | `--surface`, `--surface-subtle`, `--surface-sunken` and shadow tokens exist; no optical/translucency/fallback material tier. |
| Shared liquid navigation lens | CONFIRMED_ABSENT | Selection is per-item background plus `.nav-item[aria-current=page]::before`; no lens node/controller. |
| Spring physics engine | CONFIRMED_ABSENT | Timing curves are cubic-bezier CSS; progress RAF is linear time interpolation. |
| Velocity preservation on retarget | CONFIRMED_ABSENT | Entry restarts classes; progress restarts from prior payload; no velocity state. |
| One physical indicator across destinations | CONFIRMED_ABSENT | Separate pseudo-element generated on selected nav; approval CTA is not `.nav-item`. |
| WAAPI physical controller | CONFIRMED_ABSENT | No product `.animate()` calls or Animation controller. Tests' `getAnimations()` inspect CSS effects. |
| WebGPU/WebGL refraction | CONFIRMED_ABSENT | No rendering contexts or GPU pipeline; inline SVG is used for glyphs/charts. |
| Apple-style sheet/popover architecture | PARTIAL | Native `<dialog>` already handles focused tasks and modal accessibility; no sheet detents or Popover API layer. |
| Apple-native control primitive layer | PARTIAL | Native buttons/inputs/select/details/progress and shared CSS primitives exist, with current Shopeers styling. No Apple control contract. |
| “No motion / CSS-only reduced motion” historical premise | SUPERSEDED | M1-M6 and the JS `reducedMotionQuery` are present. M0 evidence stays historical. |

## 5. Existing motion inventory

Canonical tokens (`style.css:61-63`): instant 80ms, fast 120ms, base 180ms, enter 220ms, dialog 260ms, slow 320ms. Standard `cubic-bezier(.22,1,.36,1)`, enter `(.16,1,.3,1)`, exit `(.4,0,1,1)`. These are theme-invariant. Below, “clear entry” means the per-node RAF/timer cleanup in section 6. “No” in the final column means presentation itself does not block input; business busy locks still apply.

| Class / trigger | Owner and properties | Timing / easing | Interruption and cleanup | Reduced motion / accessibility | Blocks? | Decision |
|---|---|---|---|---|---|---|
| CONTROL_FEEDBACK: hover/press | CSS `button,.nav-item,.nav-summary`; background/border/text; `button:active:not(:disabled)` scale .985 | fast colors, instant scale / standard | Browser retargets; pseudo-state release; no JS ownership | Movement omitted; enabled/disabled semantics and instant focus ring remain | No | KEEP |
| CONTROL_FEEDBACK: selected nav / glyph | CSS `[aria-current=page]`, `.nav-item .icon,.nav-summary .icon`; color/background/border, press scale | base colors, instant scale / standard | Attribute changes immediately; old pseudo-marker disappears | `aria-current` unchanged; color changes instantaneous | No | REPLACE_PRESENTATION_ONLY for marker; KEEP semantics |
| OTHER: analytics disclosure | CSS `.nav-summary .nav-caret`; rotation -180deg/0 and color | base / standard | Native details toggles immediately, CSS retargets; no height animation | Rotation snaps to correct state; native summary keyboard behavior | No | KEEP |
| PAGE_ENTRY: different workspace host | `activateWorkspace` -> `playEntryMotion`, `.workspace-main>section.motion-enter[.is-ready]`; opacity 0->1, translateY 6->0 | enter / enter | Target restarts clear entry; prior hidden host can finish bounded cleanup | JS skips classes/RAF; section, heading and nav are immediately correct | No | EXTEND at existing seam, no second router |
| DRAWER: menu open | `sidebar` + `.nav-open .app-sidebar.motion-enter`; opacity, translateY -6->0 | enter / enter | Close is instant; clears entry; CSS only moves at <=980px | JS bypass; `display`, inert and expanded state remain | No | EXTEND; retain instant close/focus |
| DIALOG_ENTER: native showModal | CSS `dialog[open]`, `::backdrop`; opacity, scale .975 and Y 8px for surface; backdrop opacity | dialog surface, enter backdrop / enter | Content swap while open does not replay; exit cancels CSS entry; print forces static | CSS entirely off, same native dialog semantics | Native modality, not animation | KEEP initially |
| DIALOG_EXIT: close/Cancel/Escape accepted | `closeDialogAnimated`; surface opacity, scale .985/Y 4px; backdrop opacity | fast / exit | Single `dialogCloseTimer`; opacity transitionend or +60ms fallback; native close resets listener/classes | JS native close immediately; permission check and dialogVersion immediate | Closing surface has pointer-events:none; modality ends on native close | EXTEND presentation only |
| NOTICE: notify then expiry | `notify`, `hideNotice`; opacity/Y 8px entry, Y 4px exit | enter / enter; base / exit | New message cancels old exit; six-second reading timer restarted only by notify; transitionend or fallback ends exit | Entry skipped; expiry hides directly; `role=status` remains | No | KEEP |
| REFRESH: existing content reload | `markRefreshing` / `settleRefreshing`, `.is-refreshing`; opacity to .78 | base / standard | Actual accepted response/error settles; stale paths return without painting | Dimming and `aria-busy` stay, transition omitted | No animation lock; loaders may disable paging/search controls | KEEP |
| LIST_REPLACEMENT: changed rendered query | `playEntryMotion(host,'--motion-base')`; `.list-host/.state.motion-enter`; opacity only | base / standard | Clear entry on same node; per-feature rendered-query tracking; dynamic hosts may detach | JS skip; empty/error text and actual list replacement still happen | No | KEEP |
| SCANNER_FEEDBACK: accepted scanner result | `playScanFeedback`, `.scan-result.is-scan-ok`; success background immediately, release color | 1200ms semantic hold; slow / standard release | `scanTimers` WeakMap; next scan clears before request, hold removes tint | Hold/state remain, release instantaneous; input remains selected, no motion focus theft | No; scanner request itself locks submit | KEEP |
| THEME: explicit toggle | `theme(value,true)` + `html.is-theming` low-specificity `:where()` rule; background/text/border | base / standard | Clears previous theme timer, expires token+60; component motion wins cascade | JS doesn't arm; initial storage restoration also instant | No | EXTEND token colors later |
| OTHER: changed production progress | `playProgressSettle`; native progress `.value` interpolated from old payload | base / linear timestamp ratio (no easing token) | Ends at ratio 1; detached node ends next callback; no tracked cancel handle | Initial call bypasses interpolation; payload values unchanged | No | KEEP initially; explicit cancellation before reuse for physical motion |
| OTHER: focus/loading/error/print | `:focus-visible`, `.state`, `.error`, print dialog override | None | Immediate; no perpetual skeleton/spinner loop | Meaning survives complete motion bypass | No presentation delay | KEEP |

Refresh hosts are `order-list`, `batch-list`, `product-list`, `command-center-content`, `integrations-body`. Replacement fades cover `order-list`/`board-message`, `batch-list`, `workforce-list`, `audit-list`, `approval-list`, `marketing-budget-list`, `pr-page-list`. Product search filters `productsCache` immediately and deliberately has no per-letter fade. Analytics/activity do not acquire replacement fades just because they are lists. Scanner feedback is used by the two primary scanners; do not assume every secondary scanning dialog uses it.

## 6. Lifecycle ownership and known limitations

```text
USER INPUT
  |
  v
FEATURE HANDLER / existing guardPending contract
  |
  v
SEMANTIC NAVIGATION: activateWorkspace()
  +-- immediate feature-counter invalidation and section hidden state
  +-- immediate view, then activeNavigation() / aria-current
  +-- existing playEntryMotion() scheduling (never awaited)
  +-- immediate drawer close, inert/expanded state, focus
  |
  +--> FEATURE DATA LOADER --> epoch/counter/view/report checks --> render
  |
  +--> PRESENTATION COORDINATION (future observation, not a second router)
         +-- one nav lens per surface, target from semantic selection
         +-- existing page entry and icon CSS, each with its own properties
         +-- cancel/settle on teardown or preference change
                  |
                  v
             SETTLED PRESENTATION: no continuous RAF work

SESSION CLEAR / confirmed mutation / denied recovery
  +-- act immediately; never await presentation
```

Semantic state is authoritative. Motion observes state. Motion never owns business/navigation truth.

| Owner | Actual lifetime | Consequence for a future spring |
|---|---|---|
| `entryFrames`, `entryTimers` WeakMaps | `clearEntryMotion(node)` cancels/removes one node's frame/timer/classes. No argument only enumerates workspace sections. `playEntryMotion` forces layout via offsetHeight then schedules one RAF and a token+60 timer. | WeakMap is not global cancellation: callbacks still retain a node until execution. Add explicit lens cancel/reset, not another entry-class consumer. |
| `activateWorkspace` | Hides old sections but does not immediately clear every old entry/list timer. Existing tests wait for bounded settling. | Rapid navigation may have several finite entry cleanups; a persistent spring must cancel/retarget immediately and hold one frame handle. |
| Dialog | `dialogVersion` increments before animated close. `transitionend` filtered by target and opacity, fallback 180ms; native `close` listener removes timer/listener/classes. Direct successful writes/session clear call native close. | Never delay invalidation, success or teardown. A late response must fail its version guard during the exit, while dialog is still physically open. Closing CSS blocks pointer input but does not set inert. A0 reproduced keyboard submission during exit; see the probe below. |
| Notice | Separate six-second notice timer, entry WeakMaps, exit timer/listener. `resetNoticeMotion` removes classes/exit ownership, not the entry WeakMap entries. `hideNotice(true)` hides immediately on session clear. | Bounded entry/read timers can still expire harmlessly on a hidden notice. Do not describe current teardown as cancelling every timer. |
| Refresh | `is-refreshing` and `aria-busy` are cleared on accepted success/error paths; stale returns often bypass cleanup. Whole-session clear empties/hides hosts but does not comprehensively call `settleRefreshing`. | A hidden old host can retain busy/dim state until a later load settles it. Preserve safety guards; future motion cleanup must not mark stale data “current.” |
| Dynamic list hosts | Replacing `innerHTML` can detach a fading host; its old timer remains bounded and only touches that node. | A lens should live outside replaceable workspace/report content. An integrator needs `isConnected`/visibility checks and explicit cancellation, not merely finite timers. |
| Progress RAF | Untracked per-row callbacks; stop at 180ms or disconnected node. Hidden but connected rows can still finish. Reduced-motion is checked at entry, not on each frame. | Do not reuse this helper as a spring engine. It has no velocity, cancellation handle or preference-change subscription. |
| Scanner tint / theme | Scanner WeakMap timer ends after 1200ms; theme timer after base+60. `clearWorkspace` does not explicitly cancel both. | Finite decorative cleanup may cross logout; future persistent controller must reset immediately, with no inherited target/velocity for another identity. |

There is no JS `reducedMotionQuery` change listener. CSS responds to live preference changes, but an already running progress interpolation can continue briefly and an already closing dialog/notice can wait for its fallback. These are audit findings and future test inputs, not repairs in A0. No existing helper writes a physical lens transform; reserve its node/transform exclusively for the future controller so page entry, control `scale`, and lens motion cannot overwrite each other.

**Confirmed existing dialog-exit gap:** in the disposable browser fixture, open New Order, fill valid fields, let entry settle, press Escape, then immediately Enter. The native dialog remained `open: true`, `is-closing: true`, `inert: false`; the browser emitted one POST to `/api/orders`. The probe intercepted that request and fulfilled it with 422 before it reached the server, so it did not perform a mutation. `formDialog()` checks `modalBusy` before dispatch but checks its captured `dialogVersion` only after the response. Closing invalidates late rendering, but does not prevent this new keyboard-triggered submission. This is a potential unintended-write window in baseline behavior, not evidence of a server-side duplicate or authorization bypass. Resolve and regress it in a separately authorized fix before extending dialog exit/sheet presentation; A0 changes neither code nor tests.

## 7. Reduced-motion contract

CSS uses `@media(prefers-reduced-motion:reduce)` and `@media(prefers-reduced-motion:no-preference)` (`style.css:537-676`). The reduce block disables transitions/animations on `*`, strips decorative transforms on `.motion-enter,.motion-exit`, and explicitly covers `dialog::backdrop` and `.notice`. It deliberately does not globally remove the disclosure caret's state rotation. Print has its own static dialog override.

JS uses `window.matchMedia('(prefers-reduced-motion: reduce)')` (`app.mjs:34`) and `reducedMotion()`. `playEntryMotion`, `theme(...,true)`, `playProgressSettle`, `closeDialogAnimated` and `hideNotice` provide bypasses. State still changes: selection tint, focus, hidden/inert, scanner success hold, refresh dim/aria-busy, notice text and native close all remain. Notice's six-second read window and transaction timing do not change. Animated close's presentation delay disappears; semantic dialog invalidation already occurred.

No logic depends solely on `animationend`. Only notice/dialog presentation exits listen to `transitionend`, with fallbacks. Future lens behavior must snap or hide with velocity zero and cancelled RAF when motion is reduced, including a change during flight. No fake 0.01ms transition may serve as a completion signal. Preference bypass must be testable before animation initialization.

## 8. One shared lens: proposed integration seam

Attach the semantic notification at the end of `activeNavigation(id)`, after setting the attribute. The controller may read `#app-sidebar [aria-current="page"]`; it must not intercept clicks, fetch, change view, hide sections, set focus, or choose a route. Its notification must be exception-contained, with geometry reads coalesced after the synchronous navigation stack; decorative failure must leave semantic navigation working. Reuse `reducedMotionQuery` and `drawerQuery`. Wire visibility/teardown from `sidebar`, `enterWorkspace`, `clearWorkspace`, and role visibility changes. Observe layout only while needed.

There is currently **one sidebar DOM surface**, reused as the mobile drawer. Create one decorative child of `#app-sidebar`, outside `.sidebar-nav` so the separate `#approvals` CTA is included. Desktop `position:sticky` already establishes a positioned ancestor; <=980px changes it to static, so A2 must explicitly provide a positioning context there. The future node must have `aria-hidden=true`, no tabindex, and pointer-events:none. A2 must test stacking against `.sidebar-cta` and `.sidebar-actions`; nav text/focus must remain above the lens, and selected per-button fill/marker should only yield when the lens has valid geometry. Failure or reduced motion keeps current semantic styling.

Use one coordinate system: target bounding rect minus sidebar bounding rect, minus sidebar border (`clientLeft/clientTop`), plus sidebar scroll offsets for an absolute child in scroll content. Read all geometry before writing. Size tracks the actual button, including wrapped text; do not assume a fixed 40px row or infer position from destination index. Ancestor entry translation must not be animated a second time on the lens.

| Event / question | Proposed behavior and reason |
|---|---|
| Desktop container / scroll | Sidebar is sticky, `overflow:auto`, viewport-height constrained. Ordinary groups are not sticky. `.sidebar-actions` is bottom-sticky and has a gradient pseudo-element; its target geometry changes differently while scrolling. Re-measure on sidebar scroll in one coalesced frame. |
| Analitik disclosure | Native `<details open class=nav-collapse>` moves all following buttons. On toggle remeasure; if the selected child is collapsed, hide the decorative lens and retain its `aria-current`. Do not silently select the summary or reopen the disclosure. Reappear at measured target when expanded. |
| Offscreen target | Clip to sidebar viewport and exclude the footer's occluded region. Hide when selected target has no visible area; do not scroll or change selection just to display decoration. Restore at its real geometry when visible. |
| Resize / breakpoint | ResizeObserver on sidebar and active target plus drawerQuery event; invalidate queued measurements on teardown. Remeasure once; geometry-only changes snap or settle briefly without carrying obsolete displacement across layout systems. |
| Text zoom / font reflow | Measure actual target and container on size changes; disclosure/layout events also trigger refresh. Test 200% root text and actual browser zoom later; current tests emulate text scaling, not every OS scaling mode. |
| Role-gated items disappear | After role UI update, re-read selected visible target. Hide/reset if hidden or disconnected. Never activate another route as a lens fallback. |
| First login | `enterWorkspace` selects Production. Start settled at its geometry, with zero velocity, preserving existing no-entry-on-first-login behavior. |
| Mobile open / close | Same DOM lens instance. Closed display:none/inert drawer cancels and hides it; opening measures after layout and snaps to current selection. Drawer close must remain immediate. |
| Logout / clearWorkspace | Cancel queued read and integration frame; clear target, velocity and timestamps; hide immediately. Current teardown hides the workspace but does not remove sidebar aria-current or reset `view`, so observing attribute changes alone cannot detect logout. Do not retain a controller's old-user geometry as navigation state. |
| Four clicks in <300ms | Every accepted navigation updates semantics/counters synchronously; rejected/recovery-intercepted clicks do not retarget. Retarget the same running state without resetting current velocity; only last semantic selection is the resting target. |
| Approval CTA | Resolve by aria-current/id, never `.nav-item` alone. Its sticky/overflow/paint behavior needs explicit geometry and stacking tests. Do not create a second approval lens. |

A second future navigation surface would receive its own single decoration only when that surface actually exists. No anticipatory mobile tab bar or observer framework is needed in A0/A1.

## 9. Spring options and recommendation

| Criterion | A: CSS transition / cubic-bezier | B: WAAPI generated spring keyframes | C: requestAnimationFrame integrator |
|---|---|---|---|
| Interruption | Easy visual retarget from current computed position | Cancel/sample/regenerate Animation | Retarget live state |
| Velocity continuity | No explicit physical velocity; not the requested guarantee | Must derive velocity from keyframe function at currentTime (including playbackRate), then regenerate with that initial velocity; transform position alone is insufficient | Keep current velocity and replace target only |
| Retarget quality | Useful static/fallback selection; fixed curve restarts | Good with careful sampling/time mapping | Directly satisfies repeated target changes |
| Performance | Transform/opacity can be composited; little JS | Transform keyframes can be composited; regeneration work on interruptions | Small main-thread cost while moving; layout reads only on invalidation, transform write per frame |
| Complexity | Lowest | Sampling, cancellation and finish races add complexity | Small explicit numeric state and one cancellable frame |
| Reduced motion | Disable transition / static marker | Cancel and assign final state | Cancel, zero velocity and snap/hide |
| Testability | End geometry; physics not independently testable | Test generator plus browser timeline/cancel races | Deterministic step/convergence tests plus browser geometry |
| Existing helper fit | Same CSS token language, but not physical | Would introduce another lifecycle mechanism | RAF already exists, but do not repurpose finite entry/progress helpers |
| Browser contract | Existing baseline capability | Modern browser API; no current product dependency on it | Existing product dependency; avoids raising the API floor solely for lens physics |

**Recommend C for the physical lens**, constrained to one lens owner, not a general animation engine. Native RAF is one-shot, must be re-requested, and is commonly paused in background tabs; use its timestamp rather than assuming 60Hz. [MDN requestAnimationFrame](https://developer.mozilla.org/en-US/docs/Web/API/Window/requestAnimationFrame). WAAPI exposes timeline/currentTime/cancellation, not a ready-made physical velocity state; the sampling approach above is this audit's design analysis. [MDN Web Animations usage](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Using_the_Web_Animations_API).

Conceptual state: `position`, `velocity`, `target` for x/y (and width/height only if later evidence warrants physical resizing), `lastTimestamp`, `running`, plus one nullable frame handle and target-node identity. Retarget keeps position/velocity. Use a high damping ratio near critical; numerical constants are future tuning choices, not alleged Apple values. Integrate elapsed seconds with bounded substeps (proposed <=1/120s, capped catch-up <=32ms). Background/visibility resume should remeasure and snap rather than simulate an unbounded elapsed interval.

Proposed settle criterion: each animated coordinate within 0.25 CSS px and speed below 2 CSS px/s; then assign exact target, zero velocity, clear timestamp/handle and stop scheduling. Validate tolerances at DPR/zoom extremes before freezing them. Cancel on detach, drawer hide, reduced-motion activation and session clear. Layout movement from scroll/resize should rebase/snap geometry rather than inject accidental physical velocity. No RAF runs while settled; no external dependency and no production code in A0.

Current repository evidence establishes Chromium CI and a default local Edge runner, not an explicit supported-minimum browser matrix. Existing features include ES modules, native dialog, inert, CSS individual scale and :has. Test Safari/WebKit and Firefox before claiming Apple-platform parity; the Windows Chromium baseline cannot establish it.

## 10. Shell and material feasibility

The shell is opaque today. Body/canvas use `--bg/--canvas`; `.masthead` is sticky top 0/z-index 20; `.app-shell` is a two-column grid; `.app-sidebar` is sticky below the header and scrolls; `.workspace-main` is an opaque canvas with min-width:0. Cards use surface colors, 20px corners, border and small shadow. Dialog is a native top-layer surface with a translucent dark backdrop and large shadow; notice is fixed with large shadow. Mobile drawer is an in-flow displayed section, **not** a fixed overlay or sheet.

No CSS `filter` or `backdrop-filter` is present. Existing opacity compositing includes entry/exit, .78 refresh dim, .45 disabled controls, SVG gradient stops and decorative pseudo-elements. Pseudo-elements include selected-nav rail, sticky footer gradient, CTA dots and native dialog backdrop. Shadow tiers already exist, including `--shadow-lg:0 18px 48px ...`; do not duplicate that elevation system. Multiple opaque foregrounds mean adding blur to a parent would not automatically reveal content through all children.

| Future tier | Current candidates | Proposed treatment / purpose |
|---|---|---|
| CONTENT | Tables, numbers, charts, form fields, lists, production ledger, KPI text | Opaque/readable; preserve foreground and semantic color contrast |
| STANDARD SURFACE | Cards, list groups, filters, workspace content panels | Reuse surface tokens; solid light/dark fill and restrained borders |
| RAISED SURFACE | Dialog body, notice, focused task content | Solid/semi-opaque raised token with limited shadow; readability above content |
| FUNCTIONAL GLASS | Masthead toolbar, sidebar/navigation chrome, later mobile navigation and popover/sheet chrome | Opt-in bounded translucent layer, only where underlying context actually exists; contrast and opaque fallback first |
| PROMINENT GLASS | One active lens or genuinely floating contextual control | Small-area emphasis; avoid stacking blur layers; keep text outside the optical treatment |

Do not glass the whole body, workspace-main, every card, tables, charts, production values, error banners, scanner result text or financial summaries. A1 should define semantic material tokens and opaque fallbacks; actual blur belongs to A4 after measurement. Future enhancement should be feature-gated with `@supports`, honor reduced-transparency where supported, and offer a solid-material fallback for unsupported preferences. Forced-colors must use system colors and visible borders/selection with effects disabled. Avoid continuous optical/refraction rendering.

The transparency preference currently has limited browser availability, so detecting it cannot be the only way to obtain solid chrome. [MDN prefers-reduced-transparency](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@media/prefers-reduced-transparency). Backdrop effects require a transparent or partly transparent foreground to show through; assess the real stacking/painting result before adding blur to the existing opaque shell. [MDN backdrop-filter](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/backdrop-filter).

Apple's materials guidance reserves Liquid Glass for navigation/control context and describes adapting material appearance to accessibility preferences. That supports limiting the web treatment to functional chrome; it does not imply CSS blur is equivalent to Apple's renderer. [Apple Materials](https://developer.apple.com/design/human-interface-guidelines/materials).

Existing adaptive primitives are reusable: grid `minmax(0,1fr)`, rem typography, wrapping `.actions`, responsive `.form-grid`, contained `.table-scroll`, sidebar disclosure and native dialog. Production already uses `container-type:inline-size` and 48rem/30rem/19rem container queries inside its bounded 1360px workspace (`style.css:1153-1246`), a particularly useful foundation for tablet split views. People uses auto-fit stat cells, overriding its older 6/3/2-column rules. <=980px currently groups tablet/mobile into one drawer behavior; a future iPad-like persistent workspace mode needs a deliberate breakpoint/composition decision rather than stretching phone layouts across desktop.

## 11. Command Center golden-screen inventory

Evidence: `index.html` section `command-center-view`; `showCommandCenter` and helpers `app.mjs:631-879`; CSS business/operations grid rules and breakpoint overrides `:783-806`; [command_center.py](../beeloft/command_center.py) `build_command_center`; [store.py](../beeloft/store.py) `jubelio_marketplace_performance` (`:1028`).

| Component | Stable host / current structure | Classification |
|---|---|---|
| Heading / updated / refresh / back | `.dashboard-heading`, `command-center-updated`, `command-center-refresh`, `command-center-back` | KEEP_DATA_AND_STRUCTURE; controls CONTROL_LAYER_CANDIDATE |
| KPI summary | `command-center-summary`, four definition-list cards | KEEP_DATA_RECOMPOSE_VISUALLY; CONTENT_LAYER |
| Marketplace business band | `.business-section`, `business-title`, `command-center-period`, `.business-grid` primary/rail | KEEP_DATA_AND_STRUCTURE |
| Hero / trend / funnel | `command-center-hero`, real daily SVG trend, gross/net context and four status counts | KEEP_DATA_RECOMPOSE_VISUALLY; CONTENT_LAYER |
| Channels | `command-center-channels`, semantic table inside `.table-scroll`, sales drill-down | CONTENT_LAYER; drill-down CONTROL_LAYER_CANDIDATE |
| Contribution | `command-center-contribution`, bars scaled from gross sales | KEEP_DATA_RECOMPOSE_VISUALLY; CONTENT_LAYER |
| Products | `command-center-products`, ranked top five products | KEEP_DATA_AND_STRUCTURE; CONTENT_LAYER |
| Operational strip | `command-center-operations`: active orders, pending decisions, exceptions, net profit | KEEP_DATA_RECOMPOSE_VISUALLY; CONTENT_LAYER |
| Attention queue | `command-center-attention`, priority mark/title/detail/action from backend | KEEP_DATA_AND_STRUCTURE; action CONTROL_LAYER_CANDIDATE |
| Snapshots | `command-center-snapshots`: domain queue, production, quality, capacity, people, inventory, sales, finance, integrations, AI shortcut | CONTENT_LAYER; NEEDS_FUTURE_COMPONENT_PRIMITIVE for consistent metric/gauge/list presentation |
| State presentation | `command-center-message`, report visibility, summary busy, refresh dim | KEEP_DATA_AND_STRUCTURE; later shared state primitive |

Responsive collapse: <=1240px narrows padding/gaps and primary/rail ratio, <=1040px reduces summary to two columns and grid ratio, <=980px makes business/operations single-column and rails two-column, <=760px rails become one-column, <=650px KPI/heading/funnel/attention actions stack with smaller padding. Later CSS overrides matter: inspect `.business-grid/.operations-grid`, not only earlier `.command-center-content` rules.

### Real metric contract

The complete top-level report is `generated_at`, `status`, `production`, `quality`, `capacity`, `workforce`, `approvals`, `inventory`, `sales`, `finance`, `integrations`, `attention`. The following is a field inventory, not sample business data.

| Domain | Real backend fields available to preserve |
|---|---|
| Status | `state`, `attention_count`, `critical_count`; attention records carry id, priority, kind, title, detail, action, action_label |
| Production | `active_orders`, `overdue_orders`, `in_progress_quantity`, `rework_quantity`, `open_issues` |
| Quality | as_of/period_start, inspected_quantity, first_pass_yield_percent, nonconforming_rate_percent, rework_rate_percent, reject_rate_percent, reinspected_quantity, reinspection_nonconforming_quantity/rate_percent, groups, attention_groups |
| Capacity | as_of/horizon_end, capacity_complete, required_minutes, available_minutes, work_centers, attention/overloaded/deadline_risk/near_capacity_work_centers, at_risk_orders, coverage_gaps, missing_standard_quantity |
| Workforce | as_of, active/recorded/unrecorded_employees, present, leave, absent, work_minutes, overtime_minutes |
| Approvals | pending_count, pending_amount, pending_without_amount, by_kind; same aggregate source, not a sampled list count |
| Inventory | mapped_products, matched, mismatched, missing_from_snapshot, quarantined, out_of_stock, at_risk, materials_to_purchase, recommended_production_quantity, coverage_complete, snapshot_at; UI combines mismatched/missing_from_snapshot/quarantined |
| Marketplace summary | orders, completed_orders, pending/processing/completed/cancelled, units, gross_revenue, average_order_value, refund_amount, net_revenue, matched_refunds, unmatched_refunds, unmatched_refund_amount, marketplaces, quarantined_orders |
| Marketplace breakdowns | Per-channel counts/units/completed gross/AOV/refund/net/contribution_percent; per-product product_id/sku/product_name/color/size/units/orders/gross_revenue; daily date/orders/units/gross_revenue; snapshot and return-snapshot timestamps, order and trend date ranges |
| Sales summary | snapshot_at, accepted_orders, quarantined_orders, units, gross_revenue, pending, processing, completed, cancelled |
| Finance | Optional current period with gross_revenue, sales_returns, cost_of_goods_sold, operating_expenses, other_income, other_expenses, cash_balance, receivables_balance, payables_balance, derived net_revenue/gross_profit/net_profit/net_liquidity and period metadata. UI currently uses net_revenue/net_profit/cash_balance. Payables/receivables each snapshot_at, outstanding, overdue_count, overdue_amount, due_next_7_days_amount |
| Integrations | attention_count; per-system system/label/health/attention_count; health is categorical source state, not an invented numerical score |

`jubelio_marketplace_performance()` uses the latest order batch only; completed orders supply sales, units and AOV. Refunds are deducted only when matched to completed orders in that batch; unmatched refunds are separate. Channel names are normalized case-insensitively, products rank by real units, and daily rows are real completed-order dates with no invented gap filling. AOV is gross completed revenue divided by completed count. Preserve decimal strings and current exact money formatting; this programme must not recalculate business money in a motion layer.

Frontend-only display derivations are domain exception counts, rework/WIP ratio, required/available load, attendance relative bars, compact number formatting, chart scaling and peak from actual daily values. Some bars use a minimum visible length; these are visual encodings, not new metrics. There is no backend sales-growth percentage, generic health score, revenue target, traffic/conversion, marketplace fees, commissions or true channel margin in this report. Quality attention may describe a real period comparison, which must not be repurposed as a sales trend delta. Do not invent any missing value or label snapshots as “today's revenue.”

## 12. Design-system gap matrix

| Area | CURRENT | TARGET | REUSE | CHANGE_LATER | RISK |
|---|---|---|---|---|---|
| Typography | Segoe UI first, rem scale, generic 26px-equivalent h1; Production 30px before narrow-container override | Platform-aware system hierarchy | rem and tabular numbers | Tokenize roles; evaluate stack on Apple/Windows | Text reflow/200% |
| Color | Semantic blue + danger/warning/success, light/dark tokens | Adaptive accent/semantic roles | Existing meanings | Foundation palette review | Status contrast |
| Canvas | Opaque gray/dark canvas | Quiet adaptive workspace background | --canvas | Theme tuning | Unnecessary translucent content |
| Surface | Solid/subtle/sunken | Explicit content/chrome materials | Existing solid tokens | Tier aliases and fallbacks | Layer ambiguity |
| Border | line/strong/edge tokens | Semantic separators | Tokens | Contrast calibration | Thin separators disappear |
| Radius | Cards20/input12/nav10/chip8/pill | Scale-specific native-feeling roles | Existing ladder structure | Explicit DESIGN.md revision | Baseline tests pin values |
| Shadow | Three tiers | Elevation for overlap/focus | Tiers | Optical tuning on chrome | Large-area paint cost |
| Button | Native pill, press scale, instant focus | Consistent hierarchy/sizing | Native element, locks | Control variants later | Submit/disabled regressions |
| Input | Native 40/44px, 12px radius | Clear focus/error/read-only states | Validation/types | Token/style pass | Keyboard/accessibility |
| Search | Native search/filter forms; SKU local filter | Clear scoped search | Current query semantics | Visual search primitive | Debounce changing behavior |
| Navigation | Registry + aria-current | One decorative physical lens | Entire semantic route path | A2/A3 observer | Split navigation truth |
| Sidebar | 256px sticky, disclosure, sticky approval CTA | Adaptive Apple-like chrome | DOM/nav ordering | Material and tablet composition | Scroll/CTA lens clipping |
| Toolbar | Sticky masthead and wrapping actions | Functional translucent control layer | Current controls | A4 chrome | Obscured content/focus |
| Card | 20px opaque bordered surfaces | Structured opaque content | Content markup/data | Visual composition by phase | Glass everywhere |
| Table/list | Semantic tables/contained scroll and card rows | Readable density and selection | Row actions/escaping | Shared presentation primitive | 320px text overflow |
| Status chip | Text + semantic tint, color transition | Compact accessible status | Meanings and text | Shape/type tuning | Color-only status |
| Dialog | One native modal, guarded exit | Native-feeling focused task | Native semantics/version guards | A7 presentation | Delayed commit/old response |
| Popover | No general popover layer | Anchored nonmodal context | Existing task actions | Native platform capability first | Focus/dismissal/viewport |
| Sheet | No detents; mobile drawer is in-flow | Adaptive focused presentation | Existing form contracts | A7 after focus design | Swipe discarding unresolved write |
| Toast | role=status, six-second timer | Restrained contextual notice | notify/hideNotice | Material/padding only initially | Timing or announcement changes |
| Loading | Text + busy markers, refresh dim | Clear immediate pending context | Existing states | Shared styling | Animation becoming readiness |
| Empty state | Explicit contextual messages | Consistent empty/filter-empty presentation | Business copy | Layout primitive | Meaning conflation |
| Error state | Immediate error/retry/auth flows | Readable actionable error | fail/retry/session contracts | Visual hierarchy | Stale content or hidden error |
| Icon behavior | Inline SVG sprite, currentColor, aria-hidden | Consistent optical size/state response | Sprite and accessible labels | Audit glyphs individually | Decorative glyphs announced |
| Motion | CSS tokens plus finite JS scheduling | Interruptible lens with velocity | Existing timing/lifecycle seams | One controller | Competing transforms |
| Reduced motion | CSS and JS bypasses | Full live cancellation | Shared media query | Mid-flight handling/tests | Orphan frame callback |
| Transparency | No glass preference/fallback layer | Solid fallback and opt-in chrome | Opaque baseline | A1 contract, A4 effects | Unsupported media feature |
| Dark mode | Explicit stored theme with shared tokens | Equal material/readability behavior | theme storage, cascade | Alpha/contrast testing | Wallpaper/content-dependent contrast |
| Responsive layout | Desktop sidebar, <=980 drawer; rem reflow and Production container queries | Phone/tablet/desktop composition | CSS grids/actions/details/container queries | Tablet workspace decision | Stretched phone desktop |

## 13. Existing test guarantees and future tests

Tests were inspected as assertions, not just filenames. The suite entry point is [tests/run_browser.py](../tests/run_browser.py) -> [browser_smoke.cjs](../tests/browser_smoke.cjs). A passing assertion supports its fixture/state combinations, not universal UI or browser parity.

| Contract | Current tests / concrete scope | Remaining boundary |
|---|---|---|
| 27 pages, one visible section, aria-current | `test_workspace_navigation.py`, `browser_navigation_foundation.cjs`, `browser_motion_consistency.cjs`; destination-set equality, internal detail, transient showModal instrumentation | A new lens must not become another active-state source |
| Late responses | Navigation foundation holds board/analytics/audit/approval responses; utilities holds scans/downloads; feature modules guard replacements | Lens cancellation and geometry staleness not covered |
| Widths 1440/1024/768/390/320, 320+200% | M6 sweeps all 27; foundation includes role/theme/mobile keyboard matrix; production/shared UI/Command Center modules measure layout | Real device DPR, OS zoom, Safari remain unverified |
| Drawer | `browser_motion_workspace.cjs`: entry transition lifecycle, inert, 40 Tab presses while closed, heading focus, Escape | Lens on drawer open/close/disclosure/scroll |
| Motion foundation | `test_motion_contract.py` pins tokens, raw-duration exclusions, CSS query placement and add/remove class coverage; `browser_motion_foundation.cjs` press/disabled/focus | Static class removal existence does not prove all teardown paths |
| Workspace motion | M2 checks actual transition events, no first-entry replay, shared analytics host, rapid navigation and settled cleanup | Velocity continuity / four-way physical retarget |
| Dialog safety | `browser_motion_dialogs.cjs`: entry/backdrop, accepted and blocked exit, rapid entry-to-exit, direct close, no late repaint, focus, reduced motion, print, dark and 320+200 | These assertions miss keyboard submission during exit, reproduced by the A0 intercepted-request probe (section 6). Future regression must assert zero new writes after accepted dismissal; sheet/popover behavior also needs coverage. |
| Refresh/replacement | `browser_motion_data_states.cjs` and M6: held requests, dim/busy, real opacity transition, no per-row fade, retry after failed replacement, report failure cleanup | Interrupted hidden-host busy cleanup not universally guaranteed |
| Scanner/progress/theme | `browser_motion_microinteractions.cjs`: actual changed progress, scanner tint/selection/error/rapid pair, theme only on toggle, no infinite effects | Mid-flight preference change and immediate global timer teardown |
| Production/Command Center | `browser_production_premium_ui.cjs`, `browser_shared_ui.cjs`, `browser_kpi_glyphs.cjs`, `browser_management_command_center.cjs`; hierarchy, real payloads, filters/paging, role states, responsive/dark; Production has text contrast checks | No global glass contrast/performance guarantee |
| Pending / actor / session | Smoke lost-response replay; `browser_cross_account_retry.cjs`, `browser_stale_session_first_submit.cjs`, `browser_logout_failure.cjs`, `browser_ai_investigation_logout.cjs`, `browser_login_form.cjs`; failed/uncertain/switched logout, exact key/actor retry and drafts | Presentation must remain outside these controls |
| Feature pages | workforce, product_external_mappings, integrations, audit_trail, unified_approvals, purchase_requests, marketing_budgets, each analytics browser module; workspace_utilities and both scanner modules | Preserve feature assertions during later visual rewrites |
| No endless work | M5/M6 inspect effect timing iterations for Infinity; A0 separately measures pending/executed RAF at rest | getAnimations alone cannot detect a JS RAF loop |

Future **lens** tests: exactly one node per actual surface; aria-hidden/nonfocusable/noninteractive; unchanged single aria-current; resting x/y/size within tolerance of selected button; four destinations in <300ms with held network response; analytics child-to-child and disclosure close/open; sidebar scrolling including sticky approval CTA and occlusion; target disappearance; resize/text zoom; mobile reopening; first login and logout; reduced-motion from initial load and mid-flight; no measurement/frame callback after teardown.

Future **spring** tests: smallest deterministic stepping check for convergence at varied frame intervals, retained velocity immediately before/after retarget, bounded background delta, cancellation and exact final snap; browser instrumentation asserts at most one pending integrator frame and zero at rest/detach/logout. Test physical geometry, not arbitrary sleeps or class names alone.

Future **glass** tests: `backdrop-filter` unsupported/disabled fallback, reduced-transparency and user solid-mode path, light/dark text and non-text contrast over worst-case content, forced-colors selection/focus, 320px/200%, scroll paint/frame cost on representative low-end/mobile hardware. No future tests or test changes are added by A0.

## 14. Performance baseline

Single local synthetic sample on Windows, Python 3.12.14, Node 24.18.0, bundled Playwright 1.62.1 / Chromium 151.0.7922.34. It uses the existing runner's three demo production orders, admin session, and **no imported vendor snapshots**. This is a reproducible fixture-sized baseline, not a typical production population, statistical benchmark or hardware budget. Concurrent baseline suites were running, so timing includes local contention.

| Measurement | Observed |
|---|---|
| `app.mjs` | 613,016 bytes Git blob; 618,367 Windows checkout bytes |
| `client.mjs` | 3,532 bytes Git blob; 3,592 checkout |
| `style.css` | 90,403 bytes Git blob; 91,649 checkout |
| `index.html` | 37,692 bytes Git blob; 38,012 checkout |
| Primary destinations | 27 (admin); non-admin hides two |
| Initial document DOMContentLoaded / load | 235.0ms / 286.4ms, loopback, no network/CPU throttling |
| Command Center click to report visible | 521ms, includes click automation and request/render; not pure backend latency |
| Settled Command Center descendants | 402; entire document 1,092 elements including hidden workspaces and SVG sprite |
| RAF work at rest | 0 pending callbacks; executed count remained 14 across an additional 1,000ms idle window |
| Running CSS/Web Animations at rest | 0 |
| Command Center document overflow | 0px at 1440/1024/768/390/320 and 320 with 200% root text, separately light and dark |

Git blob/checkout size difference is line endings, not generated product changes. Measurements wrap RAF/cancelRAF before app load, count pending handles and callbacks, query `document.getAnimations()` after settling, and compare scrollWidth/clientWidth after layout. Ad-hoc measurement files/logs stay in the OS temp audit directory; no instrumentation ships in the application. Existing baseline tests supply the broader all-destination checks.

Populated marketplace DOM cost, GPU memory, paint traces, mobile battery and Safari performance are **not measured**. A4/A5 must compare populated synthetic snapshots and representative hardware against this baseline and capture a better distribution before setting budgets. Current invariant to preserve: effectively zero continuous animation work when settled; no permanent RAF loop, even when glass is enabled.

## 15. Session and transaction safety

**PRESENTATION MOTION MUST NEVER BECOME TRANSACTION STATE.**

`epoch` invalidates cross-session callbacks. Feature counters invalidate old workspace loads. `dialogVersion` invalidates old dialog renderers and is bumped before an accepted animated close. `modalBusy` and `unresolved` block close/Cancel/Escape before presentation begins. `guardPending()` routes to `recover()` rather than dropping stored work. `pendingKey()` namespaces drafts as `beeloft.pending.<user.id>`; draft stores exact transaction body, idempotency key and actor id.

`formDialog()` writes the draft before submission. On confirmed success it clears the matching stored transaction, verifies epoch/actor/dialogVersion, clears busy/unresolved and calls native `dialog.close()` before success rendering and parent refresh. A lens/exit animation cannot defer that commit acknowledgement or re-submit it. Uncertain results retain exact transaction identity; `sameActorGuard` and `client.mjs` `X-Beeloft-Actor` binding protect retries. Server actor authorization is the enforcement boundary, not the decorative frontend.

`logout()` deduplicates in-flight revocation and probes session identity after failures. Failed logout with same actor or unknown server outcome preserves the workspace with a persistent honest warning. A different active actor clears old workspace, does not revoke the new identity, and preserves old pending storage. Confirmed inactive session clears immediately. `clearWorkspace()` increments epoch/counters, clears identity/API actor binding, closes dialog, empties content, resets entry history, hides workspace/notice, closes drawer and focuses login. Existing finite cleanup limitations are listed in section 6; future spring cancellation must be immediate and must not weaken this session path.

## 16. Verification record

Verification was started on the exact baseline before documentation edits. Product and test files remain identical to that baseline. Original environment failures are retained separately from the clean-environment verification.

| Command | Result |
|---|---|
| `python -m unittest discover -s tests -v` | PASS: 574 tests in 636.199s, but default Python 3.11.9 is below the declared requirement. Not accepted alone as supported-runtime proof. |
| Existing `.venv/Scripts/python.exe -m unittest discover -s tests -v` | FAIL: 574 tests in 640.405s; 3 failures and 8 subtest errors, all in `test_static_security`. Existing Starlette 0.52.1 is below the source minimum 1.3.1 and pinned 1.6.0. |
| Existing venv `-m unittest discover -s tests -p test_static_security.py -v` | Reproduced: 4 tests, 3 failures/8 errors in 1.083s. Minimum-version assertion fails; mocked UNC/path-resolution cases raise Windows commonpath errors or call forbidden filesystem resolution. Product/tests untouched. |
| Same focused security module in clean Python 3.12.14 / Starlette 1.6.0 env | PASS: 4 tests in 1.197s. Confirms the stale local dependency was the cause of that failure set. |
| Bare `python -m pip check` | FAIL: unrelated installed `comic-sol-web` pins authlib 1.7.2 (installed 1.5.2), python-multipart 0.0.32 (0.0.20), uvicorn 0.35.0 (0.52.4). |
| Existing venv `-m pip check` | PASS, but installed editable metadata reports beeloft-one 0.82.0; this does not validate current pyproject requirements. |
| Clean temporary Python 3.12.14 env, pinned `requirements.txt`, full unittest suite | PASS: 574 tests in 1207.386s, exit 0. |
| Clean temporary env `-m pip check` and `-m compileall -q beeloft` | PASS, exit 0; Starlette 1.6.0 installed from repository lock. |
| `.venv/Scripts/python.exe -m compileall -q beeloft` | PASS, exit 0. |
| `node --check beeloft/static/app.mjs` | PASS, exit 0. |
| `node --check beeloft/static/client.mjs` | PASS, exit 0. |
| `node tests/test_client.mjs` | PASS: escaping/date/retry/read-only POST/auth/actor/errors, CSV downloads, date boundary errors. |
| `.venv/Scripts/python.exe tests/run_browser.py --channel chromium` | Default module lookup failed: `MODULE_NOT_FOUND: playwright`. No test changes. |
| Same browser command with existing bundled `--playwright-module` absolute path | PASS full suite in the existing venv, no `BEELOFT_QA_ONLY` filter; all M1-M6, navigation, session and feature modules passed, final no-JS-errors assertion passed. |
| Clean temporary env browser suite, same bundled Playwright | PASS full suite, exit 0, no module filter, final no-JS-errors assertion passed. Direct script initially could not import beeloft because this temporary env has no editable install; successful rerun used `PYTHONPATH` set to repository root. No product/test changes. |
| A0 synthetic performance/idle/layout probe | PASS; measurements in section 14. |
| A0 dialog-exit keyboard probe | Existing gap reproduced: Escape then Enter emitted one intercepted POST while the dialog was closing. Request fulfilled with 422 before server dispatch; no mutation. Details in section 6; existing suite does not assert this case. |
| Documentation checks | All 27 nav-to-section rows match the source registry; relative links resolve; table column counts are consistent; original M0 text is unchanged apart from the separated status note; `git diff --check` passes. Product/test/config paths have no diff from baseline. |

The bundled Playwright 1.62.1 and Node 24 differ from CI's pinned Playwright 1.63.0 / Node 22. This is a local baseline run, not a CI success claim. A disposable environment under `%TEMP%/beeloft-a0-audit/venv` was created with the existing Python 3.12 runtime and `pip install -r requirements.txt`; no project dependencies or existing environments were modified. Its direct-script imports use repository-root `PYTHONPATH` rather than changing installed editable metadata. No browser results from older commits are substituted. Logs are under `%TEMP%/beeloft-a0-audit` (`unittest-default.log`, `unittest.log`, `security-repro.log`, `unittest-clean.log`, `browser.log`, `browser-clean.log`, `performance.json`).

## 17. Recommended sequence and phase gates

| Phase | Bounded deliverable / exit gate |
|---|---|
| A0 | This evidence, current-status note, exact-baseline tests and limitations; documentation-only commit. Stop here. |
| A1 | Reconcile DESIGN.md with the approved Apple direction; define type/color/radius/elevation/material roles, light/dark and solid fallback contracts. Keep navigation/motion/business APIs intact; no glass renderer, lens or spring. Update existing visual token assertions only alongside intentional specification changes. |
| A2 | One static shared selection decoration plus geometry/visibility lifecycle and semantic integration tests. Retain current selected styling as fallback; resolve analytics and approval CTA geometry first. |
| A3 | Add the small cancellable RAF spring to the A2 node; prove velocity continuity, convergence, rapid retarget, reduced-motion and zero idle work. |
| A4 | Apple-like shell and functional glass chrome with solid/forced-colors fallback and measured paint cost. Tablet/mobile composition reviewed separately. |
| A5 | Command Center golden screen; preserve field meanings/real metrics, loading/empty/error and action destinations; populated synthetic visual/accessibility review. |
| REVIEW GATE | Approve hierarchy, behavior, keyboard/assistive behavior, dark/light, 320px/200%, reduced motion/transparency and performance before propagation. |
| A6 | Native-like reusable controls only where existing native elements/shared styles fall short. |
| A7 | Sheet/popover/alert presentation using native capabilities, preserving modalBusy/unresolved/version/focus contracts. |
| A8 | Production conversion with existing transaction and progress regression suite. |
| A9 | Materials + People. |
| A10 | Approval + Analytics, retaining shared report host and exact approval semantics. |
| A11 | AI + Integrations + Utilities; preserve actor-bound recovery and scanner keyboard input. |
| A12 | Final parity/accessibility/performance audit across supported browsers/devices, including idle-work and populated-data comparison. |

A2 is intentionally geometry/static selection before A3 physical movement. This makes lens correctness independently reviewable; it does not ship a temporary second animation framework. No automatic A1 work follows A0.

## 18. Risks and explicit non-goals

Highest integration risks are dual navigation truth; transforms shared between entry and lens; analytics children mistaken for one destination; sticky approval CTA omitted by `.nav-item` queries; hidden/disconnected targets measured as real; old-identity frames surviving clear; the confirmed keyboard-submit window during dialog exit; modal exit delaying commit; CSS transparency without an opaque fallback; and existing visual assertions silently rewritten to permit an accidental regression. Section 6's bounded cleanup is not sufficient lifecycle infrastructure for a perpetual integrator.

A0 does not change frontend markup/styles/behavior, backend APIs, schema/migrations, store/domain logic, money/production calculations, approval semantics, auth/session/OIDC, idempotency/actor binding/recovery, QC/rework, analytics formulas or business copy. It adds no glass, lens DOM, springs, page transitions, framework, animation library, speculative primitive package or future tests. No deployment, push, PR, merge, or business data modification is authorized by this audit. Only the requested documentation commit is in scope.
