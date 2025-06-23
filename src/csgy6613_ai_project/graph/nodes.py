import os
import httpx
import json
import asyncio
from typing import List, Dict
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from .state import GraphState

def get_video_info(state: GraphState, youtube_service) -> Dict:
    """Node to fetch the video transcript."""
    print("---NODE: GETTING VIDEO INFO---")
    url = state["youtube_url"]
    video_id = youtube_service.extract_video_id(url)
    if not video_id:
        return {"error": "Invalid YouTube URL provided. Please check the link and try again."}
    
    # --- FIX: Ensure both transcript types are fetched correctly ---
    transcript = youtube_service.get_transcript(video_id, with_timestamps=False)
    timed_transcript = youtube_service.get_transcript(video_id, with_timestamps=True)
    
    if not transcript or not timed_transcript:
        return {"error": f"Could not retrieve transcript for video ID: {video_id}. The video may have transcripts disabled or is not a standard YouTube video."}
    
    return {"video_id": video_id, "transcript": transcript, "timed_transcript": timed_transcript}


async def segment_transcript_into_chapters(state: GraphState, segmentation_agent) -> Dict:
    """Node to run the topic segmentation agent and map timestamps."""
    print("---NODE: SEGMENTING TRANSCRIPT---")
    if state.get("error"): return {}
    
    if "timed_transcript" not in state or not state["timed_transcript"]:
        return {"error": "Failed to process video timeline. Cannot segment transcript."}

    transcript = state["transcript"]
    timed_transcript = state["timed_transcript"]
    
    chapters = await segmentation_agent.run(transcript)
    
    # --- Accurate Timestamp Mapping ---
    current_search_index = 0
    for chapter in chapters:
        chapter_content_words = chapter.get("content", "").split()
        if not chapter_content_words:
            chapter['start_time'] = 0
            continue
        
        # Find the start of the chapter by looking for the first few words
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
            # Fallback if phrase not found
            chapter['start_time'] = timed_transcript[current_search_index]['start'] if current_search_index < len(timed_transcript) else 0

    return {"chapters": chapters}


async def generate_chapter_summaries(state: GraphState, summarizer_model) -> Dict:
    """Node to generate a summary for each identified chapter."""
    print("---NODE: GENERATING CHAPTER SUMMARIES---")
    if state.get("error") or not state.get("chapters"): return {}

    chapters = state["chapters"]
    print(f"Processing {len(chapters)} chapters for summarization")
    
    # Process each chapter with aggressive summarization
    processed_chapters = []
    
    for i, chapter in enumerate(chapters):
        chapter_text = chapter.get("content", "No content available for this chapter.")
        chapter_title = chapter.get('title', 'Untitled')
        
        print(f"\n--- Processing Chapter {i+1}: {chapter_title} ---")
        print(f"Original content length: {len(chapter_text.split())} words")
        
        # Try multiple approaches to get a proper summary
        summary = await _force_summarization(chapter_text, chapter_title, summarizer_model)
        
        # Create processed chapter with both summary and original content
        processed_chapter = {
            "title": chapter_title,
            "chapter_summary": summary,
            "content": chapter_text,  # Keep for timestamp mapping
            "start_time": chapter.get("start_time", 0)
        }
        
        processed_chapters.append(processed_chapter)
        
        print(f"Final summary length: {len(summary.split())} words")
        print(f"Summary preview: {summary[:150]}...")
        
        # Verify it's actually a summary
        if len(summary.split()) > 100:
            print("🚨 WARNING: Summary is still very long!")
        else:
            print("✅ Summary appears to be properly condensed")
    
    # Generate overall summary from chapter summaries only
    summary_texts = [ch["chapter_summary"] for ch in processed_chapters]
    final_summary = await _create_overall_summary(summary_texts, processed_chapters, summarizer_model)

    print(f"\n--- Final Results ---")
    print(f"Generated {len(processed_chapters)} chapter summaries")
    print(f"Overall summary length: {len(final_summary.split())} words")

    return {"chapters": processed_chapters, "summary": final_summary}


async def _force_summarization(chapter_text: str, chapter_title: str, model) -> str:
    """Aggressively force proper summarization with multiple attempts."""
    
    # First attempt - very strict prompt
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
        summary = await chain.ainvoke({"title": chapter_title, "text": chapter_text})
        
        # Check if it's actually a summary
        if _is_proper_summary(summary, chapter_text):
            return summary.strip()
            
    except Exception as e:
        print(f"First summarization attempt failed: {e}")
    
    # Second attempt - even more aggressive
    aggressive_prompt = ChatPromptTemplate.from_template(
        """You are a summarization bot. Your job is to create SHORT summaries.

        FORBIDDEN: Do not copy text from the input
        REQUIRED: Create 2-3 short bullet points only
        
        What is the main topic of this text? Answer in 2-3 bullet points:
        
        {text}
        
        Summary:"""
    )
    
    try:
        chain = aggressive_prompt | model | StrOutputParser()
        summary = await chain.ainvoke({"text": chapter_text[:1000]})  # Limit input size
        
        if _is_proper_summary(summary, chapter_text):
            return summary.strip()
            
    except Exception as e:
        print(f"Second summarization attempt failed: {e}")
    
    # Final fallback - manual extraction
    return _manual_summary_fallback(chapter_text, chapter_title)


