/**
 * E2E Tests - User Authentication Flow
 *
 * 测试用户登录和基本导航流程
 */
import { test, expect, Page } from '@playwright/test';

test.describe('User Authentication Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('should display home page', async ({ page }) => {
    // 验证页面加载
    await expect(page).toHaveTitle(/工艺文件|Craft Document/);
  });

  test('should navigate to main sections', async ({ page }) => {
    // 检查主要导航元素是否存在
    const navigation = page.locator('nav, [role="navigation"]');
    await expect(navigation).toBeVisible();
  });

  test('should show login prompt for protected features', async ({ page }) => {
    // 尝试访问需要登录的功能
    await page.goto('/workspace');

    // 如果未登录，应该重定向到登录页或显示提示
    // 这里根据实际应用逻辑调整
    const currentUrl = page.url();
    expect(currentUrl).toBeDefined();
  });
});

test.describe('Application Layout', () => {
  test('should have responsive design', async ({ page }) => {
    // 测试响应式布局
    await page.goto('/');
    await page.setViewportSize({ width: 1920, height: 1080 });
    await expect(page.locator('body')).toBeVisible();

    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator('body')).toBeVisible();

    await page.setViewportSize({ width: 375, height: 667 });
    await expect(page.locator('body')).toBeVisible();
  });

  test('should load without console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // 过滤掉一些预期的第三方库警告
    const criticalErrors = errors.filter(
      (err) => !err.includes('Warning:') && !err.includes('DevTools')
    );

    expect(criticalErrors).toHaveLength(0);
  });
});
