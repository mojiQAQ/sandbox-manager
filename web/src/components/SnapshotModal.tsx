import { useState } from 'react'
import { Modal, Form, Input, message } from 'antd'
import { saveAsTemplate } from '../api/sandboxes'

interface SnapshotModalProps {
  open: boolean
  sandboxId: string | null
  onClose: () => void
  onSuccess: () => void
}

export default function SnapshotModal({ open, sandboxId, onClose, onSuccess }: SnapshotModalProps) {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)

  const handleSubmit = async () => {
    if (!sandboxId) return
    try {
      const values = await form.validateFields()
      setLoading(true)

      await saveAsTemplate(sandboxId, {
        name: values.name,
        description: values.description || '',
      })
      message.success('快照保存成功')
      onSuccess()
      onClose()
      form.resetFields()
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) return
      message.error('快照保存失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="保存为模板快照"
      open={open}
      onOk={handleSubmit}
      onCancel={() => {
        onClose()
        form.resetFields()
      }}
      confirmLoading={loading}
      okText="保存"
      cancelText="取消"
      destroyOnClose
    >
      <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
        <Form.Item
          name="name"
          label="模板名称"
          rules={[
            { required: true, message: '请输入模板名称' },
            {
              pattern: /^[a-z0-9][a-z0-9_-]*$/,
              message: '只允许小写字母、数字、连字符和下划线，且必须以字母或数字开头',
            },
          ]}
        >
          <Input placeholder="例如: my-snapshot" className="mono" />
        </Form.Item>
        <Form.Item name="description" label="描述">
          <Input.TextArea placeholder="描述这个快照的用途" rows={3} />
        </Form.Item>
      </Form>
      <p style={{ color: '#9ca3af', fontSize: 12, marginTop: 8 }}>
        快照将保存沙盒 <span className="mono" style={{ color: '#06b6d4' }}>{sandboxId?.slice(0, 12)}</span> 的当前状态为新模板。
      </p>
    </Modal>
  )
}
