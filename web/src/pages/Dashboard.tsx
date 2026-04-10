import { useState, useCallback } from 'react'
import { Row, Col, Card, Statistic, Table, message, Typography, Space } from 'antd'
import {
  CloudServerOutlined,
  AppstoreOutlined,
  LinkOutlined,
  InfoCircleOutlined,
  RocketOutlined,
} from '@ant-design/icons'
import 'react-router-dom'
import usePolling from '../hooks/usePolling'
import { getSystemStatus, getHealth, getSandboxes, getConnectInfo } from '../api/sandboxes'
import { getTemplates, buildTemplate } from '../api/templates'
import { createSandbox } from '../api/sandboxes'
import TemplateCard from '../components/TemplateCard'
import BuildLogModal from '../components/BuildLogModal'
import StatusBadge from '../components/StatusBadge'
import type { SystemStatus, HealthResponse, TemplateListItem, SandboxListItem } from '../api/types'

const { Text } = Typography

export default function Dashboard() {
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null)
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [templates, setTemplates] = useState<TemplateListItem[]>([])
  const [sandboxes, setSandboxes] = useState<SandboxListItem[]>([])
  const [launchLoading, setLaunchLoading] = useState<string | null>(null)
  const [buildModalOpen, setBuildModalOpen] = useState(false)
  const [buildingTemplate, setBuildingTemplate] = useState<string | null>(null)

  const fetchData = useCallback(async () => {
    try {
      const [statusData, healthData, templateData, sandboxData] = await Promise.all([
        getSystemStatus(),
        getHealth(),
        getTemplates(),
        getSandboxes(),
      ])
      setSystemStatus(statusData)
      setHealth(healthData)
      setTemplates(templateData)
      setSandboxes(sandboxData)
    } catch {
      // 静默处理，避免轮询时反复弹错误
    }
  }, [])

  usePolling(fetchData, 5000)

  const handleLaunch = async (templateName: string) => {
    setLaunchLoading(templateName)
    try {
      const sandbox = await createSandbox({ template_name: templateName })
      message.success(`沙盒已从 ${templateName} 模板启动`)
      await fetchData()

      // 根据连接类型自动跳转（新 tab）
      const tpl = templates.find((t) => t.name === templateName)
      if (tpl?.connect_type === 'url') {
        try {
          const info = await getConnectInfo(sandbox.id)
          if (info.url) {
            window.open(info.url, '_blank')
          }
        } catch {
          // 获取连接信息失败时忽略
        }
      } else {
        window.open(`/terminal/${sandbox.id}`, '_blank')
      }
    } catch {
      message.error('启动沙盒失败')
    } finally {
      setLaunchLoading(null)
    }
  }

  const handleBuild = async (templateName: string) => {
    try {
      await buildTemplate(templateName)
      setBuildingTemplate(templateName)
      setBuildModalOpen(true)
    } catch {
      message.error('触发构建失败')
    }
  }

  const connected = health?.opensandbox_connected ?? false
  const displayTemplates = templates.slice(0, 4)
  const recentSandboxes = [...sandboxes]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5)

  const recentColumns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      render: (id: string) => (
        <Text className="mono" style={{ color: '#06b6d4', fontSize: 12 }}>
          {id.slice(0, 12)}
        </Text>
      ),
    },
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string | null) => name || '-',
    },
    {
      title: '模板',
      dataIndex: 'template_name',
      key: 'template_name',
      render: (name: string | null) =>
        name ? <Text className="mono" style={{ color: '#8b5cf6' }}>{name}</Text> : '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => <StatusBadge status={status} />,
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => new Date(t).toLocaleString('zh-CN'),
    },
  ]

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card className="stat-card" variant="borderless">
            <Statistic
              title={
                <Space>
                  <LinkOutlined />
                  <span>连接状态</span>
                </Space>
              }
              value={connected ? '已连接' : '未连接'}
              valueStyle={{ color: connected ? '#10b981' : '#ef4444', fontSize: 18 }}
              prefix={
                <span
                  className="indicator-dot"
                  style={{
                    backgroundColor: connected ? '#10b981' : '#ef4444',
                    boxShadow: connected
                      ? '0 0 6px rgba(16,185,129,0.5)'
                      : '0 0 6px rgba(239,68,68,0.5)',
                  }}
                />
              }
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card" variant="borderless">
            <Statistic
              title={
                <Space>
                  <CloudServerOutlined />
                  <span>活跃沙盒</span>
                </Space>
              }
              value={systemStatus?.active_sandboxes ?? '-'}
              valueStyle={{ color: '#06b6d4', fontSize: 24 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card" variant="borderless">
            <Statistic
              title={
                <Space>
                  <AppstoreOutlined />
                  <span>已构建模板</span>
                </Space>
              }
              value={`${systemStatus?.built_templates ?? '-'} / ${systemStatus?.total_templates ?? '-'}`}
              valueStyle={{ color: '#8b5cf6', fontSize: 24 }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="stat-card" variant="borderless">
            <Statistic
              title={
                <Space>
                  <InfoCircleOutlined />
                  <span>系统版本</span>
                </Space>
              }
              value={health?.version ?? '-'}
              valueStyle={{
                color: '#9ca3af',
                fontSize: 16,
                fontFamily: '"JetBrains Mono", monospace',
              }}
            />
          </Card>
        </Col>
      </Row>

      {/* 快速启动 */}
      <div className="quick-launch-section" style={{ marginBottom: 24 }}>
        <div className="section-title">
          <RocketOutlined style={{ color: '#06b6d4' }} />
          快速启动
        </div>
        <Row gutter={16}>
          {displayTemplates.map((tpl) => (
            <Col span={6} key={tpl.name}>
              <TemplateCard
                template={tpl}
                onLaunch={handleLaunch}
                onBuild={handleBuild}
                loading={launchLoading === tpl.name}
              />
            </Col>
          ))}
          {displayTemplates.length === 0 && (
            <Col span={24}>
              <div
                style={{
                  textAlign: 'center',
                  padding: 40,
                  color: '#6b7280',
                }}
              >
                暂无模板，请先在模板管理页面添加模板
              </div>
            </Col>
          )}
        </Row>
      </div>

      {/* 最近沙盒 */}
      <div>
        <div className="section-title">最近沙盒</div>
        <Table
          dataSource={recentSandboxes}
          columns={recentColumns}
          rowKey="id"
          pagination={false}
          size="small"
          locale={{ emptyText: '暂无沙盒' }}
        />
      </div>

      {/* 构建日志弹窗 */}
      <BuildLogModal
        open={buildModalOpen}
        templateName={buildingTemplate}
        onClose={() => setBuildModalOpen(false)}
        onBuildComplete={fetchData}
      />
    </div>
  )
}
