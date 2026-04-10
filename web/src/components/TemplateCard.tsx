import {
  CodeOutlined,
  GlobalOutlined,
  ApiOutlined,
  RocketOutlined,
  BuildOutlined,
} from '@ant-design/icons'
import { Button, Space, Tag } from 'antd'
import StatusBadge from './StatusBadge'
import type { TemplateListItem } from '../api/types'

interface TemplateCardProps {
  template: TemplateListItem
  onLaunch: (name: string) => void
  onBuild: (name: string) => void
  loading?: boolean
}

const connectIcons: Record<string, React.ReactNode> = {
  shell: <CodeOutlined />,
  url: <GlobalOutlined />,
  port: <ApiOutlined />,
}

export default function TemplateCard({ template, onLaunch, onBuild, loading }: TemplateCardProps) {
  const isReady = template.status === 'ready'
  const isUnbuilt = template.status === 'unbuilt' || template.status === 'failed'
  const isBuilding = template.status === 'building'

  return (
    <div className="template-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontSize: 20,
              color: '#8b5cf6',
              display: 'flex',
              alignItems: 'center',
            }}
          >
            {connectIcons[template.connect_type] || <CodeOutlined />}
          </span>
          <span
            className="mono"
            style={{ fontSize: 15, fontWeight: 600, color: '#e5e7eb' }}
          >
            {template.name}
          </span>
        </div>
        <StatusBadge status={template.status} />
      </div>

      <p style={{ color: '#9ca3af', fontSize: 13, marginBottom: 16, minHeight: 38 }}>
        {template.description || '暂无描述'}
      </p>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Tag
          style={{
            background: 'rgba(139, 92, 246, 0.1)',
            borderColor: 'rgba(139, 92, 246, 0.2)',
            color: '#8b5cf6',
            fontSize: 11,
          }}
        >
          {template.connect_type}
        </Tag>
        <Space>
          {isReady && (
            <Button
              type="primary"
              size="small"
              icon={<RocketOutlined />}
              loading={loading}
              onClick={(e) => {
                e.stopPropagation()
                onLaunch(template.name)
              }}
            >
              启动
            </Button>
          )}
          {isUnbuilt && (
            <Button
              size="small"
              icon={<BuildOutlined />}
              loading={loading}
              onClick={(e) => {
                e.stopPropagation()
                onBuild(template.name)
              }}
              style={{ borderColor: '#3b82f6', color: '#3b82f6' }}
            >
              构建
            </Button>
          )}
          {isBuilding && (
            <Button size="small" disabled>
              构建中...
            </Button>
          )}
        </Space>
      </div>
    </div>
  )
}
