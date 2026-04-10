import { Layout, Menu } from 'antd'
import {
  DashboardOutlined,
  CloudServerOutlined,
  AppstoreOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'

const { Sider, Header, Content } = Layout

const menuItems = [
  {
    key: '/',
    icon: <DashboardOutlined />,
    label: '仪表盘',
  },
  {
    key: '/sandboxes',
    icon: <CloudServerOutlined />,
    label: '沙盒管理',
  },
  {
    key: '/templates',
    icon: <AppstoreOutlined />,
    label: '模板管理',
  },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()

  // 匹配当前路径到 menu key
  const selectedKey = location.pathname.startsWith('/terminal')
    ? '/sandboxes'
    : location.pathname === '/'
      ? '/'
      : `/${location.pathname.split('/')[1]}`

  return (
    <Layout style={{ height: '100vh' }}>
      <Sider
        width={220}
        style={{
          borderRight: '1px solid rgba(6, 182, 212, 0.08)',
        }}
      >
        <div className="sidebar-logo">
          <span className="logo-bracket">[</span>
          &nbsp;SBX&nbsp;
          <span className="logo-bracket">]</span>
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
          style={{ borderRight: 'none', marginTop: 8 }}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid rgba(6, 182, 212, 0.08)',
            height: 48,
          }}
        >
          <span
            style={{
              color: '#9ca3af',
              fontFamily: '"JetBrains Mono", monospace',
              fontSize: 12,
            }}
          >
            Sandbox Manager
          </span>
        </Header>
        <Content
          style={{
            padding: 24,
            overflow: 'auto',
            background: '#0a0e17',
          }}
        >
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
