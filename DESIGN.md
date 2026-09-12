---
name: RotorWatch Console
description: A calm flight-operations console for scarce Indian drone hardware.
colors:
  signal-lime: "#b8ff52"
  signal-deep: "#497900"
  mineral-paper: "#f2f3ed"
  carbon-ink: "#151712"
  quiet-graphite: "#64685f"
  instrument-white: "#fcfcf8"
  night-ground: "#0e100d"
  focus-blue: "#5c77ff"
  preorder-orange: "#ff8651"
  fault-red: "#bd3a36"
typography:
  display:
    fontFamily: "Space Grotesk Variable, sans-serif"
    fontSize: "clamp(2.8rem, 6.5vw, 6rem)"
    fontWeight: 680
    lineHeight: 0.88
    letterSpacing: "-0.04em"
  body:
    fontFamily: "Manrope Variable, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
    letterSpacing: "normal"
  control:
    fontFamily: "Manrope Variable, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 730
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  field: "8px"
  control: "9px"
  card: "12px"
  panel: "15px"
  glass: "16px"
spacing:
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
components:
  button-primary:
    backgroundColor: "{colors.carbon-ink}"
    textColor: "{colors.mineral-paper}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "11px 16px"
    height: "42px"
  input:
    backgroundColor: "{colors.instrument-white}"
    textColor: "{colors.carbon-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
    height: "42px"
  panel:
    backgroundColor: "{colors.instrument-white}"
    textColor: "{colors.carbon-ink}"
    rounded: "{rounded.panel}"
    padding: "24px"
---

# Design System: RotorWatch Console

## Overview

**Creative North Star: "The Flight Signal Desk"**

RotorWatch feels like a calm instrument panel built for a technically fluent drone builder, not a generic analytics dashboard. Its hierarchy is editorial and decisive: oversized Space Grotesk carries the operating idea, while Manrope keeps dense inventory facts legible. A warm mineral ground avoids the cold-blue default of technical products; rare signal lime identifies state, progress, and high-value action.

The interface is spacious where decisions are made and compact where evidence is inspected. Glass is reserved for the floating command bar, hero, and monitor control. Product lists, filters, run history, and forms remain quieter so transparency never competes with operational truth.

## Delivery Surface

The console is compiled by Vite during the root multi-stage Docker build and served by FastAPI from the same Render Web Service and HTTPS origin as the API. Production uses relative `/api` requests and has no Node process, development server, cross-origin frontend host, or frontend-held secret. Direct navigation to each console section is preserved by the backend's narrowly scoped SPA fallback.

**Key Characteristics:**

- Strong asymmetric headline paired with a compact system-pulse instrument.
- Warm mineral light theme and intentional near-black dark theme.
- Signal lime used sparingly for readiness, health, and primary action.
- Thin neutral rules, restrained radii, and chart-free operational summaries.
- Responsive reflow with no document-level horizontal scrolling at 320px or wider.

## Colors

The palette combines warm hardware neutrals with one electrical signal color and small semantic accents.

### Primary

- **Rotor Signal Lime:** marks live health, completed checks, active dark-theme actions, and the brand device. Its rarity is part of its meaning.
- **Carbon Ink:** carries primary text and the light-theme primary action.

### Secondary

- **Focus Blue:** appears in keyboard focus only, where it must remain visually distinct from stock state.
- **Pre-order Orange:** is reserved for pre-order state and partial-run warnings.
- **Fault Red:** is reserved for failures, unknown/problem emphasis, and destructive controls.

### Neutral

- **Mineral Paper:** the light-theme environmental ground.
- **Instrument White:** the solid field and dense-control surface.
- **Quiet Graphite:** secondary text, timestamps, and non-critical labels.
- **Night Ground:** the dark-theme environmental ground; dark surfaces remain green-neutral rather than blue-black.

### Named Rules

**The Signal Scarcity Rule.** Signal lime communicates readiness or action; it never becomes broad decorative fill.

**The State Is Semantic Rule.** Green, orange, and red must retain their operational meanings across themes.

## Typography

**Display Font:** Space Grotesk Variable (with sans-serif fallback)

**Body Font:** Manrope Variable (with system-ui and sans-serif fallbacks)

**Character:** Space Grotesk gives headlines an engineered, compressed rhythm without resorting to monospace costume. Manrope provides open, readable forms for data, controls, and explanatory copy.

### Hierarchy

