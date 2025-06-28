import os
import asyncio
import gradio as gr
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from services import youtube_service
from graph.graph import create_work_graph
from agents.topic_segmentation_agent import TopicSegmentationAgent

def setup_environment():
    load_dotenv()
    try:
        if not os.getenv("GEMINI_API_KEY") or not os.getenv("SERPER_API_KEY"):
            raise ValueError("GEMINI_API_KEY and SERPER_API_KEY must be set.")
    except ValueError as e:
        print(f"ERROR: {e}")
        exit()

def initialize_llms():
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    flash_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=gemini_api_key, temperature=0.2)
    pro_model = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", google_api_key=gemini_api_key, temperature=0.3)
    return pro_model, flash_model 

def format_output(final_state):
    """
    Formats the final state of the graph, including chapter summaries.
    """
    if not isinstance(final_state, dict) or final_state.get("error"):
        error_msg = final_state.get("error", "An unexpected error occurred.")
        return f"## ❌ Error\n\n{error_msg}", "", "", ""

    # Format Overall Summary
    summary = final_state.get("summary", "No summary generated.")
    summary_output = f"## 📝 Overall Summary\n\n{summary}"

    # Format Chapter Summaries
    chapters = final_state.get("chapters", [])
    chapter_report = "## 📖 Chapters\n\n"
    if chapters:
        for chapter in chapters:
            start_time = chapter.get('start_time', 0)
            start_time_min = int(start_time // 60)
            start_time_sec = int(start_time % 60)
            chapter_report += f"### {chapter.get('title', 'Untitled Chapter')} `({start_time_min:02d}:{start_time_sec:02d})`\n"
            chapter_report += f"{chapter.get('chapter_summary', 'No summary available for this chapter.')}\n\n"
    else:
        chapter_report += "No chapters were identified."
        
    # Format Fact-Check Report
    fact_check_results = final_state.get("fact_check_results", [])
    fact_check_report = "## 🔎 Fact-Check Report\n\n"
    filtered_results = []
    if fact_check_results:
        for res in fact_check_results:
            score = res.get('false_confidence_score', 0.0)
            verdict = "False" if score >= 0.8 else "Possibly False" if score > 0.5 else ""
            if verdict:
                res['verdict'] = verdict
                filtered_results.append(res)
    if filtered_results:
        for res in filtered_results:
            emoji = "❌" if res['verdict'] == 'False' else "🤔"
            fact_check_report += f"* **{emoji} Claim:** {res.get('claim', 'N/A')}\n  * **Verdict & Explanation:** {res.get('verdict')} - {res.get('explanation', 'N/A')}\n\n"
    else:
        fact_check_report += "✅ Our analysis found no inaccuracies in the verifiable claims."

    return summary_output, chapter_report, fact_check_report

def create_interface(app_graph):
    """Creates and returns the Gradio interface with separate output panels."""
    async def gradio_wrapper(url):
        final_state = {}
        activity_log = ""
        yield "*Processing...*", "*Processing...*", "*Processing...*", "▶️ **Starting Analysis**\n"
        
        async for event in app_graph.astream_events({"youtube_url": url}, version="v1"):
            kind = event["event"]
            if kind == "on_chain_end" and event["name"] == "LangGraph":
                final_state = event["data"]["output"]
        
        if isinstance(final_state, list):
            final_state = final_state[-1]

        summary, chapters, fact_check = format_output(final_state)
        activity_log += "✅ **Done!**"
        yield summary, chapters, fact_check, activity_log

    with gr.Blocks(theme=gr.themes.Soft()) as iface:
        gr.Markdown("# 🤖 AI Content Analyzer (v2.0)")
        with gr.Row():
            url_input = gr.Textbox(lines=1, placeholder="Enter a YouTube video URL here...", label="YouTube URL", scale=4)
            submit_button = gr.Button("Analyze", variant="primary", scale=1)
        
        with gr.Tab("Overall Summary"):
            summary_output = gr.Markdown()
        with gr.Tab("Detailed Chapters"):
            chapter_output = gr.Markdown(label="Video Chapters")
        with gr.Tab("Fact-Check Report"):
            fact_check_output = gr.Markdown()
        with gr.Tab("Agent Activity"):
             activity_log_output = gr.Markdown(label="Agent Activity Log")

        submit_button.click(
            fn=gradio_wrapper,
            inputs=url_input,
            outputs=[summary_output, chapter_output, fact_check_output, activity_log_output]
        )
    return iface

if __name__ == "__main__":
    setup_environment()
    pro_model, flash_model = initialize_llms()
    
    segmentation_agent = TopicSegmentationAgent(model=flash_model)
    
    app_graph = create_work_graph(
        youtube_service=youtube_service,
        segmentation_agent=segmentation_agent,
        summarizer_model=pro_model, 
        claim_extractor_model=flash_model,
        search_query_model=flash_model
    )
    
    app = create_interface(app_graph)
    app.launch(share=True)
