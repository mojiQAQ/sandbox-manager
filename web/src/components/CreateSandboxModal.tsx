import { useState, useEffect } from 'react'
import { Modal, Form, Input, Select, message } from 'antd'
import { getTemplates } from '../api/templates'
import { createSandbox } from '../api/sandboxes'
import type { TemplateListItem, CreateSandboxRequest } from '../api/types'

interface CreateSandboxModalProps {
  open: boolean
  onClose: () => void
  onSuccess: () => void
}

export default function CreateSandboxModal({ open, onClose, onSuccess }: CreateSandboxModalProps) {
  const [form] = Form.useForm()
  const [templates, setTemplates] = useState<TemplateListItem[]>([])
  const [loading, setLoading] = useState(false)
  const [mode, setMode] = useState<'template' | 'image'>('template')

  useEffect(() => {
    if (open) {
      getTemplates()
        .then(setTemplates)
        .catch(() => message.error('加载模板列表失败'))
      form.resetFields()
      setMode('template')
    }
  }, [open, form])

  const readyTemplates = templates.filter((t) => t.status === 'ready')

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields()
      setLoading(true)

      const req: CreateSandboxRequest = {}
      if (mode === 'template') {
        req.template_name = values.template_name
      } else {
        req.image = values.image
      }
      if (values.name) {
        req.name = values.name
      }

      await createSandbox(req)
      message.success('沙盒创建成功')
      onSuccess()
      onClose()
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error('创建沙盒失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="创建沙盒"
      open={open}
      onOk={handleSubmit}
      onCancel={onClose}
      confirmLoading={loading}
      okText="创建"
      cancelText="取消"
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item label="创建方式">
          <Select
            value={mode}
            onChange={(v) => {
              setMode(v)
              form.resetFields(['template_name', 'image'])
            }}
            options={[
              { value: 'template', label: '选择模板' },
              { value: 'image', label: '自定义镜像' },
            ]}
          />
        </Form.Item>

        {mode === 'template' ? (
          <Form.Item
            name="template_name"
            label="模板"
            rules={[{ required: true, message: '请选择模板' }]}
          >
            <Select
              placeholder="选择一个已构建的模板"
              options={readyTemplates.map((t) => ({
                value: t.name,
                label: `${t.name}${t.description ? ' - ' + t.description : ''}`,
              }))}
              showSearch
              optionFilterProp="label"
              notFoundContent="暂无可用模板"
            />
          </Form.Item>
        ) : (
          <Form.Item
            name="image"
            label="Docker 镜像"
            rules={[{ required: true, message: '请输入 Docker 镜像名' }]}
          >
            <Input placeholder="例如: ubuntu:22.04" className="mono" />
          </Form.Item>
        )}

        <Form.Item name="name" label="沙盒名称（可选）">
          <Input placeholder="自定义名称，留空自动生成" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
