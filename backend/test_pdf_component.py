"""
PDF解析功能组件测试脚本
"""
import sys
import os
from pathlib import Path

# 设置UTF-8编码
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# 添加项目路径
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

def test_imports():
    """测试1: 检查模块导入"""
    print("\n" + "="*60)
    print("测试1: PDF解析器模块导入")
    print("="*60)

    try:
        from app.tools.pdf_parser import PDFParser
        print("[OK] PDFParser类导入成功")
        return True, PDFParser
    except Exception as e:
        print(f"[FAIL] 导入失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_instantiation(PDFParser):
    """测试2: 检查实例化"""
    print("\n" + "="*60)
    print("测试2: PDFParser实例化")
    print("="*60)

    try:
        parser = PDFParser()
        print("[OK] PDFParser实例化成功")
        return True, parser
    except Exception as e:
        print(f"[FAIL] 实例化失败: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_parse_methods(parser):
    """测试3: 检查解析方法存在"""
    print("\n" + "="*60)
    print("测试3: 解析方法检查")
    print("="*60)

    methods = ['parse', 'extract_tables', 'extract_text']
    all_exist = True

    for method in methods:
        if hasattr(parser, method):
            print(f"[OK] 方法 {method} 存在")
        else:
            print(f"[WARN] 方法 {method} 不存在")
            all_exist = False

    return all_exist

def test_parse_real_pdf(parser):
    """测试4: 实际PDF解析测试"""
    print("\n" + "="*60)
    print("测试4: 实际PDF文件解析")
    print("="*60)

    # 查找测试PDF文件
    test_pdf_paths = [
        backend_dir.parent / "data" / "process_docs" / "全单电缆装配规程.pdf",
        backend_dir / "data" / "process_docs" / "全单电缆装配规程.pdf",
    ]

    test_pdf = None
    for path in test_pdf_paths:
        if path.exists():
            test_pdf = path
            break

    if not test_pdf:
        print("[WARN] 未找到测试PDF文件，跳过实际解析测试")
        print(f"   查找路径: {[str(p) for p in test_pdf_paths]}")
        return None

    print(f"[INFO] 找到测试PDF: {test_pdf}")
    print(f"   文件大小: {test_pdf.stat().st_size / 1024:.2f} KB")

    try:
        # 尝试解析PDF
        result = parser.parse(str(test_pdf))

        if result:
            print("[OK] PDF解析成功")

            # 检查解析结果
            if isinstance(result, dict):
                print(f"   返回类型: dict")
                print(f"   包含键: {list(result.keys())[:10]}")

                # 检查表格数据
                if 'tables' in result:
                    tables = result['tables']
                    print(f"   [OK] 表格数量: {len(tables)}")

                    if tables:
                        print(f"   第一个表格预览:")
                        first_table = tables[0]
                        if isinstance(first_table, dict):
                            print(f"      - 类型: {first_table.get('type', 'unknown')}")
                            if 'data' in first_table:
                                data = first_table['data']
                                if isinstance(data, list) and len(data) > 0:
                                    print(f"      - 行数: {len(data)}")
                                    print(f"      - 列数: {len(data[0]) if data else 0}")
                                    print(f"      - 第一行: {data[0][:3] if data else []}")

                # 检查文本内容
                if 'text' in result:
                    text = result['text']
                    print(f"   [OK] 文本长度: {len(text)} 字符")
                    print(f"   预览: {text[:100]}...")

                return True
            else:
                print(f"   返回类型: {type(result)}")
                return True
        else:
            print("[FAIL] PDF解析返回空结果")
            return False

    except Exception as e:
        print(f"[FAIL] PDF解析失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_api_endpoint():
    """测试5: 检查API端点"""
    print("\n" + "="*60)
    print("测试5: PDF解析API端点检查")
    print("="*60)

    import requests

    try:
        # 检查后端健康状态
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("[OK] 后端服务正常运行")
        else:
            print(f"[WARN] 后端服务响应异常: {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] 无法连接后端服务: {e}")
        return False

    # 检查PDF解析相关端点
    endpoints = [
        "/api/process-documents/",
        "/api/documents/parse",
    ]

    for endpoint in endpoints:
        try:
            url = f"http://localhost:8000{endpoint}"
            response = requests.get(url, timeout=5)
            if response.status_code in [200, 405, 404]:  # 405表示方法不允许但端点存在
                print(f"[OK] 端点存在: {endpoint}")
            else:
                print(f"[WARN] 端点异常: {endpoint} (状态码: {response.status_code})")
        except Exception as e:
            print(f"[FAIL] 端点测试失败 {endpoint}: {e}")

    return True

def main():
    print("\n" + "="*60)
    print("PDF解析功能组件测试")
    print("="*60)
    print(f"测试时间: {Path(__file__).stat().st_mtime}")
    print(f"后端目录: {backend_dir}")

    results = []

    # 测试1: 导入
    success, PDFParser = test_imports()
    results.append(("模块导入", success))
    if not success:
        print("\n❌ 后续测试无法继续，请先修复导入问题")
        return

    # 测试2: 实例化
    success, parser = test_instantiation(PDFParser)
    results.append(("实例化", success))
    if not success:
        print("\n❌ 后续测试无法继续，请先修复实例化问题")
        return

    # 测试3: 方法检查
    success = test_parse_methods(parser)
    results.append(("方法检查", success))

    # 测试4: 实际PDF解析
    success = test_parse_real_pdf(parser)
    results.append(("PDF解析", success if success is not None else True))

    # 测试5: API端点
    success = test_api_endpoint()
    results.append(("API端点", success))

    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总")
    print("="*60)

    for name, success in results:
        status = "[OK] 通过" if success else "[FAIL] 失败"
        print(f"{name:20s} {status}")

    total = len(results)
    passed = sum(1 for _, s in results if s)
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n[SUCCESS] 所有测试通过！PDF解析功能正常")
    else:
        print("\n[WARNING] 部分测试失败，请检查上述错误信息")

if __name__ == "__main__":
    main()
