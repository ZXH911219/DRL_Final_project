"""Reasoning page - Display 5-step reasoning chains"""

import streamlit as st
import plotly.graph_objects as go

def render_reasoning():
    """Render reasoning page with chain-of-thought visualization"""
    
    st.markdown("## 🧠 Reasoning Analysis")
    
    # Select a result to analyze
    col_select, col_refresh = st.columns([4, 1])
    
    with col_select:
        selected_result = st.selectbox(
            "Select result to analyze",
            [
                "Machine Learning Overview (Score: 0.94)",
                "Real-World Applications (Score: 0.87)",
                "Industry Use Cases (Score: 0.81)",
            ],
            label_visibility="collapsed"
        )
    
    with col_refresh:
        if st.button("🔄 Regenerate", use_container_width=True):
            st.rerun()
    
    st.markdown("---")
    
    # 5-Step Reasoning Chain
    st.subheader("📊 5-Step Chain-of-Thought Reasoning")
    
    reasoning_steps = [
        {
            "step": 1,
            "title": "Visual Perception",
            "description": "Analysis of slide visual elements",
            "confidence": 0.95,
            "findings": [
                "✓ Detected title: 'Machine Learning Overview'",
                "✓ Found 2 key diagrams",
                "✓ 3 paragraphs of text content",
            ],
            "emoji": "👁️"
        },
        {
            "step": 2,
            "title": "Query Understanding",
            "description": "Parse and understand user query",
            "confidence": 0.92,
            "findings": [
                "✓ Primary concept: 'Machine Learning'",
                "✓ Secondary: 'Applications'",
                "✓ Intent: Find use case examples",
            ],
            "emoji": "🎯"
        },
        {
            "step": 3,
            "title": "Semantic Alignment",
            "description": "Match query with slide content",
            "confidence": 0.88,
            "findings": [
                "✓ Title alignment: 89% match",
                "✓ Content alignment: 85% match",
                "✓ Concept coverage: Complete",
            ],
            "emoji": "🔗"
        },
        {
            "step": 4,
            "title": "Deep Reasoning",
            "description": "Infer relationships and relevance",
            "confidence": 0.91,
            "findings": [
                "✓ Slide demonstrates ML fundamentals",
                "✓ Provides practical context",
                "✓ Highly relevant to query intent",
            ],
            "emoji": "💡"
        },
        {
            "step": 5,
            "title": "Confidence Assessment",
            "description": "Final confidence and recommendation",
            "confidence": 0.94,
            "findings": [
                "✓ Overall relevance: VERY HIGH",
                "✓ Recommendation: STRONG MATCH",
                "✓ Rank position: #1",
            ],
            "emoji": "✅"
        },
    ]
    
    # Visualize steps
    for step_info in reasoning_steps:
        with st.expander(
            f"{step_info['emoji']} Step {step_info['step']}: {step_info['title']}",
            expanded=(step_info['step'] == 1)
        ):
            col_desc, col_conf = st.columns([3, 1])
            
            with col_desc:
                st.caption(step_info['description'])
                
                # Findings
                st.markdown("**Key Findings:**")
                for finding in step_info['findings']:
                    st.markdown(f"  {finding}")
            
            with col_conf:
                st.metric("Confidence", f"{step_info['confidence']:.0%}")
                
                # Progress bar
                st.progress(step_info['confidence'])
    
    st.markdown("---")
    
    # Overall reasoning score
    st.subheader("📈 Reasoning Score Breakdown")
    
    col_score1, col_score2, col_score3, col_score4 = st.columns(4)
    
    with col_score1:
        st.metric("Retrieval Score", "0.87", delta="")
    with col_score2:
        st.metric("Reasoning Score", "0.92", delta="")
    with col_score3:
        st.metric("Confidence", "0.94", delta="")
    with col_score4:
        st.metric("Final Rank", "1/247", delta="")
    
    # Final score composition
    st.markdown("---")
    st.subheader("Score Composition")
    
    fig = go.Figure(data=[
        go.Bar(name='Retrieval', x=['Score Weight'], y=[40]),
        go.Bar(name='Reasoning', x=['Score Weight'], y=[40]),
        go.Bar(name='Verification', x=['Score Weight'], y=[20]),
    ])
    
    fig.update_layout(
        barmode='stack',
        showlegend=True,
        height=300,
        template='plotly_white',
        yaxis_title="Weight (%)",
        margin=dict(l=0, r=0, t=0, b=0)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # Key insights
    st.markdown("---")
    st.subheader("🔑 Key Insights")
    
    insight1, insight2, insight3 = st.columns(3)
    
    with insight1:
        st.info("""
        **Strong Alignment**
        
        Query concepts match slide content perfectly, indicating a highly relevant result.
        """)
    
    with insight2:
        st.success("""
        **Clear Evidence**
        
        Multiple evidence points support the reasoning conclusion with high confidence.
        """)
    
    with insight3:
        st.warning("""
        **Minor Gap**
        
        Slide could benefit from explicit examples matching the specific query context.
        """)

    st.markdown("---")
    st.subheader("📊 信心度多維度分析 (Confidence Radar)")
    
    categories = [step['title'] for step in reasoning_steps]
    confidences = [step['confidence'] for step in reasoning_steps]
    
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=confidences + [confidences[0]], 
        theta=categories + [categories[0]],
        fill='toself',
        line_color='#A23B72'
    ))
    fig_radar.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1])
        ),
        showlegend=False,
        height=400,
        margin=dict(l=40, r=40, t=20, b=20)
    )
    st.plotly_chart(fig_radar, use_container_width=True)
