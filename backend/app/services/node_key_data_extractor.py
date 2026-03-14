"""
节点关键数据提取器
PR5: 为异步任务提供数据提取逻辑
"""
from typing import Dict, Any
from app.utils.logger import logger


class NodeKeyDataExtractor:
    """
    节点关键数据提取器
    
    为每个节点类型定义关键数据提取函数
    """
    
    @staticmethod
    def extract(node_type: str, node_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取关键数据（PR5）
        
        Args:
            node_type: 节点类型
            node_output: 节点输出数据
        
        Returns:
            结构化的关键数据
        """
        if node_type == "analysis":
            return NodeKeyDataExtractor._extract_analyze_key_data(node_output)
        elif node_type == "planning":
            return NodeKeyDataExtractor._extract_planner_key_data(node_output)
        # 其他节点类型后续补充
        return {}
    
    @staticmethod
    def _extract_analyze_key_data(node_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取 Analyze Node 的关键数据
        
        Args:
            node_output: 分析节点的输出数据
        
        Returns:
            结构化的关键数据
        """
        # 提取选择信息
        selections = {
            "has_plan_selection": bool(node_output.get("selected_plan_id")),
            "selected_plan_id": node_output.get("selected_plan_id"),
            "has_solution_selection": bool(node_output.get("selected_solutions")),
            "selected_solutions": node_output.get("selected_solutions", [])
        }
        
        # 提取改进方案（只保留关键字段，最多5个）
        solutions = []
        improvement_solutions = node_output.get("improvement_solutions", [])
        for sol in improvement_solutions[:5]:
            solutions.append({
                "id": sol.get("id"),
                "name": sol.get("name"),
                "title": sol.get("title"),
                "key_suggestions": sol.get("suggestions", [])[:3] if isinstance(sol.get("suggestions"), list) else []  # 只保留前3个
            })
        
        # 提取决策信息
        decision = node_output.get("decision", {})
        decision_data = {
            "action": decision.get("action") if isinstance(decision, dict) else None,
            "reason": (decision.get("reason", "")[:100] if isinstance(decision, dict) else ""),  # 截断
            "confidence": decision.get("confidence", 0.0) if isinstance(decision, dict) else 0.0
        }
        
        return {
            "selections": selections,
            "solutions": solutions,
            "decision": decision_data
        }
    
    @staticmethod
    def _extract_planner_key_data(node_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取 Planner Node 的关键数据
        
        Args:
            node_output: 规划节点的输出数据
        
        Returns:
            结构化的关键数据
        """
        plan_options = node_output.get("plan_options", [])
        
        # 提取计划选项（只保留关键字段，最多5个）
        options_list = []
        for opt in plan_options[:5]:
            options_list.append({
                "id": opt.get("id"),
                "title": opt.get("title"),
                "angle": opt.get("angle"),
                "estimated_words": opt.get("estimated_words")
            })
        
        # 提取选择信息
        selections = {
            "has_selection": bool(node_output.get("selected_plan_id")),
            "selected_plan_id": node_output.get("selected_plan_id")
        }
        
        return {
            "plan_options": options_list,
            "selections": selections
        }
