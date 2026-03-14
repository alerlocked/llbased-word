/**
 * SettingsDrawer - 设置抽屉
 */
import { Drawer, Form, Input, Select, Switch, Button, message } from 'antd'
import { colors } from '../../styles/design-tokens'

interface SettingsDrawerProps {
  visible: boolean
  onClose: () => void
}

const SettingsDrawer: React.FC<SettingsDrawerProps> = ({
  visible,
  onClose
}) => {
  const [form] = Form.useForm()

  const handleSave = () => {
    message.success('设置已保存')
    onClose()
  }

  return (
    <Drawer
      title="设置"
      placement="right"
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
    </Drawer>
  )
}

export default SettingsDrawer
