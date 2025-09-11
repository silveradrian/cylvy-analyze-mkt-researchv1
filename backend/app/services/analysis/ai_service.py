"""AI Service for generating insights and analysis"""

import os
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from loguru import logger

class AIService:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            logger.warning("OpenAI API key not configured")
            self.client = None
        else:
            self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def analyze_content(self, prompt: str, model: str = "gpt-4o-mini") -> Dict[str, Any]:
        """Generate AI analysis for content"""
        if not self.api_key:
            return {
                "error": "AI service not configured",
                "analysis": "AI analysis is not available. Please configure OpenAI API key."
            }
        
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a digital marketing analyst specializing in competitive brand intelligence and brand messaging strategy."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            analysis = response.choices[0].message.content
            
            return {
                "analysis": analysis,
                "model": model
            }
            
        except Exception as e:
            logger.error(f"AI analysis error: {e}")
            return {
                "error": str(e),
                "analysis": "Unable to generate AI analysis at this time."
            }
    
    async def generate_insights(
        self, 
        data: Dict[str, Any], 
        insight_type: str = "general"
    ) -> Dict[str, Any]:
        """Generate specific insights based on data type"""
        
        prompts = {
            "company": """
                Based on the company data provided, generate insights on:
                1. Market positioning and competitive advantages
                2. Content strategy effectiveness
                3. Digital presence strengths and weaknesses
                
            """,
            "page": """
                Analyze this page/content and provide:
                1. Content quality assessment
                2. SEO effectiveness
                3. Target audience alignment
                4. Key messaging analysis
               
            """,
            "competitor": """
                Provide competitive analysis insights:
                1. Competitive positioning
                2. Strengths vs competitors
                3. Market gaps and opportunities
                4. Differentiation strategies
                5. Action items
            """
        }
        
        base_prompt = prompts.get(insight_type, prompts["general"])
        full_prompt = f"{base_prompt}\n\nData:\n{data}"
        
        return await self.analyze_content(full_prompt)