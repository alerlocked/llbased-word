"""
Tests for Tools

Validates:
1. RAGRetriever tool
2. TerminologyTool
3. ComplianceTool
4. DocumentTool
"""
import pytest

from app.agents.core import ToolRegistry


class TestRAGRetriever:
    """Tests for RAGRetriever tool"""

    def setup_method(self):
        """Clear registry before each test"""
        ToolRegistry.clear()

    def test_rag_retriever_registration(self):
        """Test RAGRetriever is properly registered"""
        from app.tools.rag_retriever import RAGRetriever

        assert "rag_retriever" in ToolRegistry.list_tools()

        tool_class = ToolRegistry.get("rag_retriever")
        assert tool_class == RAGRetriever

    def test_rag_retriever_creation(self):
        """Test RAGRetriever can be created"""
        from app.tools.rag_retriever import RAGRetriever

        tool = RAGRetriever(config={"top_k": 10})
        assert tool.top_k == 10
        assert tool.similarity_threshold == 0.7

    @pytest.mark.asyncio
    async def test_rag_retriever_execute_empty_query(self):
        """Test RAGRetriever with empty query"""
        from app.tools.rag_retriever import RAGRetriever

        tool = RAGRetriever(config={})

        result = await tool.execute("")
        assert result["success"] is False
        assert result["error_code"] == "INVALID_QUERY"

    @pytest.mark.asyncio
    async def test_rag_retriever_execute_invalid_query(self):
        """Test RAGRetriever with invalid query type"""
        from app.tools.rag_retriever import RAGRetriever

        tool = RAGRetriever(config={})

        result = await tool.execute(12345)  # Not a string
        assert result["success"] is False
        assert result["error_code"] == "INVALID_QUERY"

    @pytest.mark.asyncio
    async def test_rag_retriever_mock_search(self):
        """Test RAGRetriever mock search (when VectorStore unavailable)"""
        from app.tools.rag_retriever import RAGRetriever

        tool = RAGRetriever(config={})

        result = await tool.execute("test query")
        # Should return mock result since VectorStore is not available
        assert result["success"] is True
        assert "results" in result
        assert result["query"] == "test query"

    def test_rag_retriever_get_info(self):
        """Test getting tool info"""
        from app.tools.rag_retriever import RAGRetriever

        info = ToolRegistry.get_info("rag_retriever")
        assert info is not None
        assert info["name"] == "rag_retriever"
        assert "description" in info


