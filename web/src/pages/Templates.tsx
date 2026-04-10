import { useState, useCallback } from 'react'
import {
  Table,
  Button,
  Space,
  message,
  Typography,
  Popconfirm,
  Tooltip,
} from 'antd'
import {
  BuildOutlined,
  DeleteOutlined,
  ReloadOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import usePolling from '../hooks/usePolling'
import { getTemplates, buildTemplate, deleteTemplate } from '../api/templates'
import StatusBadge from '../components/StatusBadge'
import BuildLogModal from '../components/BuildLogModal'
import type { TemplateListItem } from '../api/types'

const { Text } = Typography

export default function Templates() {
  const [templates, setTemplates] = useState<TemplateListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [buildModalOpen, setBuildModalOpen] = useState(false)
  const [buildingTemplate, setBuildingTemplate] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchTemplates = useCallback(async () => {
    try {
      const data = await getTemplates()
      setTemplates(data)
    } catch {
      // 轮询中静默处理
    }
  }, [])

  usePolling(fetchTemplates, 5000)

  const handleRefresh = async () => {
    setLoading(true)
    await fetchTemplates()
    setLoading(false)
  }

  const handleBuild = async (name: string) => {
    setActionLoading(name)
    try {
      await buildTemplate(name)
      setBuildingTemplate(name)
      setBuildModalOpen(true)
    } catch {
      message.error('触发构建失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleBuildAll = async () => {
    const unbuildable = templates.filter(
      (t) => t.status === 'unbuilt' || t.status === 'failed',
    )
    if (unbuildable.length === 0) {
      message.info('没有需要构建的模板')
      return
    }
    setLoading(true)
    try {
      await Promise.all(unbuildable.map((t) => buildTemplate(t.name)))
      message.success(`已触发 ${unbuildable.length} 个模板构建`)
      await fetchTemplates()
    } catch {
      message.error('部分构建触发失败')
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (name: string) => {
    setActionLoading(name)
    try {
      await deleteTemplate(name)
      message.success('模板已删除')
      await fetchTemplates()
    } catch {
      message.error('删除失败')
    } finally {
      setActionLoading(null)
    }
  }

  const formatSize = (bytes: number | null) => {
    if (bytes === null || bytes === undefined) return '-'
    const mb = bytes / (1024 * 1024)
    return `${mb.toFixed(1)} MB`
  }

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 180,
      render: (name: string) => (
        <Text className="mono" style={{ color: '#8b5cf6', fontWeight: 500 }}>
          {name}
        </Text>
      ),
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      width: 220,
      render: (desc: string) => (
        <Text style={{ color: '#9ca3af' }}>
          {desc || '暂无描述'}
        </Text>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 110,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: '来源',
      dataIndex: 'source',
      key: 'source',
      width: 100,
      render: (source: string) => {
        const labels: Record<string, string> = {
          builtin: '内置',
          custom: '自定义',
          snapshot: '快照',
        }
        return (
          <Text style={{ color: '#9ca3af', fontSize: 12 }}>
            {labels[source] || source}
          </Text>
        )
      },
    },
    {
      title: '连接类型',
      dataIndex: 'connect_type',
      key: 'connect_type',
      width: 100,
      render: (type: string) => (
        <Text className="mono" style={{ fontSize: 12, color: '#9ca3af' }}>
          {type}
        </Text>
      ),
    },
    {
      title: '镜像大小',
      dataIndex: 'size_bytes',
      key: 'size_bytes',
      width: 110,
      render: (bytes: number | null) => (
        <Text className="mono" style={{ fontSize: 12, color: '#9ca3af' }}>
          {formatSize(bytes)}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: unknown, record: TemplateListItem) => (
        <Space size={4}>
          {(record.status === 'unbuilt' || record.status === 'failed') && (
            <Button
              type="text"
              size="small"
              icon={<BuildOutlined />}
              onClick={() => handleBuild(record.name)}
              loading={actionLoading === record.name}
              style={{ color: '#3b82f6' }}
            >
              构建
            </Button>
          )}
          {record.status === 'building' && (
            <Button
              type="text"
              size="small"
              loading
              style={{ color: '#3b82f6' }}
            >
              构建中
            </Button>
          )}
          <Tooltip title="查看详情">
            <Button
              type="text"
              size="small"
              icon={<InfoCircleOutlined />}
              onClick={() => {
                setBuildingTemplate(record.name)
                setBuildModalOpen(true)
              }}
              style={{ color: '#9ca3af' }}
            />
          </Tooltip>
          <Popconfirm
            title="确认删除？"
            description={`将删除模板 ${record.name} 及其镜像`}
            onConfirm={() => handleDelete(record.name)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              type="text"
              size="small"
              icon={<DeleteOutlined />}
              loading={actionLoading === record.name}
              danger
            />
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button
            type="primary"
            icon={<BuildOutlined />}
            onClick={handleBuildAll}
            loading={loading}
          >
            全部构建
          </Button>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
          刷新
        </Button>
      </div>

      <Table
        dataSource={templates}
        columns={columns}
        rowKey="name"
        loading={loading}
        pagination={{
          pageSize: 20,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 个模板`,
        }}
        size="middle"
        locale={{ emptyText: '暂无模板' }}
      />

      <BuildLogModal
        open={buildModalOpen}
        templateName={buildingTemplate}
        onClose={() => {
          setBuildModalOpen(false)
          setBuildingTemplate(null)
        }}
        onBuildComplete={fetchTemplates}
      />
    </div>
  )
}