- **Display** (680, fluid up to 6rem, 0.88): dashboard hero only; tracking never exceeds -0.04em.
- **Page headline** (680, fluid up to 5.2rem, 0.95): primary title on catalog, watchlist, monitoring, and alerts.
- **Section headline** (650, fluid 1.45–2rem): names the evidence or action below it without a separate kicker.
- **Body** (400, 1rem, 1.65–1.7): explanations with a practical maximum measure around 620px.
- **Control** (730, 0.875rem): buttons, navigation, and fields.

### Named Rules

**The Heading Carries Its Weight Rule.** Never add a tiny uppercase eyebrow above a heading; name the section clearly in the heading itself.

**The Two-Voice Rule.** Space Grotesk owns display and data emphasis; Manrope owns reading and interaction.

## Layout

The desktop shell uses a 168px navigation rail and one fluid content column inside a container capped at 1480px. The hero uses an asymmetric two-column grid; inventory facts then move through a full-width metric strip and a wide evidence panel paired with a compact health panel. Section spacing is fluid and intentionally larger than intra-component spacing.

Below 980px the rail becomes a horizontally scrollable command strip and content becomes one column. Catalog cards move from three to two columns, then one below 680px. At 390px and below, navigation labels visually collapse while accessible names remain. Layout relies on grid, flex, `minmax()`, `clamp()`, and content sizing rather than fixed page geometry.

## Elevation & Depth

Depth is ambient and hierarchical. A broad, low-opacity shadow belongs only to high-value glass surfaces and panels; flat inventory cells and dense run rows use tonal contrast or hairline rules. Hover state uses a small vertical lift, while focus uses a blue outline rather than a glow.

### Shadow Vocabulary

- **Light ambient:** `0 20px 55px rgba(38, 43, 29, 0.09)` for elevated operational surfaces.
- **Dark ambient:** `0 20px 60px rgba(0, 0, 0, 0.28)` for the same hierarchy in dark mode.
- **Drawer depth:** `-20px 0 60px rgba(0, 0, 0, 0.15)` for the product-history layer.

### Named Rules

**The Ambient-Only Rule.** Never use zero-blur hard offset shadows; elevation should read as air, not a sticker edge.

## Shapes

Fields and compact controls use 8–9px corners, content cards use 12px, operational panels use 15–16px, and the large hero may reach 22px. Status pills are the only fully rounded elements. The recurring geometry is a clean instrument rectangle with one-pixel rules, not an assortment of decorative blobs.

## Components

Components feel tactile enough to operate and quiet enough to leave product evidence in charge.

### Buttons

- **Shape:** compact instrument control with 9px corners and a minimum 42px height.
- **Primary:** carbon on mineral in light mode; signal lime on carbon in dark mode.
- **Hover / Focus:** lift by 2px on hover; use the shared three-pixel focus outline on keyboard focus.
- **Secondary / Ghost:** instrument-white or transparent, always with explicit border/state contrast.

### Chips

- **Style:** availability chips use a one-pixel semantic border and a very light state tint.
- **State:** `IN_STOCK`, `PREORDER`, `OUT_OF_STOCK`, and `UNKNOWN` stay textually explicit; color is never the only signal.

### Cards / Containers

- **Corner Style:** 12px for product cards and 15–16px for operational panels.
- **Background:** glass surfaces use controlled alpha; dense cards use solid or nearly solid neutral surfaces.
- **Shadow Strategy:** only elevated operational panels use ambient depth.
- **Border:** one-pixel neutral rules establish structure in both themes.

### Inputs / Fields

- **Style:** solid instrument surface, one-pixel rule, 8px corners, 42px minimum height.
- **Focus:** shared focus-blue outline and signal-colored caret.
- **Error / Disabled:** errors name the failure and recovery; disabled controls retain legible text at reduced opacity.

### Navigation

The desktop rail is text-and-icon navigation with a quiet solid active state. Tablet and mobile use a sticky horizontal control strip; the narrowest layout hides visual labels while preserving accessible button names and focus treatment.

### System Pulse

The pulse pairs a factual run status with an abstract eight-bar signal. Bars breathe slowly, stop under reduced-motion preferences, and never imply a fabricated percentage.

## Do's and Don'ts

### Do:

- **Do** keep live product state, source, price, and freshness visually close.
- **Do** reserve transparency and ambient shadow for high-value operational surfaces.
- **Do** use tabular numerals for dashboard metrics and run counts.
- **Do** preserve explicit loading, success, error, empty, focus, and reduced-motion states.

### Don't:

- **Don't** add decorative charts, grid overlays, neon fields, or rainbow gradients.
- **Don't** place eyebrow labels or sequence numbers above otherwise clear headings.
- **Don't** use an LLM-style monospace costume, emoji as icons, or hard offset shadows.
- **Don't** let narrow layouts clip actions, product names, filters, or document content.
