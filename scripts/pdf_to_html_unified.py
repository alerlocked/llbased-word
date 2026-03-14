# -*- coding: utf-8 -*-
"""
PDF to HTML Unified Converter
统一的 PDF 转 HTML 转换脚本

特性：
- 支持 MinerU 和 pdfplumber 两种后端
- 自动选择最佳后端
- 支持复杂表格（合并单元格）
- 生成完整的 HTML 报告

使用方法：
    python scripts/pdf_to_html_unified.py <pdf_path> [--output-dir <dir>] [--backend <auto|mineru|pdfplumber>]

示例：
    python scripts/pdf_to_html_unified.py test.pdf
    python scripts/pdf_to_html_unified.py test.pdf --output-dir ./output
    python scripts/pdf_to_html_unified.py test.pdf --backend mineru
"""
import os
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from enum import Enum
from dataclasses import dataclass, field

# Windows 编码处理
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class BackendType(Enum):
    """后端类型枚举"""
    AUTO = "auto"
    MINERU = "mineru"
    PDFPLUMBER = "pdfplumber"


@dataclass
class TableData:
    """表格数据结构"""
    page_number: int
    table_index: int
    rows: List[List[str]]
    bbox: Tuple[float, float, float, float] = (0, 0, 0, 0)
    has_merged_cells: bool = False
    confidence: float = 0.0
    extraction_method: str = "unknown"
    html_content: str = ""
    img_path: str = ""
    caption: List[str] = field(default_factory=list)


@dataclass
class ParseResult:
    """解析结果"""
    pdf_name: str
    total_pages: int
    tables: List[TableData]
    backend_used: str
    parse_time: float
    success: bool
    error_message: str = ""


# ============== CSS 样式 ==============
HTML_CSS = """
* { box-sizing: border-box; }
body {
    font-family: "Microsoft YaHei", "SimSun", Arial, sans-serif;
    margin: 0;
    padding: 20px;
    background: #f5f5f5;
    line-height: 1.6;
}
.container {
    max-width: 1200px;
    margin: 0 auto;
    background: white;
    padding: 30px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}
h1 {
    color: #333;
    border-bottom: 3px solid #4CAF50;
    padding-bottom: 15px;
    margin-bottom: 10px;
}
.meta {
    color: #666;
    font-size: 14px;
    margin-bottom: 30px;
    display: flex;
    gap: 20px;
    flex-wrap: wrap;
}
.meta span {
    background: #f0f0f0;
    padding: 5px 12px;
    border-radius: 4px;
}
nav {
    background: #333;
    color: white;
    padding: 10px 15px;
    border-radius: 5px;
    margin-bottom: 20px;
    position: sticky;
    top: 0;
    z-index: 100;
}
nav span {
    font-weight: bold;
    margin-right: 10px;
}
nav a {
    color: #ddd;
    text-decoration: none;
    margin: 0 3px;
    padding: 3px 8px;
    border-radius: 3px;
    font-size: 12px;
}
nav a:hover { background: #555; color: white; }
.page-section {
    margin-bottom: 40px;
    padding-bottom: 30px;
    border-bottom: 2px dashed #e0e0e0;
}
.page-section:last-child { border-bottom: none; }
.page-header {
    background: linear-gradient(135deg, #4CAF50, #45a049);
    color: white;
    padding: 10px 20px;
    border-radius: 5px;
    margin-bottom: 15px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.page-header h2 { margin: 0; font-size: 18px; }
.page-header .badge {
    background: rgba(255,255,255,0.2);
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
}
.table-container {
    overflow-x: auto;
    margin: 15px 0;
    border: 1px solid #e0e0e0;
    border-radius: 5px;
}
table {
    border-collapse: collapse;
    width: 100%;
    background: white;
}
td, th {
    border: 1px solid #ddd;
    padding: 8px 12px;
    text-align: left;
    vertical-align: middle;
    font-size: 13px;
}
th { background-color: #f5f5f5; font-weight: bold; }
tr:nth-child(even) { background-color: #fafafa; }
tr:hover { background-color: #f0f7f0; }
.image-container {
    margin: 20px 0;
    padding: 15px;
    background: #f9f9f9;
    border-radius: 5px;
    border-left: 4px solid #4CAF50;
}
.image-container h4 {
    margin: 0 0 10px 0;
    color: #333;
}
.image-container img {
    max-width: 100%;
    border: 1px solid #ddd;
    border-radius: 3px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
}
.confidence-high { color: #4CAF50; }
.confidence-medium { color: #FF9800; }
.confidence-low { color: #f44336; }
.footer {
    margin-top: 30px;
    padding-top: 20px;
    border-top: 1px solid #ddd;
    text-align: center;
    color: #999;
    font-size: 12px;
}
@media print {
    nav { display: none; }
    .page-section { page-break-after: always; }
    .page-section:last-child { page-break-after: auto; }
}
"""


