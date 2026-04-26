/**
 * ProfilePage - User profile with knowledge, principles, and preferences.
 */
import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Card, Form, Select, Switch, Slider, Button, Space, message, Row, Col,
  Typography, Divider, Tag, Empty, Table, Tooltip, Popconfirm, Input, Modal
} from 'antd'
import {
  ArrowLeftOutlined, EditOutlined, SaveOutlined, CheckCircleOutlined,
  UserOutlined, BookOutlined, DeleteOutlined, PlusOutlined,
  SafetyOutlined, HeartOutlined, SearchOutlined
} from '@ant-design/icons'
import apiClient from '../services/apiClient'
import { colors, radius, spacing, typography, animation } from '../styles/design-tokens'

const { Title, Text } = Typography

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

interface KnowledgeEntry {
  id: string
  entity: string
  conditions: Record<string, string>
  attributes: Record<string, string>
  source: string
  created_at: string
  updated_at: string
}

interface Principle {
  id: string
  dimension: string
  name: string
  description: string
  check_expression: string
  enabled: boolean
  source: string
}

interface Preference {
  id: string
  dimension: string
  category: string
  description: string
  positive_examples: string[]
  negative_examples: string[]
  learned_from: string
  source_ids: string[]
  confidence: number
  sample_count: number
  created_at: string
  updated_at: string
}

interface Profile {
  id: string
  user_id: string
  domain: string
  writing: WritingConfig
  review: ReviewConfig
  knowledge: KnowledgeEntry[]
  principles: Principle[]
  preferences_list: Preference[]
  frequent_terms: Record<string, number>
  ai_generated_summary: string
  source_document_ids: string[]
  triples: Array<{ s: string; r: string; o: string }>
  preferences: Record<string, unknown>
}

interface PresetTemplate {
  name: string
  domain: string
  icon: string
  description: string
  writing: WritingConfig
  review: ReviewConfig
}

const PRESET_TEMPLATES: PresetTemplate[] = [
  { name: '装配工艺', domain: 'assembly', icon: '\u{1F527}', description: '技术文档 \u00B7 详细', writing: { tone: '技术文档', terminology: 'assembly', detail_level: '详细' }, review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 } },
  { name: '焊接工艺', domain: 'welding', icon: '\u{1F525}', description: '技术文档 \u00B7 详细', writing: { tone: '技术文档', terminology: 'welding', detail_level: '详细' }, review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 } },
  { name: '涂装工艺', domain: 'coating', icon: '\u{1F3A8}', description: '技术文档 \u00B7 适中', writing: { tone: '技术文档', terminology: 'coating', detail_level: '适中' }, review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.15 } },
  { name: '通用工艺', domain: 'general', icon: '\u{1F4CB}', description: '操作手册 \u00B7 适中', writing: { tone: '操作手册', terminology: 'standard', detail_level: '适中' }, review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.2 } },
]

const TONE_OPTIONS = [
  { label: '技术文档', value: '技术文档' },
  { label: '培训材料', value: '培训材料' },
  { label: '操作手册', value: '操作手册' },
]
const TERMINOLOGY_OPTIONS = [
  { label: 'standard（通用）', value: 'standard' },
  { label: 'assembly（装配）', value: 'assembly' },
  { label: 'welding（焊接）', value: 'welding' },
  { label: 'coating（涂装）', value: 'coating' },
]
const DETAIL_LEVEL_OPTIONS = [
  { label: '简要', value: '简要' },
  { label: '适中', value: '适中' },
  { label: '详细', value: '详细' },
]

const DIMENSION_LABELS: Record<string, string> = {
  text_compliance: '文本合规',
  data_validity: '数据合理性',
  terminology: '术语一致性',
  readability: '可读性',
  executability: '可执行性',
  style: '风格',
}

const DIMENSION_COLORS: Record<string, string> = {
  text_compliance: 'blue',
  data_validity: 'green',
  terminology: 'purple',
}

