/**
 * SettingsDrawer - 设置抽屉
 */
import { Drawer, Form, Input, Select, Switch, Button, message } from 'antd'
import { colors } from '../../styles/design-tokens'

interface SettingsDrawerProps {
  visible: boolean
  onClose: () => void
  /** When true, render as inline panel instead of floating Drawer */
  inline?: boolean
}

const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  visible,
  onClose,
  inline = false
}) => {
  const [form] = Form.useForm()

  const handleSave = () => {
    message.success('设置已保存')
    onClose()
  }

  const content = (
    <Form
      form={form}
      layout="vertical"
      initialValues={{
        theme: 'light',
        autoSave: true,
        language: 'zh-CN'
      }}
    >
      <Form.Item name="theme" label="主题">
        <Select
          options={[
            { label: '浅色', value: 'light' },
            { label: '深色', value: 'dark' }
          ]}
        />
      </Form.Item>

      <Form.Item name="autoSave" label="自动保存" valuePropName="checked">
        <Switch />
      </Form.Item>

      <Form.Item name="language" label="语言">
        <Select
          options={[
            { label: '简体中文', value: 'zh-CN' },
            { label: 'English', value: 'en-US' }
          ]}
        />
      </Form.Item>
    </Form>
  )

  if (inline) {
    return (
      <div style={{
        width: 400,
        borderRight: `1px solid ${colors.borderLight}`,
        background: colors.bgPrimary,
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        overflow: 'auto',
      }}>
        <div style={{
          padding: '16px 20px',
          borderBottom: `1px solid ${colors.borderLight}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}>
          <span style={{ fontWeight: 600, fontSize: 16 }}>设置</span>
          <Button size="small" onClick={onClose}>关闭</Button>
        </div>
        <div style={{ padding: 20, flex: 1, overflow: 'auto' }}>
          {content}
        </div>
        <div style={{
          padding: '12px 20px',
          borderTop: `1px solid ${colors.borderLight}`,
          textAlign: 'right',
        }}>
          <Button onClick={onClose} style={{ marginRight: 8 }}>取消</Button>
          <Button type="primary" onClick={handleSave}>保存</Button>
        </div>
      </div>
    )
  }

  return (
    <Drawer
      title="设置"
      placement="left"
      width={400}
      onClose={onClose}
      open={visible}
      footer={
        <div style={{ textAlign: 'right' }}>
          <Button onClick={onClose} style={{ marginRight: 8 }}>
            取消
          </Button>
          <Button type="primary" onClick={handleSave}>
            保存
          </Button>
        </div>
      }
    >
      {content}
    </Drawer>
  )
}

export default SettingsDrawer
