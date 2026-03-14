/**
 * 调试日志工具 - 集中管理调试日志
 * 避免在代码中重复写入硬编码的调试URL
 */

interface DebugLogData {
  location: string;
  message: string;
  data?: any;
  timestamp?: string;
  sessionId?: string;
  runId?: string;
  hypothesisId?: string;
}

/**
 * 发送调试日志到日志服务
 * @param location 日志位置（如组件名、函数名）
 * @param message 日志消息
 * @param data 可选的附加数据
 * @param sessionId 会话ID（可选）
 * @param runId 运行ID（可选）
 * @param hypothesisId 假设ID（可选）
 */
export async function logDebug(
  location: string,
  message: string,
  data?: any,
  sessionId?: string,
  runId?: string,
  hypothesisId?: string
): Promise<void> {
  try {
    // 从环境变量获取调试服务URL，默认为空（不发送）
    const debugUrl = process.env.REACT_APP_DEBUG_LOG_URL || '';

    if (!debugUrl) {
      // 如果没有配置调试URL，只在控制台输出
      console.log(`[DEBUG] ${location}: ${message}`, data || '');
      return;
    }

    const logData: DebugLogData = {
      location,
      message,
      data,
      timestamp: new Date().toISOString(),
      sessionId: sessionId || 'debug-session',
      runId,
      hypothesisId
    };

    // 异步发送日志，不阻塞主流程
    fetch(debugUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(logData),
    }).catch(() => {
      // 静默处理错误，不干扰主应用
    });

  } catch (error) {
    // 静默处理错误
  }
}

/**
 * 简化的组件日志记录
 * @param componentName 组件名称
 * @param event 事件描述
 * @param data 附加数据
 */
export function logComponentEvent(componentName: string, event: string, data?: any): void {
  logDebug(componentName, event, data);
}

/**
 * 错误日志记录
 * @param location 错误位置
 * @param error 错误对象或消息
 * @param context 上下文信息
 */
export function logError(location: string, error: any, context?: any): void {
  const errorMessage = error instanceof Error ? error.message : String(error);
  logDebug(location, `ERROR: ${errorMessage}`, { error, context });
}

/**
 * 性能日志记录
 * @param location 位置
 * @param metric 指标名称
 * @param value 指标值
 * @param unit 单位（如ms, MB等）
 */
export function logPerformance(location: string, metric: string, value: number, unit?: string): void {
  logDebug(location, `PERFORMANCE: ${metric}`, { value, unit });
}

/**
 * 代理调试日志 - 用于Agent开发调试
 * @param location 位置
 * @param message 消息
 * @param data 数据
 * @param hypothesisId 假设ID
 */
export function logAgentDebug(
  location: string,
  message: string,
  data?: any,
  hypothesisId?: string
): void {
  logDebug(location, message, data, 'debug-session', 'run1', hypothesisId);
}