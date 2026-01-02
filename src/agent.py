import os
import json
import typing
from typing import List, Literal
from pydantic import BaseModel
try:
    import google.generativeai as genai
except ImportError:
    genai = None

class IncidentReport(BaseModel):
    title: str
    severity: Literal['Critical', 'Warning', 'Info']
    impacted_services: List[str]
    summary: str
    noise_reduction_ratio: float

class Analyzer:
    """
    Analyzes batches of logs using Google Gemini 2.0 Flash Lite to produce Incident Reports.
    """
    
    def __init__(self):
        self.model = None
        if not genai:
             print("WARNING: google-generativeai package not installed.")
             return
             
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel("gemini-2.0-flash-lite")
        else:
            self.model = None
            print("WARNING: GEMINI_API_KEY not found. Analyzer will fail or use fallback.")

    async def analyze_batch(self, logs: List[str]) -> IncidentReport:
        """
        Sends logs to LLM and returns specific IncidentReport.
        """
        if not logs:
            return self._create_fallback_report("No logs provided")
        
        if not self.model:
             return self._create_fallback_report("Missing API Key")

        prompt = self._create_prompt(logs)
        
        try:
            # Using generate_content_async if available, else sync wrapped in thread/executor usually.
            # google-generativeai python client 'generate_content_async' exists.
            
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json"
                )
            )
            
            response_text = response.text
            # Basic cleanup if markdown backticks exist
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            data = json.loads(response_text)
            

            
            # Handle potential list response from LLM
            if isinstance(data, list):
                if data:
                    data = data[0]
                else:
                    return self._create_fallback_report("Empty JSON list returned")
                    
            # Calculate noise reduction log count / 1 incident = ratio? 
            # Or is it defined by LLM? Spec says "noise_reduction_ratio (float)".
            # We should probably calculate it ourselves or let LLM estimate? 
            # "Core KPI: Reduce 1,000 raw error logs into <5 actionable..."
            # Let's let LLM populate it as per Pydantic model, or calculation?
            # Prompt says "Group by Root Cause". One batch might result in ONE report?
            # "Output: Structured Pydantic object IncidentReport" (Singular).
            # So ratio = len(logs) / 1 (since we return 1 report).
            # But the field is in the model. Let's assume LLM generates it or we override it.
            # Ideally LLM might not be good at math. 
            # But let's trust the prompt for now.
            
            return IncidentReport(**data)

        except Exception as e:
            print(f"Analyzer Error: {e}")
            return self._create_fallback_report(str(e))

    def _create_prompt(self, logs: List[str]) -> str:
        log_text = "\n".join(logs)
        return f"""
        You are a Site Reliability Engineer. 
        Analyze the following log batch and Identify the Single Root Cause Incident.
        Ignore transient noise.
        
        Logs:
        {log_text}
        
        Return a JSON object matching this schema:
        {{
            "title": "Short descriptive title",
            "severity": "Critical" | "Warning" | "Info",
            "impacted_services": ["service1", "service2"],
            "summary": "Concise explanation of the root cause",
            "noise_reduction_ratio": <float representing raw_logs_count / incident_count (which is 1)>
        }}
        """

    def _create_fallback_report(self, reason: str) -> IncidentReport:
        return IncidentReport(
            title="Analysis Failed",
            severity="Info",
            impacted_services=[],
            summary=f"Could not analyze logs: {reason}",
            noise_reduction_ratio=1.0
        )
