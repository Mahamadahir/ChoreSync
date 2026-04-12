export const Colors = {
  // Brand
  brandPrimary: '#94433A',
  terracotta: '#C1665B',

  // Surfaces
  warmCream: '#FDFBF7',
  lightClay: '#F5F2ED',
  surface: '#FDFBF7',
  white: '#FFFFFF',

  // Text
  charcoal: '#2F3332',
  onSurface: '#2F3332',

  // Neutrals
  outline: '#A8A29E',
  stone400: '#A8A29E',
  stone500: '#78716C',
  stone200: '#E7E5E4',
  stone300: '#D6D3D1',

  // Semantic
  error: '#DC2626',
  success: '#16A34A',
  warning: '#D97706',

  // Tab bar / nav
  navBackground: 'rgba(251,249,245,0.92)',
  navBorder: 'rgba(168,162,158,0.2)',

  // Dark mode equivalents (used in dark theme override)
  dark: {
    background: '#1C1917',
    surface: '#292524',
    terracotta: '#C1665B',
    charcoal: '#F5F5F4',
    stone400: '#78716C',
  },
} as const;

/**
 * Full Material You (M3) semantic token set shared across all feature screens.
 * Every screen's local `const C = { ... }` block is replaced with an import
 * of this object so there is exactly one place to change the palette.
 */
export const Palette = {
  // ── Backgrounds / surfaces ────────────────────────────────
  bg:                      '#fbf9f5',
  surface:                 '#fbf9f5',   // same as bg; use for true-surface contexts
  surfaceContainerLowest:  '#ffffff',
  surfaceContainerLow:     '#f5f3ef',
  surfaceContainer:        '#efeeea',
  surfaceContainerHigh:    '#eae8e4',
  surfaceContainerHighest: '#e4e2de',

  // ── Primary (terracotta red) ──────────────────────────────
  primary:          '#94433a',
  primaryContainer: '#b35b50',
  primaryFixed:     '#ffdad5',
  primaryLight:     '#c17a73',   // gradient start / muted accent
  primaryDisabled:  '#c87d76',   // disabled button gradient stop

  // ── Secondary (forest green) ─────────────────────────────
  secondary:              '#496640',
  secondaryLight:         '#6a8f5a',   // gradient end
  secondaryContainer:     '#caecbc',
  onSecondaryContainer:   '#4f6c45',

  // ── Tertiary (warm amber) ─────────────────────────────────
  tertiary:               '#7f521f',
  tertiaryFixed:          '#ffdcbd',
  onTertiaryFixed:        '#2c1600',
  onTertiaryFixedVariant: '#663d0b',

  // ── On-colors ─────────────────────────────────────────────
  onSurface:        '#1b1c1a',
  onSurfaceVariant: '#554240',

  // ── Outlines ──────────────────────────────────────────────
  outline:        '#87726f',
  outlineVariant: '#dac1bd',

  // ── Error ─────────────────────────────────────────────────
  error:           '#ba1a1a',
  errorContainer:  '#ffdad6',
  onErrorContainer:'#93000a',

  // ── Neutrals ──────────────────────────────────────────────
  white:    '#ffffff',
  stone400: '#a8a29e',
  stone500: '#78716c',

  // ── Disabled gradient stops (used in auth/action buttons) ─
  disabledStart: '#aaaaaa',
  disabledEnd:   '#bbbbbb',
} as const;
