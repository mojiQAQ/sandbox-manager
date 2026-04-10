import { useState, useCallback } from 'react'
import {
  Table,
  Button,
  Space,
  message,
  Tooltip,
  Typography,
  Popconfirm,
} from 'antd'
import {
  PlusOutlined,
  DeleteOutlined,
  ReloadOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  CameraOutlined,
  CodeOutlined,
  GlobalOutlined,
} from '@ant-design/icons'
import 'react-router-dom'
import usePolling from '../hooks/usePolling'
import {
  getSandboxes,
  deleteSandbox,
  deleteAllSandboxes,
  pauseSandbox,
  resumeSandbox,
  getConnectInfo,
} from '../api/sandboxes'
import StatusBadge from '../components/StatusBadge'
import CreateSandboxModal from '../components/CreateSandboxModal'
import SnapshotModal from '../components/SnapshotModal'
import type { SandboxListItem } from '../api/types'

const { Text } = Typography

export default function Sandboxes() {
  const [sandboxes, setSandboxes] = useState<SandboxListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([])
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false)
  const [snapshotSandboxId, setSnapshotSandboxId] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const fetchSandboxes = useCallback(async () => {
    try {
      const data = await getSandboxes()
      setSandboxes(data)
    } catch {
      // 轮询中静默处理
    }
  }, [])

  usePolling(fetchSandboxes, 5000)

  const handleRefresh = async () => {
    setLoading(true)
    await fetchSandboxes()
    setLoading(false)
  }

  const handleDelete = async (id: string) => {
    setActionLoading(id)
    try {
      await deleteSandbox(id)
      message.success('沙盒已删除')
      await fetchSandboxes()
    } catch {
      message.error('删除失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleBatchDelete = async () => {
    setLoading(true)
    try {
      const result = await deleteAllSandboxes()
      message.success(`已删除 ${result.deleted} 个沙盒`)
      setSelectedRowKeys([])
      await fetchSandboxes()
    } catch {
      message.error('批量删除失败')
    } finally {
      setLoading(false)
    }
  }

  const handlePauseResume = async (id: string, currentStatus: string) => {
    setActionLoading(id)
    try {
      if (currentStatus === 'running') {
        await pauseSandbox(id)
        message.success('沙盒已暂停')
      } else if (currentStatus === 'paused') {
        await resumeSandbox(id)
        message.success('沙盒已恢复')
      }
      await fetchSandboxes()
    } catch {
      message.error('操作失败')
    } finally {
      setActionLoading(null)
    }
  }

  const handleConnect = (id: string) => {
    window.open(`/terminal/${id}`, '_blank')
  }

  const handleSnapshot = (id: string) => {
    setSnapshotSandboxId(id)
    setSnapshotModalOpen(true)
  }

  const handleQuickConnect = async (record: SandboxListItem) => {
    if (record.status !== 'running') {
      message.warning('沙盒未运行，无法连接')
      return
    }
    if (record.connect_type === 'url') {
      try {
        const info = await getConnectInfo(record.id)
        if (info.url) {
          window.open(info.url, '_blank')
        } else {
          message.error('未获取到访问地址')
        }
      } catch {
        message.error('获取连接信息失败')
      }
    } else {
      window.open(`/terminal/${record.id}`, '_blank')
    }
  }

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 140,
      render: (id: string) => (
        <Tooltip title={id}>
          <Text className="mono" style={{ color: '#06b6d4', fontSize: 12 }} copyable={{ text: id }}>
            {id.slice(0, 12)}
          </Text>
        </Tooltip>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      width: 160,
      render: (name: string | null) => name || <Text style={{ color: '#6b7280' }}>-</Text>,
    },
    {
      title: '模板',
      dataIndex: 'template_name',
      key: 'template_name',
      width: 140,
      render: (name: string | null) =>
        name ? (
          <Text className="mono" style={{ color: '#8b5cf6', fontSize: 12 }}>
            {name}
          </Text>
        ) : (
          '-'
        ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: '连接方式',
      dataIndex: 'connect_type',
      key: 'connect_type',
      width: 130,
      render: (type: string | null, record: SandboxListItem) => {
        if (!type) return '-'
        const disabled = record.status !== 'running'
        if (type === 'url') {
          return (
            <Button
              type="link"
              size="small"
              icon={<GlobalOutlined />}
              onClick={() => handleQuickConnect(record)}
              disabled={disabled}
              style={{ padding: 0, color: disabled ? '#6b7280' : '#06b6d4' }}
            >
              打开网页
            </Button>
          )
        }
        return (
          <Button
            type="link"
            size="small"
            icon={<CodeOutlined />}
            onClick={() => handleQuickConnect(record)}
            disabled={disabled}
            style={{ padding: 0, color: disabled ? '#6b7280' : '#10b981' }}
          >
            进入终端
          </Button>
        )
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (t: string) => (
        <Text style={{ color: '#9ca3af', fontSize: 12 }}>
          {new Date(t).toLocaleString('zh-CN')}
        </Text>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 340,
      render: (_: unknown, record: SandboxListItem) => (
        <Space size={4}>
          <Tooltip title="连接终端">
            <Button
              type="text"
              size="small"
              icon={<CodeOutlined />}
              onClick={() => handleConnect(record.id)}
              disabled={record.status !== 'running'}
              style={{ color: record.status === 'running' ? '#06b6d4' : undefined }}
            >
              终端
            </Button>
          </Tooltip>
          <Tooltip title={record.status === 'running' ? '暂停' : record.status === 'paused' ? '恢复' : '不可操作'}>
            <Button
              type="text"
              size="small"
              icon={record.status === 'paused' ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={() => handlePauseResume(record.id, record.status)}
              disabled={record.status === 'stopped'}
              loading={actionLoading === record.id}
              style={{
                color:
                  record.status === 'running'
                    ? '#f59e0b'
                    : record.status === 'paused'
                      ? '#10b981'
                      : undefined,
              }}
            >
              {record.status === 'paused' ? '恢复' : '暂停'}
            </Button>
          </Tooltip>
          <Tooltip title="快照">
            <Button
              type="text"
              size="small"
              icon={<CameraOutlined />}
              onClick={() => handleSnapshot(record.id)}
              disabled={record.status !== 'running'}
              style={{ color: record.status === 'running' ? '#8b5cf6' : undefined }}
            >
              快照
            </Button>
          </Tooltip>
          <Popconfirm
            title="确认删除？"
            description="此操作将永久删除该沙盒"
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Tooltip title="删除">
              <Button
                type="text"
                size="small"
                icon={<DeleteOutlined />}
                loading={actionLoading === record.id}
                danger
              >
                删除
              </Button>
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            创建沙盒
          </Button>
          <Popconfirm
            title="确认批量删除？"
            description="此操作将删除所有沙盒"
            onConfirm={handleBatchDelete}
            okText="全部删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
          >
            <Button
              danger
              icon={<DeleteOutlined />}
              disabled={sandboxes.length === 0}
            >
              全部删除
            </Button>
          </Popconfirm>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>
          刷新
        </Button>
      </div>

      <Table
        dataSource={sandboxes}
        columns={columns}
        rowKey="id"
        loading={loading}
        rowSelection={{
          selectedRowKeys,
          onChange: setSelectedRowKeys,
        }}
        pagination={{
          pageSize: 20,
          showSizeChanger: false,
          showTotal: (total) => `共 ${total} 个沙盒`,
        }}
        size="middle"
        locale={{ emptyText: '暂无沙盒' }}
      />

      <CreateSandboxModal
        open={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
        onSuccess={fetchSandboxes}
      />

      <SnapshotModal
        open={snapshotModalOpen}
        sandboxId={snapshotSandboxId}
        onClose={() => {
          setSnapshotModalOpen(false)
          setSnapshotSandboxId(null)
        }}
        onSuccess={fetchSandboxes}
      />
    </div>
  )
}
