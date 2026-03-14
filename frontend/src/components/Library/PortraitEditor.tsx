/**
 * PortraitEditor - 画像编辑器组件
 * 六维可视化编辑，Schema验证和实时提示
 */
import { useState, useEffect } from 'react'
import { 
  Card, 
  Form, 
  Input, 
  Button, 
  Space, 
  Typography, 
  Tabs, 
  InputNumber,
  Select,
  Tag,
  message,
  Divider,
  Row,
  Col
} from 'antd'
import { SaveOutlined, CloseOutlined, PlusOutlined, DeleteOutlined } from '@ant-design/icons'
import { StylePortrait, updatePortrait, createPortrait } from '../../services/styleService'
import type { FormInstance } from 'antd/es/form'

const { TextArea } = Input
const { Title, Text, Paragraph } = Typography
const { TabPane } = Tabs
const { Option } = Select

interface PortraitEditorProps {
  portrait?: StylePortrait & { id?: number }
  portraitId?: number
  userId?: number
  onSave?: (portrait: StylePortrait) => void
  onCancel?: () => void
}

export const PortraitEditor: React.FC<PortraitEditorProps> = ({
  portrait,
  portraitId,
  userId,
  onSave,
  onCancel
}) => {
  const [form] = Form.useForm<StylePortrait>()
  const [saving, setSaving] = useState(false)
  const [formChanged, setFormChanged] = useState(false)

  useEffect(() => {
    if (portrait) {
      form.setFieldsValue(portrait)
    } else {
      // 创建新画像的默认值
      form.setFieldsValue({
        style_overview: {
          summary: '',
          tags: [],
          formality_constraint: {},
          paragraph_constraint: {}
        },
        methodology: {
          approach: '',
          analogy_rule: {},
          structure_template: '',
          mandatory_patterns: []
        },
        thinking_core: {
          values: [],
          value_judgment_function: {},
          logic_patterns: [],
          argumentation_rules: {}
        },
        expression_features: {
          sentence_length_ratio: {},
          sentence_constraints: {},
          opening_habits: [],
          keywords: [],
          formality_level: '半正式'
        },
        writing_habits: {
          opening_phrases: [],
          opening_rule: {},
          transition_patterns: [],
          closing_patterns: [],
          paragraph_length_preference: ''
        },
        unique_markers: {
          background: '',
          expertise: [],
          identity_framework: {},
          perspective_rules: []
        },
        version: 1,
        confidence_score: 0.5,
        source: 'manual'
      })
    }
  }, [portrait, form])

  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      if ((portrait || portraitId) && userId) {
        // 更新现有画像
        const id = portraitId || (portrait as any)?.id
        if (!id) {
          throw new Error('缺少画像ID，无法更新')
        }
        const updated = await updatePortrait(id, values)
        if (onSave) {
          onSave(updated.portrait)
        }
      } else if (userId) {
        // 创建新画像
        const created = await createPortrait(values, userId)
        if (onSave) {
          onSave(created.portrait)
        }
      } else {
        // 仅回调，不保存到后端
        if (onSave) {
          onSave(values)
        }
      }

      message.success('保存成功')
      setFormChanged(false)
    } catch (error: any) {
      if (error.errorFields) {
        message.error('请检查表单填写是否正确')
      } else {
        message.error('保存失败: ' + (error.message || '未知错误'))
        console.error('保存失败:', error)
      }
    } finally {
      setSaving(false)
    }
  }

  const handleFormChange = () => {
    setFormChanged(true)
  }

  return (
    <Card
      title={
        <Title level={4} style={{ margin: 0 }}>
          {portrait ? `编辑画像 v${portrait.version}` : '创建新画像'}
        </Title>
      }
      extra={
        <Space>
          <Button icon={<CloseOutlined />} onClick={onCancel}>
            取消
          </Button>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={handleSave}
            loading={saving}
            disabled={!formChanged}
          >
            保存
          </Button>
        </Space>
      }
    >
      <Form
        form={form}
        layout="vertical"
        onValuesChange={handleFormChange}
        initialValues={portrait}
      >
        <Tabs defaultActiveKey="overview">
          {/* 1. 风格概述 */}
          <TabPane tab="风格概述" key="overview">
            <Form.Item
              label="风格概述描述"
              name={['style_overview', 'summary']}
              rules={[{ required: true, message: '请输入风格概述' }]}
            >
              <TextArea rows={3} placeholder="例如：河南小镇青年口语风" />
            </Form.Item>

            <Form.Item
              label="风格标签"
              name={['style_overview', 'tags']}
            >
              <Select
                mode="tags"
                placeholder="添加标签，按Enter确认"
                tokenSeparators={[',']}
              />
            </Form.Item>

            <Divider>可执行约束</Divider>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="语气参数约束（JSON）"
                  name={['style_overview', 'formality_constraint']}
                  tooltip="例如：{'oral_ratio': 0.7, 'forbidden_connectors': ['综上所述']}"
                >
                  <TextArea
                    rows={4}
                    placeholder='{"oral_ratio": 0.7, "forbidden_connectors": ["综上所述"]}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ style_overview: { formality_constraint: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误，保持原值
                      }
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="段落约束（JSON）"
                  name={['style_overview', 'paragraph_constraint']}
                  tooltip="例如：{'max_lines': 3, 'avg_chars_per_para': 150}"
                >
                  <TextArea
                    rows={4}
                    placeholder='{"max_lines": 3, "avg_chars_per_para": 150}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ style_overview: { paragraph_constraint: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误
                      }
                    }}
                  />
                </Form.Item>
              </Col>
            </Row>
          </TabPane>

          {/* 2. 创作方法论 */}
          <TabPane tab="创作方法论" key="methodology">
            <Form.Item
              label="核心方法描述"
              name={['methodology', 'approach']}
              rules={[{ required: true, message: '请输入核心方法' }]}
            >
              <TextArea rows={2} placeholder="例如：产品经理视角切入+生活化类比" />
            </Form.Item>

            <Form.Item
              label="结构模板"
              name={['methodology', 'structure_template']}
            >
              <Input placeholder="例如：问题-分析-解决方案" />
            </Form.Item>

            <Form.Item
              label="强制要求的模式"
              name={['methodology', 'mandatory_patterns']}
            >
              <Select mode="tags" placeholder="添加模式，按Enter确认" />
            </Form.Item>

            <Divider>可执行规则</Divider>

            <Form.Item
              label="类比规则（JSON）"
              name={['methodology', 'analogy_rule']}
              tooltip="例如：{'required': true, 'object_priority': ['product', 'nature'], 'frequency_per_point': 1}"
            >
              <TextArea
                rows={4}
                placeholder='{"required": true, "object_priority": ["product", "nature", "daily"]}'
                onBlur={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value)
                    form.setFieldsValue({ methodology: { analogy_rule: parsed } })
                  } catch (err) {
                    // 忽略JSON解析错误
                  }
                }}
              />
            </Form.Item>
          </TabPane>

          {/* 3. 思维内核 */}
          <TabPane tab="思维内核" key="thinking">
            <Form.Item
              label="核心价值观"
              name={['thinking_core', 'values']}
            >
              <Select mode="tags" placeholder="添加价值观，按Enter确认" />
            </Form.Item>

            <Form.Item
              label="逻辑模式"
              name={['thinking_core', 'logic_patterns']}
            >
              <Select mode="tags" placeholder="例如：因果分析、对比论证" />
            </Form.Item>

            <Divider>可执行约束</Divider>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="价值判断函数（JSON）"
                  name={['thinking_core', 'value_judgment_function']}
                  tooltip="例如：{'conflict_resolution': 'improvement_over_criticism'}"
                >
                  <TextArea
                    rows={4}
                    placeholder='{"conflict_resolution": "improvement_over_criticism"}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ thinking_core: { value_judgment_function: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误
                      }
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="论证规则约束（JSON）"
                  name={['thinking_core', 'argumentation_rules']}
                >
                  <TextArea
                    rows={4}
                    placeholder='{}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ thinking_core: { argumentation_rules: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误
                      }
                    }}
                  />
                </Form.Item>
              </Col>
            </Row>
          </TabPane>

          {/* 4. 表达特征 */}
          <TabPane tab="表达特征" key="expression">
            <Form.Item
              label="正式程度"
              name={['expression_features', 'formality_level']}
            >
              <Select>
                <Option value="正式">正式</Option>
                <Option value="半正式">半正式</Option>
                <Option value="非正式">非正式</Option>
                <Option value="口语化">口语化</Option>
              </Select>
            </Form.Item>

            <Form.Item
              label="开场习惯"
              name={['expression_features', 'opening_habits']}
            >
              <Select mode="tags" placeholder="添加开场习惯" />
            </Form.Item>

            <Form.Item
              label="高频词"
              name={['expression_features', 'keywords']}
            >
              <Select mode="tags" placeholder="添加高频词" />
            </Form.Item>

            <Divider>可执行约束</Divider>

            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="句式约束（JSON）"
                  name={['expression_features', 'sentence_constraints']}
                  tooltip="例如：{'short_sentence_ratio': 0.4, 'max_length': 15}"
                >
                  <TextArea
                    rows={4}
                    placeholder='{"short_sentence_ratio": 0.4, "max_length": 15}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ expression_features: { sentence_constraints: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误
                      }
                    }}
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="句式长短比（JSON）"
                  name={['expression_features', 'sentence_length_ratio']}
                >
                  <TextArea
                    rows={4}
                    placeholder='{}'
                    onBlur={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value)
                        form.setFieldsValue({ expression_features: { sentence_length_ratio: parsed } })
                      } catch (err) {
                        // 忽略JSON解析错误
                      }
                    }}
                  />
                </Form.Item>
              </Col>
            </Row>
          </TabPane>

          {/* 5. 创作习惯 */}
          <TabPane tab="创作习惯" key="habits">
            <Form.Item
              label="开场短语模板库"
              name={['writing_habits', 'opening_phrases']}
              rules={[{ required: true, message: '至少需要一个开场短语' }]}
            >
              <Select mode="tags" placeholder="例如：说实话...、这两天...、有个现象..." />
            </Form.Item>

            <Form.Item
              label="过渡模式"
              name={['writing_habits', 'transition_patterns']}
            >
              <Select mode="tags" placeholder="添加过渡模式" />
            </Form.Item>

            <Form.Item
              label="结尾模式"
              name={['writing_habits', 'closing_patterns']}
            >
              <Select mode="tags" placeholder="添加结尾模式" />
            </Form.Item>

            <Form.Item
              label="段落长度偏好"
              name={['writing_habits', 'paragraph_length_preference']}
            >
              <Input placeholder="例如：短段落、中等段落" />
            </Form.Item>

            <Divider>可执行约束</Divider>

            <Form.Item
              label="开场规则（JSON）"
              name={['writing_habits', 'opening_rule']}
              tooltip="例如：{'use_template_only': true, 'forbid_innovation': true}"
            >
              <TextArea
                rows={4}
                placeholder='{"use_template_only": true, "forbid_innovation": true, "random_select": true}'
                onBlur={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value)
                    form.setFieldsValue({ writing_habits: { opening_rule: parsed } })
                  } catch (err) {
                    // 忽略JSON解析错误
                  }
                }}
              />
            </Form.Item>
          </TabPane>

          {/* 6. 独特标记 */}
          <TabPane tab="独特标记" key="markers">
            <Form.Item
              label="背景信息"
              name={['unique_markers', 'background']}
            >
              <TextArea rows={2} placeholder="个人背景、经历等" />
            </Form.Item>

            <Form.Item
              label="专业领域"
              name={['unique_markers', 'expertise']}
            >
              <Select mode="tags" placeholder="例如：产品经理、技术写作" />
            </Form.Item>

            <Form.Item
              label="视角规则"
              name={['unique_markers', 'perspective_rules']}
            >
              <Select mode="tags" placeholder="例如：分析问题时使用产品经理视角" />
            </Form.Item>

            <Divider>可执行约束</Divider>

            <Form.Item
              label="身份锚定框架（JSON）"
              name={['unique_markers', 'identity_framework']}
              tooltip="例如：{'default_analysis_framework': 'user-need-scene', 'mandatory_terms': ['迭代', '闭环'], 'term_density_per_1k': 3}"
            >
              <TextArea
                rows={4}
                placeholder='{"default_analysis_framework": "user-need-scene", "mandatory_terms": ["迭代", "闭环"]}'
                onBlur={(e) => {
                  try {
                    const parsed = JSON.parse(e.target.value)
                    form.setFieldsValue({ unique_markers: { identity_framework: parsed } })
                  } catch (err) {
                    // 忽略JSON解析错误
                  }
                }}
              />
            </Form.Item>
          </TabPane>

          {/* 元数据 */}
          <TabPane tab="元数据" key="metadata">
            <Row gutter={16}>
              <Col span={12}>
                <Form.Item
                  label="版本号"
                  name="version"
                  rules={[{ required: true }]}
                >
                  <InputNumber min={1} disabled={!!portrait} />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="置信度"
                  name="confidence_score"
                  rules={[{ required: true, min: 0, max: 1 }]}
                >
                  <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>

            <Form.Item
              label="来源"
              name="source"
            >
              <Select>
                <Option value="auto">自动生成</Option>
                <Option value="manual">手动创建</Option>
                <Option value="hybrid">混合</Option>
              </Select>
            </Form.Item>
          </TabPane>
        </Tabs>
      </Form>
    </Card>
  )
}

export default PortraitEditor
