// Plus Jakarta Sans — headlines / brand
// Be Vietnam Pro      — body / labels
// Loaded via expo-font in App.tsx

export const Fonts = {
  headline: 'PlusJakartaSans',
  body: 'BeVietnamPro',
  label: 'BeVietnamPro',
} as const;

export const FontWeights = {
  light: '300',
  regular: '400',
  medium: '500',
  semibold: '600',
  bold: '700',
  extrabold: '800',
} as const;

export const TextStyles = {
  // Headlines
  displayLarge:  { fontFamily: 'PlusJakartaSans-ExtraBold', fontSize: 32, letterSpacing: -0.8 },
  displayMedium: { fontFamily: 'PlusJakartaSans-Bold',      fontSize: 24, letterSpacing: -0.5 },
  titleLarge:    { fontFamily: 'PlusJakartaSans-Bold',      fontSize: 20, letterSpacing: -0.3 },
  titleMedium:   { fontFamily: 'PlusJakartaSans-SemiBold',  fontSize: 16, letterSpacing: -0.2 },
  titleSmall:    { fontFamily: 'PlusJakartaSans-SemiBold',  fontSize: 14, letterSpacing: 0 },

  // Body
  bodyLarge:     { fontFamily: 'BeVietnamPro-Regular', fontSize: 16, lineHeight: 24 },
  bodyMedium:    { fontFamily: 'BeVietnamPro-Regular', fontSize: 14, lineHeight: 21 },
  bodySmall:     { fontFamily: 'BeVietnamPro-Regular', fontSize: 12, lineHeight: 18 },

  // Labels (uppercase tracking)
  labelLarge:    { fontFamily: 'BeVietnamPro-SemiBold', fontSize: 11, letterSpacing: 1.2, textTransform: 'uppercase' as const },
  labelMedium:   { fontFamily: 'BeVietnamPro-Medium',   fontSize: 10, letterSpacing: 1.0, textTransform: 'uppercase' as const },
} as const;
