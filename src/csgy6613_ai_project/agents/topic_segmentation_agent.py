from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
from typing import List, Dict

class TopicSegmentationAgent:
    def __init__(self, model):
        self.model = model

    async def run(self, transcript: str) -> List[Dict]:
        """Analyzes a transcript to identify topical segments and their content."""
        print("---AGENT: Running Topic Segmentation---")
        
        prompt = ChatPromptTemplate.from_template(
            """You are an expert at analyzing long transcripts and creating a "table of contents."
            Your goal is to segment the provided transcript into logical chapters based on topic.

            **Instructions:**
            1.  Read the entire transcript to understand its structure.
            2.  Identify the natural breakpoints where the topic shifts.
            3.  For each identified segment/chapter, provide a short, descriptive title.
            4.  For each chapter, extract the **exact corresponding text** from the original transcript.

            Return the output as a JSON array of objects. Each object must have two keys:
            - "title": A short, descriptive title for the chapter.
            - "content": The full text content of that chapter from the original transcript.

            **Transcript:**
            ---
            {transcript}
            ---
            """
        )
        
        chain = prompt | self.model | JsonOutputParser()
        
        try:
            chapters = await chain.ainvoke({"transcript": transcript})
            return chapters
        except Exception as e:
            print(f"Error in TopicSegmentationAgent: {e}")
            # Fallback to treating the whole transcript as one chapter
            return [{"title": "Full Video Summary", "content": transcript}]