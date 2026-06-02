"""Home page - System overview and statistics"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

def render_home():
    """Render home page with system overview"""
    
    st.markdown("## 🏠 System Overview")
    
    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total PPTs", "0", delta="Today", delta_color="off")
    with col2:
        st.metric("Total Queries", "0", delta="This week", delta_color="off")
    with col3:
        st.metric("Avg Latency", "0 ms", delta="↓ 5%", delta_color="inverse")
    with col4:
        st.metric("System Health", "✅ 99.9%", delta="", delta_color="off")
    
    st.markdown("---")
    
    # Two column layout
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.subheader("📊 Query Performance Trend")
        
        # Mock data
        dates = [(datetime.now() - timedelta(days=i)).strftime('%m-%d') for i in range(7)][::-1]
        latencies = [145 + np.random.randint(-20, 20) for _ in dates]
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=dates, y=latencies,
            mode='lines+markers',
            name='Avg Latency (ms)',
            line=dict(color='#2E86AB', width=3),
            marker=dict(size=8),
        ))
        fig.update_layout(
            height=350,
            template='plotly_white',
            hovermode='x unified',
            margin=dict(l=0, r=0, t=0, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col_right:
        st.subheader("🎯 Feature Distribution")
        
        features = ['ColPali\nExtraction', 'MaxSim\nRetrieval', 'MM-R5\nReasoning', 'Argos\nVerification']
        usage_pct = [28, 25, 32, 15]
        colors = ['#2E86AB', '#A23B72', '#06A77D', '#F18F01']
        
        fig = go.Figure(data=[go.Pie(
            labels=features,
            values=usage_pct,
            marker=dict(colors=colors),
            textposition='inside',
            textinfo='label+percent',
        )])
        fig.update_layout(
            height=350,
            template='plotly_white',
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Recent activity
    st.subheader("📝 Recent Activity")
    
    with st.expander("View Activity Log", expanded=False):
        activities = [
            ("System initialized", "🟢 Success", "Just now"),
            ("Test suite passed (87/87)", "🟢 Success", "5 minutes ago"),
            ("Docker images built", "🟢 Success", "10 minutes ago"),
            ("Configuration loaded", "🟢 Success", "15 minutes ago"),
        ]
        
        for activity, status, time in activities:
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.caption(activity)
            with col2:
                st.caption(status)
            with col3:
                st.caption(time)
            st.divider()
    
    st.markdown("---")
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📤 Upload PPT", use_container_width=True):
            st.switch_page("pages/upload.py")
    with col2:
        if st.button("🔎 Search", use_container_width=True):
            st.switch_page("pages/search.py")
    with col3:
        if st.button("📊 Analytics", use_container_width=True):
            st.switch_page("pages/analytics.py")
    with col4:
        if st.button("⚙️ Settings", use_container_width=True):
            st.switch_page("pages/settings.py")
    
    # Feature highlights
    st.markdown("---")
    st.subheader("✨ Key Features")
    
    feat_col1, feat_col2, feat_col3 = st.columns(3)
    
    with feat_col1:
        st.markdown("""
        ### 🎯 Vision Ingestion
        - Extracts 1024×128 multi-vectors
        - ColPali-based feature extraction
        - 600 DPI image rendering
        - ImageBind multimodal alignment
        """)
    
    with feat_col2:
        st.markdown("""
        ### 🔍 Smart Retrieval
        - Two-stage MaxSim ranking
        - Sub-200ms latency
        - Full-text search support
        - >95% recall rate
        """)
    
    with feat_col3:
        st.markdown("""
        ### 🧠 Intelligent Reasoning
        - 5-step chain-of-thought
        - MM-R5 inference engine
        - Confidence scoring
        - Interpretable results
        """)
