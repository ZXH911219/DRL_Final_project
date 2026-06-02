"""Settings page - System and user preferences"""

import streamlit as st
import json

def render_settings():
    """Render settings page with system and user preferences"""
    
    st.markdown("## ⚙️ Settings")
    
    # Tab selection
    tab_general, tab_retrieval, tab_reasoning, tab_verification, tab_advanced = st.tabs(
        ["General", "Retrieval", "Reasoning", "Verification", "Advanced"]
    )
    
    with tab_general:
        st.subheader("General Settings")
        
        # Language preference
        language = st.selectbox(
            "Language Preference",
            ["English", "中文 (Chinese)", "日本語 (Japanese)"],
            index=0
        )
        
        # Theme
        theme = st.radio(
            "Display Theme",
            ["Light", "Dark", "Auto"],
            horizontal=True
        )
        
        # Results per page
        results_per_page = st.slider(
            "Results per page",
            min_value=5,
            max_value=50,
            value=20,
            step=5
        )
        
        # Auto-refresh
        col1, col2 = st.columns(2)
        
        with col1:
            auto_refresh = st.checkbox("Enable auto-refresh", value=True)
        
        with col2:
            if auto_refresh:
                refresh_interval = st.number_input(
                    "Refresh interval (seconds)",
                    min_value=5,
                    max_value=300,
                    value=30
                )
        
        st.markdown("---")
        
        # User profile
        st.subheader("User Profile")
        
        col1, col2 = st.columns(2)
        
        with col1:
            user_name = st.text_input("Display Name", value="John Doe")
        
        with col2:
            user_email = st.text_input("Email", value="user@example.com")
    
    with tab_retrieval:
        st.subheader("Retrieval Settings")
        
        # Stage 1 settings
        st.markdown("**Stage 1: Vector Filtering**")
        
        k1_candidates = st.slider(
            "Number of candidates from vector filtering (K1)",
            min_value=100,
            max_value=1000,
            value=500,
            step=100
        )
        
        filtering_method = st.selectbox(
            "Filtering method",
            ["IVF (Inverted File Index)", "LSH (Locality Sensitive Hashing)"],
            index=0
        )
        
        st.markdown("---")
        
        # Stage 2 settings
        st.markdown("**Stage 2: MaxSim Reranking**")
        
        k2_results = st.slider(
            "Final results after MaxSim (K2)",
            min_value=5,
            max_value=50,
            value=20,
            step=5
        )
        
        maxsim_aggregation = st.selectbox(
            "MaxSim aggregation method",
            ["Mean", "Weighted", "Max"],
            index=0
        )
        
        st.markdown("---")
        
        # Hybrid retrieval
        st.markdown("**Hybrid Retrieval**")
        
        enable_fts = st.checkbox("Enable Full-Text Search (FTS) filtering", value=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            fts_weight = st.slider("FTS weight", 0.0, 1.0, 0.3, 0.1)
        
        with col2:
            vector_weight = st.slider("Vector weight", 0.0, 1.0, 0.7, 0.1)
        
        # Validate weights
        if abs(fts_weight + vector_weight - 1.0) > 0.01:
            st.warning(f"Weights sum to {fts_weight + vector_weight:.1f}, should be 1.0")
    
    with tab_reasoning:
        st.subheader("Reasoning Settings")
        
        # Model settings
        st.markdown("**Model Configuration**")
        
        reasoning_model = st.selectbox(
            "Reasoning Model",
            ["MM-R5 (Recommended)", "GPT-4 Vision", "Claude-3 Vision"],
            index=0
        )
        
        temperature = st.slider(
            "Temperature (Creativity)",
            min_value=0.0,
            max_value=1.0,
            value=0.7,
            step=0.1
        )
        
        max_reasoning_steps = st.slider(
            "Max reasoning steps",
            min_value=3,
            max_value=10,
            value=5,
            step=1
        )
        
        st.markdown("---")
        
        # Scoring weights
        st.markdown("**Reasoning Score Composition**")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            retrieval_weight = st.number_input("Retrieval weight", value=0.4, min_value=0.0, max_value=1.0, step=0.1)
        
        with col2:
            reasoning_weight = st.number_input("Reasoning weight", value=0.4, min_value=0.0, max_value=1.0, step=0.1)
        
        with col3:
            completeness_weight = st.number_input("Completeness weight", value=0.2, min_value=0.0, max_value=1.0, step=0.1)
        
        # Validate weights
        total_weight = retrieval_weight + reasoning_weight + completeness_weight
        if abs(total_weight - 1.0) > 0.01:
            st.warning(f"Weights sum to {total_weight:.1f}, should be 1.0")
        
        st.markdown("---")
        
        # Inference settings
        st.markdown("**Inference Settings**")
        
        reasoning_timeout = st.number_input(
            "Reasoning timeout (seconds)",
            min_value=1,
            max_value=60,
            value=10
        )
        
        batch_reasoning = st.checkbox("Enable batch reasoning for multiple results", value=True)
        
        if batch_reasoning:
            batch_size = st.number_input("Batch size", min_value=1, max_value=20, value=5)
    
    with tab_verification:
        st.subheader("Verification Settings")
        
        # Hallucination detection
        st.markdown("**Hallucination Detection**")
        
        enable_verification = st.checkbox("Enable verification", value=True)
        
        hallucination_threshold = st.slider(
            "Hallucination risk threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.45,
            step=0.05,
            help="Results with risk above this threshold will be flagged"
        )
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            evidence_gap_weight = st.number_input("Evidence gap weight", value=0.4, min_value=0.0, max_value=1.0, step=0.1)
        
        with col2:
            semantic_weight = st.number_input("Semantic mismatch weight", value=0.35, min_value=0.0, max_value=1.0, step=0.1)
        
        with col3:
            unreferenced_weight = st.number_input("Unreferenced claims weight", value=0.25, min_value=0.0, max_value=1.0, step=0.1)
        
        st.markdown("---")
        
        # Evidence settings
        st.markdown("**Evidence Mapping**")
        
        evidence_coverage_threshold = st.slider(
            "Minimum evidence coverage",
            min_value=0.0,
            max_value=1.0,
            value=0.88,
            step=0.05
        )
        
        visualize_evidence = st.checkbox("Generate visual evidence maps", value=True)
        
        st.markdown("---")
        
        # Risk actions
        st.markdown("**Risk Actions**")
        
        low_risk_action = st.selectbox(
            "Low risk results (< 15%):",
            ["Accept", "Flag for review"],
            index=0
        )
        
        medium_risk_action = st.selectbox(
            "Medium risk results (15-45%):",
            ["Flag for review", "Reject"],
            index=0
        )
        
        high_risk_action = st.selectbox(
            "High risk results (> 45%):",
            ["Reject", "Flag for review"],
            index=0
        )
    
    with tab_advanced:
        st.subheader("Advanced Settings")
        
        # API settings
        st.markdown("**API Configuration**")
        
        api_endpoint = st.text_input(
            "API Endpoint",
            value="http://localhost:8000/api",
            help="Backend API endpoint URL"
        )
        
        api_timeout = st.number_input(
            "API timeout (seconds)",
            min_value=5,
            max_value=300,
            value=30
        )
        
        st.markdown("---")
        
        # Database settings
        st.markdown("**Database Configuration**")
        
        lancedb_path = st.text_input(
            "LanceDB path",
            value="/data/lancedb",
            help="Path to LanceDB vector store"
        )
        
        cache_enabled = st.checkbox("Enable caching", value=True)
        
        if cache_enabled:
            cache_duration = st.number_input(
                "Cache duration (minutes)",
                min_value=1,
                max_value=1440,
                value=60
            )
        
        st.markdown("---")
        
        # Logging
        st.markdown("**Logging & Debugging**")
        
        log_level = st.selectbox(
            "Log level",
            ["INFO", "DEBUG", "WARNING", "ERROR"],
            index=0
        )
        
        enable_debug = st.checkbox("Enable debug mode", value=False)
        
        save_audit_logs = st.checkbox("Save audit logs", value=True)
        
        st.markdown("---")
        
        # Export/Import settings
        st.subheader("Backup & Import")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📥 Export Settings"):
                settings = {
                    "general": {"language": language, "theme": theme},
                    "retrieval": {"k1": k1_candidates, "k2": k2_results},
                    "reasoning": {"temperature": temperature},
                    "verification": {"hallucination_threshold": hallucination_threshold}
                }
                st.json(settings)
                st.download_button(
                    "Download Settings JSON",
                    json.dumps(settings, indent=2),
                    file_name="drl_settings.json"
                )
        
        with col2:
            if st.button("📤 Import Settings"):
                st.info("Upload a settings JSON file to import")
                uploaded_file = st.file_uploader("Choose a settings file", type="json")
                if uploaded_file:
                    st.success("Settings imported successfully!")
    
    # Save settings button
    st.markdown("---")
    
    col_save, col_reset = st.columns(2)
    
    with col_save:
        if st.button("✅ Save Settings", use_container_width=True, key="save_settings"):
            st.success("✅ Settings saved successfully!")
    
    with col_reset:
        if st.button("🔄 Reset to Defaults", use_container_width=True, key="reset_settings"):
            st.warning("⚠️ Settings reset to defaults")
