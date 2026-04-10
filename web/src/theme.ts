import type { ThemeConfig } from 'antd'
import theme from 'antd/es/theme'

const { darkAlgorithm } = theme

const cyberpunkTheme: ThemeConfig = {
  algorithm: darkAlgorithm,
  token: {
    // Seed tokens
    colorPrimary: '#06b6d4',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#3b82f6',
    colorBgBase: '#0a0e17',
    colorTextBase: '#e5e7eb',
    borderRadius: 6,
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
    fontFamilyCode: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
    fontSize: 14,
  },
  components: {
    Layout: {
      siderBg: '#0d1117',
      headerBg: '#0d1117',
      bodyBg: '#0a0e17',
      triggerBg: '#111827',
    },
    Menu: {
      darkItemBg: '#0d1117',
      darkItemSelectedBg: 'rgba(6, 182, 212, 0.15)',
      darkItemHoverBg: 'rgba(6, 182, 212, 0.08)',
      darkItemSelectedColor: '#06b6d4',
    },
    Table: {
      headerBg: '#111827',
      rowHoverBg: 'rgba(6, 182, 212, 0.04)',
      borderColor: 'rgba(6, 182, 212, 0.08)',
    },
    Card: {
      colorBgContainer: '#111827',
      colorBorderSecondary: 'rgba(6, 182, 212, 0.08)',
    },
    Modal: {
      contentBg: '#111827',
      headerBg: '#111827',
    },
    Button: {
      primaryShadow: '0 0 8px rgba(6, 182, 212, 0.3)',
    },
    Input: {
      colorBgContainer: '#0d1117',
      activeBorderColor: '#06b6d4',
      hoverBorderColor: 'rgba(6, 182, 212, 0.5)',
    },
    Select: {
      colorBgContainer: '#0d1117',
      colorBgElevated: '#111827',
      optionActiveBg: 'rgba(6, 182, 212, 0.1)',
    },
    Tag: {
      defaultBg: 'transparent',
    },
    Tooltip: {
      colorBgSpotlight: '#1e293b',
    },
  },
}

export default cyberpunkTheme
