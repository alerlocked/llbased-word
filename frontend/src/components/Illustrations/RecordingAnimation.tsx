/**
 * RecordingAnimation - 录音/创作主题 Lottie 动画组件
 * 用于空状态、加载状态等场景
 */
import Lottie from 'lottie-react'
import { CSSProperties } from 'react'

// 简约风格的录音动画数据 - 人物录音场景
const recordingAnimationData = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 90,
  "w": 400,
  "h": 300,
  "nm": "Recording",
  "ddd": 0,
  "assets": [],
  "layers": [
    // 声波层 - 从麦克风发出的声波
    {
      "ddd": 0,
      "ind": 1,
      "ty": 4,
      "nm": "Wave1",
      "sr": 1,
      "ks": {
        "o": { "a": 1, "k": [
          {"t": 0, "s": [100], "e": [0]},
          {"t": 30, "s": [0]}
        ]},
        "p": { "a": 0, "k": [200, 150, 0] },
        "s": { "a": 1, "k": [
          {"t": 0, "s": [100, 100, 100], "e": [150, 150, 100]},
          {"t": 30, "s": [150, 150, 100]}
        ]}
      },
      "shapes": [{
        "ty": "el",
        "p": { "a": 0, "k": [0, 0] },
        "s": { "a": 0, "k": [60, 60] },
        "nm": "Circle"
      }, {
        "ty": "st",
        "c": { "a": 0, "k": [0.96, 0.65, 0.14, 1] },
        "w": { "a": 0, "k": 3 },
        "nm": "Stroke"
      }]
    },
    // 声波层2
    {
      "ddd": 0,
      "ind": 2,
      "ty": 4,
      "nm": "Wave2",
      "sr": 1,
      "ks": {
        "o": { "a": 1, "k": [
          {"t": 15, "s": [100], "e": [0]},
          {"t": 45, "s": [0]}
        ]},
        "p": { "a": 0, "k": [200, 150, 0] },
        "s": { "a": 1, "k": [
          {"t": 15, "s": [100, 100, 100], "e": [150, 150, 100]},
          {"t": 45, "s": [150, 150, 100]}
        ]}
      },
      "shapes": [{
        "ty": "el",
        "p": { "a": 0, "k": [0, 0] },
        "s": { "a": 0, "k": [60, 60] },
        "nm": "Circle"
      }, {
        "ty": "st",
        "c": { "a": 0, "k": [0.96, 0.65, 0.14, 1] },
        "w": { "a": 0, "k": 3 },
        "nm": "Stroke"
      }]
    },
    // 声波层3
    {
      "ddd": 0,
      "ind": 3,
      "ty": 4,
      "nm": "Wave3",
      "sr": 1,
      "ks": {
        "o": { "a": 1, "k": [
          {"t": 30, "s": [100], "e": [0]},
          {"t": 60, "s": [0]}
        ]},
        "p": { "a": 0, "k": [200, 150, 0] },
        "s": { "a": 1, "k": [
          {"t": 30, "s": [100, 100, 100], "e": [150, 150, 100]},
          {"t": 60, "s": [150, 150, 100]}
        ]}
      },
      "shapes": [{
        "ty": "el",
        "p": { "a": 0, "k": [0, 0] },
        "s": { "a": 0, "k": [60, 60] },
        "nm": "Circle"
      }, {
        "ty": "st",
        "c": { "a": 0, "k": [0.96, 0.65, 0.14, 1] },
        "w": { "a": 0, "k": 3 },
        "nm": "Stroke"
      }]
    },
    // 麦克风图标
    {
      "ddd": 0,
      "ind": 4,
      "ty": 4,
      "nm": "Mic",
      "sr": 1,
      "ks": {
        "o": { "a": 0, "k": 100 },
        "p": { "a": 0, "k": [200, 150, 0] },
        "s": { "a": 1, "k": [
          {"t": 0, "s": [100, 100, 100], "e": [105, 105, 100]},
          {"t": 15, "s": [105, 105, 100], "e": [100, 100, 100]},
          {"t": 30, "s": [100, 100, 100]}
        ]}
      },
      "shapes": [
        // 麦克风头部
        {
          "ty": "rc",
          "p": { "a": 0, "k": [0, -15] },
          "s": { "a": 0, "k": [30, 45] },
          "r": { "a": 0, "k": 15 },
          "nm": "MicHead"
        },
        {
          "ty": "fl",
          "c": { "a": 0, "k": [0.12, 0.12, 0.12, 1] },
          "nm": "Fill"
        },
        // 麦克风支架
        {
          "ty": "gr",
          "it": [
            {
              "ty": "rc",
              "p": { "a": 0, "k": [0, 25] },
              "s": { "a": 0, "k": [8, 30] },
              "r": { "a": 0, "k": 4 },
              "nm": "Stand"
            },
            {
              "ty": "fl",
              "c": { "a": 0, "k": [0.12, 0.12, 0.12, 1] },
              "nm": "Fill"
            }
          ],
          "nm": "StandGroup"
        }
      ]
    }
  ]
}

