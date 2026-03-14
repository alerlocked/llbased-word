"""
Unit tests for info_requirements module

Tests the information requirements templates and task type detection.
"""
import pytest
from app.agents.orchestrator.info_requirements import (
    InfoItem,
    InfoPriority,
    InputType,
    TaskInfoRequirements,
    get_info_requirements,
    get_all_task_types,
    detect_task_type,
    register_info_requirements,
    INFO_REQUIREMENTS,
)


class TestInfoItem:
    """Tests for InfoItem dataclass"""

    def test_info_item_creation(self):
        """Test creating an InfoItem with all fields"""
        item = InfoItem(
            name="screw_spec",
            description="螺钉规格",
            example="M8",
            impact="规格决定螺纹参数",
            priority=InfoPriority.HIGH,
            input_type=InputType.TEXT,
            aliases=["螺钉规格", "螺丝规格"]
        )

        assert item.name == "screw_spec"
        assert item.description == "螺钉规格"
        assert item.example == "M8"
        assert item.priority == InfoPriority.HIGH
        assert len(item.aliases) == 2

    def test_info_item_default_aliases(self):
        """Test that aliases defaults to empty list"""
        item = InfoItem(
            name="test",
            description="Test item"
        )

        assert item.aliases == []

    def test_info_item_matches_exact_name(self):
        """Test matching against exact name"""
        item = InfoItem(
            name="screw_spec",
            description="螺钉规格",
            aliases=["螺钉规格"]
        )

        assert item.matches("screw_spec") is True
        assert item.matches("SCREW_SPEC") is True  # Case insensitive

    def test_info_item_matches_alias(self):
        """Test matching against aliases"""
        item = InfoItem(
            name="screw_spec",
            description="螺钉规格",
            aliases=["螺钉规格", "螺丝规格"]
        )

        assert item.matches("螺钉规格") is True
        assert item.matches("螺丝规格") is True
        assert item.matches("螺栓规格") is False

    def test_info_item_matches_case_insensitive(self):
        """Test case-insensitive matching"""
        item = InfoItem(
            name="Material",
            description="材料",
            aliases=["MATERIAL"]
        )

        assert item.matches("material") is True
        assert item.matches("MATERIAL") is True
        assert item.matches("Material") is True


class TestTaskInfoRequirements:
    """Tests for TaskInfoRequirements dataclass"""

    def test_task_requirements_creation(self):
        """Test creating TaskInfoRequirements"""
        req = TaskInfoRequirements(
            task_type="test_task",
            description="Test task description",
            required=[
                InfoItem(name="req1", description="Required 1")
            ],
            optional=[
                InfoItem(name="opt1", description="Optional 1")
            ],
            keywords=["test", "task"]
        )

        assert req.task_type == "test_task"
        assert len(req.required) == 1
        assert len(req.optional) == 1
        assert len(req.keywords) == 2

    def test_task_requirements_default_keywords(self):
        """Test that keywords defaults to empty list"""
        req = TaskInfoRequirements(
            task_type="test",
            description="Test",
            required=[],
            optional=[]
        )

        assert req.keywords == []


class TestGetInfoRequirements:
    """Tests for get_info_requirements function"""

    def test_get_existing_requirements(self):
        """Test getting requirements for existing task type"""
        req = get_info_requirements("calculate_torque")

        assert req is not None
        assert req.task_type == "calculate_torque"
        assert len(req.required) == 3  # screw_spec, material, strength_grade
        assert len(req.optional) == 2  # connected_material, lubrication

    def test_get_nonexistent_requirements(self):
        """Test getting requirements for non-existent task type"""
        req = get_info_requirements("nonexistent_task")

        assert req is None

    def test_get_all_defined_requirements(self):
        """Test that all predefined task types have requirements"""
        expected_types = [
            "calculate_torque",
            "edit_document",
            "create_document",
            "search_knowledge",
            "proofread",
            "review"
        ]

        for task_type in expected_types:
            req = get_info_requirements(task_type)
            assert req is not None, f"Missing requirements for {task_type}"
            assert len(req.required) > 0, f"No required items for {task_type}"


class TestGetAllTaskTypes:
    """Tests for get_all_task_types function"""

    def test_returns_list_of_task_types(self):
        """Test that function returns a list"""
        task_types = get_all_task_types()

        assert isinstance(task_types, list)
        assert len(task_types) >= 6  # At least 6 predefined types

    def test_contains_expected_types(self):
        """Test that expected task types are present"""
        task_types = get_all_task_types()

        assert "calculate_torque" in task_types
        assert "edit_document" in task_types
        assert "create_document" in task_types
        assert "proofread" in task_types
        assert "review" in task_types


