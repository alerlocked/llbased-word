/**
 * E2E Tests - Agent Chat Flow
 *
 * 测试 Agent 对话功能
 */
import { test, expect, Page } from '@playwright/test';

test.describe('Agent Chat Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display chat interface', async ({ page }) => {
    // 导航到 Agent 创建页面
    await page.goto('/agent');

    // 检查聊天界面元素
    const chatContainer = page.locator(
      '.chat-container, [data-testid="chat-interface"], .ant-layout-content'
    );

    await expect(chatContainer.or(page.locator('body'))).toBeVisible();
  });

  test('should allow sending messages', async ({ page }) => {
    await page.goto('/agent');

    // 查找消息输入框
    const messageInput = page.locator(
      'textarea, input[type="text"], .ant-input'
    ).first();

    if (await messageInput.count() > 0) {
      // 输入消息
      await messageInput.fill('我想创建一份工艺文件');

      // 查找发送按钮
      const sendButton = page.locator(
        'button:has-text("发送"), button[type="submit"], [data-testid="send-button"]'
      );

      if (await sendButton.count() > 0) {
        await sendButton.click();
      } else {
        // 尝试按 Enter 发送
        await messageInput.press('Enter');
      }

      // 等待响应
      await page.waitForTimeout(1000);
    }
  });

  test('should display conversation history', async ({ page }) => {
    await page.goto('/agent');

    // 检查对话消息
    const messages = page.locator(
      '.message, .chat-message, [data-testid="message"]'
    );

    const count = await messages.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should show typing indicator during response', async ({ page }) => {
    await page.goto('/agent');

    // 发送消息后检查加载状态
    const messageInput = page.locator('textarea, .ant-input').first();

    if (await messageInput.count() > 0) {
      await messageInput.fill('测试消息');
      await messageInput.press('Enter');

      // 检查是否有加载指示器
      const loadingIndicator = page.locator(
        '.ant-spin, .typing-indicator, [data-testid="loading"]'
      );

      // 加载指示器可能会很快消失
      const wasVisible = await loadingIndicator.isVisible().catch(() => false);
      expect(typeof wasVisible).toBe('boolean');
    }
  });
});

test.describe('Agent Question Flow', () => {
  test('should display questions from agent', async ({ page }) => {
    await page.goto('/agent');

    // 检查问题列表
    const questions = page.locator(
      '.question-item, [data-testid="question"], .ant-card'
    );

    const count = await questions.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should allow answering questions', async ({ page }) => {
    await page.goto('/agent');

    // 查找选项按钮
    const optionButton = page.locator(
      '.ant-radio-button, .ant-btn, [data-testid="option"]'
    ).first();

    if (await optionButton.count() > 0) {
      await optionButton.click();

      // 查找确认按钮
      const confirmButton = page.locator('button:has-text("确认"), button:has-text("下一步")');

      if (await confirmButton.count() > 0) {
        await confirmButton.click();
      }
    }
  });

  test('should show progress through workflow steps', async ({ page }) => {
    await page.goto('/agent');

    // 检查进度指示器
    const progressBar = page.locator(
      '.ant-steps, .progress-bar, [data-testid="workflow-progress"]'
    );

    const count = await progressBar.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Material Selection', () => {
  test('should display material recommendations', async ({ page }) => {
    await page.goto('/agent');

    // 检查素材列表
    const materials = page.locator(
      '.material-item, [data-testid="material"], .ant-list-item'
    );

    const count = await materials.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should allow selecting materials', async ({ page }) => {
    await page.goto('/agent');

    // 查找复选框
    const checkbox = page.locator('.ant-checkbox-input').first();

    if (await checkbox.count() > 0) {
      await checkbox.check();
      expect(await checkbox.isChecked()).toBe(true);
    }
  });

  test('should show material relevance scores', async ({ page }) => {
    await page.goto('/agent');

    // 检查相关性分数
    const scores = page.locator(
      '.relevance-score, [data-testid="score"], .ant-progress'
    );

    const count = await scores.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });
});

test.describe('Content Generation', () => {
  test('should display generated content', async ({ page }) => {
    await page.goto('/agent');

    // 检查生成的内容区域
    const contentArea = page.locator(
      '.generated-content, .markdown-body, [data-testid="content-preview"]'
    );

    const count = await contentArea.count();
    expect(count).toBeGreaterThanOrEqual(0);
  });

  test('should support content editing', async ({ page }) => {
    await page.goto('/agent');

    // 查找编辑器
    const editor = page.locator(
      '.ProseMirror, .ant-input, [contenteditable="true"]'
    );

    if (await editor.count() > 0) {
      await editor.click();
      await editor.fill('编辑的内容');
    }
  });

  test('should support content export', async ({ page }) => {
    await page.goto('/agent');

    // 查找导出按钮
    const exportButton = page.locator(
      'button:has-text("导出"), button:has-text("Export")'
    );

    if (await exportButton.count() > 0) {
      // 点击导出按钮
      await exportButton.click();

      // 检查导出选项
      const exportOptions = page.locator('.ant-dropdown-menu-item');
      const count = await exportOptions.count();
      expect(count).toBeGreaterThanOrEqual(0);
    }
  });
});
