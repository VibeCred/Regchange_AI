"""
RegChange AI — LLM Classifier (Optional Ollama/Llama Integration)
Enhances deterministic classification with LLM interpretation.
Gracefully degrades when LLM is unavailable.
"""
import json
import logging
import os
import httpx
from typing import Optional
from backend.config import OLLAMA_BASE_URL, OLLAMA_MODEL, LLM_TIMEOUT
from backend.models.change import ChangeRecord

logger = logging.getLogger(__name__)


class LLMClassifier:
    """Optional LLM enhancement for change classification."""
    
    def __init__(self):
        self.available = False
        self.model = OLLAMA_MODEL
        self.base_url = OLLAMA_BASE_URL
        self.prompt_version = "v1"
        self._check_availability()
    
    def _check_availability(self):
        """Check if Ollama is running and model is available."""
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                models = [m['name'] for m in data.get('models', [])]
                self.available = any(self.model in m for m in models)
                if self.available:
                    logger.info(f"LLM available: {self.model}")
                else:
                    logger.info(f"Ollama running but model '{self.model}' not found. Available: {models}")
            else:
                logger.info("Ollama not responding")
        except Exception as e:
            logger.info(f"LLM not available: {e}")
            self.available = False
    
    def is_available(self) -> bool:
        """Check if LLM is available."""
        return self.available
    
    def enhance_change(self, change: ChangeRecord) -> ChangeRecord:
        """
        Enhance a change record with LLM interpretation.
        Only processes substantive changes for efficiency.
        """
        if not self.available:
            return change
        
        if not change.is_substantive:
            return change
        
        try:
            prompt = self._build_prompt(change)
            response = self._call_llm(prompt)
            
            if response:
                change.llm_explanation = response.get('explanation', '')
                change.llm_classification = response
                change.llm_available = True
                change.prompt_version = self.prompt_version
                change.model_version = self.model
                
                # LLM can suggest impact explanation
                if response.get('impact_explanation'):
                    change.impact_explanation = response['impact_explanation']
        
        except Exception as e:
            logger.warning(f"LLM enhancement failed for {change.change_id}: {e}")
            change.llm_available = False
        
        return change
    
    def enhance_batch(self, changes: list[ChangeRecord]) -> list[ChangeRecord]:
        """Enhance a batch of changes."""
        if not self.available:
            logger.info("LLM not available, skipping enhancement")
            return changes
        
        substantive = [c for c in changes if c.is_substantive]
        logger.info(f"Enhancing {len(substantive)} substantive changes with LLM")
        
        for change in substantive:
            self.enhance_change(change)
        
        return changes
    
    def _build_prompt(self, change: ChangeRecord) -> str:
        """Build a focused, evidence-grounded prompt."""
        old_text = change.old_requirement or "(No old text - newly added)"
        new_text = change.new_requirement or "(No new text - removed)"
        
        prompt = f"""You are a regulatory compliance analyst examining changes between two versions of an RBI circular.

IMPORTANT RULES:
1. ONLY analyze the text provided below. Do NOT invent any requirements, section numbers, or facts.
2. Base your analysis SOLELY on the evidence given.
3. If uncertain, say so explicitly.
4. Return valid JSON only.

OLD TEXT:
{old_text[:800]}

NEW TEXT:
{new_text[:800]}

DETECTED CHANGE TYPE: {change.change_type.value}
DETECTED CATEGORY: {change.category.value}

TASK: Analyze this regulatory change and provide:
1. A clear explanation of what changed and why it matters
2. The practical impact on regulated entities
3. Whether this is truly substantive or editorial

Return JSON:
{{
  "explanation": "Clear explanation of the change",
  "impact_explanation": "Practical impact on regulated entities", 
  "is_substantive": true/false,
  "confidence_note": "Any uncertainty or caveats"
}}"""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> Optional[dict]:
        """Call Ollama API and parse response."""
        try:
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for consistency
                        "num_predict": 500,
                    },
                    "format": "json",
                },
                timeout=LLM_TIMEOUT,
            )
            
            if response.status_code == 200:
                data = response.json()
                text = data.get('response', '')
                
                # Parse JSON from response
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    # Try to extract JSON from text
                    import re
                    json_match = re.search(r'\{.*\}', text, re.DOTALL)
                    if json_match:
                        return json.loads(json_match.group())
                    return {"explanation": text}
            
            return None
        
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return None

    def _load_prompt_template(self, template_name: str) -> str:
        """Load a prompt template from the prompts directory."""
        prompts_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "prompts"
        )
        template_path = os.path.join(prompts_dir, template_name)
        
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                return f.read()
        
        return ""
