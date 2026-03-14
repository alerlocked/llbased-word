import { Form, Input, Button, Card, message } from 'antd'
import MainLayout from '../components/Layout/MainLayout'

/**
 * 系统设置页面
 * 配置API密钥等
 */
const SettingsPage: React.FC = () => {
  const [form] = Form.useForm()

  const handleSave = (values: any) => {
    // TODO: 保存配置到localStorage或后端
    console.log('保存配置:', values)
    message.success('配置已保存')
  }

  return (
    <MainLayout>
      <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
        <h2 style={{ marginBottom: 24 }}>系统设置</h2>
      
      <Card title="API配置">
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSave}
        >
          <Form.Item
            label="通义千问 API Key"
            name="dashscopeApiKey"
            rules={[{ required: true, message: '请输入通义千问API Key' }]}
            extra="通义千问API密钥，用于语音识别和文本生成功能"
          >
            <Input.Password placeholder="请输入通义千问API Key" />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存配置
            </Button>
          </Form.Item>
        </Form>
      </Card>
      </div>
    </MainLayout>
  )
}

export default SettingsPage




