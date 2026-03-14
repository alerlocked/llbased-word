"""
Playwright E2E Test Configuration
Fixtures and configuration for end-to-end tests of the Process Document System.
"""
import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "backend"))

from app.database import Base, get_db
from app.models.database import CreationProject, Material, UploadedImage
from main import app


# Test database configuration
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session) -> Generator:
    """Create a test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    from httpx import AsyncClient, ASGITransport
    import asyncio

    async def create_client():
        transport = ASGITransport(app=app)
        return AsyncClient(transport=transport, base_url="http://test")

    # For sync tests
    loop = asyncio.new_event_loop()
    client = loop.run_until_complete(create_client())
    yield client
    loop.run_until_complete(client.aclose())
    loop.close()
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session) -> AsyncGenerator:
    """Create an async test client with database override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="session")
async def browser():
    """Create a browser instance for the test session."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        yield browser
        await browser.close()


@pytest_asyncio.fixture
async def page(browser) -> AsyncGenerator[Page, None]:
    """Create a new page for each test."""
    context = await browser.new_context()
    page = await context.new_page()
    yield page
    await context.close()


@pytest.fixture
def sample_project_data():
    """Sample project data for testing."""
    return {
        "name": "Test Process Document"
    }


@pytest.fixture
def sample_content():
    """Sample content for project editing."""
    return "# Process Document\n\nThis is a test process document.\n\n## Section 1\n\nContent here."


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for upload testing."""
    # Create a minimal valid PDF content
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
196
%%EOF
"""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(pdf_content)
        yield Path(f.name)
    os.unlink(f.name)


@pytest.fixture
def temp_image_file():
    """Create a temporary image file for upload testing."""
    # Create a minimal PNG (1x1 pixel, transparent)
    png_content = bytes([
        0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,  # PNG signature
        0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,  # IHDR chunk
        0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
        0x08, 0x06, 0x00, 0x00, 0x00, 0x1F, 0x15, 0xC4,
        0x89, 0x00, 0x00, 0x00, 0x0A, 0x49, 0x44, 0x41,  # IDAT chunk
        0x54, 0x78, 0x9C, 0x63, 0x00, 0x01, 0x00, 0x00,
        0x05, 0x00, 0x01, 0x0D, 0x0A, 0x2D, 0xB4, 0x00,
        0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE,  # IEND chunk
        0x42, 0x60, 0x82
    ])
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        f.write(png_content)
        yield Path(f.name)
    os.unlink(f.name)


@pytest.fixture
def temp_docx_file():
    """Create a temporary DOCX file for upload testing."""
    # Create a minimal DOCX (ZIP with required structure)
    import zipfile
    import io

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Required files for DOCX
        zf.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>''')
        zf.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>''')
        zf.writestr('word/document.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p><w:r><w:t>Test content</w:t></w:r></w:p></w:body>
</w:document>''')
        zf.writestr('word/_rels/document.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>
''')

    buf.seek(0)
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
        f.write(buf.read())
        yield Path(f.name)
    os.unlink(f.name)


@pytest.fixture
def temp_invalid_file():
    """Create an invalid file for error handling testing."""
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"Invalid file content")
        yield Path(f.name)
    os.unlink(f.name)


# Helper functions
async def create_test_project(async_client: AsyncClient, name: str = "Test Project") -> dict:
    """Helper to create a test project."""
    response = await async_client.post("/api/creation/projects", json={"name": name})
    assert response.status_code == 200
    return response.json()


async def cleanup_test_project(async_client: AsyncClient, project_id: int):
    """Helper to cleanup a test project."""
    try:
        await async_client.delete(f"/api/creation/projects/{project_id}")
    except Exception:
        pass
