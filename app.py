"""Streamlit UI for the multi-agent PPT retrieval system."""

import streamlit as st
from datetime import datetime
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core.config import settings
from src.core.logging import logger


# Page configuration
st.set_page_config(
    page_title="DRL PPT Retrieval",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main {
        max-width: 1200px;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    """Main Streamlit application."""
    
    # Header
    st.title("🔍 DRL Multi-Modal PPT Retrieval System")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("Settings")
        
        # Mode selection
        mode = st.radio(
            "Select Search Mode",
            ["Text Search", "Image Search", "Multi-Modal"],
            index=2,
        )
        
        # Advanced options
        with st.expander("Advanced Options"):
            retrieval_mode = st.selectbox(
                "Retrieval Strategy",
                ["Hybrid (Vector + FTS)", "Vector-Only", "FTS-Only"],
            )
            
            top_k = st.slider(
                "Number of Results",
                min_value=1,
                max_value=50,
                value=10,
                step=1,
            )
            
            show_reasoning = st.checkbox(
                "Show Reasoning Process",
                value=True,
            )
            
            show_verification = st.checkbox(
                "Show Verification Details",
                value=True,
            )
        
        # System status
        st.markdown("---")
        st.subheader("System Status")
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Indexed Slides", "0")
        with col2:
            st.metric("Query Latency", "-- ms")
    
    # Main content area
    st.subheader("Search Query")
    
    # Search interface based on mode
    if mode == "Text Search":
        query = st.text_input(
            "Enter your search query",
            placeholder="e.g., machine learning in finance",
        )
        query_image = None
    
    elif mode == "Image Search":
        st.markdown("Upload an image for retrieval")
        query_image = st.file_uploader(
            "Choose an image",
            type=["jpg", "jpeg", "png"],
        )
        query = ""
    
    else:  # Multi-Modal
        col1, col2 = st.columns(2)
        
        with col1:
            query = st.text_input(
                "Enter text query (optional)",
                placeholder="e.g., machine learning",
            )
        
        with col2:
            query_image = st.file_uploader(
                "Upload reference image (optional)",
                type=["jpg", "jpeg", "png"],
            )
    
    # Search button
    st.markdown("---")
    search_btn = st.button("🔍 Search", use_container_width=True)
    
    # Search results
    if search_btn and (query or query_image):
        st.info("🔄 Searching... (System in development)")
        
        # Placeholder results
        st.subheader("Search Results")
        
        # Results container
        for i in range(3):
            with st.container(border=True):
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    st.markdown(f"**Slide #{i+1}**")
                    st.caption("Preview")
                
                with col2:
                    st.write(f"**Relevance Score:** 0.{85-i*5}")
                    st.caption("This is a placeholder for slide content preview")
                    
                    if show_reasoning:
                        with st.expander("📊 View Reasoning"):
                            st.write("""
                            **Chain-of-Thought Reasoning:**
                            1. Visual Perception: Detected relevant visual elements
                            2. Semantic Alignment: Matched query concepts
                            3. Deep Reasoning: Inferred complex relationships
                            4. Confidence: High confidence (0.92)
                            """)
                    
                    if show_verification:
                        with st.expander("✓ Verification Details"):
                            col_v1, col_v2, col_v3 = st.columns(3)
                            with col_v1:
                                st.metric("Status", "PASS", delta="✓")
                            with col_v2:
                                st.metric("Coverage", "98%")
                            with col_v3:
                                st.metric("Risk", "Low", delta_color="off")
                
                with col3:
                    st.button("📖 View Full Slide", key=f"slide_{i}")
        
        # Export results
        st.markdown("---")
        col_export1, col_export2, col_export3 = st.columns(3)
        with col_export1:
            st.download_button(
                "📥 Export as JSON",
                data="{}",
                file_name="results.json",
            )
        with col_export2:
            st.download_button(
                "📥 Export as CSV",
                data="",
                file_name="results.csv",
            )
        with col_export3:
            if st.button("📋 Copy Results"):
                st.success("Results copied to clipboard!")
    
    # Help section
    with st.expander("❓ Help & FAQ"):
        st.markdown("""
        ### Frequently Asked Questions
        
        **Q: What is Multi-Modal Search?**
        A: Multi-modal search combines text and image features to find relevant slides.
        
        **Q: How does the Reasoning Process work?**
        A: The system uses MM-R5 to generate explanations for why each slide is relevant.
        
        **Q: What does the Verification Status mean?**
        A: PASS = High confidence, WARN = Medium confidence, FAIL = Low confidence
        
        **Q: Can I search with just an image?**
        A: Yes! Select "Image Search" mode and upload your reference image.
        """)
    
    # Footer
    st.markdown("---")
    st.caption(
        "DRL Multi-Modal PPT Retrieval System v0.1.0 | "
        f"Built with ❤️ | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )


if __name__ == "__main__":
    main()