// ========================================
// Component
// ========================================
const ProfilePage: React.FC = () => {
  const navigate = useNavigate()
  const [form] = Form.useForm()

  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [editing, setEditing] = useState(false)
  const [profile, setProfile] = useState<Profile | null>(null)
  const [selectedDomain, setSelectedDomain] = useState<string>('assembly')
  const [activeSection, setActiveSection] = useState<'knowledge' | 'principles' | 'preferences'>('knowledge')

  // Add knowledge modal
  const [addKnowledgeVisible, setAddKnowledgeVisible] = useState(false)
  const [newKnowledge, setNewKnowledge] = useState({ entity: '', conditions: '', attributes: '', source: '' })

  // Add principle modal
  const [addPrincipleVisible, setAddPrincipleVisible] = useState(false)
  const [newPrinciple, setNewPrinciple] = useState({ dimension: 'text_compliance', name: '', description: '' })

  const [formValues, setFormValues] = useState<{
    writing: WritingConfig
    review: ReviewConfig
  }>({
    writing: { tone: '技术文档', terminology: 'standard', detail_level: '详细' },
    review: { check_completeness: true, check_accuracy: true, allowed_deviation: 0.1 },
  })

  // Load profile for the selected domain
  const profileApiBase = `/profile/${selectedDomain}`

  const fetchProfile = useCallback(async () => {
    setLoading(true)
    try {
      const response = await apiClient.get(profileApiBase)
      const data = response.data.profile
      setProfile(data)
      setFormValues({ writing: data.writing, review: data.review })
      form.setFieldsValue({
        tone: data.writing.tone,
        terminology: data.writing.terminology,
        detail_level: data.writing.detail_level,
        check_completeness: data.review.check_completeness,
        check_accuracy: data.review.check_accuracy,
        allowed_deviation: Math.round(data.review.allowed_deviation * 100),
      })
    } catch (error) {
      console.error('Failed to load profile:', error)
    } finally {
      setLoading(false)
    }
  }, [form, selectedDomain])

  useEffect(() => { fetchProfile() }, [fetchProfile])

  // Save config
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const writing = { tone: values.tone, terminology: values.terminology, detail_level: values.detail_level }
      const review = { check_completeness: values.check_completeness, check_accuracy: values.check_accuracy, allowed_deviation: values.allowed_deviation / 100 }
      await apiClient.put(profileApiBase, { writing, review })
      message.success('画像已保存')
      setEditing(false)
      setFormValues({ writing, review })
      setProfile(prev => prev ? { ...prev, writing, review } : null)
    } catch (error) {
      console.error('Save failed:', error)
    } finally {
      setSaving(false)
    }
  }

  // Knowledge CRUD
  const handleAddKnowledge = async () => {
    try {
      const conditions: Record<string, string> = {}
      const attributes: Record<string, string> = {}
      newKnowledge.conditions.split(',').forEach(pair => {
        const [k, v] = pair.split('=').map(s => s.trim())
        if (k && v) conditions[k] = v
      })
      newKnowledge.attributes.split(',').forEach(pair => {
        const [k, v] = pair.split('=').map(s => s.trim())
        if (k && v) attributes[k] = v
      })
      await apiClient.post(`${profileApiBase}/knowledge`, {
        entity: newKnowledge.entity,
        conditions,
        attributes,
        source: newKnowledge.source,
      })
      message.success('知识条目已添加')
      setAddKnowledgeVisible(false)
      setNewKnowledge({ entity: '', conditions: '', attributes: '', source: '' })
      fetchProfile()
    } catch (error) {
      message.error('添加失败')
    }
  }

  const handleDeleteKnowledge = async (id: string) => {
    try {
      await apiClient.delete(`${profileApiBase}/knowledge/${id}`)
      message.success('已删除')
      fetchProfile()
    } catch { message.error('删除失败') }
  }

  // Principle CRUD
  const handleAddPrinciple = async () => {
    try {
      await apiClient.post(`${profileApiBase}/principles`, newPrinciple)
      message.success('原则已添加')
      setAddPrincipleVisible(false)
      setNewPrinciple({ dimension: 'text_compliance', name: '', description: '' })
      fetchProfile()
    } catch { message.error('添加失败') }
  }

  const handleDeletePrinciple = async (id: string) => {
    try {
      await apiClient.delete(`${profileApiBase}/principles/${id}`)
      message.success('已删除')
      fetchProfile()
    } catch { message.error('删除失败') }
  }

  const handleDeletePreference = async (id: string) => {
    try {
      await apiClient.delete(`${profileApiBase}/preferences/${id}`)
      message.success('已删除')
      fetchProfile()
    } catch { message.error('删除失败') }
  }

  const deviationPercent = Math.round(formValues.review.allowed_deviation * 100)

  const hasData = profile && (
    (profile.knowledge?.length ?? 0) > 0 ||
    (profile.principles?.length ?? 0) > 0 ||
    (profile.preferences_list?.length ?? 0) > 0 ||
    (profile.triples?.length ?? 0) > 0 ||
    Object.keys(profile.frequent_terms ?? {}).length > 0
  )

  return (
    <div style={{ minHeight: '100vh', background: colors.bgTertiary, padding: '0 0 48px 0' }}>
      {/* Nav */}
      <nav style={{
        height: 56, padding: '0 24px', borderBottom: `1px solid ${colors.borderLight}`,
        background: colors.bgSecondary, display: 'flex', alignItems: 'center', gap: 16,
      }}>
        <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate('/')} style={{ color: colors.textSecondary }}>返回</Button>
        <div style={{ width: 1, height: 24, background: colors.border }} />
        <Title level={4} style={{ margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <UserOutlined /> 用户画像
        </Title>
      </nav>

      <div style={{ maxWidth: 1080, margin: '0 auto', padding: '24px 24px 0' }}>
        {/* Presets */}
        <div style={{ marginBottom: 24 }}>
          <Text style={{ fontSize: typography.fontSize.md, fontWeight: typography.fontWeight.medium, color: colors.textSecondary, marginBottom: 12, display: 'block' }}>推荐人设</Text>
          <Row gutter={[16, 16]}>
            {PRESET_TEMPLATES.map(t => (
              <Col key={t.domain} xs={12} sm={12} md={6}>
                <Card hoverable size="small" style={{ borderRadius: radius.md, border: profile?.domain === t.domain && !editing ? `2px solid ${colors.primary}` : `1px solid ${colors.borderLight}` }} styles={{ body: { padding: 16, textAlign: 'center' } }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>{t.icon}</div>
                  <div style={{ fontWeight: typography.fontWeight.semibold, fontSize: typography.fontSize.base, color: colors.textPrimary, marginBottom: 4 }}>{t.name}</div>
                  <div style={{ fontSize: typography.fontSize.xs, color: colors.textTertiary, marginBottom: 12 }}>{t.description}</div>
                  <Button size="small" type="primary" ghost onClick={() => {
                    setSelectedDomain(t.domain)
                    message.info(`切换到「${t.name}」画像`)
                  }}>应用</Button>
                </Card>
              </Col>
            ))}
          </Row>
        </div>

        {/* Config */}
        <Card title={<Space><UserOutlined /><span>写作与审查配置</span>{profile && <Tag color="blue">{profile.domain}</Tag>}</Space>}
          extra={<Space>{!editing ? <Button type="primary" ghost icon={<EditOutlined />} onClick={() => setEditing(true)}>编辑</Button> : (
            <><Button onClick={() => { setEditing(false); if (profile) { form.setFieldsValue({ tone: profile.writing.tone, terminology: profile.writing.terminology, detail_level: profile.writing.detail_level, check_completeness: profile.review.check_completeness, check_accuracy: profile.review.check_accuracy, allowed_deviation: Math.round(profile.review.allowed_deviation * 100) }) } }}>取消</Button>
              <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button></>
          )}</Space>} loading={loading} style={{ borderRadius: radius.md, marginBottom: 24 }}>
          <Form form={form} layout="vertical" onValuesChange={() => { const v = form.getFieldsValue(); setFormValues({ writing: { tone: v.tone || '技术文档', terminology: v.terminology || 'standard', detail_level: v.detail_level || '详细' }, review: { check_completeness: v.check_completeness ?? true, check_accuracy: v.check_accuracy ?? true, allowed_deviation: (v.allowed_deviation ?? 10) / 100 } }) }} disabled={!editing}>
            <Row gutter={48}>
              <Col xs={24} md={12}>
                <Text strong style={{ fontSize: typography.fontSize.md, display: 'block', marginBottom: 16 }}>写作配置</Text>
                <Form.Item label="语气" name="tone"><Select options={TONE_OPTIONS} /></Form.Item>
                <Form.Item label="术语库" name="terminology"><Select options={TERMINOLOGY_OPTIONS} /></Form.Item>
                <Form.Item label="详细程度" name="detail_level"><Select options={DETAIL_LEVEL_OPTIONS} /></Form.Item>
              </Col>
              <Col xs={24} md={12}>
                <Text strong style={{ fontSize: typography.fontSize.md, display: 'block', marginBottom: 16 }}>审查配置</Text>
                <Form.Item label="完整性检查" name="check_completeness" valuePropName="checked"><Switch checkedChildren="开启" unCheckedChildren="关闭" /></Form.Item>
                <Form.Item label="准确性检查" name="check_accuracy" valuePropName="checked"><Switch checkedChildren="开启" unCheckedChildren="关闭" /></Form.Item>
                <Form.Item label={`允许偏差：${deviationPercent}%`} name="allowed_deviation"><Slider min={0} max={100} step={5} marks={{ 0: '0%', 50: '50%', 100: '100%' }} /></Form.Item>
              </Col>
            </Row>
          </Form>
        </Card>

        {/* Data Sections: Knowledge / Principles / Preferences */}
        <Card style={{ borderRadius: radius.md, marginBottom: 24 }}
          title={<Space>{activeSection === 'knowledge' ? <BookOutlined /> : activeSection === 'principles' ? <SafetyOutlined /> : <HeartOutlined />} {
            activeSection === 'knowledge' ? '知识库' : activeSection === 'principles' ? '审查原则' : '偏好学习'
          }</Space>}
          extra={
            <Space>
              {(['knowledge', 'principles', 'preferences'] as const).map(s => (
                <Button key={s} size="small" type={activeSection === s ? 'primary' : 'default'} onClick={() => setActiveSection(s)}>
                  {s === 'knowledge' ? `知识 (${profile?.knowledge?.length ?? 0})` : s === 'principles' ? `原则 (${profile?.principles?.length ?? 0})` : `偏好 (${profile?.preferences_list?.length ?? 0})`}
                </Button>
              ))}
              {activeSection === 'knowledge' && <Button size="small" icon={<PlusOutlined />} onClick={() => setAddKnowledgeVisible(true)}>添加</Button>}
              {activeSection === 'principles' && <Button size="small" icon={<PlusOutlined />} onClick={() => setAddPrincipleVisible(true)}>添加</Button>}
            </Space>
          }
        >
          {/* Knowledge Section */}
          {activeSection === 'knowledge' && (
            (profile?.knowledge?.length ?? 0) > 0 ? (
              <Table size="small" pagination={{ pageSize: 10, size: 'small' }}
                dataSource={(profile?.knowledge ?? []).map(k => ({ key: k.id, ...k }))}
                columns={[
                  { title: '实体', dataIndex: 'entity', key: 'entity', width: 120, fixed: 'left' as const },
                  { title: '条件', dataIndex: 'conditions', key: 'conditions', width: 250,
                    render: (v: Record<string, string>) => Object.entries(v || {}).map(([k, val]) => <Tag key={k}>{k}={val}</Tag>)
                  },
                  { title: '属性', dataIndex: 'attributes', key: 'attributes', width: 300,
                    render: (v: Record<string, string>) => Object.entries(v || {}).map(([k, val]) => <Tag key={k} color="blue">{k}: {val}</Tag>)
                  },
                  { title: '来源', dataIndex: 'source', key: 'source', width: 100, ellipsis: true },
                  { title: '', key: 'action', width: 50,
                    render: (_: unknown, record: KnowledgeEntry) => (
                      <Popconfirm title="确定删除？" onConfirm={() => handleDeleteKnowledge(record.id)}>
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ),
                  },
                ]}
                scroll={{ x: 820 }}
              />
            ) : (
              <Empty description={<span>暂无知识条目。点击「添加」手动录入，或在素材库中学习文档。</span>} />
            )
          )}

          {/* Principles Section */}
          {activeSection === 'principles' && (
            (profile?.principles?.length ?? 0) > 0 ? (
              <Table size="small" pagination={{ pageSize: 10, size: 'small' }}
                dataSource={(profile?.principles ?? []).map(p => ({ key: p.id, ...p }))}
                columns={[
                  { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 100,
                    render: (v: string) => <Tag color={DIMENSION_COLORS[v] || 'default'}>{DIMENSION_LABELS[v] || v}</Tag>
                  },
                  { title: '名称', dataIndex: 'name', key: 'name', width: 150 },
                  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
                  { title: '', key: 'action', width: 50,
                    render: (_: unknown, record: Principle) => (
                      <Popconfirm title="确定删除？" onConfirm={() => handleDeletePrinciple(record.id)}>
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty description="暂无审查原则。点击「添加」创建。" />
            )
          )}

          {/* Preferences Section */}
          {activeSection === 'preferences' && (
            (profile?.preferences_list?.length ?? 0) > 0 ? (
              <Table size="small" pagination={{ pageSize: 10, size: 'small' }}
                dataSource={(profile?.preferences_list ?? []).map(p => ({ key: p.id, ...p }))}
                columns={[
                  { title: '维度', dataIndex: 'dimension', key: 'dimension', width: 90,
                    render: (v: string) => <Tag>{DIMENSION_LABELS[v] || v}</Tag>
                  },
                  { title: '类别', dataIndex: 'category', key: 'category', width: 130 },
                  { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
                  { title: '来源', dataIndex: 'learned_from', key: 'learned_from', width: 90,
                    render: (v: string) => <Tag color={v === 'user_correction' ? 'green' : v === 'ab_choice' ? 'purple' : 'default'}>{v === 'user_correction' ? '用户修改' : v === 'ab_choice' ? 'A/B选择' : v === 'document' ? '文档学习' : v}</Tag>
                  },
                  { title: '置信', dataIndex: 'confidence', key: 'confidence', width: 70,
                    render: (v: number) => `${Math.round(v * 100)}%`
                  },
                  { title: '', key: 'action', width: 50,
                    render: (_: unknown, record: Preference) => (
                      <Popconfirm title="确定删除？" onConfirm={() => handleDeletePreference(record.id)}>
                        <Button type="text" size="small" danger icon={<DeleteOutlined />} />
                      </Popconfirm>
                    ),
                  },
                ]}
              />
            ) : (
              <Empty description="暂无偏好数据。用户使用过程中会自动学习。" />
            )
          )}

          {/* Legacy triples display (if any) */}
          {activeSection === 'knowledge' && (profile?.triples?.length ?? 0) > 0 && (
            <div style={{ marginTop: 16 }}>
              <Divider />
              <Text type="secondary" style={{ fontSize: typography.fontSize.xs }}>
                历史三元组数据（{profile.triples.length} 条，建议迁移到条件组格式）
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                {profile.triples.slice(0, 20).map((t, i) => (
                  <Tag key={i} style={{ fontSize: typography.fontSize.xs }}>{t.s} [{t.r}] {t.o}</Tag>
                ))}
              </div>
            </div>
          )}

          {/* Frequent terms */}
          {activeSection === 'knowledge' && Object.keys(profile?.frequent_terms ?? {}).length > 0 && (
            <div style={{ marginTop: 16 }}>
              <Divider />
              <Text strong style={{ fontSize: typography.fontSize.md, display: 'block', marginBottom: 8 }}>
                高频术语（{Object.keys(profile.frequent_terms).length} 个）
              </Text>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {Object.entries(profile.frequent_terms).sort(([, a], [, b]) => b - a).slice(0, 50).map(([term, count]) => (
                  <Tooltip key={term} title={`出现 ${count} 次`}>
                    <Tag color={count >= 10 ? 'red' : count >= 5 ? 'orange' : 'default'}>{term} ({count})</Tag>
                  </Tooltip>
                ))}
              </div>
            </div>
          )}
        </Card>

        {!hasData && (
          <Card style={{ borderRadius: radius.md }}>
            <Empty description="在素材库中学习文档，或手动添加知识和原则，开始构建用户画像。" />
          </Card>
        )}
      </div>

      {/* Add Knowledge Modal */}
      <Modal title="添加知识条目" open={addKnowledgeVisible} onOk={handleAddKnowledge} onCancel={() => setAddKnowledgeVisible(false)} okText="添加" width={600}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div><Text strong>实体名称</Text><Input placeholder="如：螺栓" value={newKnowledge.entity} onChange={e => setNewKnowledge({ ...newKnowledge, entity: e.target.value })} /></div>
          <div><Text strong>条件（逗号分隔，key=value 格式）</Text><Input placeholder="如：材质=不锈钢, 牌号=M2, 头型=沉头" value={newKnowledge.conditions} onChange={e => setNewKnowledge({ ...newKnowledge, conditions: e.target.value })} /></div>
          <div><Text strong>属性（逗号分隔，key=value 格式）</Text><Input placeholder="如：力矩=45\u00B15 N\u00B7m, 工具=扭矩扳手" value={newKnowledge.attributes} onChange={e => setNewKnowledge({ ...newKnowledge, attributes: e.target.value })} /></div>
          <div><Text strong>来源标准</Text><Input placeholder="如：QJ903-10B-2011" value={newKnowledge.source} onChange={e => setNewKnowledge({ ...newKnowledge, source: e.target.value })} /></div>
        </div>
      </Modal>

      {/* Add Principle Modal */}
      <Modal title="添加审查原则" open={addPrincipleVisible} onOk={handleAddPrinciple} onCancel={() => setAddPrincipleVisible(false)} okText="添加" width={600}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div><Text strong>维度</Text><Select value={newPrinciple.dimension} onChange={v => setNewPrinciple({ ...newPrinciple, dimension: v })} options={[
            { label: '文本合规性', value: 'text_compliance' }, { label: '数据合理性', value: 'data_validity' }, { label: '术语一致性', value: 'terminology' },
          ]} /></div>
          <div><Text strong>名称</Text><Input placeholder="如：数据可验证性" value={newPrinciple.name} onChange={e => setNewPrinciple({ ...newPrinciple, name: e.target.value })} /></div>
          <div><Text strong>描述</Text><Input.TextArea rows={3} placeholder="这条规则检查什么" value={newPrinciple.description} onChange={e => setNewPrinciple({ ...newPrinciple, description: e.target.value })} /></div>
        </div>
      </Modal>
    </div>
  )
}

export default ProfilePage
