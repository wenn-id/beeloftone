# Beeloft One / operations workspace

Direction source: the Shopeers AI-powered B2B eCommerce analytics dashboard by Dipa Inhouse —
<https://dribbble.com/shots/26628350-Shopeers-AI-Powered-B2B-eCommerce-Analytics-Dashboard>.
That shot is treated as the visual specification, not as inspiration. Antislop applies during implementation.

The artwork itself is not redistributed in this repository. To compare against it locally, save the shot from
the link above to `docs/reference/shopeers-dashboard-reference.png`, which is git-ignored.

ENERGY 2 / RHYTHM 2 / MOTION 1.

- Beeloft One is an operational decision workspace for Indonesian production and management teams. The
  reference's visual system is reconstructed as closely as the real data allows, while Beeloft keeps its own
  data, Indonesian labels, APIs, permissions, and business rules.
- Every geometric and chromatic value below was measured from the reference artboard (1441 x 1033 inside the
  1600 x 1200 presentation matte, i.e. a 1440px-wide application). The grey surround in the shot is Dribbble
  matting, so the application is full-bleed rather than a floating panel.
- One value deliberately departs from that measurement: the card radius is 20px where the reference measures
  16px, because softer corners were requested after review. Surfaces nested inside cards were raised to match
  (breakdown panel 14px, severity and rank tiles 11-12px, sidebar call to action 18px, small marks 10px) so the
  concentric curves stay consistent. Nothing else about the shape system changed.
- Frame: a 256px white sidebar and a 72px white header, separated from a `#f4f5f8` content canvas by 1px
  `#ebecef` rules. The header's brand cell occupies the sidebar column so the vertical rule runs unbroken from
  the top of the viewport, exactly as in the reference.
- Content: 32px horizontal padding, a 1120px working column, a 22px grid gap, and a 1.67fr / 1fr split between
  the decision column and the operational rail.
- Cards: 20px radius, 1px `#ebecef` border, 18-22px padding, and a low-opacity shadow. KPI cards are 130px tall
  with the label and a blue glyph on the first line, a 32px/800 figure, a semantic chip, and a 12.5px footer.
- Colour: primary `#2d5efb` (5.11:1 on white, and white on it), `#eef3fd` for the active navigation surface, a
  `#3c5dff` 3px edge marker, and red / amber / green reserved for real semantic state and always paired with text.
- Type: 26px/700 page titles, 17px/650 card titles, 15px navigation and KPI labels, 13px body, 12px captions.
  Base size is expressed in `rem` so 200% text zoom scales the whole interface.
- Icons: one hand-authored SVG sprite in `index.html` — 24px viewBox, 1.7 stroke, round caps, rendered at 18px.
  No emoji, no icon font, no runtime dependency.
- Controls: buttons are 40px pills, inputs are 40px with a 12px radius, navigation rows are 40px with a 10px
  radius (44px on touch-width viewports), and chips and badges use an 8px radius.
- Navigation groups are separated by inset rules rather than uppercase headers, matching the reference. The
  twelve analytics destinations sit in an expanded disclosure group, and the approval inbox is the reference's
  gradient promo block, pinned to the bottom of the sidebar. No route or destination was added or removed.
- The Command Center is a marketplace business dashboard first and an operational queue second. It answers, in
  order: how is Beeloft selling, which marketplace contributes most, which products sell most, and what needs
  operational action. Two numbered bands enforce that hierarchy.
- Band 01 — marketplace business performance, sourced from Jubelio. Four KPI cards (net sales, total orders,
  units sold, AOV order selesai); a hero card carrying total sales with the real daily sales trend and the order
  funnel as the reference's nested breakdown; the marketplace performance comparison in the reference's table
  slot; and a rail with marketplace contribution and top selling products.
- Band 02 — operational decisions, visually secondary: a compact inline stat strip, `Perlu perhatian` as the
  reference's list surface, and the rail of snapshot cards carrying a yield gauge, load meters, a three-up
  attendance split, integration badges, and the AI surface.
- Marketplace channels are whatever Jubelio actually returns, normalised case-insensitively. No channel is
  hardcoded, so a business that does not sell on a given marketplace never sees an empty slot for it.
- Sales, units, and AOV share one definition: completed orders. AOV is completed gross revenue divided by
  completed order count and is labelled `AOV order selesai` so the denominator is never ambiguous.
- Jubelio figures are snapshot-scoped, so they are never labelled "today" or "this month". Surfaces say
  `Jubelio snapshot`, carry the snapshot time, and state the real derived order date range.
- Analytics surfaces only ever visualise fields that already exist in `/api/command-center`. Marketplace fees,
  commissions, vouchers, shipping subsidy, conversion, traffic, true channel margin, and per-shop breakdowns are
  absent from the source data and are therefore absent from the interface. No trend, target, delta, placeholder
  identity, or business metric is invented.
- Motion is limited to hover, focus, and disclosure state. Reduced-motion preferences remove non-essential
  transitions.
- Every interactive control keeps a visible focus ring, keyboard operation, mobile reflow, and usable text at
  200% zoom with no horizontal overflow at 320, 390, 768, 1024, or 1440 CSS pixels.
