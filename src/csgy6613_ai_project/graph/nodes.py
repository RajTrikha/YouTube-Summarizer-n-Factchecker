import os
import httpx
import json
import asyncio
from typing import List, Dict, Optional
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from .state import GraphState
import time
from functools import wraps

# Simplified rate limiting decorator
def rate_limit(calls_per_minute=8):
    """Simplified rate limiting decorator"""
    def decorator(func):
        last_called = [0.0]
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            min_interval = 60.0 / calls_per_minute
            
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            
            last_called[0] = time.time()
            
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    await asyncio.sleep(60)
                    return await func(*args, **kwargs)
                raise
        return wrapper
    return decorator

def get_video_info(state: GraphState, youtube_service) -> Dict:
    """Node to fetch the video transcript."""
    print("---NODE: GETTING VIDEO INFO---")
    url = state["youtube_url"]
    video_id = youtube_service.extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL provided. Please check the link and try again."}
    
    transcript = youtube_service.get_transcript(video_id, with_timestamps=False)
    timed_transcript = youtube_service.get_transcript(video_id, with_timestamps=True)
    
    if not transcript or not timed_transcript:
        return {"error": f"Could not retrieve transcript for video ID: {video_id}. The video may have transcripts disabled or is not a standard YouTube video."}
    
    return {"video_id": video_id, "transcript": transcript, "timed_transcript": timed_transcript}

@rate_limit(calls_per_minute=8)
async def segment_transcript_into_chapters(state: GraphState, segmentation_agent) -> Dict:
    """Node to run the topic segmentation agent and map timestamps."""
    print("---NODE: SEGMENTING TRANSCRIPT---")
    if state.get("error"): 
        return {}
    
    if "timed_transcript" not in state or not state["timed_transcript"]:
        return {"error": "Failed to process video timeline. Cannot segment transcript."}

    transcript = state["transcript"]
    timed_transcript = state["timed_transcript"]
    
    chapters = await segmentation_agent.run(transcript)
    
    # Map timestamps efficiently
    current_search_index = 0
    for chapter in chapters:
        chapter_content_words = chapter.get("content", "").split()
        if not chapter_content_words:
            chapter['start_time'] = 0
            continue
        
        start_phrase = " ".join(chapter_content_words[:10])
        start_index = -1
        for i in range(current_search_index, len(timed_transcript)):
            if start_phrase in timed_transcript[i]['text']:
                start_index = i
                break
        
        if start_index != -1:
            chapter['start_time'] = timed_transcript[start_index]['start']
            current_search_index = start_index
        else:
            chapter['start_time'] = timed_transcript[current_search_index]['start'] if current_search_index < len(timed_transcript) else 0

    return {"chapters": chapters}

@rate_limit(calls_per_minute=6)
async def generate_chapter_summaries(state: GraphState, summarizer_model) -> Dict:
    """Node to generate a summary for each identified chapter."""
    print("---NODE: GENERATING CHAPTER SUMMARIES---")
    if state.get("error") or not state.get("chapters"): 
        return {}

    chapters = state["chapters"]
    print(f"Processing {len(chapters)} chapters for summarization")
    
    processed_chapters = []
    
    for i, chapter in enumerate(chapters):
        chapter_text = chapter.get("content", "No content available for this chapter.")
        chapter_title = chapter.get('title', 'Untitled')
        
        print(f"\n--- Processing Chapter {i + 1}: {chapter_title} ---")
        
        if i > 0:
            await asyncio.sleep(10)  # Delay between chapters
        
        summary = await _create_summary(chapter_text, chapter_title, summarizer_model)
        
        processed_chapters.append({
            "title": chapter_title,
            "chapter_summary": summary,
            "start_time": chapter.get("start_time", 0)
        })
    
    # Generate overall summary
    await asyncio.sleep(8)
    summary_texts = [ch["chapter_summary"] for ch in processed_chapters]
    final_summary = await _create_overall_summary(summary_texts, processed_chapters, summarizer_model)

    return {"chapters": processed_chapters, "summary": final_summary}

