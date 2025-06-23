from langgraph.graph import StateGraph, END
from .state import GraphState
from . import nodes

def create_work_graph(youtube_service, segmentation_agent, summarizer_model, claim_extractor_model, search_query_model):
    """Assembles the nodes into a runnable graph."""
    
    workflow = StateGraph(GraphState)

    # Define wrappers for async nodes
    async def run_segmentation(state):
        return await nodes.segment_transcript_into_chapters(state, segmentation_agent)

    async def run_summarize_chapters(state):
        return await nodes.generate_chapter_summaries(state, summarizer_model)

    async def run_extract_claims(state):
        return await nodes.extract_claims(state, claim_extractor_model)

    async def run_search_for_evidence(state):
        return await nodes.search_for_evidence(state, search_query_model)
    
    def check_for_error(state):
        return "end" if state.get("error") else "continue"

    # Add nodes to the graph
    workflow.add_node("get_video_info", lambda state: nodes.get_video_info(state, youtube_service))
    workflow.add_node("segment_transcript", run_segmentation)
    workflow.add_node("generate_chapter_summaries", run_summarize_chapters)
    workflow.add_node("extract_claims", run_extract_claims)
    workflow.add_node("search_for_evidence", run_search_for_evidence)

    # Define the graph's sequential flow
    workflow.set_entry_point("get_video_info")
    workflow.add_conditional_edges("get_video_info", check_for_error, {"continue": "segment_transcript", "end": END})
    workflow.add_edge("segment_transcript", "generate_chapter_summaries")
    workflow.add_edge("generate_chapter_summaries", "extract_claims")
    
    workflow.add_conditional_edges(
        "extract_claims",
        nodes.should_continue_fact_checking,
        {"continue_fact_checking": "search_for_evidence", "end": END}
    )
    workflow.add_conditional_edges(
        "search_for_evidence",
        nodes.should_continue_fact_checking,
        {"continue_fact_checking": "search_for_evidence", "end": END}
    )

    app = workflow.compile()
    return app

