import pytest
import asyncio
from unittest.mock import MagicMock, patch
from src.agent import Analyzer, IncidentReport

# Mock output JSON
MOCK_JSON_RESPONSE = """
{
    "title": "Database Connection Failure",
    "severity": "Critical",
    "impacted_services": ["inventory-db", "order-service"],
    "summary": "The inventory database pool is exhausted.",
    "noise_reduction_ratio": 50.0
}
"""

@pytest.mark.asyncio
async def test_analyzer_success():
    with patch("src.agent.genai") as mock_genai:
        # Setup mock model
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Setup mock response
        mock_response = MagicMock()
        mock_response.text = MOCK_JSON_RESPONSE
        
        # Async mock for generate_content_async
        future = asyncio.Future()
        future.set_result(mock_response)
        mock_model.generate_content_async.return_value = future
        
        # Initialize
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
            analyzer = Analyzer()
        
        logs = ["log1", "log2", "log3"]
        report = await analyzer.analyze_batch(logs)
        
        assert isinstance(report, IncidentReport)
        assert report.title == "Database Connection Failure"
        assert report.severity == "Critical"
        assert len(report.impacted_services) == 2
        assert report.noise_reduction_ratio == 50.0

@pytest.mark.asyncio
async def test_analyzer_failure_fallback():
    with patch("src.agent.genai") as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        
        # Make it raise exception
        mock_model.generate_content_async.side_effect = Exception("API Timeout")
        
        with patch.dict("os.environ", {"GEMINI_API_KEY": "fake_key"}):
            analyzer = Analyzer()
        
        logs = ["log1"]
        report = await analyzer.analyze_batch(logs)
        
        assert report.title == "Analysis Failed"
        assert "API Timeout" in report.summary
        assert report.noise_reduction_ratio == 1.0

if __name__ == "__main__":
    import sys
    try:
        asyncio.run(test_analyzer_success())
        print("test_analyzer_success passed")
        asyncio.run(test_analyzer_failure_fallback())
        print("test_analyzer_failure_fallback passed")
    except AssertionError as e:
        print(f"Test failed: {e}")
        sys.exit(1)