async def _create_summary(chapter_text: str, chapter_title: str, model) -> str:
    """Create summary with original prompt structure."""
    strict_prompt = ChatPromptTemplate.from_template(
        """CRITICAL: You must create a SHORT summary. DO NOT reproduce the original text.

        Task: Summarize this chapter in exactly 3 bullet points.
        
        Rules:
        1. Each bullet point = ONE sentence maximum
        2. Total word count must be under 50 words
        3. Use your own words, not the speaker's words
        4. Focus only on the main idea
        
        Chapter: {title}
        
        Text: {text}
        
        Write exactly 3 bullet points (• format):"""
    )
    
    try:
        chain = strict_prompt | model | StrOutputParser()
        summary = await chain.ainvoke({"title": chapter_title, "text": chapter_text[:1500]})
        
        # Simple validation - if too long, use fallback
        if len(summary.split()) > 60:
            return _fallback_summary(chapter_text, chapter_title)
        
        return summary.strip()
    except Exception as e:
        print(f"Summarization failed: {e}")
        return _fallback_summary(chapter_text, chapter_title)

def _fallback_summary(text: str, title: str) -> str:
    """Create a basic summary when AI fails."""
    sentences = text.split('. ')[:3]
    summary_points = []
    
    for sentence in sentences:
        if len(sentence.strip()) > 10:
            clean_sentence = sentence.strip()[:80]
            if not clean_sentence.endswith('.'):
                clean_sentence += "..."
            summary_points.append(f"• {clean_sentence}")
    
    if not summary_points:
        summary_points = [f"• Discussion about {title.lower()}", f"• Content covers video material"]
    
    return "\n".join(summary_points[:3])

@rate_limit(calls_per_minute=6)
async def _create_overall_summary(summary_texts: List[str], chapters: List[Dict], model) -> str:
    """Create overall summary from chapter summaries."""
    combined_summaries = []
    for i, summary in enumerate(summary_texts):
        chapter_title = chapters[i]["title"]
        combined_summaries.append(f"**{chapter_title}:**\n{summary}")
    
    prompt = ChatPromptTemplate.from_template(
        """Create a cohesive overview based on these chapter summaries.
        
        Requirements:
        - 2-3 paragraphs maximum
        - Highlight main themes and key insights
        - Flow logically from one idea to the next
        
        Chapter Summaries:
        {summaries}
        
        Overall Summary:"""
    )
    
    try:
        chain = prompt | model | StrOutputParser()
        result = await chain.ainvoke({"summaries": "\n\n".join(combined_summaries)})
        return result.strip()
    except Exception as e:
        print(f"Error creating overall summary: {e}")
        return "Summary of key topics and insights from the video content."

@rate_limit(calls_per_minute=6)
async def extract_claims(state: GraphState, claim_extractor_model) -> Dict:
    """Node to extract verifiable claims from the transcript."""
    print("---NODE: EXTRACTING VERIFIABLE CLAIMS---")
    if state.get("error"): 
        return {}
        
    transcript = state["transcript"]
    if not transcript:
        return {"claims": []}
        
    prompt = ChatPromptTemplate.from_template(
        """You are a precise and analytical claim extractor. Your sole purpose is to identify statements that are objective, verifiable, and publicly knowable.
        
        **CRITICAL: DO NOT EXTRACT:** 
        - Opinions
        - Analogies  
        - Predictions
        - Personal Anecdotes
        - Vague statements
        
        **ONLY EXTRACT:** 
        - Specific, objective claims with numbers, dates, names, or clear events
        
        From the following text, extract up to 5 of the most important, verifiable factual claims. 
        Return as a raw JSON array of strings.
        
        Transcript: --- {transcript}"""
    )
    
    chain = prompt | claim_extractor_model | StrOutputParser()
    
    try:
        response_text = await chain.ainvoke({"transcript": transcript[:2000]})  # Limit input
        json_text = response_text.strip().lstrip("```json").rstrip("```").strip()
        claims = json.loads(json_text)
        return {"claims": claims[:5]}  # Limit claims
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from claims response: {e}")
        return {"claims": []}
    except Exception as e:
        print(f"Error extracting claims: {e}")
        return {"claims": []}

