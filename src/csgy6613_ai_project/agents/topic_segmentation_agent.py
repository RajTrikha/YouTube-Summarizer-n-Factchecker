from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
import json
import re
from typing import List, Dict

class TopicSegmentationAgent:
    def __init__(self, model):
        self.model = model

    async def run(self, transcript: str) -> List[Dict]:
        """Analyzes a transcript to identify topical segments and their content."""
        print("---AGENT: Running Topic Segmentation---")
        
        # Simplified prompt without JSON examples that could cause template issues
        prompt = ChatPromptTemplate.from_template(
            """You are an expert at analyzing transcripts and creating logical chapters.

Your task: Segment this transcript into 3-7 logical chapters based on topic shifts.

Guidelines:
- Look for natural breakpoints where topics change
- Create meaningful, descriptive titles (5-10 words max)
- Extract the exact text that belongs to each chapter
- Aim for substantial content per chapter (not tiny segments)

Output Format: Valid JSON array with objects containing exactly these keys:
- "title": Short descriptive title
- "content": Exact text from transcript for that chapter

Transcript to analyze:
{transcript}

Return only the JSON array, no other text."""
        )
        
        chain = prompt | self.model | JsonOutputParser()
        
        try:
            chapters = await chain.ainvoke({"transcript": transcript})
            
            # Validate the output
            if not isinstance(chapters, list) or len(chapters) == 0:
                raise ValueError("Invalid response format")
            
            # Validate each chapter
            validated_chapters = []
            for i, chapter in enumerate(chapters):
                if not isinstance(chapter, dict):
                    continue
                
                title = chapter.get("title", f"Chapter {i+1}")
                content = chapter.get("content", "")
                
                # Ensure we have meaningful content
                if len(content.strip()) < 50:  # Skip very short segments
                    continue
                
                validated_chapters.append({
                    "title": str(title)[:100],  # Limit title length
                    "content": str(content)
                })
            
            if len(validated_chapters) == 0:
                raise ValueError("No valid chapters found")
            
            print(f"Successfully segmented transcript into {len(validated_chapters)} chapters")
            return validated_chapters
            
        except Exception as e:
            print(f"Error in TopicSegmentationAgent: {e}")
            return self._smart_fallback_segmentation(transcript)
    
    def _smart_fallback_segmentation(self, transcript: str) -> List[Dict]:
        """Smarter fallback that tries to find natural breakpoints."""
        print("Using smart fallback segmentation...")
        
        # Try to find natural breakpoints in the text
        sentences = self._split_into_sentences(transcript)
        
        if len(sentences) < 10:
            return [{"title": "Complete Video Content", "content": transcript}]
        
        # Look for transition phrases that might indicate topic changes
        transition_phrases = [
            "now let's", "moving on", "next", "another", "so", "but", "however",
            "on the other hand", "meanwhile", "in addition", "furthermore",
            "let me", "i want to", "what we have", "what's interesting"
        ]
        
        breakpoints = [0]  # Always start with beginning
        
        for i, sentence in enumerate(sentences[1:], 1):
            sentence_lower = sentence.lower().strip()
            
            # Look for transition phrases at the start of sentences
            for phrase in transition_phrases:
                if sentence_lower.startswith(phrase) and i > len(sentences) // 4:
                    # Only add breakpoint if it's not too close to the last one
                    if len(breakpoints) == 0 or i - breakpoints[-1] > len(sentences) // 8:
                        breakpoints.append(i)
                        break
        
        # Ensure we don't have too many chapters
        if len(breakpoints) > 6:
            # Keep only the most significant breakpoints
            step = len(breakpoints) // 6
            breakpoints = breakpoints[::step]
        
        # Create chapters from breakpoints
        chapters = []
        for i in range(len(breakpoints)):
            start_idx = breakpoints[i]
            end_idx = breakpoints[i + 1] if i + 1 < len(breakpoints) else len(sentences)
            
            chapter_sentences = sentences[start_idx:end_idx]
            chapter_content = " ".join(chapter_sentences)
            
            # Create a simple title based on the first few words
            first_words = " ".join(chapter_content.split()[:8])
            chapter_title = f"Chapter {i + 1}: {first_words}..."
            
            chapters.append({
                "title": chapter_title,
                "content": chapter_content
            })
        
        print(f"Smart fallback created {len(chapters)} chapters")
        return chapters
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using simple heuristics."""
        # Simple sentence splitting - can be improved with proper NLP
        sentences = re.split(r'[.!?]+\s+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        return sentences