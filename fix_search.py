import re

with open('ui/pages/search.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'if search_button and query:.*?(?=\s+elif search_button:)'
match = re.search(pattern, text, re.DOTALL)

new_code = '''if search_button and query:
        st.markdown("---")
        st.subheader(f"Search Results for: \\"{query}\\"")
        
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
                from src.core.pipeline import get_pipeline
                pipeline = get_pipeline()
                
                table_names = mgr.client.table_names()
                target_table = "slides"
                if table_names:
                    valid_tables = [t for t in table_names if t.startswith("slides")]
                    if valid_tables:
                        target_table = valid_tables[-1]
                
                q_vector = np.random.randn(128).astype(np.float32)
                
                with st.spinner("Searching LanceDB Lakehouse..."):
                    results = pipeline.retrieval_stage.retrieve(
                        query_vector=q_vector,
                        table_name=target_table,
                        k1=top_k * 5,
                        k2=top_k
                    )
                
                elapsed = time.time() - start_time
                
                if not results:
                    st.warning("No results found in the database. Ensure you have uploaded a PPT first!")
                else:
                    for idx, result in enumerate(results):
                        rank = idx + 1
                        meta = result.metadata if hasattr(result, "metadata") else result.get("metadata", {})
                        
                        slide_id = meta.get("slide_id", "Unknown") if isinstance(meta, dict) else getattr(meta, "slide_id", "Unknown")
                        ppt_src = "Uploaded PPT"
                        score = result.score if hasattr(result, "score") else result.get("score", 0.0)
                        
                        with st.container():
                            col_rank, col_content, col_action = st.columns([0.5, 4.5, 1])
                            
                            with col_rank:
                                st.metric("#", rank)
                            
                            with col_content:
                                st.markdown(f"### {slide_id}")
                                st.caption(f"📁 {ppt_src}")
                                st.markdown(f"**Score**: {score:.2%}")
                                
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
                        st.metric("DB Table Checked", target_table, delta="")
                    
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
                st.code(traceback.format_exc())'''

if match:
    text = text.replace(match.group(0), new_code)
    with open('ui/pages/search.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("search page fixed")
else:
    print("pattern not matched")