@rate_limit(calls_per_minute=4)
async def search_for_evidence(state: GraphState, search_query_model) -> Dict:
    """Node to search for evidence for the next claim to be fact-checked."""
    claim_index = len(state.get("fact_check_results", []))
    claims = state.get("claims", [])
    
    if claim_index >= len(claims):
        return {}
        
    claim = claims[claim_index]
    print(f"---NODE: SEARCHING FOR EVIDENCE ({claim_index + 1}/{len(claims)}) for claim: '{claim}'---")
    
    serper_api_key = os.getenv("SERPER_API_KEY")
    if not serper_api_key:
        print("Warning: SERPER_API_KEY not found. Skipping web search.")
        return _add_fact_check_result(state, claim, "Web search unavailable - API key not configured.", 0.5)
    
    # Generate search query (keeping original approach but simplified)
    query_gen_prompt = ChatPromptTemplate.from_template(
        "Generate 1 focused search query to verify this claim: \"{claim}\"\n"
        "Return just the query."
    )
    
    try:
        query_gen_chain = query_gen_prompt | search_query_model | StrOutputParser()
        query = await query_gen_chain.ainvoke({"claim": claim})
        query = query.strip().strip("\"")
    except Exception as e:
        print(f"Error generating search query: {e}")
        query = claim  # Fallback to using the claim itself
    
    # Search for evidence
    await asyncio.sleep(3)
    evidence = await _search_web(query, serper_api_key)
    
    # Analyze the evidence (keeping original detailed prompt)
    await asyncio.sleep(5)
    analysis_prompt = ChatPromptTemplate.from_template(
        """You are an expert fact-checker. Use your internal knowledge and critically evaluate the provided evidence.
        
        Analyze this claim: "{claim}"
        
        Evidence from web search: {evidence}
        
        Return a single raw JSON object with these keys:
        - "explanation": A brief analysis of the claim's accuracy
        - "false_confidence_score": A number from 0.0 to 1.0 (0.0 = definitely true, 1.0 = definitely false)
        """
    )
    
    try:
        analysis_chain = analysis_prompt | search_query_model | StrOutputParser()
        response_text = await analysis_chain.ainvoke({"claim": claim, "evidence": json.dumps(evidence)})
        json_text = response_text.strip().lstrip("```json").rstrip("```").strip()
        verdict_data = json.loads(json_text)
    except Exception as e:
        print(f"Error analyzing evidence: {e}")
        verdict_data = {"explanation": "Analysis failed due to technical error.", "false_confidence_score": 0.5}
    
    return _add_fact_check_result(state, claim, verdict_data["explanation"], verdict_data["false_confidence_score"])

async def _search_web(query: str, api_key: str) -> List[Dict]:
    """Search web for evidence."""
    evidence = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = json.dumps({"q": query})
            headers = {'X-API-KEY': api_key, 'Content-Type': 'application/json'}
            
            response = await client.post("https://google.serper.dev/search", headers=headers, content=payload)
            response.raise_for_status()
            results = response.json()
            
            # Extract top 3 results
            for item in results.get('organic', [])[:3]:
                evidence.append({
                    "source": item.get('link'),
                    "snippet": item.get('snippet')
                })
    except Exception as e:
        print(f"Error searching for query '{query}': {e}")
    
    return evidence

def _add_fact_check_result(state: GraphState, claim: str, explanation: str, score: float) -> Dict:
    """Add fact-check result to state."""
    current_results = state.get("fact_check_results", [])
    current_results.append({
        "claim": claim, 
        "explanation": explanation,
        "false_confidence_score": score
    })
    return {"fact_check_results": current_results}

def should_continue_fact_checking(state: GraphState) -> str:
    """Conditional edge to decide if we should continue fact-checking."""
    if state.get("error") or not state.get("claims"):
        return "end"
    
    num_results = len(state.get("fact_check_results", []))
    num_claims = len(state.get("claims", []))
    
    if num_results < num_claims:
        return "continue_fact_checking"
    return "end"