class TestDetectTaskType:
    """Tests for detect_task_type function"""

    def test_detect_calculate_torque(self):
        """Test detecting torque calculation task"""
        result = detect_task_type("帮我计算M8螺钉的拧紧力矩")
        assert result == "calculate_torque"

    def test_detect_calculate_torque_with_bolt(self):
        """Test detecting torque calculation with bolt keyword"""
        result = detect_task_type("螺栓预紧力计算")
        assert result == "calculate_torque"

    def test_detect_edit_document(self):
        """Test detecting document edit task"""
        result = detect_task_type("修改工序3的参数")
        assert result == "edit_document"

    def test_detect_create_document(self):
        """Test detecting document creation task"""
        result = detect_task_type("创建新的工艺文件")
        assert result == "create_document"

    def test_detect_search_knowledge(self):
        """Test detecting knowledge search task"""
        result = detect_task_type("查找数控车削参数")
        assert result == "search_knowledge"

    def test_detect_proofread(self):
        """Test detecting proofread task"""
        result = detect_task_type("校对这个文档的术语")
        assert result == "proofread"

    def test_detect_review(self):
        """Test detecting review task"""
        result = detect_task_type("审查这个工艺的合规性")
        assert result == "review"

    def test_detect_no_match(self):
        """Test when no task type matches"""
        result = detect_task_type("今天天气怎么样")
        assert result is None

    def test_detect_case_insensitive(self):
        """Test case-insensitive detection"""
        result = detect_task_type("编辑工艺文件")
        assert result == "edit_document"

    def test_detect_multiple_keywords(self):
        """Test detection with multiple matching keywords"""
        # "工艺文件" matches both create_document and edit_document
        # Should return the one with more keyword matches
        result = detect_task_type("创建工艺文件")
        assert result == "create_document"


class TestRegisterInfoRequirements:
    """Tests for register_info_requirements function"""

    def test_register_new_requirements(self):
        """Test registering a new task type"""
        new_req = TaskInfoRequirements(
            task_type="custom_task",
            description="Custom task",
            required=[
                InfoItem(name="custom_field", description="Custom field")
            ],
            optional=[],
            keywords=["custom"]
        )

        register_info_requirements("custom_task", new_req)

        # Verify it was registered
        retrieved = get_info_requirements("custom_task")
        assert retrieved is not None
        assert retrieved.task_type == "custom_task"

        # Cleanup
        del INFO_REQUIREMENTS["custom_task"]

    def test_register_overwrites_existing(self):
        """Test that registering overwrites existing requirements"""
        original = get_info_requirements("calculate_torque")
        original_required_count = len(original.required)

        modified = TaskInfoRequirements(
            task_type="calculate_torque",
            description="Modified",
            required=[InfoItem(name="only_one", description="One")],
            optional=[],
            keywords=[]
        )

        register_info_requirements("calculate_torque", modified)

        retrieved = get_info_requirements("calculate_torque")
        assert len(retrieved.required) == 1

        # Restore original
        register_info_requirements("calculate_torque", original)


class TestPredefinedRequirements:
    """Tests for predefined INFO_REQUIREMENTS"""

    def test_calculate_torque_requirements(self):
        """Test calculate_torque has correct requirements"""
        req = get_info_requirements("calculate_torque")

        required_names = [item.name for item in req.required]
        assert "screw_spec" in required_names
        assert "material" in required_names
        assert "strength_grade" in required_names

        # Check priorities
        for item in req.required:
            assert item.priority == InfoPriority.HIGH

    def test_edit_document_requirements(self):
        """Test edit_document has correct requirements"""
        req = get_info_requirements("edit_document")

        required_names = [item.name for item in req.required]
        assert "target_section" in required_names
        assert "edit_content" in required_names

    def test_create_document_requirements(self):
        """Test create_document has correct requirements"""
        req = get_info_requirements("create_document")

        required_names = [item.name for item in req.required]
        assert "document_type" in required_names
        assert "part_info" in required_names

    def test_proofread_requirements(self):
        """Test proofread has correct requirements"""
        req = get_info_requirements("proofread")

        required_names = [item.name for item in req.required]
        assert "content" in required_names

    def test_review_requirements(self):
        """Test review has correct requirements"""
        req = get_info_requirements("review")

        required_names = [item.name for item in req.required]
        assert "content" in required_names

    def test_all_required_items_have_high_priority(self):
        """Test that all required items have HIGH priority"""
        for task_type in get_all_task_types():
            req = get_info_requirements(task_type)
            for item in req.required:
                assert item.priority == InfoPriority.HIGH, \
                    f"Required item {item.name} in {task_type} should have HIGH priority"

    def test_optional_items_can_have_various_priorities(self):
        """Test that optional items can have different priorities"""
        req = get_info_requirements("calculate_torque")

        optional_priorities = [item.priority for item in req.optional]
        assert InfoPriority.MEDIUM in optional_priorities
        assert InfoPriority.LOW in optional_priorities
