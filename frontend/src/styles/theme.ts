import type { GlobalThemeOverrides } from 'naive-ui'

const FONT = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", "PingFang SC", sans-serif'

export const lightOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#6366f1',
    primaryColorHover: '#4f46e5',
    primaryColorPressed: '#4338ca',
    borderRadius: '10px',
    bodyColor: '#fafafa',
    cardColor: '#ffffff',
    modalColor: '#ffffff',
    textColorBase: '#1f2937',
    textColor1: '#1f2937',
    textColor2: '#4b5563',
    textColor3: '#6b7280',
    borderColor: '#e5e7eb',
    dividerColor: '#eceef1',
    fontFamily: FONT,
  },
  Card: { borderRadius: '10px', color: '#ffffff' },
  Button: { borderRadiusMedium: '6px', borderRadiusSmall: '6px', borderRadiusTiny: '6px' },
  Tag: { borderRadius: '6px' },
  Input: { borderRadius: '6px' },
  Select: { peers: { InternalSelection: { borderRadius: '6px' } } },
  Menu: { itemHeight: '40px' },
}

export const darkOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: '#6366f1',
    primaryColorHover: '#4f46e5',
    primaryColorPressed: '#4338ca',
    borderRadius: '10px',
    bodyColor: '#15171c',
    cardColor: '#1c1f26',
    modalColor: '#1c1f26',
    textColorBase: '#e5e7eb',
    textColor1: '#e5e7eb',
    textColor2: '#c9cdd4',
    textColor3: '#9ca3af',
    borderColor: '#2a2e37',
    dividerColor: '#262a32',
    fontFamily: FONT,
  },
  Card: { borderRadius: '10px', color: '#1c1f26' },
  Button: { borderRadiusMedium: '6px', borderRadiusSmall: '6px', borderRadiusTiny: '6px' },
  Tag: { borderRadius: '6px' },
  Input: { borderRadius: '6px' },
  Select: { peers: { InternalSelection: { borderRadius: '6px' } } },
  Menu: { itemHeight: '40px', color: '#111317', itemTextColor: '#9ca3af', itemTextColorActive: '#e5e7eb', itemColorActive: '#262a32' },
  Layout: { siderColor: '#111317', siderBorderColor: '#2a2e37' },
}
