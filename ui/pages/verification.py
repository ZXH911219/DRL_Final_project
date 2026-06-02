"""Verification page - Display evidence maps and hallucination detection"""

import streamlit as st
import plotly.graph_objects as go
from PIL import Image, ImageDraw
import numpy as np

def generate_evidence_map():
    """Generate a mock evidence map image"""
    # Create a simple image to represent a slide
    width, height = 800, 600
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Draw slide structure
    draw.rectangle([20, 20, 780, 100], outline='black', width=2)  # Title
    draw.text((40, 50), "Machine Learning Overview", fill='black')
    
    draw.rectangle([20, 120, 780, 350], outline='blue', width=2, fill=(220, 240, 255))  # Content
    draw.text((40, 250), "Diagram & Content Area", fill='black')
    
    draw.rectangle([20, 370, 780, 580], outline='green', width=2, fill=(220, 255, 220))  # Footer
    draw.text((40, 470), "Additional Information", fill='black')
    
    # Draw evidence highlight boxes
    colors = [
        (100, 200, 100),  # Green - strong evidence
        (100, 150, 255),  # Blue - medium evidence
        (255, 200, 100),  # Orange - weak evidence
    ]
    
    highlights = [
        (25, 25, 75, 95, "Title", 0),
        (25, 125, 350, 345, "Diagram", 1),
        (360, 125, 775, 345, "Content", 1),
        (25, 375, 775, 575, "Evidence", 0),
    ]
    
    for x1, y1, x2, y2, label, color_idx in highlights:
        # Draw semi-transparent highlight
        overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle([x1, y1, x2, y2], fill=(*colors[color_idx], 80))
        img = Image.alpha_composite(img.convert('RGBA'), overlay).convert('RGB')
    
    return img

def render_verification():
    """Render verification page with evidence maps and hallucination detection"""
    
    st.markdown("## ✅ Verification & Evidence")
    
    # Tabs for different verification aspects
    tab_evidence, tab_hallucination, tab_audit = st.tabs(
        ["📍 Evidence Map", "🚨 Hallucination Detection", "📋 Audit Trail"]
    )
    
    with tab_evidence:
        st.subheader("Evidence Visualization")
        
        # Display evidence map
        col_map, col_regions = st.columns([2, 1])
        
        with col_map:
            st.info("**Evidence Map**: Green = Strong | Blue = Medium | Orange = Weak")
            img = generate_evidence_map()
            st.image(img)
        
        with col_regions:
            st.markdown("**Identified Regions:**")
            
            regions = [
                {"name": "Title", "type": "Text", "confidence": 0.98, "color": "green"},
                {"name": "Diagram", "type": "Image", "confidence": 0.85, "color": "blue"},
                {"name": "Content", "type": "Text", "confidence": 0.92, "color": "green"},
                {"name": "Evidence", "type": "Mixed", "confidence": 0.88, "color": "blue"},
            ]
            
            for region in regions:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{region['name']}** ({region['type']})")
                with col2:
                    st.markdown(f"`{region['confidence']:.0%}`")
        
        st.markdown("---")
        
        # Coverage metrics
        st.subheader("Coverage Metrics")
        
        col_cov1, col_cov2, col_cov3, col_cov4 = st.columns(4)
        
        with col_cov1:
            st.metric("Visual Coverage", "98%", delta="+2%")
        with col_cov2:
            st.metric("Text Coverage", "95%", delta="+1%")
        with col_cov3:
            st.metric("Overall Coverage", "96.5%", delta="")
        with col_cov4:
            st.metric("Threshold", "88%", delta="")
        
        # Coverage breakdown
        fig_coverage = go.Figure(data=[
            go.Scatterpolar(
                r=[98, 95, 92, 88, 96.5],
                theta=['Visual', 'Text', 'Evidence', 'Threshold', 'Overall'],
                fill='toself',
                name='Coverage'
            )
        ])
        
        fig_coverage.update_layout(
            title="Coverage by Category",
            height=400,
            template='plotly_dark'
        )
        st.plotly_chart(fig_coverage, use_container_width=True)
    
    with tab_hallucination:
        st.subheader("Hallucination Risk Assessment")
        
        # Risk gauge
        col_gauge, col_details = st.columns([1, 1])
        
        with col_gauge:
            st.info("""
            **Hallucination Risk: Low (8%)**
            
            ✅ Within acceptable threshold
            """)
            
            # Risk gauge
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=8,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Risk Score (%)"},
                delta={'reference': 15},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 15], 'color': "lightgreen"},
                        {'range': [15, 45], 'color': "lightyellow"},
                        {'range': [45, 100], 'color': "lightcoral"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 45
                    }
                }
            ))
            fig_gauge.update_layout(height=300, template='plotly_dark')
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        with col_details:
            st.markdown("**Risk Components:**")
            
            risk_components = [
                {"name": "Evidence Gap", "value": 2, "severity": "🟢"},
                {"name": "Semantic Mismatch", "value": 1, "severity": "🟢"},
                {"name": "Unreferenced Claims", "value": 5, "severity": "🟡"},
                {"name": "Overall Risk", "value": 8, "severity": "🟢"},
            ]
            
            for component in risk_components:
                st.markdown(
                    f"{component['severity']} **{component['name']}**: {component['value']}%"
                )
        
        st.markdown("---")
        
        # Verified vs Unverified Claims
        st.subheader("Claim Verification Status")
        
        verified = [
            "✓ Title contains 'Machine Learning'",
            "✓ Slide includes visual diagrams",
            "✓ Content discusses applications",
            "✓ Evidence regions identified",
        ]
        
        unverified = [
            "? Specific use case mentioned",
        ]
        
        col_verified, col_unverified = st.columns(2)
        
        with col_verified:
            st.markdown("**✅ Verified Claims** (96%)")
            for claim in verified:
                st.success(claim)
        
        with col_unverified:
            st.markdown("**❓ Unverified Claims** (4%)")
            for claim in unverified:
                st.warning(claim)
    
    with tab_audit:
        st.subheader("Verification Audit Trail")
        
        # Audit log
        audit_log = [
            {
                "timestamp": "2024-04-17 10:23:45",
                "action": "Visual Grounding",
                "status": "✅ PASS",
                "details": "Located 4 evidence regions"
            },
            {
                "timestamp": "2024-04-17 10:23:46",
                "action": "Consistency Check",
                "status": "✅ PASS",
                "details": "Semantic alignment: 92%"
            },
            {
                "timestamp": "2024-04-17 10:23:47",
                "action": "Hallucination Detection",
                "status": "✅ PASS",
                "details": "Risk score: 8% (LOW)"
            },
            {
                "timestamp": "2024-04-17 10:23:48",
                "action": "Evidence Mapping",
                "status": "✅ PASS",
                "details": "Coverage: 96.5%"
            },
            {
                "timestamp": "2024-04-17 10:23:49",
                "action": "Final Verdict",
                "status": "✅ VERIFIED",
                "details": "Ready for user display"
            },
        ]
        
        for log_entry in audit_log:
            with st.expander(f"{log_entry['status']} {log_entry['action']}"):
                col_time, col_details = st.columns([1, 2])
                
                with col_time:
                    st.caption(log_entry['timestamp'])
                
                with col_details:
                    st.markdown(f"**{log_entry['details']}**")
        
        st.markdown("---")
        
        # Summary
        st.success("""
        **✅ Verification Complete**
        
        - Status: PASSED
        - Evidence Coverage: 96.5%
        - Hallucination Risk: 8% (LOW)
        - Confidence: HIGH
        """)
