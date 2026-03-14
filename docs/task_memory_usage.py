"""
任务记忆系统 - 使用示例

演示如何使用Repository、ContextManager和ContextBuilder
"""
import asyncio
from app.repositories import get_repository, create_repository
from app.services.context_manager import ContextManager
from app.services.context_builder import ContextBuilder
from app.agents.orchestrator import ProcessOrchestrator


async def example_basic_usage():
    """基础使用示例"""
    print("=" * 60)
    print("示例1: 基础Repository使用")
    print("=" * 60)

    # 获取Repository实例
    repo = get_repository()

    # 创建任务
    task_id = repo.create_task(
        task_name="电缆装配编辑",
        task_type="craft_document_edit",
        source_docs=["全单电缆装配规程.pdf"],
        tags=["电缆", "装配"],
    )
    print(f"创建任务: {task_id}")

    # 添加用户消息
    msg_id = repo.add_message(
        task_id=task_id,
        role="user",
        content="帮我修改G5a表格中的剥线工具",
    )
    print(f"添加消息: {msg_id}")

    # 添加助手回复
    repo.add_message(
        task_id=task_id,
        role="assistant",
        content="好的，我找到了G5a表格。当前剥线工具是...",
    )

    # 添加决策记录
    dec_id = repo.add_decision(
        task_id=task_id,
        decision_type="tool_selection",
        context="用户要求修改剥线工具",
        options=["剥线钳", "热剥器", "激光剥线"],
        selected="剥线钳",
        reason="根据工艺规范G4a要求，推荐使用剥线钳",
        user_confirmed=True,
    )
    print(f"添加决策: {dec_id}")

    # 获取任务上下文
    context = repo.get_context(task_id)
    print(f"\n任务上下文:\n{context[:500]}...")

    # 列出所有任务
    tasks = repo.list_tasks()
    print(f"\n任务列表: {len(tasks)}个任务")
    for t in tasks[:3]:
        print(f"  - {t.task_id}: {t.task_name} ({t.status.value})")


async def example_context_manager():
    """文档上下文管理示例"""
    print("\n" + "=" * 60)
    print("示例2: 文档上下文管理")
    print("=" * 60)

    cm = ContextManager()

    # 获取已解析文档列表
    docs = cm.get_document_list()
    print(f"已解析文档: {len(docs)}个")
    for doc in docs[:3]:
        print(f"  - {doc.name}: {doc.table_count}个表格, {doc.page_count}页")

    if docs:
        doc_name = docs[0].name

        # 获取文档表格
        tables = cm.get_document_tables(doc_name)
        print(f"\n{doc_name}的表格:")
        for t in tables[:5]:
            print(f"  - 第{t.page}页: {t.caption or '(无标题)'}")

        # 按标题搜索
        matched = cm.search_by_caption(doc_name, "G4a")
        print(f"\n搜索'G4a'的结果: {len(matched)}个匹配")

        # 构建文档上下文
        context = cm.build_document_context([doc_name], include_html=False, max_tables=10)
        print(f"\n文档上下文长度: {len(context)}字符")


async def example_context_builder():
    """上下文构建器示例"""
    print("\n" + "=" * 60)
    print("示例3: 上下文构建器")
    print("=" * 60)

    repo = get_repository()
    builder = ContextBuilder(repository=repo)

    # 创建任务并添加一些数据
    task_id = repo.create_task(
        task_name="材料定额计算",
        source_docs=["全单电缆装配规程.pdf"],
    )

    repo.add_message(task_id=task_id, role="user", content="计算G10a表格的材料用量")
    repo.add_message(task_id=task_id, role="assistant", content="正在分析G10a表格...")

    repo.add_decision(
        task_id=task_id,
        decision_type="method_choice",
        context="材料计算方法选择",
        options=["按长度计算", "按重量计算"],
        selected="按长度计算",
        reason="电缆材料通常按长度计量",
    )

    # 构建完整上下文
    context = builder.build_context(
        task_id=task_id,
        include_documents=True,
        include_history=True,
        include_decisions=True,
    )

    print(f"构建的上下文长度: {len(context)}字符")
    print(f"Token估计: {builder.estimate_tokens(context)}")
    print(f"\n上下文预览:\n{context[:800]}...")


async def example_orchestrator():
    """Orchestrator使用示例"""
    print("\n" + "=" * 60)
    print("示例4: Orchestrator集成")
    print("=" * 60)

    from app.services.context_builder import ContextBuilder

    repo = get_repository()
    orchestrator = ProcessOrchestrator(
        repository=repo,
        context_builder=ContextBuilder(repo),
    )

    # 创建任务
    task_id = await orchestrator.create_task(
        task_name="工艺卡编辑",
        source_docs=["全单电缆装配规程.pdf"],
    )
    print(f"创建任务: {task_id}")

    # 处理用户意图（注意：子Agent还未实现，会返回pending状态）
    result = await orchestrator.process_intent(
        user_input="帮我检查G5a表格的合规性",
        task_id=task_id,
    )

    print(f"\n处理结果:")
    print(f"  - 成功: {result.get('success')}")
    print(f"  - 意图类型: {result.get('intent', {}).get('type')}")
    print(f"  - 任务数量: {len(result.get('tasks', []))}")
    print(f"  - 状态: {result.get('state')}")

    # 获取任务上下文
    context = await orchestrator.get_task_context()
    print(f"\n任务上下文长度: {len(context)}字符")

    # 列出任务
    tasks = await orchestrator.list_tasks()
    print(f"\n任务列表: {len(tasks)}个任务")


async def main():
    """运行所有示例"""
    print("\n" + "=" * 60)
    print("任务记忆系统 - 使用示例")
    print("=" * 60)

    try:
        await example_basic_usage()
        await example_context_manager()
        await example_context_builder()
        await example_orchestrator()

        print("\n" + "=" * 60)
        print("所有示例运行完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