class PDFToHTMLConverter:
    """PDF to HTML 统一转换器"""

    def __init__(self, backend: BackendType = BackendType.AUTO):
        """
        初始化转换器

        Args:
            backend: 后端类型 (AUTO, MINERU, PDFPLUMBER)
        """
        self.backend = backend
        self._mineru_available = self._check_mineru_available()
        self._pdfplumber_available = self._check_pdfplumber_available()

    def _check_mineru_available(self) -> bool:
        """检查 MinerU 是否可用"""
        try:
            from mineru.cli.common import do_parse
            return True
        except ImportError:
            return False

    def _check_pdfplumber_available(self) -> bool:
        """检查 pdfplumber 是否可用"""
        try:
            import pdfplumber
            return True
        except ImportError:
            return False

    def _select_backend(self, pdf_path: str) -> BackendType:
        """
        自动选择最佳后端

        策略：
        1. 如果指定了具体后端，使用指定的
        2. 如果有表格，优先使用 MinerU
        3. 否则使用 pdfplumber

        Args:
            pdf_path: PDF 文件路径

        Returns:
            选择的后端类型
        """
        if self.backend != BackendType.AUTO:
            return self.backend

        # 检查是否有表格（快速检测）
        has_tables = self._quick_detect_tables(pdf_path)

        if has_tables and self._mineru_available:
            return BackendType.MINERU
        elif self._pdfplumber_available:
            return BackendType.PDFPLUMBER
        elif self._mineru_available:
            return BackendType.MINERU
        else:
            raise RuntimeError("没有可用的 PDF 解析后端，请安装 mineru 或 pdfplumber")

    def _quick_detect_tables(self, pdf_path: str, sample_pages: int = 5) -> bool:
        """
        快速检测 PDF 是否包含表格

        Args:
            pdf_path: PDF 文件路径
            sample_pages: 检测的样本页数

        Returns:
            是否包含表格
        """
        if not self._pdfplumber_available:
            return True  # 无法检测，假设有表格

        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages_to_check = min(sample_pages, len(pdf.pages))
                for i in range(pages_to_check):
                    tables = pdf.pages[i].find_tables()
                    if tables:
                        return True
            return False
        except Exception:
            return True  # 检测失败，假设有表格

    def convert(self, pdf_path: str, output_dir: Optional[str] = None) -> ParseResult:
        """
        转换 PDF 为 HTML

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录，默认为 PDF 同目录

        Returns:
            解析结果
        """
        import time
        start_time = time.time()

        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return ParseResult(
                pdf_name=pdf_path.name,
                total_pages=0,
                tables=[],
                backend_used="none",
                parse_time=0,
                success=False,
                error_message=f"文件不存在: {pdf_path}"
            )

        # 选择后端
        try:
            selected_backend = self._select_backend(str(pdf_path))
        except RuntimeError as e:
            return ParseResult(
                pdf_name=pdf_path.name,
                total_pages=0,
                tables=[],
                backend_used="none",
                parse_time=0,
                success=False,
                error_message=str(e)
            )

        # 根据后端解析
        if selected_backend == BackendType.MINERU:
            result = self._parse_with_mineru(pdf_path)
        else:
            result = self._parse_with_pdfplumber(pdf_path)

        result.backend_used = selected_backend.value
        result.parse_time = time.time() - start_time

        # 生成 HTML
        if result.success:
            output_path = self._generate_html(result, output_dir)
            result.output_path = output_path

        return result

    def _parse_with_mineru(self, pdf_path: Path) -> ParseResult:
        """使用 MinerU 解析 PDF"""
        try:
            from mineru.cli.common import do_parse

            pdf_name = pdf_path.stem
            temp_dir = tempfile.mkdtemp(prefix="mineru_output_")

            try:
                output_dir = os.path.join(temp_dir, "output")

                # 读取 PDF
                with open(pdf_path, 'rb') as f:
                    pdf_bytes = f.read()

                # 执行解析
                do_parse(
                    output_dir=output_dir,
                    pdf_file_names=[pdf_path.name],
                    pdf_bytes_list=[pdf_bytes],
                    p_lang_list=["ch"],
                    backend="vlm-auto-engine",
                    parse_method="auto",
                    formula_enable=False,
                    table_enable=True,
                    f_draw_layout_bbox=False,
                    f_draw_span_bbox=False,
                    f_dump_md=True,
                    f_dump_middle_json=True,
                    f_dump_model_output=False,
                    f_dump_orig_pdf=False,
                    f_dump_content_list=True,
                )

                # 提取表格数据
                tables = self._extract_mineru_tables(output_dir, pdf_path.name)

                # 计算总页数
                total_pages = max(t.page_number for t in tables) + 1 if tables else 0

                return ParseResult(
                    pdf_name=pdf_name,
                    total_pages=total_pages,
                    tables=tables,
                    backend_used="mineru",
                    parse_time=0,
                    success=True
                )

            finally:
                # 清理临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)

        except Exception as e:
            return ParseResult(
                pdf_name=pdf_path.stem,
                total_pages=0,
                tables=[],
                backend_used="mineru",
                parse_time=0,
                success=False,
                error_message=f"MinerU 解析失败: {str(e)}"
            )

    def _extract_mineru_tables(self, output_dir: str, pdf_filename: str) -> List[TableData]:
        """从 MinerU 输出中提取表格"""
        tables = []

        # 查找 content_list.json
        content_list_path = None
        for root, _, files in os.walk(output_dir):
            for f in files:
                if f == "content_list.json" or f.endswith("_content_list.json"):
                    content_list_path = os.path.join(root, f)
                    break

        if not content_list_path or not os.path.exists(content_list_path):
            return tables

        try:
            with open(content_list_path, 'r', encoding='utf-8') as f:
                content_list = json.load(f)

            table_idx = 0
            for item in content_list:
                if item.get("type") != "table":
                    continue

                page_idx = item.get("page_idx", 0)
                html_content = item.get("table_body", "") or item.get("html", "") or item.get("text", "")

                if not html_content or "<table" not in str(html_content).lower():
                    continue

                # 解析 HTML 表格
                rows = self._parse_html_table(str(html_content))
                if not rows:
                    continue

                # 检测合并单元格
                has_merged = self._detect_merged_cells(str(html_content))

                table = TableData(
                    page_number=page_idx,
                    table_index=table_idx,
                    rows=rows,
                    bbox=tuple(item.get("bbox", (0, 0, 0, 0))),
                    has_merged_cells=has_merged,
                    confidence=0.95,
                    extraction_method="mineru",
                    html_content=str(html_content),
                    img_path=item.get("img_path", ""),
                    caption=item.get("table_caption", [])
                )
                tables.append(table)
                table_idx += 1

        except Exception as e:
            print(f"解析 MinerU 输出失败: {e}")

        return tables

    def _parse_with_pdfplumber(self, pdf_path: Path) -> ParseResult:
        """使用 pdfplumber 解析 PDF"""
        try:
            import pdfplumber

            pdf_name = pdf_path.stem
            tables = []

            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                for page_num, page in enumerate(pdf.pages):
                    page_tables = page.find_tables()

                    for table_idx, table in enumerate(page_tables):
                        table_data = table.extract()
                        if not table_data:
                            continue

                        # 检测合并单元格
                        has_merged = self._detect_merged_cells_pdfplumber(table_data)

                        # 生成 HTML
                        html_content = self._rows_to_html(table_data)

                        table = TableData(
                            page_number=page_num,
                            table_index=len(tables),
                            rows=table_data,
                            bbox=table.bbox,
                            has_merged_cells=has_merged,
                            confidence=0.85,
                            extraction_method="pdfplumber",
                            html_content=html_content
                        )
                        tables.append(table)

            return ParseResult(
                pdf_name=pdf_name,
                total_pages=total_pages,
                tables=tables,
                backend_used="pdfplumber",
                parse_time=0,
                success=True
            )

        except Exception as e:
            return ParseResult(
                pdf_name=pdf_path.stem,
                total_pages=0,
                tables=[],
                backend_used="pdfplumber",
                parse_time=0,
                success=False,
                error_message=f"pdfplumber 解析失败: {str(e)}"
            )

    def _parse_html_table(self, html: str) -> List[List[str]]:
        """
        解析 HTML 表格为二维数组，正确处理 colspan 和 rowspan

        Args:
            html: HTML 表格内容

        Returns:
            二维数组
        """
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')

            if not table:
                return []

            tr_list = table.find_all('tr')
            if not tr_list:
                return []

            # 计算最大列数
            max_cols = 0
            for tr in tr_list:
                col_count = 0
                for cell in tr.find_all(['td', 'th']):
                    colspan = int(cell.get('colspan', 1))
                    col_count += colspan
                max_cols = max(max_cols, col_count)

            if max_cols == 0:
                return []

            # 使用占用矩阵处理合并单元格
            num_rows = len(tr_list)
            occupied = [[False] * max_cols for _ in range(num_rows)]
            result = [[''] * max_cols for _ in range(num_rows)]

            for row_idx, tr in enumerate(tr_list):
                col_idx = 0
                cells = tr.find_all(['td', 'th'])

                for cell in cells:
                    while col_idx < max_cols and occupied[row_idx][col_idx]:
                        col_idx += 1

                    if col_idx >= max_cols:
                        break

                    colspan = int(cell.get('colspan', 1))
                    rowspan = int(cell.get('rowspan', 1))
                    text = cell.get_text(strip=True)

                    for r in range(row_idx, min(row_idx + rowspan, num_rows)):
                        for c in range(col_idx, min(col_idx + colspan, max_cols)):
                            result[r][c] = text
                            if r != row_idx or c != col_idx:
                                occupied[r][c] = True

                    if rowspan > 1:
                        for r in range(row_idx + 1, min(row_idx + rowspan, num_rows)):
                            for c in range(col_idx, min(col_idx + colspan, max_cols)):
                                occupied[r][c] = True

                    col_idx += colspan

            return result

        except ImportError:
            return self._parse_html_simple(html)
        except Exception:
            return self._parse_html_simple(html)

    def _parse_html_simple(self, html: str) -> List[List[str]]:
        """简单的 HTML 表格解析（不依赖 BeautifulSoup）"""
        import re

        rows = []
        tr_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
        cell_pattern = re.compile(r'<t[dh][^>]*>(.*?)</t[dh]>', re.DOTALL | re.IGNORECASE)
        clean_pattern = re.compile(r'<[^>]+>')

        for tr_match in tr_pattern.finditer(html):
            tr_content = tr_match.group(1)
            cells = []
            for cell_match in cell_pattern.finditer(tr_content):
                cell_content = cell_match.group(1)
                clean_text = clean_pattern.sub('', cell_content).strip()
                cells.append(clean_text)
            if cells:
                rows.append(cells)

        return rows

    def _detect_merged_cells(self, html: str) -> bool:
        """从 HTML 检测合并单元格"""
        import re
        return bool(re.search(r'colspan\s*=\s*["\']?\d', html, re.IGNORECASE)) or \
               bool(re.search(r'rowspan\s*=\s*["\']?\d', html, re.IGNORECASE))

    def _detect_merged_cells_pdfplumber(self, table_data: List[List[str]]) -> bool:
        """从 pdfplumber 表格数据检测合并单元格"""
        if not table_data:
            return False

        none_count = sum(1 for row in table_data for cell in row if cell is None)
        total_cells = sum(len(row) for row in table_data)

        return (none_count / total_cells) > 0.05 if total_cells > 0 else False

    def _rows_to_html(self, rows: List[List[str]]) -> str:
        """将行数据转换为 HTML 表格"""
        if not rows:
            return ""

        html_parts = ["<table>"]
        for i, row in enumerate(rows):
            tag = "th" if i == 0 else "td"
            cells = [f"<{tag}>{cell if cell else ''}</{tag}>" for cell in row]
            html_parts.append(f"<tr>{''.join(cells)}</tr>")
        html_parts.append("</table>")

        return "".join(html_parts)

    def _generate_html(self, result: ParseResult, output_dir: Optional[str] = None) -> str:
        """
        生成完整的 HTML 报告

        Args:
            result: 解析结果
            output_dir: 输出目录

        Returns:
            输出文件路径
        """
        if output_dir is None:
            output_dir = str(Path(result.pdf_name).parent) if '/' in result.pdf_name else "."
        else:
            output_dir = str(output_dir)

        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{result.pdf_name}_parsed.html")

        # 按页面分组表格
        tables_by_page: Dict[int, List[TableData]] = {}
        for table in result.tables:
            if table.page_number not in tables_by_page:
                tables_by_page[table.page_number] = []
            tables_by_page[table.page_number].append(table)

        # 生成 HTML
        html_parts = [
            '<!DOCTYPE html>',
            '<html lang="zh-CN">',
            '<head>',
            '<meta charset="utf-8">',
            f'<title>{result.pdf_name} - PDF 解析报告</title>',
            '<style>',
            HTML_CSS,
            '</style>',
            '</head>',
            '<body>',
            '<div class="container">',
            f'<h1>{result.pdf_name}</h1>',
            '<div class="meta">',
            f'<span>总页数: {result.total_pages}</span>',
            f'<span>表格数: {len(result.tables)}</span>',
            f'<span>后端: {result.backend_used}</span>',
            f'<span>耗时: {result.parse_time:.2f}s</span>',
            f'<span>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M")}</span>',
            '</div>',
            '',
            # 导航栏
            '<nav>',
            '<span>快速跳转:</span>',
        ]

        # 添加页面导航链接
        for p in range(result.total_pages):
            html_parts.append(f'<a href="#page-{p + 1}">{p + 1}</a>')

        html_parts.extend([
            '</nav>',
            '',
        ])

        # 生成每页内容
        for page_idx in range(result.total_pages):
            page_num = page_idx + 1
            page_tables = tables_by_page.get(page_idx, [])

            html_parts.extend([
                f'<!-- 第{page_num}页 -->',
                f'<section id="page-{page_num}" class="page-section">',
                f'<div class="page-header">',
                f'<h2>第 {page_num} 页</h2>',
                f'<span class="badge">{len(page_tables)} 个表格</span>',
                f'</div>',
                '',
            ])

            # 添加表格
            for table in page_tables:
                # 添加标题
                if table.caption:
                    html_parts.append(f'<p class="caption">{" ".join(table.caption)}</p>')

                # 添加置信度标签
                confidence_class = "confidence-high" if table.confidence >= 0.9 else \
                                   "confidence-medium" if table.confidence >= 0.7 else "confidence-low"
                html_parts.append(
                    f'<p><small class="{confidence_class}">置信度: {table.confidence:.0%} | '
                    f'方法: {table.extraction_method}' +
                    (' | 包含合并单元格' if table.has_merged_cells else '') +
                    '</small></p>'
                )

                # 添加表格 HTML
                if table.html_content:
                    html_parts.extend([
                        '<div class="table-container">',
                        table.html_content if '<table' in table.html_content else f'<table>{table.html_content}</table>',
                        '</div>',
                        '',
                    ])

                # 添加图片
                if table.img_path:
                    html_parts.extend([
                        '<div class="image-container">',
                        '<h4>表格截图</h4>',
                        f'<img src="{table.img_path}" alt="表格截图">',
                        '</div>',
                        '',
                    ])

            html_parts.extend([
                '</section>',
                '',
            ])

        # 添加页脚
        html_parts.extend([
            '<div class="footer">',
            f'<p>由 {result.backend_used} 后端自动生成</p>',
            '<p>项目: 智能工艺文件辅助编辑系统</p>',
            '</div>',
            '',
            '</div>',  # container
            '</body>',
            '</html>'
        ])

        # 保存 HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_parts))

        return output_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='PDF to HTML 统一转换工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/pdf_to_html_unified.py test.pdf
    python scripts/pdf_to_html_unified.py test.pdf --output-dir ./output
    python scripts/pdf_to_html_unified.py test.pdf --backend mineru
    python scripts/pdf_to_html_unified.py test.pdf --backend pdfplumber
        """
    )

    parser.add_argument('pdf_path', help='PDF 文件路径')
    parser.add_argument('--output-dir', '-o', help='输出目录（默认为 PDF 同目录）')
    parser.add_argument('--backend', '-b',
                       choices=['auto', 'mineru', 'pdfplumber'],
                       default='auto',
                       help='解析后端 (默认: auto 自动选择)')

    args = parser.parse_args()

    print("=" * 60)
    print("PDF to HTML 统一转换工具")
    print("=" * 60)
    print(f"输入文件: {args.pdf_path}")
    print(f"输出目录: {args.output_dir or '同目录'}")
    print(f"后端选择: {args.backend}")
    print()

    # 创建转换器
    backend = BackendType(args.backend)
    converter = PDFToHTMLConverter(backend=backend)

    # 执行转换
    result = converter.convert(args.pdf_path, args.output_dir)

    # 输出结果
    if result.success:
        print(f"转换成功!")
        print(f"  后端使用: {result.backend_used}")
        print(f"  总页数: {result.total_pages}")
        print(f"  表格数: {len(result.tables)}")
        print(f"  耗时: {result.parse_time:.2f}s")

        # 计算表格识别准确率（基于置信度）
        if result.tables:
            avg_confidence = sum(t.confidence for t in result.tables) / len(result.tables)
            print(f"  平均置信度: {avg_confidence:.1%}")

            # 统计合并单元格
            merged_count = sum(1 for t in result.tables if t.has_merged_cells)
            if merged_count > 0:
                print(f"  包含合并单元格的表格: {merged_count}")

        print(f"\n输出文件: {getattr(result, 'output_path', 'N/A')}")
    else:
        print(f"转换失败: {result.error_message}")
        sys.exit(1)


if __name__ == "__main__":
    main()
