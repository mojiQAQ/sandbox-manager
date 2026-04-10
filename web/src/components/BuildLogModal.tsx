import { useState, useEffect, useRef, useCallback } from 'react'
import { Modal, Spin, Result } from 'antd'
import { LoadingOutlined, CheckCircleOutlined, CloseCircleOutlined } from '@ant-design/icons'
import { getTemplateBuildStatus } from '../api/templates'
import type { TemplateBuildStatus } from '../api/types'

interface BuildLogModalProps {
  open: boolean
  templateName: string | null
  onClose: () => void
  onBuildComplete: () => void
}

export default function BuildLogModal({
  open,
  templateName,
  onClose,
  onBuildComplete,
}: BuildLogModalProps) {
  const [status, setStatus] = useState<TemplateBuildStatus | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // 当弹窗关闭时重置状态
  const handleAfterClose = useCallback(() => {
    setStatus(null)
    clearTimer()
  }, [clearTimer])

  useEffect(() => {
    if (!open || !templateName) {
      clearTimer()
      return
    }

    let cancelled = false

    const pollStatus = async () => {
      try {
        const result = await getTemplateBuildStatus(templateName)
        if (cancelled) return
        setStatus(result)

        if (result.status !== 'building') {
          clearTimer()
          onBuildComplete()
        }
      } catch {
        // 继续轮询
      }
    }

    pollStatus()
    timerRef.current = setInterval(pollStatus, 2000)

    return () => {
      cancelled = true
      clearTimer()
    }
  }, [open, templateName, clearTimer, onBuildComplete])

  const isBuilding = !status || status.status === 'building'
  const isSuccess = status?.status === 'ready'
  const isFailed = status?.status === 'failed'

  return (
    <Modal
      title={
        <span>
          构建模板:{' '}
          <span className="mono" style={{ color: '#8b5cf6' }}>
            {templateName}
          </span>
        </span>
      }
      open={open}
      onCancel={onClose}
      afterClose={handleAfterClose}
      footer={null}
      width={520}
    >
      <div
        style={{
          minHeight: 160,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px 0',
        }}
      >
        {isBuilding && (
          <>
            <Spin indicator={<LoadingOutlined style={{ fontSize: 40, color: '#3b82f6' }} />} />
            <p style={{ marginTop: 20, color: '#9ca3af', fontSize: 14 }}>
              正在构建镜像，请稍候...
            </p>
            <p style={{ color: '#6b7280', fontSize: 12, marginTop: 4 }}>
              状态: {status?.status || '等待中'}
            </p>
          </>
        )}

        {isSuccess && (
          <Result
            icon={<CheckCircleOutlined style={{ color: '#10b981' }} />}
            title="构建成功"
            subTitle={`模板 ${templateName} 镜像已就绪`}
            style={{ padding: 0 }}
          />
        )}

        {isFailed && (
          <Result
            icon={<CloseCircleOutlined style={{ color: '#ef4444' }} />}
            status="error"
            title="构建失败"
            subTitle={status?.build_error || '未知错误'}
            style={{ padding: 0 }}
          />
        )}
      </div>
    </Modal>
  )
}
