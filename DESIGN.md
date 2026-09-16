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
- Frame: a 256px white sidebar and a 72px white header, separated from a `#f4f5f8` content canvas by 1px
  `#ebecef` rules. The header's brand cell occupies the sidebar column so the vertical rule runs unbroken from
  the top of the viewport, exactly as in the reference.
- Content: 32px horizontal padding, a 1120px working column, a 22px grid gap, and a 1.67fr / 1fr split between
  the decision column and the operational rail.
- Cards: 16px radius, 1px `#ebecef` border, 18-22px padding, and a low-opacity shadow. KPI cards are 130px tall
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
- The Command Center answers one question: what needs a decision today. It maps onto the reference composition
  as: four real KPIs; a hero analytics card (exception total, a per-domain bar chart, and a Kritis / Perlu
  perhatian / Informasi breakdown with proportional bars); `Perlu perhatian` as the reference's list surface with
  a column header, dashed row rules, a severity tile, and a right-aligned action; and an operational rail of
  snapshot cards carrying a yield gauge, load meters, a three-up attendance split, integration badges, and the
  AI surface.
- Analytics surfaces only ever visualise fields that already exist in `/api/command-center`. Where the reference
  shows a time series that Beeloft has no dataset for, the slot carries the closest real distribution or ratio
  instead. No trend, target, delta, placeholder identity, or business metric is invented.
- Motion is limited to hover, focus, and disclosure state. Reduced-motion preferences remove non-essential
  transitions.
- Every interactive control keeps a visible focus ring, keyboard operation, mobile reflow, and usable text at
  200% zoom with no horizontal overflow at 320, 390, 768, 1024, or 1440 CSS pixels.
