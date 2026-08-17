---
name: T-REX DataLab Design System
colors:
  surface: '#fcf9f8'
  surface-dim: '#dcd9d9'
  surface-bright: '#fcf9f8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f6f3f2'
  surface-container: '#f0edec'
  surface-container-high: '#ebe7e7'
  surface-container-highest: '#e5e2e1'
  on-surface: '#1c1b1b'
  on-surface-variant: '#3e4a3f'
  inverse-surface: '#313030'
  inverse-on-surface: '#f3f0ef'
  outline: '#6e7a6e'
  outline-variant: '#bdcabc'
  surface-tint: '#006d34'
  primary: '#006b33'
  on-primary: '#ffffff'
  primary-container: '#008742'
  on-primary-container: '#f7fff3'
  inverse-primary: '#6fdc8c'
  secondary: '#40674b'
  on-secondary: '#ffffff'
  secondary-container: '#bfeac7'
  on-secondary-container: '#446b4f'
  tertiary: '#815200'
  on-tertiary: '#ffffff'
  tertiary-container: '#a1680d'
  on-tertiary-container: '#fffbff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#8bf9a6'
  primary-fixed-dim: '#6fdc8c'
  on-primary-fixed: '#00210b'
  on-primary-fixed-variant: '#005226'
  secondary-fixed: '#c2edca'
  secondary-fixed-dim: '#a6d1af'
  on-secondary-fixed: '#00210e'
  on-secondary-fixed-variant: '#294e35'
  tertiary-fixed: '#ffddb7'
  tertiary-fixed-dim: '#ffb95c'
  on-tertiary-fixed: '#2a1700'
  on-tertiary-fixed-variant: '#653e00'
  background: '#fcf9f8'
  on-background: '#1c1b1b'
  surface-variant: '#e5e2e1'
  slate-gray: '#4A5568'
  surface-faint: '#F8FAFC'
  border-subtle: '#E2E8F0'
  success-green: '#19924B'
  warning-orange: '#F5B054'
typography:
  headline-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  data-table:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 18px
  label-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  sidebar-width: 260px
  container-max: 1440px
  gutter: 1.5rem
  stack-sm: 0.5rem
  stack-md: 1rem
  stack-lg: 2rem
---

## Brand & Style
The design system is anchored in the concept of "Industrial Precision." It is built for a high-performance data analysis and machine learning environment where accuracy, reliability, and technical sophistication are paramount. 

The visual style follows a **Corporate / Modern** aesthetic with a lean toward **Industrial Minimalism**. It prioritizes information density and data readability without sacrificing a premium, "lab" atmosphere. The interface uses a structured sidebar-based navigation, clean borders, and a high-contrast palette to ensure that complex data sets remain the primary focus. 

The emotional response should be one of "Robust Confidence"—users should feel they are operating powerful, stable machinery through a refined digital interface.

## Colors
The palette is derived from the industrial heritage of the T-REX brand, utilizing a deep **Forest Green (#19924B)** as the primary action color. This is balanced by **Deep Obsidian (#002812)** for structural elements like sidebars and headers, providing a solid "industrial" foundation.

**Functional Application:**
- **Primary:** Used for main call-to-actions, progress bars, and active states.
- **Secondary:** Reserved for the global sidebar and primary navigation backgrounds.
- **Tertiary (Accent):** The T-REX orange is used sparingly for highlights, status warnings, or to draw attention to specific data anomalies.
- **Neutral:** A range of slate grays and near-blacks are used for typography and UI borders to ensure high contrast for data readability.

## Typography
The system employs a tri-font strategy to balance character and utility:
- **Plus Jakarta Sans:** Used for headlines and brand-heavy moments. It adds a modern, welcoming touch to the industrial frame.
- **Inter:** The workhorse font for all body copy, inputs, and complex data tables. It was chosen for its exceptional legibility at small sizes.
- **JetBrains Mono:** Used specifically for technical metadata, timestamps, and machine learning parameters to reinforce the "Lab" aesthetic.

Turkish language support is native to these selections, ensuring correct rendering of characters like "ğ, ü, ş, i, ö, ç" across all weights.

## Layout & Spacing
The layout follows a **Fixed-Fluid Hybrid** model. A fixed-width sidebar (260px) persists on the left for global navigation, while the main content area utilizes a fluid grid that expands to a maximum of 1440px to prevent excessive line lengths on ultra-wide monitors.

**Grid Logic:**
- **Columns:** 12-column system for the main content area.
- **Margins:** 24px (1.5rem) on desktop; 16px on mobile.
- **Data Density:** Use a compact 8px base unit for internal component spacing to maximize the amount of information visible on a single screen without overcrowding.

## Elevation & Depth
Depth is communicated through **Tonal Layers** and **Low-Contrast Outlines** rather than heavy shadows, maintaining a "flat-industrial" look.

- **Level 0 (Base):** The main canvas background, using a very light gray (#F8FAFC).
- **Level 1 (Surface):** Cards, data tables, and white containers. These use a 1px solid border (#E2E8F0) to define their boundaries.
- **Level 2 (Interaction):** Hover states on cards or buttons may utilize a subtle, tight shadow (0 4px 6px -1px rgba(0, 0, 0, 0.05)) to suggest "lift."
- **Sidebar:** Positioned at Level 3, utilizing a dark background to visually recede while grounding the navigation.

## Shapes
To maintain an industrial and professional feel, the design system utilizes **Soft (0.25rem)** roundedness. This provides enough softening to feel modern and user-friendly while remaining sharp enough to feel like a precise technical tool. 

- **Inputs and Buttons:** 4px (0.25rem) radius.
- **Large Cards/Containers:** 8px (0.5rem) radius.
- **Status Badges:** Fully rounded (pill) to distinguish them from interactive buttons.

## Components
Consistent component styling ensures the platform feels like a cohesive "DataLab."

- **Side Navigation (Yan Menü):** Dark background (#002812), white text with 70% opacity, and primary green highlight for the active state. Use icons for every entry.
- **Data Tables (Veri Tabloları):** Zebra striping is avoided; use subtle 1px horizontal dividers only. Header text should be uppercase JetBrains Mono at 11px for a "technical spec" look.
- **Upload Zones (Yükleme Alanları):** Dashed borders in slate gray with a primary green icon. Provide clear Turkish instructions (e.g., "Dosyayı buraya sürükleyin").
- **Status Badges (Durum Rozetleri):** Use light background tints of the status color (e.g., light green for 'Tamamlandı', light orange for 'Beklemede') with dark text.
- **Progress Bars (İlerleme Çubukları):** Thin (4px) bars. The background track should be a light gray, with the fill using the Primary Green gradient.
- **Chart Containers:** White background, 1px border, with a "Header" section containing the chart title (Turkish) and a filtered date range picker.