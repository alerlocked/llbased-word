/**
 * ProfilePage - 用户画像管理页面
 * 参考 GetDraft "推荐人设" 模式：预设模板 + 卡片展示 + 表单编辑 + 实时预览
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Form, Select, Switch, Slider, Button, Space, message, Row, Col, Typography, Divider, Tag, Empty, Table, Tooltip
} from 'antd'
import {
  ArrowLeftOutlined, EditOutlined, SaveOutlined, CheckCircleOutlined, UserOutlined, BookOutlined, ExperimentOutlined, FileTextOutlined
} from '@ant-design/icons'
import apiClient from '../services/apiClient'
import { colors, radius, shadows, spacing, typography, animation } from '../styles/design-tokens'

const { Title, Text, Paragraph } = Typography

// ========================================
// Types
// ========================================
interface WritingConfig {
  tone: string
  terminology: string
  detail_level: string
}

interface ReviewConfig {
  check_completeness: boolean
  check_accuracy: boolean
  allowed_deviation: number
}

interface WritingPreferences {
  preferred_sentence_length: string
  use_passive_voice: boolean
  include_examples: boolean
  include_caution_notes: boolean
  custom_vocabulary: Record<string, string>
  avoid_phrases: string[]
  confidence: number
  sample_count: number
  last_updated: string
}

interface Profile {
  id: string
  user_id: string
  domain: string
  writing: WritingConfig
  review: ReviewConfig
  preferences: WritingPreferences
  triples: Array<{ s: string; r: string; o: string }>
  frequent_terms: Record<string, number>
  ai_generated_summary: string
  source_document_ids: string[]
}

interface PresetTemplate {
  name: string
  domain: string
  icon: string
  description: string
  writing: WritingConfig
  review: ReviewConfig
}

// ========================================
// Preset Templates
// ========================================
const PRESET_TEMPLATES: PresetTemplate[] = [
  {
    name: '装配工艺',
    domain: 'assembly',
    icon: '🔧',
    description: '技术文档 · 详细',
    writing: { tone: '技术文档', terminology: 'assembly', detail_level: '详细' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 }
  },
  {
    name: '焊接工艺',
    domain: 'welding',
    icon: '🔥',
    description: '技术文档 · 详细',
    writing: { tone: '技术文档', terminology: 'welding', detail_level: '详细' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 }
  },
  {
    name: '涂装工艺',
    domain: 'coating',
    icon: '🎨',
    description: '技术文档 · 适中',
    writing: { tone: '技术文档', terminology: 'coating', detail_level: '适中' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.15 }
  },
  {
    name: '通用工艺',
    domain: 'general',
    icon: '📋',
    description: '操作手册 · 适中',
    writing: { tone: '操作手册', terminology: 'standard', detail_level: '适中' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.2 }
  }
]

// ========================================
// Select Options
// ========================================
const TONE_OPTIONS = [
  { label: '技术文档', value: '技术文档' },
  { label: '培训材料', value: '培训材料' },
  { label: '操作手册', value: '操作手册' }
]

const TERMINOLOGY_OPTIONS = [
  { label: 'standard（通用）', value: 'standard' },
  { label: 'assembly（装配）', value: 'assembly' },
  { label: 'welding（焊接）', value: 'welding' },
  { label: 'coating（涂装）', value: 'coating' }
]

const DETAIL_LEVEL_OPTIONS = [
  { label: '简要', value: '简要' },
  { label: '适中', value: '适中' },
  { label: '详细', value: '详细' }
]

// ========================================
// Component
// ========================================
const ProfilePage: React.FC = () => {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  // State
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [formValues, setFormValues] = useState<{
    writing: WritingConfig
    review: ReviewConfig
  }>({
    writing: { tone: '技术文档', terminology: 'standard', detail_level: '详细' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 }
  })

  // Load profile
  const fetchProfile = useCallback(async () => {
    setLoading(true)
    try {
      const response = await apiClient.get('/profile/default')
      const data = response.data.profile
      setProfile(data)
      setFormValues({
        writing: data.writing,
        review: data.review
      })
      form.setFieldsValue({
        tone: data.writing.tone,
        terminology: data.writing.terminology,
        detail_level: data.writing.detail_level,
        check_completeness: data.review.check_completeness,
        check_accuracy: data.review.check_accuracy,
        allowed_deviation: Math.round(data.review.allowed_deviation * 100)
      })
    } catch (error) {
      console.error('加载画像失败:', error)
    } finally {
      setLoading(false)
    }
  }, [form])

  useEffect(() => {
    fetchProfile()
  }, [fetchProfile])

  // Apply preset template
  const handleApplyPreset = (template: PresetTemplate) => {
    setFormValues({
      writing: { ...template.writing },
      review: { ...template.review }
    })
    form.setFieldsValue({
      tone: template.writing.tone,
      terminology: template.writing.terminology,
      detail_level: template.writing.detail_level,
      check_completeness: template.review.check_completeness,
      check_accuracy: template.review.check_accuracy,
      allowed_deviation: Math.round(template.review.allowed_deviation * 100)
    })
    setEditing(true)
    message.info(`已应用「${template.name}」模板，修改后请保存`)
  }

  // Form value change handler
  const handleFormChange = () => {
    const values = form.getFieldsValue()
    setFormValues({
      writing: {
        tone: values.tone || '技术文档',
        terminology: values.terminology || 'standard',
        detail_level: values.detail_level || '详细'
      },
      review: {
        check_completeness: values.check_completeness ?? true,
        check_accuracy: values.check_accuracy ?? true,
        allowed_deviation: (values.allowed_deviation ?? 10) / 100
      }
    })
  }

  // Save profile
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)

      const writing: WritingConfig = {
        tone: values.tone,
        terminology: values.terminology,
        detail_level: values.detail_level
      }
      const review: ReviewConfig = {
        check_completeness: values.check_completeness,
        check_accuracy: values.check_accuracy,
        allowed_deviation: values.allowed_deviation / 100
      }

      await apiClient.put('/profile/default', { writing, review })

      message.success('画像已保存')
      setEditing(false)
      setFormValues({ writing, review })
      setProfile(prev => prev ? { ...prev, writing, review } : null)
    } catch (error) {
      console.error('保存失败:', error)
    } finally {
      setSaving(false)
    }
  }

  // Preview description
  const renderPreview = () => {
    const { writing, review } = formValues
    const items = [
      `使用「${writing.tone}」语气`,
      `使用 ${writing.terminology} 术语库`,
      `生成「${writing.detail_level}」级别的内容`,
    ]
    if (review.check_completeness || review.check_accuracy) {
      const checks: string[] = []
      if (review.check_completeness) checks.push('完整性')
      if (review.check_accuracy) checks.push('准确性')
      items.push(`审查时检查${checks.join('和')}`)
    }
    items.push(`允许 ${Math.round(review.allowed_deviation * 100)}% 的模板偏差`)

    return items
  }

  const deviationPercent = Math.round(formValues.review.allowed_deviation * 100)

  return (
    <div style={{
      minHeight: '100vh',
      background: colors.bgTertiary,
      padding: '0 0 48px 0'
    }}>
      {/* Top Navigation */}
      <nav style={{
        height: 56,
        padding: '0 24px',
        borderBottom: `1px solid ${colors.borderLight}`,
        background: colors.bgSecondary,
        display: 'flex',
        alignItems: 'center',
        gap: 16
      }}>
        <Button
          type="text"
          icon={<ArrowLeftOutlined />}
          onClick={() => navigate('/')}
          style={{ color: colors.textSecondary }}
        >
          返回
        </Button>
        <div style={{ width: 1, height: 24, background: colors.border }} />
        <Title level={4} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <UserOutlined /> 用户画像管理
        </Title>
      </nav>

      <div style={{ maxWidth: 960, margin: '0 auto', padding: '24px 24px 0' }}>
        {/* Preset Templates Section */}
        <div style={{ marginBottom: 24 }}>
          <Text style={{ fontSize: typography.fontSize.md, fontWeight: typography.fontWeight.medium, color: colors.textSecondary, marginBottom: 12, display: 'block' }}>
            推荐人设
          </Text>
          <Row gutter={[16, 16]}>
            {PRESET_TEMPLATES.map((template) => (
              <Col key={template.domain} xs={12} sm={12} md={6}>
                <Card
                  hoverable
                  size="small"
                  style={{
                    borderRadius: radius.md,
                    cursor: 'pointer',
                    transition: `all ${animation.duration.base}`,
                    border: profile?.domain === template.domain && !editing
                      ? `2px solid ${colors.primary}`
                      : `1px solid ${colors.borderLight}`,
                  }}
                  styles={{ body: { padding: 16, textAlign: 'center' } }}
                >
                  <div style={{ fontSize: 32, marginBottom: 8 }}>{template.icon}</div>
                  <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.base, color: colors.textPrimary, marginBottom: 4 }}>
                    {template.name}
                  </div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textTertiary, marginBottom: 12 }}>
                    {template.description}
                  </div>
                  <Button
                    size="small"
                    type="primary"
                    ghost
                    onClick={() => handleApplyPreset(template)}
                    style={{ borderRadius: radius.xs }}
                  >
                    应用
                  </Button>
                </Card>
              </Col>
            ))}
          </Row>
        </div>

        {/* Current Profile Section */}
        <Card
          title={
            <Space>
              <UserOutlined />
              <span>当前画像</span>
              {profile && (
                <Tag color="blue" style={{ marginLeft: 8 }}>
                  {profile.domain}
                </Tag>
              )}
            </Space>
          }
          extra={
            <Space>
              {!editing ? (
                <Button
                  type="primary"
                  ghost
                  icon={<EditOutlined />}
                  onClick={() => setEditing(true)}
                >
                  编辑
                </Button>
              ) : (
                <>
                  <Button onClick={() => {
                    setEditing(false)
                    if (profile) {
                      form.setFieldsValue({
                        tone: profile.writing.tone,
                        terminology: profile.writing.terminology,
                        detail_level: profile.writing.detail_level,
                        check_completeness: profile.review.check_completeness,
                        check_accuracy: profile.review.check_accuracy,
                        allowed_deviation: Math.round(profile.review.allowed_deviation * 100)
                      })
                      setFormValues({
                        writing: profile.writing,
                        review: profile.review
                      })
                    }
                  }}>
                    取消
                  </Button>
                  <Button
                    type="primary"
                    icon={<SaveOutlined />}
                    loading={saving}
                    onClick={handleSave}
                  >
                    保存
                  </Button>
                </>
              )}
            </Space>
          }
          loading={loading}
          style={{ borderRadius: radius.md, marginBottom: 24 }}
        >
          <Form
            form={form}
            layout="vertical"
            onValuesChange={handleFormChange}
            disabled={!editing}
          >
            <Row gutter={48}>
              {/* Writing Config */}
              <Col xs={24} md={12}>
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary }}>
                    ✏️ 写作配置
                  </Text>
                </div>

                <Form.Item label="语气" name="tone">
                  <Select options={TONE_OPTIONS} />
                </Form.Item>

                <Form.Item label="术语库" name="terminology">
                  <Select options={TERMINOLOGY_OPTIONS} />
                </Form.Item>

                <Form.Item label="详细程度" name="detail_level">
                  <Select options={DETAIL_LEVEL_OPTIONS} />
                </Form.Item>
              </Col>

              {/* Review Config */}
              <Col xs={24} md={12}>
                <div style={{ marginBottom: 16 }}>
                  <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary }}>
                    🔍 审查配置
                  </Text>
                </div>

                <Form.Item label="完整性检查" name="check_completeness" valuePropName="checked">
                  <Switch
                    checkedChildren="开启"
                    unCheckedChildren="关闭"
                  />
                </Form.Item>

                <Form.Item label="准确性检查" name="check_accuracy" valuePropName="checked">
                  <Switch
                    checkedChildren="开启"
                    unCheckedChildren="关闭"
                  />
                </Form.Item>

                <Form.Item label={`允许偏差：${deviationPercent}%`} name="allowed_deviation">
                  <Slider
                    min={0}
                    max={100}
                    step={5}
                    marks={{ 0: '0%', 25: '25%', 50: '50%', 75: '75%', 100: '100%' }}
                    tooltip={{ formatter: (v) => `${v}%` }}
                  />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Card>

        {/* Effect Preview Section */}
        <Card
          title={
            <Space>
              <CheckCircleOutlined />
              <span>效果预览</span>
            </Space>
          }
          style={{ borderRadius: radius.md, marginBottom: 24 }}
        >
          <div style={{
            background: colors.bgTertiary,
            borderRadius: radius.sm,
            padding: spacing.xl,
          }}>
            <Text style={{ fontSize: typography.fontSize.base, color: colors.textSecondary, display: 'block', marginBottom: 12 }}>
              基于当前画像，AI 生成内容时将：
            </Text>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {renderPreview().map((item, idx) => (
                <div key={idx} style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  fontSize: typography.fontSize.base,
                  color: colors.textPrimary
                }}>
                  <span style={{ color: colors.primary }}>&#8226;</span>
                  <span>{item}</span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Learned Knowledge Section */}
        {profile && (profile.triples.length > 0 || Object.keys(profile.frequent_terms).length > 0 || profile.ai_generated_summary) && (
          <Card
            title={
              <Space>
                <BookOutlined />
                <span>学习成果</span>
                <Tag color="green">{profile.source_document_ids.length} 篇文档</Tag>
              </Space>
            }
            style={{ borderRadius: radius.md, marginBottom: 24 }}
          >
            {/* AI Summary */}
            {profile.ai_generated_summary && (
              <div style={{ marginBottom: 20 }}>
                <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary, display: 'block', marginBottom: 8 }}>
                  <ExperimentOutlined /> 画像摘要
                </Text>
                <div style={{
                  background: colors.bgTertiary,
                  borderRadius: radius.sm,
                  padding: 16,
                  fontSize: typography.fontSize.base,
                  lineHeight: 1.8,
                  color: colors.textSecondary,
                }}>
                  {profile.ai_generated_summary}
                </div>
              </div>
            )}

            {/* Knowledge Triples */}
            {profile.triples.length > 0 && (
              <div style={{ marginBottom: 20 }}>
                <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary, display: 'block', marginBottom: 8 }}>
                  <FileTextOutlined /> 领域知识（{profile.triples.length} 条）
                </Text>
                <Table
                  size="small"
                  pagination={{ pageSize: 10, size: 'small' }}
                  style={{ fontSize: typography.fontSize.sm }}
                  dataSource={profile.triples.map((t, i) => ({ key: i, ...t }))}
                  columns={[
                    { title: '主体', dataIndex: 's', key: 's', width: '35%', ellipsis: true },
                    { title: '关系', dataIndex: 'r', key: 'r', width: '20%', ellipsis: true,
                      render: (v: string) => <Tag color="blue">{v}</Tag>
                    },
                    { title: '客体', dataIndex: 'o', key: 'o', width: '35%', ellipsis: true },
                  ]}
                />
              </div>
            )}

            {/* Frequent Terms */}
            {Object.keys(profile.frequent_terms).length > 0 && (
              <div>
                <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary, display: 'block', marginBottom: 8 }}>
                  高频术语（{Object.keys(profile.frequent_terms).length} 个）
                </Text>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {Object.entries(profile.frequent_terms)
                    .sort(([, a], [, b]) => b - a)
                    .slice(0, 50)
                    .map(([term, count]) => (
                      <Tooltip key={term} title={`出现 ${count} 次`}>
                        <Tag
                          color={count >= 10 ? 'red' : count >= 5 ? 'orange' : 'default'}
                          style={{ fontSize: typography.fontSize.sm }}
                        >
                          {term} ({count})
                        </Tag>
                      </Tooltip>
                    ))}
                </div>
              </div>
            )}

            {/* Writing Style Preferences */}
            {profile.preferences && profile.preferences.sample_count > 0 && (
              <div style={{ marginTop: 20 }}>
                <Divider />
                <Text strong style={{ fontSize: typography.fontSize.md, color: colors.textPrimary, display: 'block', marginBottom: 8 }}>
                  写作风格偏好
                </Text>
                <Row gutter={[16, 8]}>
                  <Col span={8}>
                    <Text type="secondary">句长偏好</Text>
                    <div><Tag>{profile.preferences.preferred_sentence_length}</Tag></div>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">被动语态</Text>
                    <div><Tag color={profile.preferences.use_passive_voice ? 'green' : 'default'}>{profile.preferences.use_passive_voice ? '使用' : '不使用'}</Tag></div>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary">注意事项</Text>
                    <div><Tag color={profile.preferences.include_caution_notes ? 'green' : 'default'}>{profile.preferences.include_caution_notes ? '包含' : '不包含'}</Tag></div>
                  </Col>
                </Row>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary" style={{ fontSize: typography.fontSize.xs }}>
                    置信度 {Math.round(profile.preferences.confidence * 100)}% | 基于 {profile.preferences.sample_count} 次学习
                  </Text>
                </div>
              </div>
            )}
          </Card>
        )}

        {/* Empty state when no learned data */}
        {profile && profile.triples.length === 0 && Object.keys(profile.frequent_terms).length === 0 && (
          <Card style={{ borderRadius: radius.md }}>
            <Empty
              description={
                <span>
                  尚无学习数据。在素材库中选择文档点击「学习为画像」，AI 会自动提取领域知识。
                </span>
              }
            />
          </Card>
        )}
      </div>
    </div>
  )
}

export default ProfilePage
