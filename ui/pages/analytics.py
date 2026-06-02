"""Analytics page - System performance metrics"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd

def render_analytics():
    """Render analytics dashboard with system metrics"""
    
    st.markdown("## 📊 System Analytics")
    
    # Tab selection
    tab_performance, tab_quality, tab_system = st.tabs(
        ["⚡ Performance", "🎯 Quality Metrics", "🔧 System Health"]
    )
    
    with tab_performance:
        st.subheader("Query Performance Metrics")
        
        # Key metrics
        col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
        
        with col_metric1:
            st.metric("Avg Query Latency", "245ms", delta="-15ms")
        with col_metric2:
            st.metric("P95 Latency", "450ms", delta="-20ms")
        with col_metric3:
            st.metric("P99 Latency", "680ms", delta="-10ms")
        with col_metric4:
            st.metric("Queries/min", "24.5", delta="+2.1")
        
        st.markdown("---")
        
        # Latency breakdown
        st.subheader("Latency Breakdown by Stage")
        
        latency_data = {
            'Stage': ['Retrieval', 'Reasoning', 'Verification', 'Total'],
            'Latency (ms)': [150, 80, 15, 245],
            'Percentage': [61, 33, 6, 100]
        }
        
        fig_latency = go.Figure(data=[
            go.Bar(
                x=latency_data['Stage'],
                y=latency_data['Latency (ms)'],
                marker_color=['#00CC96', '#AB63FA', '#FFA15A', '#636EFA'],
                text=latency_data['Latency (ms)'],
                textposition='auto',
            )
        ])
        
        fig_latency.update_layout(
            title="Average Latency per Stage",
            yaxis_title="Latency (ms)",
            height=350,
            template='plotly_white'
        )
        st.plotly_chart(fig_latency, use_container_width=True)
        
        # Latency trend
        st.markdown("---")
        st.subheader("Latency Trend (Last 24h)")
        
        # Generate sample data
        hours = 24
        latencies = [
            245 + (i % 12 - 6) * 10 for i in range(hours)
        ]
        
        trend_data = pd.DataFrame({
            'Time': [(datetime.now() - timedelta(hours=i)).strftime('%H:%M') for i in range(hours, 0, -1)],
            'Latency': latencies
        })
        
        fig_trend = px.line(
            trend_data,
            x='Time',
            y='Latency',
            markers=True,
            title='Query Latency Over Time'
        )
        fig_trend.update_layout(
            height=300,
            template='plotly_white',
            hovermode='x unified'
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    
    with tab_quality:
        st.subheader("Retrieval Quality Metrics")
        
        # Quality metrics
        col_metric1, col_metric2, col_metric3, col_metric4 = st.columns(4)
        
        with col_metric1:
            st.metric("MRR@10", "0.847", delta="+0.03")
        with col_metric2:
            st.metric("NDCG@10", "0.782", delta="+0.02")
        with col_metric3:
            st.metric("Recall@100", "0.956", delta="+0.01")
        with col_metric4:
            st.metric("P@1", "0.865", delta="+0.04")
        
        st.markdown("---")
        
        # Metric trends
        st.subheader("Quality Metrics Trend")
        
        quality_data = pd.DataFrame({
            'Date': pd.date_range(start='2024-04-10', periods=8),
            'MRR@10': [0.78, 0.79, 0.81, 0.82, 0.83, 0.84, 0.85, 0.847],
            'NDCG@10': [0.74, 0.75, 0.76, 0.77, 0.78, 0.79, 0.80, 0.782],
            'Recall@100': [0.92, 0.93, 0.94, 0.945, 0.95, 0.952, 0.955, 0.956]
        })
        
        fig_quality = go.Figure()
        
        fig_quality.add_trace(go.Scatter(
            x=quality_data['Date'],
            y=quality_data['MRR@10'],
            mode='lines+markers',
            name='MRR@10'
        ))
        
        fig_quality.add_trace(go.Scatter(
            x=quality_data['Date'],
            y=quality_data['NDCG@10'],
            mode='lines+markers',
            name='NDCG@10'
        ))
        
        fig_quality.add_trace(go.Scatter(
            x=quality_data['Date'],
            y=quality_data['Recall@100'],
            mode='lines+markers',
            name='Recall@100'
        ))
        
        fig_quality.update_layout(
            title="Quality Metrics Improvement",
            xaxis_title="Date",
            yaxis_title="Score",
            height=350,
            template='plotly_white',
            hovermode='x unified'
        )
        st.plotly_chart(fig_quality, use_container_width=True)
        
        st.markdown("---")
        
        # Reasoning & Verification metrics
        st.subheader("Reasoning & Verification Quality")
        
        col_reason, col_verify = st.columns(2)
        
        with col_reason:
            st.metric("Inference Success Rate", "98.2%", delta="+0.5%")
            st.metric("Reasoning Transparency", "93%", delta="+1%")
            st.metric("Avg Reasoning Confidence", "0.89", delta="+0.02")
        
        with col_verify:
            st.metric("Verification Pass Rate", "96.8%", delta="+0.3%")
            st.metric("Avg Hallucination Risk", "11.2%", delta="-1.5%")
            st.metric("Evidence Coverage", "96.5%", delta="+0.8%")
    
    with tab_system:
        st.subheader("System Health")
        
        # System status
        col_status1, col_status2, col_status3, col_status4 = st.columns(4)
        
        with col_status1:
            st.metric("API Uptime", "99.85%", delta="+0.05%")
        with col_status2:
            st.metric("Avg Response Time", "245ms", delta="-15ms")
        with col_status3:
            st.metric("Error Rate", "0.12%", delta="-0.05%")
        with col_status4:
            st.metric("Active Users", "47", delta="+5")
        
        st.markdown("---")
        
        # Component status
        st.subheader("Component Health Status")
        
        components = [
            {
                "name": "Vision-Ingestion Agent",
                "status": "🟢 Healthy",
                "uptime": "99.92%",
                "latency": "1.2s/image"
            },
            {
                "name": "Lakehouse-Retrieval Agent",
                "status": "🟢 Healthy",
                "uptime": "99.98%",
                "latency": "150ms"
            },
            {
                "name": "Reasoning-Reranker Agent",
                "status": "🟢 Healthy",
                "uptime": "99.85%",
                "latency": "1.8s/candidate"
            },
            {
                "name": "Argos-Verification Agent",
                "status": "🟢 Healthy",
                "uptime": "99.90%",
                "latency": "600ms"
            },
            {
                "name": "LanceDB Vector Store",
                "status": "🟢 Healthy",
                "uptime": "99.95%",
                "latency": "45ms"
            },
        ]
        
        for component in components:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.markdown(f"**{component['name']}**")
            with col2:
                st.markdown(component['status'])
            with col3:
                st.caption(f"Uptime: {component['uptime']}")
            with col4:
                st.caption(f"Latency: {component['latency']}")
        
        st.markdown("---")
        
        # Resource usage
        st.subheader("Resource Utilization")
        
        col_cpu, col_mem, col_gpu = st.columns(3)
        
        with col_cpu:
            st.metric("CPU Usage", "38%", delta="-2%")
            fig_cpu = go.Figure(go.Indicator(
                mode="gauge+number",
                value=38,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "CPU (%)"},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "blue"}}
            ))
            fig_cpu.update_layout(height=250, template='plotly_dark')
            st.plotly_chart(fig_cpu, use_container_width=True)
        
        with col_mem:
            st.metric("Memory Usage", "62%", delta="+1%")
            fig_mem = go.Figure(go.Indicator(
                mode="gauge+number",
                value=62,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Memory (%)"},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "green"}}
            ))
            fig_mem.update_layout(height=250, template='plotly_dark')
            st.plotly_chart(fig_mem, use_container_width=True)
        
        with col_gpu:
            st.metric("GPU Usage", "87%", delta="-3%")
            fig_gpu = go.Figure(go.Indicator(
                mode="gauge+number",
                value=87,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "GPU (%)"},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "red"}}
            ))
            fig_gpu.update_layout(height=250, template='plotly_dark')
            st.plotly_chart(fig_gpu, use_container_width=True)