def _is_proper_summary(summary: str, original_text: str) -> bool:
    """Check if the output is actually a summary and not the original text."""
    summary_words = len(summary.split())
    original_words = len(original_text.split())
    
    # Summary should be much shorter
    if summary_words > original_words * 0.3:  # More than 30% of original
        print(f"⚠️  Summary too long: {summary_words} words vs {original_words} original")
        return False
    
    # Should contain bullet points or be very short
    if summary_words > 100 and "•" not in summary and "-" not in summary:
        print("⚠️  Summary doesn't appear to be in bullet format and is too long")
        return False
    
    # Check for direct copying (basic check)
    summary_lower = summary.lower()
    original_lower = original_text.lower()
    
    # If more than 50% of summary words appear consecutively in original, it's likely copied
    summary_phrases = [summary_lower[i:i+20] for i in range(0, len(summary_lower)-20, 10)]
    copy_count = sum(1 for phrase in summary_phrases if phrase in original_lower)
    
    if copy_count > len(summary_phrases) * 0.5:
        print("⚠️  Summary appears to be copied from original text")
        return False
    
    return True


def _manual_summary_fallback(text: str, title: str) -> str:
    """Create a basic summary when AI fails."""
    words = text.split()
    
    # Extract first few sentences as key points
    sentences = text.split('. ')
    key_sentences = sentences[:3]
    
    # Create manual bullet points
    summary_points = []
    for sentence in key_sentences:
        if len(sentence.strip()) > 10:
            # Take first part of sentence and clean it up
            clean_sentence = sentence.strip()[:100]
            if not clean_sentence.endswith('.'):
                clean_sentence += "..."
            summary_points.append(f"• {clean_sentence}")
    
    if not summary_points:
        summary_points = [f"• Discussion about {title.lower()}", f"• Content covers approximately {len(words)} words of material"]
    
    return "\n".join(summary_points[:3])


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
        response_text = await chain.ainvoke({"transcript": transcript})
        # Clean up the response to extract JSON
        json_text = response_text.strip().lstrip("```json").rstrip("```").strip()
        claims = json.loads(json_text)
        return {"claims": claims}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from claims response: {e}")
        print(f"Raw response: {response_text}")
        return {"claims": []}


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
        current_results = state.get("fact_check_results", [])
        current_results.append({
            "claim": claim, 
            "explanation": "Web search unavailable - API key not configured.",
            "false_confidence_score": 0.5
        })
        return {"fact_check_results": current_results}
    
    # Generate search queries
    query_gen_prompt = ChatPromptTemplate.from_template(
        "Generate 3 diverse search queries to verify this claim: \"{claim}\"\n"
        "Return just the queries, one per line."
    )
    query_gen_chain = query_gen_prompt | search_query_model | StrOutputParser()
    
    try:
        queries_str = await query_gen_chain.ainvoke({"claim": claim})
        queries = [q.strip().lstrip("123. ").strip("\"") for q in queries_str.strip().split('\n') if q.strip()]
        queries = queries[:3]  # Limit to 3 queries
    except Exception as e:
        print(f"Error generating search queries: {e}")
        queries = [claim]  # Fallback to using the claim itself
    
    evidence = []
    
    # Search for evidence
    async with httpx.AsyncClient(timeout=10.0) as client:
        for query in queries:
            print(f"  -> Searching for: '{query}'")
            payload = json.dumps({"q": query})
            headers = {'X-API-KEY': serper_api_key, 'Content-Type': 'application/json'}
            
            try:
                response = await client.post("https://google.serper.dev/search", headers=headers, content=payload)
                response.raise_for_status()
                results = response.json()
                
                # Extract top 2 results from each query
                for item in results.get('organic', [])[:2]:
                    evidence.append({
                        "source": item.get('link'),
                        "snippet": item.get('snippet')
                    })
                
                await asyncio.sleep(1)  # Rate limiting
                
            except Exception as e:
                print(f"Error searching for query '{query}': {e}")
    
    # Analyze the evidence
    analysis_prompt = ChatPromptTemplate.from_template(
        """You are an expert fact-checker. Use your internal knowledge and critically evaluate the provided evidence.
        
        Analyze this claim: "{claim}"
        
        Evidence from web search: {evidence}
        
        Return a single raw JSON object with these keys:
        - "explanation": A brief analysis of the claim's accuracy
        - "false_confidence_score": A number from 0.0 to 1.0 (0.0 = definitely true, 1.0 = definitely false)
        """
    )
    analysis_chain = analysis_prompt | search_query_model | StrOutputParser()
    
    try:
        response_text = await analysis_chain.ainvoke({"claim": claim, "evidence": json.dumps(evidence)})
        json_text = response_text.strip().lstrip("```json").rstrip("```").strip()
        verdict_data = json.loads(json_text)
    except Exception as e:
        print(f"Error analyzing evidence: {e}")
        verdict_data = {
            "explanation": "Analysis failed due to technical error.", 
            "false_confidence_score": 0.5
        }
    
    # Add result to the list
    current_results = state.get("fact_check_results", [])
    current_results.append({"claim": claim, **verdict_data})
    
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