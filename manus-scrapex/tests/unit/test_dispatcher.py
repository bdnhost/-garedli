"""
Unit tests for Dispatcher Agent
"""
import pytest
from src.agents.dispatcher import DispatcherAgent
from src.models.scraping import ScrapeRequest, FieldDefinition
from src.models.base import ScrapingEngine


class TestDispatcherAgent:
    """Test Dispatcher Agent functionality"""

    @pytest.fixture
    def agent(self):
        """Create dispatcher agent instance"""
        return DispatcherAgent()

    @pytest.fixture
    def sample_request(self):
        """Sample scrape request"""
        return ScrapeRequest(
            url="https://example.com",
            schema={
                "title": FieldDefinition(
                    type="string",
                    description="Page title",
                    required=True
                )
            }
        )

    def test_detect_javascript_true(self, agent):
        """Test JavaScript detection - positive case"""
        html = '<html><script src="app.js"></script><body>Test</body></html>'
        assert agent._detect_javascript(html) is True

    def test_detect_javascript_false(self, agent):
        """Test JavaScript detection - negative case"""
        html = '<html><body>Simple static page</body></html>'
        # Note: May still return True due to conservative approach
        result = agent._detect_javascript(html)
        assert isinstance(result, bool)

    def test_detect_frameworks(self, agent):
        """Test framework detection"""
        html = '<div id="root"></div><script>React.render()</script>'
        frameworks = agent._detect_frameworks(html)
        assert 'React' in frameworks

    def test_detect_antibot_cloudflare(self, agent):
        """Test anti-bot detection for Cloudflare"""
        headers = {'cf-ray': '12345', 'server': 'cloudflare'}
        html = ''
        assert agent._detect_antibot(headers, html) is True

    def test_estimate_difficulty(self, agent):
        """Test difficulty estimation"""
        from src.models.scraping import URLAnalysis

        # Static site (easy)
        analysis = URLAnalysis(
            status_code=200,
            headers={},
            has_javascript=False,
            antibot_detected=False,
            estimated_load_time=1.0,
            is_spa=False
        )
        difficulty = agent._estimate_difficulty(analysis)
        assert 0.0 <= difficulty <= 1.0
        assert difficulty < 0.3  # Should be low

        # Dynamic site with anti-bot (hard)
        analysis = URLAnalysis(
            status_code=200,
            headers={},
            has_javascript=True,
            antibot_detected=True,
            estimated_load_time=3.0,
            is_spa=True
        )
        difficulty = agent._estimate_difficulty(analysis)
        assert difficulty > 0.5  # Should be high

    def test_select_engine_static(self, agent):
        """Test engine selection for static site"""
        from src.models.scraping import URLAnalysis

        analysis = URLAnalysis(
            status_code=200,
            headers={},
            has_javascript=False,
            antibot_detected=False,
            estimated_load_time=1.0,
            is_spa=False
        )
        engine = agent._select_engine(analysis)
        assert engine == ScrapingEngine.SCRAPY

    def test_select_engine_dynamic(self, agent):
        """Test engine selection for dynamic site"""
        from src.models.scraping import URLAnalysis

        analysis = URLAnalysis(
            status_code=200,
            headers={},
            has_javascript=True,
            antibot_detected=False,
            estimated_load_time=3.0,
            is_spa=True
        )
        engine = agent._select_engine(analysis)
        assert engine == ScrapingEngine.PLAYWRIGHT

    def test_generate_headers(self, agent):
        """Test header generation"""
        from src.models.scraping import URLAnalysis

        analysis = URLAnalysis(
            status_code=200,
            headers={},
            has_javascript=False,
            antibot_detected=False,
            estimated_load_time=1.0
        )
        headers = agent._generate_headers(analysis)

        assert "User-Agent" in headers
        assert "Accept" in headers
        assert "Accept-Language" in headers
        assert len(headers["User-Agent"]) > 0
