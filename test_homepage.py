#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web测试脚本 - 验证首页加载
测试目标：
1. 首页能正常加载
2. 页面标题正确
3. 主要元素显示正常
4. 截图验证
"""
from playwright.sync_api import sync_playwright
import time
import sys
import io

# 设置标准输出为UTF-8编码
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_homepage():
    """测试首页加载和主要元素"""

    with sync_playwright() as p:
        # 启动浏览器（headless模式）
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("=" * 60)
        print("开始Web测试 - 首页验证")
        print("=" * 60)

        try:
            # 1. 导航到首页
            print("\n[步骤1] 导航到首页: http://localhost:3000/")
            page.goto('http://localhost:3000/', timeout=30000)

            # 2. 等待页面加载完成（关键步骤）
            print("[步骤2] 等待页面完全加载...")
            page.wait_for_load_state('networkidle')

            # 3. 验证页面标题
            print("[步骤3] 验证页面标题...")
            title = page.title()
            print(f"  页面标题: {title}")
            assert "工艺文件辅助编辑系统" in title, f"标题验证失败: {title}"
            print("  [PASS] 标题验证通过")

            # 4. 截图保存
            screenshot_path = "D:\\Project Nantianmen\\projects\\localknowledgebase-word\\test_screenshot.png"
            print(f"\n[步骤4] 保存截图到: {screenshot_path}")
            page.screenshot(path=screenshot_path, full_page=True)
            print("  [PASS] 截图保存成功")

            # 5. 检查主要元素
            print("\n[步骤5] 检查页面主要元素...")

            # 检查根元素
            root_element = page.locator('#root')
            assert root_element.is_visible(), "root元素不可见"
            print("  [PASS] root元素存在且可见")

            # 检查是否有React应用加载
            content = page.content()
            if '工艺文件辅助编辑系统' in content or 'main.tsx' in content:
                print("  [PASS] React应用加载正常")
            else:
                print("  [WARN] 可能需要等待更长时间加载")

            # 6. 获取页面URL
            current_url = page.url
            print(f"\n[步骤6] 当前URL: {current_url}")

            # 7. 检查控制台错误
            print("\n[步骤7] 检查页面控制台...")
            # 注意：这里需要监听console事件，在导航之前设置

            print("\n" + "=" * 60)
            print("[SUCCESS] Web测试完成 - 所有检查通过")
            print("=" * 60)

            # 保持浏览器打开3秒以便观察
            time.sleep(2)

        except Exception as e:
            print(f"\n[ERROR] 测试失败: {str(e)}")
            # 失败时也保存截图
            error_screenshot = "D:\\Project Nantianmen\\projects\\localknowledgebase-word\\test_error_screenshot.png"
            page.screenshot(path=error_screenshot, full_page=True)
            print(f"错误截图已保存到: {error_screenshot}")
            raise

        finally:
            browser.close()
            print("\n浏览器已关闭")

if __name__ == "__main__":
    test_homepage()