class TestTerminologyTool:
    """Tests for TerminologyTool"""

    def setup_method(self):
        """Clear registry before each test"""
        ToolRegistry.clear()

    def test_terminology_tool_registration(self):
        """Test TerminologyTool is properly registered"""
        from app.tools.terminology_tool import TerminologyTool

        assert "terminology_mapper" in ToolRegistry.list_tools()

        tool_class = ToolRegistry.get("terminology_mapper")
        assert tool_class == TerminologyTool

    def test_terminology_tool_creation(self):
        """Test TerminologyTool can be created"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={"similarity_threshold": 0.9})
        assert tool.similarity_threshold == 0.9
        assert tool.max_suggestions == 3

    @pytest.mark.asyncio
    async def test_terminology_tool_execute_string_input(self):
        """Test TerminologyTool with string input"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={})

        result = await tool.execute("剥线和压接")
        # Should return mock result
        assert result["success"] is True
        assert "mappings" in result

    @pytest.mark.asyncio
    async def test_terminology_tool_execute_dict_input(self):
        """Test TerminologyTool with dict input"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={})

        result = await tool.execute({
            "content": "剥线和压接",
            "target_standard": "enterprise_standard"
        })
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_terminology_tool_empty_text(self):
        """Test TerminologyTool with empty text"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={})

        result = await tool.execute("")
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_TEXT"

    @pytest.mark.asyncio
    async def test_terminology_tool_invalid_input(self):
        """Test TerminologyTool with invalid input type"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={})

        result = await tool.execute(12345)
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_terminology_tool_mock_mapping(self):
        """Test TerminologyTool mock mapping"""
        from app.tools.terminology_tool import TerminologyTool

        tool = TerminologyTool(config={})

        result = await tool.execute("剥线后进行压接")
        assert result["success"] is True
        assert "剥线" in result["original_text"]
        # Mock should replace with standard terms
        assert len(result["mappings"]) > 0


class TestComplianceTool:
    """Tests for ComplianceTool"""

    def setup_method(self):
        """Clear registry before each test"""
        ToolRegistry.clear()

    def test_compliance_tool_registration(self):
        """Test ComplianceTool is properly registered"""
        from app.tools.compliance_tool import ComplianceTool

        assert "compliance_checker" in ToolRegistry.list_tools()

        tool_class = ToolRegistry.get("compliance_checker")
        assert tool_class == ComplianceTool

    def test_compliance_tool_creation(self):
        """Test ComplianceTool can be created"""
        from app.tools.compliance_tool import ComplianceTool

        tool = ComplianceTool(config={"strict_mode": True})
        assert tool.strict_mode is True
        assert tool.check_level == "detailed"

    @pytest.mark.asyncio
    async def test_compliance_tool_execute_dict_input(self):
        """Test ComplianceTool with dict input"""
        from app.tools.compliance_tool import ComplianceTool

        tool = ComplianceTool(config={})

        result = await tool.execute({
            "content": "标准工艺流程",
            "standards": ["enterprise", "safety"]
        })
        assert result["success"] is True
        assert "results" in result

    @pytest.mark.asyncio
    async def test_compliance_tool_execute_string_input(self):
        """Test ComplianceTool with string input"""
        from app.tools.compliance_tool import ComplianceTool

        tool = ComplianceTool(config={})

        result = await tool.execute("工艺流程内容")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_compliance_tool_empty_content(self):
        """Test ComplianceTool with empty content"""
        from app.tools.compliance_tool import ComplianceTool

        tool = ComplianceTool(config={})

        result = await tool.execute({"content": ""})
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONTENT"

    @pytest.mark.asyncio
    async def test_compliance_tool_safety_check(self):
        """Test ComplianceTool safety check"""
        from app.tools.compliance_tool import ComplianceTool

        tool = ComplianceTool(config={})

        result = await tool.execute({
            "content": "注意安全，危险区域",
            "standards": ["safety"]
        })
        assert result["success"] is True
        # Should have detected safety keywords
        assert "safety" in result["results"]


class TestDocumentTool:
    """Tests for DocumentTool"""

    def setup_method(self):
        """Clear registry before each test"""
        ToolRegistry.clear()

    def test_document_tool_registration(self):
        """Test DocumentTool is properly registered"""
        from app.tools.document_tool import DocumentTool

        assert "document_generator" in ToolRegistry.list_tools()

        tool_class = ToolRegistry.get("document_generator")
        assert tool_class == DocumentTool

    def test_document_tool_creation(self):
        """Test DocumentTool can be created"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={"output_formats": ["html", "pdf"]})
        assert tool.output_formats == ["html", "pdf"]
        assert tool.template_name == "standard_process_template"

    @pytest.mark.asyncio
    async def test_document_tool_execute_dict_input(self):
        """Test DocumentTool with dict input"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={})

        result = await tool.execute({
            "content": "工艺内容",
            "title": "测试文档",
            "format": "html"
        })
        # Should return mock result
        assert result["success"] is True
        assert "files" in result

    @pytest.mark.asyncio
    async def test_document_tool_execute_string_input(self):
        """Test DocumentTool with string input"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={})

        result = await tool.execute("简单的工艺内容")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_document_tool_empty_content(self):
        """Test DocumentTool with empty content"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={})

        result = await tool.execute({"content": ""})
        assert result["success"] is False
        assert result["error_code"] == "EMPTY_CONTENT"

    @pytest.mark.asyncio
    async def test_document_tool_invalid_input(self):
        """Test DocumentTool with invalid input type"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={})

        result = await tool.execute(12345)
        assert result["success"] is False
        assert result["error_code"] == "INVALID_INPUT"

    @pytest.mark.asyncio
    async def test_document_tool_unsupported_format(self):
        """Test DocumentTool with unsupported format defaults to html"""
        from app.tools.document_tool import DocumentTool

        tool = DocumentTool(config={})

        result = await tool.execute({
            "content": "内容",
            "format": "unsupported_format"
        })
        assert result["success"] is True
        # Should default to html
        assert result["files"][0]["format"] == "html"

    def test_document_tool_supported_formats(self):
        """Test DocumentTool supported formats"""
        from app.tools.document_tool import DocumentTool

        assert "html" in DocumentTool.SUPPORTED_FORMATS
        assert "pdf" in DocumentTool.SUPPORTED_FORMATS
        assert "word" in DocumentTool.SUPPORTED_FORMATS
        assert "markdown" in DocumentTool.SUPPORTED_FORMATS
        assert "json" in DocumentTool.SUPPORTED_FORMATS


class TestToolRegistryIntegration:
    """Integration tests for tool registry with actual tools"""

    def setup_method(self):
        """Clear registry before each test"""
        ToolRegistry.clear()

    def test_all_tools_registered(self):
        """Test that all expected tools are registered after import"""
        # Import all tools
        from app.tools.rag_retriever import RAGRetriever
        from app.tools.terminology_tool import TerminologyTool
        from app.tools.compliance_tool import ComplianceTool
        from app.tools.document_tool import DocumentTool

        tools = ToolRegistry.list_tools()

        assert "rag_retriever" in tools
        assert "terminology_mapper" in tools
        assert "compliance_checker" in tools
        assert "document_generator" in tools

    def test_tool_creation_via_registry(self):
        """Test creating tools via registry"""
        from app.tools.rag_retriever import RAGRetriever

        # First import to register
        from app.tools import rag_retriever

        tool = ToolRegistry.create("rag_retriever", config={"top_k": 20})
        assert tool is not None
        assert tool.top_k == 20
