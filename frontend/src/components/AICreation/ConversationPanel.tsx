/**
 * ConversationPanel - 对话式交互面板
 * 整合所有对话式交互组件，提供完整的对话式生成流程
 */
import React, { useState, useEffect } from 'react'
import { Card, Steps, Button, Space, message, Spin } from 'antd'
import { ArrowRightOutlined } from '@ant-design/icons'
import {
  startConversation,
  replyQuestion,
  selectPlan,
  getMaterialReport,
  confirmMaterials,
  getReviewSuggestions,
  applySuggestions,
  Question,
  PlanOption
} from '../../services/conversationService'
import { QuestionCard } from './QuestionCard'
import { PlanOptionCard } from './PlanOptionCard'
import { MaterialReportView } from './MaterialReportView'
import { ReviewSuggestionPanel } from './ReviewSuggestionPanel'

const { Step } = Steps

interface ConversationPanelProps {
  projectId?: number
  userId?: number
  initialInput?: string
  onComplete?: (content: string) => void
}

export const ConversationPanel: React.FC<ConversationPanelProps> = ({
  projectId,
  userId,
  initialInput = '',
  onComplete
}) => {
  const [currentStep, setCurrentStep] = useState(0)
  const [sessionId, setSessionId] = useState<string>()
  const [loading, setLoading] = useState(false)

  // 状态数据
  const [questions, setQuestions] = useState<Question[]>([])
  const [questionAnswers, setQuestionAnswers] = useState<Record<string, string>>({})
  const [planOptions, setPlanOptions] = useState<PlanOption[]>([])
  const [selectedPlanId, setSelectedPlanId] = useState<string>()
  const [materialReport, setMaterialReport] = useState<any>()
  const [selectedMaterialIds, setSelectedMaterialIds] = useState<string[]>([])
  const [reviewSuggestions, setReviewSuggestions] = useState<any>()

  // 步骤定义
  const steps = [
    { title: '需求分析', description: '分析需求完整性' },
    { title: '规划选项', description: '选择写作方案' },
    { title: '素材确认', description: '确认使用素材' },
    { title: '文章生成', description: '生成文章内容' },
    { title: '评审建议', description: '查看修改建议' },
    { title: '完成', description: '文章完成' }
  ]

  // 启动对话
  useEffect(() => {
    if (initialInput && !sessionId) {
      handleStartConversation()
    }
  }, [initialInput])

  const handleStartConversation = async () => {
    setLoading(true)
    try {
      const result = await startConversation({
        initial_input: initialInput,
        project_id: projectId,
        user_id: userId
      })
      setSessionId(result.session_id)
      setQuestions(result.questions)
      setCurrentStep(result.questions.length > 0 ? 0 : 1)
    } catch (error: any) {
      message.error(`启动对话失败: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleAnswerQuestion = async (questionId: string, answer: string, optionId?: string) => {
    if (!sessionId) return

    setQuestionAnswers(prev => ({ ...prev, [questionId]: answer }))

    setLoading(true)
    try {
      const result = await replyQuestion({
        session_id: sessionId,
        question_id: questionId,
        answer,
        selected_option_id: optionId
      })

      if (result.next_questions.length > 0) {
        setQuestions(result.next_questions)
      } else if (result.plan_options.length > 0) {
        setPlanOptions(result.plan_options)
        setCurrentStep(1)
      }
    } catch (error: any) {
      message.error(`回复问题失败: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectPlan = async (planId: string) => {
    if (!sessionId) return

    setSelectedPlanId(planId)
    setLoading(true)
    try {
      await selectPlan({
        session_id: sessionId,
        plan_option_id: planId
      })
      setCurrentStep(2)
      // 这里应该触发素材检索和报告生成
      // 暂时跳过，等待后端工作流完成
    } catch (error: any) {
      message.error(`选择计划失败: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  const handleConfirmMaterials = async () => {
    if (!sessionId) return

    setLoading(true)
    try {
      await confirmMaterials({
        session_id: sessionId,
        selected_material_ids: selectedMaterialIds
      })
      setCurrentStep(3)
      // 触发文章生成
    } catch (error: any) {
      message.error(`确认素材失败: ${error.message}`)
    } finally {
      setLoading(false)
    }
  }

  if (loading && !sessionId) {
    return <Spin size="large" style={{ display: 'block', textAlign: 'center', padding: 50 }} />
  }

  return (
    <Card>
      <Steps current={currentStep} style={{ marginBottom: 24 }}>
        {steps.map((step, index) => (
          <Step key={index} title={step.title} description={step.description} />
        ))}
      </Steps>

      {currentStep === 0 && questions.length > 0 && (
        <div>
          <h3>请回答以下问题：</h3>
          {questions.map(question => (
            <QuestionCard
              key={question.id}
              question={question}
              value={questionAnswers[question.id]}
              onChange={(value, optionId) => handleAnswerQuestion(question.id, value, optionId)}
            />
          ))}
          <Button
            type="primary"
            onClick={() => {
              // 所有问题已回答，继续下一步
              setCurrentStep(1)
            }}
            disabled={questions.some(q => q.required && !questionAnswers[q.id])}
          >
            继续
          </Button>
        </div>
      )}

      {currentStep === 1 && planOptions.length > 0 && (
        <div>
          <h3>请选择写作方案：</h3>
          {planOptions.map(option => (
            <PlanOptionCard
              key={option.id}
              option={option}
              selected={selectedPlanId === option.id}
              onSelect={() => handleSelectPlan(option.id)}
            />
          ))}
        </div>
      )}

      {currentStep === 2 && materialReport && (
        <MaterialReportView
          report={materialReport}
          selectedIds={selectedMaterialIds}
          onSelect={(id, selected) => {
            if (selected) {
              setSelectedMaterialIds(prev => [...prev, id])
            } else {
              setSelectedMaterialIds(prev => prev.filter(mid => mid !== id))
            }
          }}
          onConfirm={handleConfirmMaterials}
        />
      )}

      {currentStep === 4 && reviewSuggestions && (
        <ReviewSuggestionPanel
          issues={reviewSuggestions.issues}
          overallScore={reviewSuggestions.overall_score}
          onApply={(appliedIds, rejectedIds) => {
            if (sessionId) {
              applySuggestions({
                session_id: sessionId,
                applied_suggestions: appliedIds,
                rejected_suggestions: rejectedIds
              }).then(result => {
                message.success('建议已应用')
                setCurrentStep(5)
                onComplete?.(result.updated_content)
              })
            }
          }}
        />
      )}
    </Card>
  )
}

