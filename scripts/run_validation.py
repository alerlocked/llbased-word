#!/usr/bin/env python3
"""
工艺文件辅助编辑系统 - 自动化验证脚本
执行端到端的自动化测试和准确性验证
"""
import asyncio
import json
import sys
import os
from pathlib import Path
from datetime import datetime
import argparse

# 添加项目路径到Python路径
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from app.agents.orchestrator.orchestrator import ProcessOrchestrator
from app.agents.sub_agents.pdf_parser_agent import PDFParserAgent
from app.agents.sub_agents.rag_agent import RAGAgent
from app.agents.sub_agents.terminology_agent import TerminologyAgent
from app.agents.sub_agents.compliance_agent import ComplianceAgent
from app.agents.sub_agents.document_agent import DocumentAgent

class ValidationRunner:
    """自动化验证运行器"""

    def __init__(self, config_file: str = "scripts/validation_config.json"):
        self.config_file = config_file
        self.config = self._load_config()
        self.results = []
        self.start_time = None
        self.end_time = None

    def _load_config(self) -> dict:
        """加载验证配置"""
        try:
            config_path = Path(self.config_file)
            if not config_path.exists():
                # 使用默认配置
                return self._get_default_config()

            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"警告: 无法加载配置文件 {self.config_file}: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "accuracy_thresholds": {
                "pdf_parsing": 0.97,
                "terminology_alignment": 0.95,
                "rag_retrieval": 0.95,
                "compliance_checking": 0.90,
                "document_generation": 0.95
            },
            "test_data_dir": "test_data",
            "output_dir": "validation_results",
            "enable_detailed_logging": True,
            "max_concurrent_tests": 5,
            "timeout_seconds": 300
        }

    async def run_all_validations(self):
        """运行所有验证测试"""
        self.start_time = datetime.now()
        print(f"开始自动化验证 - {self.start_time.isoformat()}")
        print("=" * 60)

        # 创建输出目录
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(exist_ok=True)

        # 运行各个组件的验证
        await self._run_pdf_parsing_validation()
        await self._run_terminology_alignment_validation()
        await self._run_rag_retrieval_validation()
        await self._run_compliance_checking_validation()
        await self._run_document_generation_validation()
        await self._run_end_to_end_workflow_validation()

        self.end_time = datetime.now()
        self._generate_final_report()

    async def _run_pdf_parsing_validation(self):
        """运行PDF解析验证"""
        print("\n🔍 验证PDF解析准确性 (目标: ≥97%)")

        test_files = [
            "cable_assembly.pdf",
            "mechanical_process.pdf"
        ]

        pdf_agent = PDFParserAgent(self.config)
        results = []

        for test_file in test_files:
            file_path = Path(self.config["test_data_dir"]) / test_file
            if not file_path.exists():
                print(f"  ⚠️  跳过不存在的测试文件: {test_file}")
                continue

            try:
                result = await pdf_agent.parse_pdf(str(file_path))
                if result["success"]:
                    accuracy = result["accuracy_metrics"]["overall_accuracy"]
                    results.append({
                        "file": test_file,
                        "accuracy": accuracy,
                        "passed": accuracy >= self.config["accuracy_thresholds"]["pdf_parsing"]
                    })
                    status = "✅" if results[-1]["passed"] else "❌"
                    print(f"  {status} {test_file}: {accuracy:.2%}")
                else:
                    results.append({
                        "file": test_file,
                        "accuracy": 0.0,
                        "passed": False,
                        "error": result.get("error", "Unknown error")
                    })
                    print(f"  ❌ {test_file}: 解析失败 - {result.get('error', 'Unknown')}")
            except Exception as e:
                results.append({
                    "file": test_file,
                    "accuracy": 0.0,
                    "passed": False,
                    "error": str(e)
                })
                print(f"  ❌ {test_file}: 异常 - {e}")

        self.results.append({
            "component": "PDF解析",
            "results": results,
            "threshold": self.config["accuracy_thresholds"]["pdf_parsing"],
            "passed": all(r["passed"] for r in results) if results else False
        })

    async def _run_terminology_alignment_validation(self):
        """运行术语对齐验证"""
        print("\n🔍 验证术语对齐准确性 (目标: ≥95%)")

        test_cases = [
            {"input": "车床加工外圆", "expected": "车削外圆"},
            {"input": "用螺栓固定零件", "expected": "螺栓连接"},
            {"input": "加热后快速冷却", "expected": "淬火"}
        ]

        terminology_agent = TerminologyAgent(self.config)
        results = []

        for test_case in test_cases:
            try:
                result = await terminology_agent.align_terminology(test_case["input"])
                if result["success"]:
                    aligned_text = result["aligned_text"]
                    # 简单的准确性检查（实际应用中需要更复杂的NLP评估）
                    accuracy = 1.0 if test_case["expected"] in aligned_text else 0.0
                    results.append({
                        "input": test_case["input"],
                        "expected": test_case["expected"],
                        "actual": aligned_text,
                        "accuracy": accuracy,
                        "passed": accuracy >= self.config["accuracy_thresholds"]["terminology_alignment"]
                    })
                    status = "✅" if results[-1]["passed"] else "❌"
                    print(f"  {status} '{test_case['input']}' -> '{aligned_text}'")
                else:
                    results.append({
                        "input": test_case["input"],
                        "expected": test_case["expected"],
                        "actual": "",
                        "accuracy": 0.0,
                        "passed": False,
                        "error": result.get("error", "Unknown error")
                    })
                    print(f"  ❌ '{test_case['input']}': 对齐失败 - {result.get('error', 'Unknown')}")
            except Exception as e:
                results.append({
                    "input": test_case["input"],
                    "expected": test_case["expected"],
                    "actual": "",
                    "accuracy": 0.0,
                    "passed": False,
                    "error": str(e)
                })
                print(f"  ❌ '{test_case['input']}': 异常 - {e}")

        self.results.append({
            "component": "术语对齐",
            "results": results,
            "threshold": self.config["accuracy_thresholds"]["terminology_alignment"],
            "passed": all(r["passed"] for r in results) if results else False
        })

    async def _run_rag_retrieval_validation(self):
        """运行RAG检索验证"""
        print("\n🔍 验证RAG检索准确性 (目标: ≥95%)")

        test_queries = [
            "数控车削参数",
            "不锈钢焊接标准",
            "热处理工艺规范"
        ]

        rag_agent = RAGAgent(self.config)
        results = []

        for query in test_queries:
            try:
                result = await rag_agent.retrieve_knowledge(query)
                if result["success"]:
                    # 检索结果的相关性评估（简化版）
                    relevance_score = len(result["results"]) > 0
                    results.append({
                        "query": query,
                        "relevance_score": float(relevance_score),
                        "result_count": len(result["results"]),
                        "passed": relevance_score >= self.config["accuracy_thresholds"]["rag_retrieval"]
                    })
                    status = "✅" if results[-1]["passed"] else "❌"
                    print(f"  {status} '{query}': {len(result['results'])} 个结果")
                else:
                    results.append({
                        "query": query,
                        "relevance_score": 0.0,
                        "result_count": 0,
                        "passed": False,
                        "error": result.get("error", "Unknown error")
                    })
                    print(f"  ❌ '{query}': 检索失败 - {result.get('error', 'Unknown')}")
            except Exception as e:
                results.append({
                    "query": query,
                    "relevance_score": 0.0,
                    "result_count": 0,
                    "passed": False,
                    "error": str(e)
                })
                print(f"  ❌ '{query}': 异常 - {e}")

        self.results.append({
            "component": "RAG检索",
            "results": results,
            "threshold": self.config["accuracy_thresholds"]["rag_retrieval"],
            "passed": all(r["passed"] for r in results) if results else False
        })

    async def _run_compliance_checking_validation(self):
        """运行合规检查验证"""
        print("\n🔍 验证合规检查准确性 (目标: ≥90%)")

        test_documents = [
            {
                "id": "valid_doc",
                "name": "有效工艺文件",
                "operations": [{"id": "op1", "name": "工序1", "description": "描述", "sequence": 1}],
                "expected_compliance": True
            },
            {
                "id": "invalid_doc",
                "name": "无效工艺文件",
                "operations": [],
                "expected_compliance": False
            }
        ]

        compliance_agent = ComplianceAgent(self.config)
        results = []

        for doc in test_documents:
            try:
                result = await compliance_agent.check_compliance(doc)
                if result["success"]:
                    is_compliant = result["compliance_status"] == "compliant"
                    expected_compliant = doc["expected_compliance"]
                    accuracy = 1.0 if is_compliant == expected_compliant else 0.0
                    results.append({
                        "document_id": doc["id"],
                        "expected_compliant": expected_compliant,
                        "actual_compliant": is_compliant,
                        "accuracy": accuracy,
                        "passed": accuracy >= self.config["accuracy_thresholds"]["compliance_checking"]
                    })
                    status = "✅" if results[-1]["passed"] else "❌"
                    print(f"  {status} {doc['id']}: {'合规' if is_compliant else '不合规'}")
                else:
                    results.append({
                        "document_id": doc["id"],
                        "expected_compliant": doc["expected_compliance"],
                        "actual_compliant": False,
                        "accuracy": 0.0,
                        "passed": False,
                        "error": result.get("error", "Unknown error")
                    })
                    print(f"  ❌ {doc['id']}: 检查失败 - {result.get('error', 'Unknown')}")
            except Exception as e:
                results.append({
                    "document_id": doc["id"],
                    "expected_compliant": doc["expected_compliance"],
                    "actual_compliant": False,
                    "accuracy": 0.0,
                    "passed": False,
                    "error": str(e)
                })
                print(f"  ❌ {doc['id']}: 异常 - {e}")

        self.results.append({
            "component": "合规检查",
            "results": results,
            "threshold": self.config["accuracy_thresholds"]["compliance_checking"],
            "passed": all(r["passed"] for r in results) if results else False
        })

    async def _run_document_generation_validation(self):
        """运行文档生成验证"""
        print("\n🔍 验证文档生成准确性 (目标: ≥95%)")

        test_content = {
            "id": "test_doc",
            "name": "测试工艺文件",
            "operations": [{"id": "op1", "name": "测试工序", "description": "测试描述", "sequence": 1}]
        }

        document_agent = DocumentAgent(self.config)
        results = []

        try:
            result = await document_agent.generate_document(test_content, formats=["json"])
            if result["success"]:
                # 验证生成的文档完整性
                generated_files = result["generated_files"]
                completeness_score = 1.0 if len(generated_files) > 0 else 0.0
                results.append({
                    "content_id": test_content["id"],
                    "completeness_score": completeness_score,
                    "file_count": len(generated_files),
                    "passed": completeness_score >= self.config["accuracy_thresholds"]["document_generation"]
                })
                status = "✅" if results[-1]["passed"] else "❌"
                print(f"  {status} {test_content['id']}: {len(generated_files)} 个文件")
            else:
                results.append({
                    "content_id": test_content["id"],
                    "completeness_score": 0.0,
                    "file_count": 0,
                    "passed": False,
                    "error": result.get("error", "Unknown error")
                })
                print(f"  ❌ {test_content['id']}: 生成失败 - {result.get('error', 'Unknown')}")
        except Exception as e:
            results.append({
                "content_id": test_content["id"],
                "completeness_score": 0.0,
                "file_count": 0,
                "passed": False,
                "error": str(e)
            })
            print(f"  ❌ {test_content['id']}: 异常 - {e}")

        self.results.append({
            "component": "文档生成",
            "results": results,
            "threshold": self.config["accuracy_thresholds"]["document_generation"],
            "passed": all(r["passed"] for r in results) if results else False
        })

    async def _run_end_to_end_workflow_validation(self):
        """运行端到端工作流验证"""
        print("\n🔍 验证端到端工作流")

        orchestrator = ProcessOrchestrator(self.config)
        results = []

        test_scenarios = [
            "为零件A创建车削工艺",
            "修改工序3的切削参数",
            "审核工艺文件P-2024-001"
        ]

        for scenario in test_scenarios:
            try:
                result = await orchestrator.process_intent(scenario)
                success = result["success"]
                results.append({
                    "scenario": scenario,
                    "success": success,
                    "passed": success
                })
                status = "✅" if success else "❌"
                print(f"  {status} '{scenario}'")
            except Exception as e:
                results.append({
                    "scenario": scenario,
                    "success": False,
                    "passed": False,
                    "error": str(e)
                })
                print(f"  ❌ '{scenario}': 异常 - {e}")

        self.results.append({
            "component": "端到端工作流",
            "results": results,
            "threshold": 1.0,  # 工作流必须100%成功
            "passed": all(r["passed"] for r in results) if results else False
        })

    def _generate_final_report(self):
        """生成最终验证报告"""
        total_components = len(self.results)
        passed_components = sum(1 for r in self.results if r["passed"])
        overall_success = passed_components == total_components

        report = {
            "validation_run": {
                "start_time": self.start_time.isoformat(),
                "end_time": self.end_time.isoformat(),
                "duration_seconds": (self.end_time - self.start_time).total_seconds()
            },
            "summary": {
                "total_components": total_components,
                "passed_components": passed_components,
                "failed_components": total_components - passed_components,
                "overall_success": overall_success
            },
            "component_results": self.results
        }

        # 保存详细报告
        report_file = Path(self.config["output_dir"]) / f"validation_report_{self.start_time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        # 打印总结
        print("\n" + "=" * 60)
        print("自动化验证完成!")
        print(f"总耗时: {(self.end_time - self.start_time).total_seconds():.2f} 秒")
        print(f"通过组件: {passed_components}/{total_components}")
        print(f"整体结果: {'✅ 通过' if overall_success else '❌ 失败'}")
        print(f"详细报告: {report_file}")

        if not overall_success:
            print("\n失败的组件:")
            for result in self.results:
                if not result["passed"]:
                    print(f"  - {result['component']}")

        # 设置退出码
        sys.exit(0 if overall_success else 1)

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="工艺文件辅助编辑系统自动化验证")
    parser.add_argument("--config", default="scripts/validation_config.json", help="验证配置文件路径")
    parser.add_argument("--test-data", default="test_data", help="测试数据目录")
    parser.add_argument("--output", default="validation_results", help="输出目录")

    args = parser.parse_args()

    # 更新配置
    config = {
        "test_data_dir": args.test_data,
        "output_dir": args.output
    }

    runner = ValidationRunner(args.config)
    # 合并配置
    runner.config.update(config)

    await runner.run_all_validations()

if __name__ == "__main__":
    asyncio.run(main())