// 打字机动画数据 - 文字逐个出现效果
const typingAnimationData = {
  "v": "5.7.4",
  "fr": 30,
  "ip": 0,
  "op": 60,
  "w": 200,
  "h": 100,
  "nm": "Typing",
  "ddd": 0,
  "assets": [],
  "layers": [
    // 光标
    {
      "ddd": 0,
      "ind": 1,
      "ty": 4,
      "nm": "Cursor",
      "sr": 1,
      "ks": {
        "o": { "a": 1, "k": [
          {"t": 0, "s": [100], "e": [0]},
          {"t": 15, "s": [0], "e": [100]},
          {"t": 30, "s": [100]}
        ]},
        "p": { "a": 1, "k": [
          {"t": 0, "s": [30, 50, 0], "e": [170, 50, 0]},
          {"t": 60, "s": [170, 50, 0]}
        ]}
      },
      "shapes": [{
        "ty": "rc",
        "p": { "a": 0, "k": [0, 0] },
        "s": { "a": 0, "k": [3, 20] },
        "r": { "a": 0, "k": 1 },
        "nm": "Cursor"
      }, {
        "ty": "fl",
        "c": { "a": 0, "k": [0.96, 0.65, 0.14, 1] },
        "nm": "Fill"
      }]
    },
    // 文字线条
    {
      "ddd": 0,
      "ind": 2,
      "ty": 4,
      "nm": "Line1",
      "sr": 1,
      "ks": {
        "o": { "a": 0, "k": 100 },
        "p": { "a": 0, "k": [100, 50, 0] }
      },
      "shapes": [{
        "ty": "rc",
        "p": { "a": 0, "k": [0, 0] },
        "s": { "a": 1, "k": [
          {"t": 0, "s": [0, 4], "e": [140, 4]},
          {"t": 60, "s": [140, 4]}
        ]},
        "r": { "a": 0, "k": 2 },
        "nm": "Line"
      }, {
        "ty": "fl",
        "c": { "a": 0, "k": [0.12, 0.12, 0.12, 1] },
        "nm": "Fill"
      }]
    }
  ]
}

interface AnimationProps {
  type?: 'recording' | 'typing' | 'both'
  size?: number
  style?: CSSProperties
  className?: string
}

/**
 * 录音动画组件
 */
export const RecordingAnimation: React.FC<AnimationProps> = ({ 
  size = 200, 
  style,
  className 
}) => {
  return (
    <div className={className} style={{ width: size, height: size * 0.75, ...style }}>
      <Lottie 
        animationData={recordingAnimationData} 
        loop={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  )
}

/**
 * 打字动画组件
 */
export const TypingAnimation: React.FC<AnimationProps> = ({ 
  size = 200, 
  style,
  className 
}) => {
  return (
    <div className={className} style={{ width: size, height: size * 0.5, ...style }}>
      <Lottie 
        animationData={typingAnimationData} 
        loop={true}
        style={{ width: '100%', height: '100%' }}
      />
    </div>
  )
}

/**
 * 空状态插画 - 组合录音和文字元素
 */
interface EmptyStateProps {
  title?: string
  description?: string
  action?: React.ReactNode
}

export const EmptyStateIllustration: React.FC<EmptyStateProps> = ({
  title = '开始创作',
  description = '上传PDF文档，AI 帮你解析并生成工艺文件',
  action
}) => {
  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '48px 24px',
      textAlign: 'center'
    }}>
      {/* 主插画 */}
      <div style={{ 
        position: 'relative',
        marginBottom: 32
      }}>
        <RecordingAnimation size={280} />
        
        {/* 装饰元素 */}
        <div style={{
          position: 'absolute',
          top: -20,
          right: -20,
          width: 40,
          height: 40,
          background: '#FFF4E0',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 20
        }}>
          🎙️
        </div>
        
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: -10,
          width: 32,
          height: 32,
          background: '#FFE8E0',
          borderRadius: '50%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 16
        }}>
          📝
        </div>
      </div>
      
      {/* 标题 */}
      <h2 style={{
        fontSize: 24,
        fontWeight: 600,
        color: '#1F1F1F',
        margin: '0 0 8px 0'
      }}>
        {title}
      </h2>
      
      {/* 描述 */}
      <p style={{
        fontSize: 14,
        color: '#666666',
        margin: '0 0 24px 0',
        maxWidth: 300
      }}>
        {description}
      </p>
      
      {/* 操作按钮 */}
      {action}
    </div>
  )
}

export default RecordingAnimation


