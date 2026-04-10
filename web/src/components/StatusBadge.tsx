import { Tag } from 'antd'
import { LoadingOutlined } from '@ant-design/icons'

type SandboxStatus = 'running' | 'paused' | 'stopped'
type TemplateStatus = 'ready' | 'building' | 'unbuilt' | 'failed'
type StatusType = SandboxStatus | TemplateStatus

const statusConfig: Record<StatusType, { color: string; label: string }> = {
  running: { color: '#10b981', label: '运行中' },
  paused: { color: '#f59e0b', label: '已暂停' },
  stopped: { color: '#ef4444', label: '已停止' },
  ready: { color: '#10b981', label: '就绪' },
  building: { color: '#3b82f6', label: '构建中' },
  unbuilt: { color: '#6b7280', label: '未构建' },
  failed: { color: '#ef4444', label: '失败' },
}

interface StatusBadgeProps {
  status: string
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status as StatusType] || {
    color: '#6b7280',
    label: status,
  }

  return (
    <Tag
      color={config.color}
      style={{
        borderColor: config.color,
        background: `${config.color}18`,
        fontSize: 12,
      }}
      className={status === 'building' ? 'status-building' : undefined}
      icon={status === 'building' ? <LoadingOutlined spin /> : undefined}
    >
      {config.label}
    </Tag>
  )
}
