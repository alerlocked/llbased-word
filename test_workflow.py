# -*- coding: utf-8 -*-
"""
完整工作流程测试脚本 - 修复版
测试任务：上传PDF文档，使用AI分析电缆装配中的潜在风险点
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, Page

# 设置UTF-8编码
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 测试配置
PDF_FILE = r"D:\ai_idea\localknowledgebase-word\data\process_docs\全单电缆装配规程.pdf"
BASE_URL = "http://localhost:3000"
SCREENSHOT_DIR = Path("D:/ai_idea/localknowledgebase-word/validation_results")
SCREENSHOT_DIR.mkdir(exist_ok=True)

def take_screenshot(page, name):
    """截图并保存"""
    path = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"[Screenshot] {path}")
    return path

def close_all_modals(page):
    """关闭所有modal对话框"""
    try:
        # 按ESC键关闭modal
        page.keyboard.press('Escape')
        time.sleep(0.3)

        # 点击所有关闭按钮
        close_buttons = page.locator('.ant-modal-close, .ant-drawer-close, .anticon-close')
        for i in range(close_buttons.count()):
            try:
                close_buttons.nth(i).click(timeout=1000)
                time.sleep(0.2)
            except:
                pass
    except:
        pass

def test_workflow(page: Page):
    """执行完整工作流程"""

    print("\n" + "="*60)
    print("开始测试：电缆装配风险点分析")
    print("="*60)

    # Step 1: 访问工作台页面
    print("\n[Step 1] 访问工作台页面...")
    page.goto(BASE_URL)
    page.wait_for_load_state('networkidle')
    take_screenshot(page, "01_homepage")

    # 关闭可能存在的modal
    close_all_modals(page)
    time.sleep(0.5)

    # Step 2: 选择现有项目
    print("\n[Step 2] 选择项目...")
    try:
        # 查找项目选择器
        project_selector = page.locator('.ant-select').first
        if project_selector.is_visible(timeout=5000):
            project_selector.click()
            time.sleep(0.5)

            options = page.locator('.ant-select-dropdown .ant-select-item')
            if options.count() > 0:
                options.first().click()
                print("  [OK] 选择了现有项目")
            else:
                page.keyboard.press('Escape')
                print("  [WARN] 没有现有项目")
        else:
            print("  [WARN] 未找到项目选择器")
    except Exception as e:
        print(f"  [WARN] 选择项目失败: {e}")

    time.sleep(1)
    take_screenshot(page, "02_project_selected")

    # Step 3: 上传PDF - 通过API直接上传
    print("\n[Step 3] 上传PDF文件...")

    # 获取当前项目ID
    try:
        # 从页面获取项目ID
        projects_response = page.evaluate('''() => {
            return fetch('http://localhost:8000/api/creation/projects')
                .then(r => r.json())
                .then(data => data.items || data);
        }''')

        if projects_response and len(projects_response) > 0:
            project_id = projects_response[0]['id']
            print(f"  [OK] 项目ID: {project_id}")

            # 通过API上传文件
            upload_result = page.evaluate('''async ({projectId, filePath}) => {
                const formData = new FormData();
                const response = await fetch(filePath);
                const blob = await response.blob();
                formData.append('file', blob, '全单电缆装配规程.pdf');

                const uploadResponse = await fetch(`http://localhost:8000/api/creation/projects/${projectId}/upload`, {
                    method: 'POST',
                    body: formData
                });
                return await uploadResponse.json();
            }''', {'projectId': project_id, 'filePath': PDF_FILE})

            print(f"  [OK] 上传结果: {upload_result}")
        else:
            print("  [WARN] 没有可用项目")
    except Exception as e:
        print(f"  [WARN] 上传失败: {e}")

    take_screenshot(page, "03_after_upload")

    # Step 4: 打开AI面板
    print("\n[Step 4] 打开AI面板...")
    try:
        # 先关闭所有modal
        close_all_modals(page)

        # 查找AI/助手按钮
        ai_buttons = [
            'button:has-text("AI")',
            'button:has-text("助手")',
            '[class*="robot"]',
            '.anticon-robot'
        ]

        clicked = False
        for selector in ai_buttons:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    clicked = True
                    print(f"  [OK] 打开了AI面板 (通过 {selector})")
                    break
            except:
                continue

        if not clicked:
            print("  [WARN] 未找到AI按钮，尝试直接在页面上操作")
    except Exception as e:
        print(f"  [WARN] 打开AI面板失败: {e}")

    time.sleep(1)
    take_screenshot(page, "04_ai_panel")

    # Step 5: 输入问题并发送
    print("\n[Step 5] 提交分析任务...")
    task_prompt = """请分析《全单电缆装配规程》这份工艺文档，找出电缆装配过程中潜在的风险点。

要求：
1. 识别工艺流程中的风险点（至少5个）
2. 对每个风险点说明：
   - 风险描述
   - 可能导致的后果
   - 初步修改建议

请以结构化的方式输出结果。"""

    try:
        # 查找输入框
        textarea = page.locator('textarea').first
        if textarea.is_visible(timeout=5000):
            textarea.fill(task_prompt)
            print("  [OK] 输入任务描述")
            time.sleep(0.5)

            # 发送
            send_btn = page.locator('button:has-text("发送")').first
            if send_btn.is_visible(timeout=2000):
                send_btn.click()
                print("  [OK] 提交任务")
            else:
                textarea.press('Enter')
                print("  [OK] 通过Enter提交")
        else:
            print("  [WARN] 未找到输入框")
    except Exception as e:
        print(f"  [WARN] 提交失败: {e}")

    take_screenshot(page, "05_task_submitted")

    # Step 6: 等待AI响应
    print("\n[Step 6] 等待AI分析结果 (最多2分钟)...")

    max_wait = 120
    start_time = time.time()
    last_content_len = 0

    while time.time() - start_time < max_wait:
        try:
            # 检查响应内容
            response_area = page.locator('.ant-drawer-body, [class*="message"]').last
            if response_area.is_visible():
                content = response_area.text_content()
                if len(content) > last_content_len:
                    last_content_len = len(content)
                    print(f"  [WAIT] 响应长度: {len(content)} 字符")
        except:
            pass

        # 每15秒截图一次
        elapsed = int(time.time() - start_time)
        if elapsed % 15 == 0 and elapsed > 0:
            take_screenshot(page, f"06_waiting_{elapsed}s")

        time.sleep(3)

    # 最终截图
    print("\n[Step 7] 获取最终结果...")
    take_screenshot(page, "07_final_result")

    # 保存页面内容
    try:
        content = page.content()
        result_file = SCREENSHOT_DIR / "page_content.html"
        with open(result_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] 页面内容已保存到: {result_file}")
    except Exception as e:
        print(f"  [WARN] 保存页面内容失败: {e}")

    print("\n" + "="*60)
    print("测试完成！")
    print(f"截图保存在: {SCREENSHOT_DIR}")
    print("="*60)

def main():
    """主函数"""
    with sync_playwright() as p:
        # 启动浏览器（使用系统Chrome）
        browser = p.chromium.launch(channel='chrome', headless=False, slow_mo=300)
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            locale='zh-CN'
        )
        page = context.new_page()

        try:
            test_workflow(page)
        except Exception as e:
            print(f"\n[ERROR] 测试失败: {e}")
            import traceback
            traceback.print_exc()
            take_screenshot(page, "error_final")
        finally:
            print("\n浏览器将在10秒后关闭...")
            time.sleep(10)
            browser.close()

if __name__ == "__main__":
    main()
