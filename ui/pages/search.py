"""Search page - Query and result display"""

import streamlit as st
import plotly.graph_objects as go


def _result_to_dict(result):
    if isinstance(result, dict):
        return result

    data = {}
    for key in [
        "slide_id",
        "page_index",
        "slide_layout",
        "source_path",
        "timestamp",
        "shapes_count",
        "has_notes",
        "title",
        "text_content",
        "score",
        "vector",
    ]:
        if hasattr(result, key):
            data[key] = getattr(result, key)

    metadata = getattr(result, "metadata", {})
    if isinstance(metadata, dict):
        data.update(metadata)
    return data


def _short_text(value, limit=220):
    text = "" if value is None else str(value).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."

def render_search():
    """Render search page"""
    
    st.markdown("## 🔎 Search PPT Content")
    
    # Search input
    col_search, col_mode = st.columns([4, 1])
    
    with col_search:
        query = st.text_input(
            "Enter your search query",
            placeholder="E.g., 'machine learning applications' or 'Q3 financial results'",
            label_visibility="collapsed"
        )
    
    with col_mode:
        search_mode = st.selectbox(
            "Mode",
            ["Text", "Image", "Hybrid"],
            label_visibility="collapsed"
        )
    
    col_search_btn, col_filter = st.columns([1, 4])
    
    with col_search_btn:
        search_button = st.button("🔍 Search", type="primary", use_container_width=True)
    
    top_k = 10
    with col_filter:
        if st.checkbox("Advanced Filters"):
            col_f1, col_f2, col_f3 = st.columns(3)
            with col_f1:
                confidence = st.slider("Min Confidence", 0, 100, 70)
            with col_f2:
                similarity = st.slider("Min Similarity", 0, 100, 50)
            with col_f3:
                top_k = st.number_input("Top Results", 1, 100, 10)
    
    if search_button and query:
        st.markdown("---")
        st.subheader(f"Search Results for: \"{query}\"")
        
        import time
        from src.utils.lancedb_manager import get_lancedb_manager
        import numpy as np
        import plotly.graph_objects as go
        
        start_time = time.time()
        
        mgr = get_lancedb_manager()
        
        if not mgr.is_connected():
            st.error("Database connection failed. Please ensure setup is correct.")
        else:
            try:
                table_names = mgr.list_tables()
                target_table = "slides"
                if table_names:
                    valid_tables = [t for t in table_names if t.startswith("slides")]
                    if "slides" in valid_tables:
                        target_table = "slides"
                    elif valid_tables:
                        target_table = valid_tables[-1]

                text_results = mgr.search_text(target_table, query, k=top_k)
                
                with st.spinner("Searching LanceDB Lakehouse..."):
                    if text_results:
                        results = text_results
                    else:
                        # If text search misses, fall back to vector retrieval.
                        from src.core.pipeline import get_pipeline
                        from src.agents.multimodal_space.vector_alignment import ImageBindSpace
                        pipeline = get_pipeline()
                        q_vector = ImageBindSpace(output_dim=128).encode_text(query)
                        results = pipeline.retrieval_stage.retrieve(
                            query_vector=q_vector,
                            table_name=target_table,
                            k1=top_k * 5,
                            k2=top_k
                        )
                
                elapsed = time.time() - start_time

                indexed_rows = 0
                table_obj = mgr.get_table(target_table)
                if table_obj is not None:
                    try:
                        indexed_rows = len(table_obj.to_pandas())
                    except Exception:
                        indexed_rows = 0
                
                if not results:
                    if indexed_rows == 0:
                        st.warning("No indexed slides found yet. Please upload and process a PPT first.")
                    else:
                        st.info(f"No matches found for this keyword. Indexed slides: {indexed_rows}. Try another keyword from the slide title/body.")
                else:
                    with st.expander(f"📌 Index Summary ({len(results)} matches)", expanded=True):
                        summary_df = []
                        for item in results[: min(len(results), 20)]:
                            row = _result_to_dict(item)
                            summary_df.append({
                                "slide_id": row.get("slide_id", "Unknown"),
                                "title": row.get("title", "") or "(untitled)",
                                "page_index": row.get("page_index", ""),
                                "has_notes": row.get("has_notes", False),
                                "shapes_count": row.get("shapes_count", ""),
                                "score": f"{float(row.get('score', 0.0)):.2%}",
                            })
                        if summary_df:
                            st.dataframe(summary_df, use_container_width=True, hide_index=True)

                    st.caption("Each slide below shows the indexed title/body snippet, source, and metadata.")

                    for idx, result in enumerate(results):
                        rank = idx + 1
                        row = _result_to_dict(result)
                        slide_id = row.get("slide_id", "Unknown")
                        title = row.get("title", "")
                        display_name = title or slide_id or row.get("doc_id", "Unknown")
                        ppt_src = "Uploaded PPT"
                        score = float(row.get("score", 0.0) or 0.0)
                        if not slide_id or slide_id == "Unknown":
                            slide_id = row.get("slide_id", row.get("doc_id", "Unknown"))
                        
                        with st.container():
                            col_rank, col_content, col_action = st.columns([0.5, 4.5, 1])
                            
                            with col_rank:
                                st.metric("#", rank)
                            
                            with col_content:
                                st.markdown(f"### {display_name}")
                                st.caption(f"📁 {ppt_src}")
                                st.markdown(f"**Score**: {score:.2%}")
                                st.markdown(f"**Slide**: {slide_id}  |  **Page**: {row.get('page_index', 'Unknown')}  |  **Layout**: {row.get('slide_layout', 'Unknown')}")
                                if row.get("source_path"):
                                    st.caption(f"Source: {row.get('source_path')}")

                                snippet = _short_text(row.get("text_content", ""))
                                if snippet:
                                    st.text_area(
                                        "Indexed content",
                                        value=snippet,
                                        height=120,
                                        key=f"snippet_{slide_id}_{rank}",
                                        label_visibility="collapsed",
                                    )

                                with st.expander("Index details", expanded=False):
                                    st.write({
                                        "slide_id": slide_id,
                                        "title": title,
                                        "page_index": row.get("page_index"),
                                        "slide_layout": row.get("slide_layout"),
                                        "source_path": row.get("source_path"),
                                        "shapes_count": row.get("shapes_count"),
                                        "has_notes": row.get("has_notes"),
                                    })
                                    if row.get("text_content"):
                                        st.code(row.get("text_content"), language="text")
                                
                            with col_action:
                                if st.button("View", key=f"view_{rank}", use_container_width=True):
                                    st.success(f"Loading: {slide_id}")
                            
                            st.divider()
                    
                    st.markdown("---")
                    st.subheader("Search Analytics")
                    
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    with col_stat1:
                        st.metric("Results Found", str(len(results)), delta="")
                    with col_stat2:
                        st.metric("Query Time", f"{elapsed:.2f}s", delta="")
                    with col_stat3:
                        st.metric("DB Table Checked", target_table, delta=f"{indexed_rows} indexed")
                    
                    scores = [r.score if hasattr(r, "score") else r.get("score", 0) for r in results]
                    if scores:
                        fig = go.Figure()
                        fig.add_trace(go.Bar(
                            y=scores,
                            marker=dict(color=scores, colorscale='RdYlGn', showscale=False),
                            name='Score'
                        ))
                        fig.update_layout(
                            title="Result Score Distribution",
                            yaxis_title="MaxSim Score",
                            xaxis_title="Result Rank",
                            height=300,
                            template='plotly_white',
                            margin=dict(l=0, r=0, t=30, b=0)
                        )
                        st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                import traceback
                st.error(f"Search failed: {e}")
                st.code(traceback.format_exc())
    
    elif search_button:
        st.warning("Please enter a search query")
    
    # Search examples
    st.markdown("---")
    st.subheader("💡 Example Queries")
    
    col_ex1, col_ex2, col_ex3 = st.columns(3)
    
    with col_ex1:
        if st.button("Deep Learning Architecture"):
            st.session_state.search_query = "Deep Learning Architecture"
            st.rerun()
    
    with col_ex2:
        if st.button("Financial Metrics Q3"):
            st.session_state.search_query = "Financial Metrics Q3"
            st.rerun()
    
    with col_ex3:
        if st.button("Team Organization"):
            st.session_state.search_query = "Team Organization"
            st.rerun()
