"""Upload & Process page - PPT ingestion and processing"""

import streamlit as st
from pathlib import Path

import tempfile
import time
from src.agents.vision_ingestion.agent import get_vision_agent


def _upsert_recent_upload(name: str, slides: int, status: str, date: str = "Just now") -> None:
    """Store the latest upload attempts in session state."""
    recent_uploads = st.session_state.get("recent_uploads", [])
    filtered_uploads = [item for item in recent_uploads if item.get("name") != name]
    filtered_uploads.insert(
        0,
        {
            "name": name,
            "slides": slides,
            "date": date,
            "status": status,
        },
    )
    st.session_state.recent_uploads = filtered_uploads[:5]

def render_upload():
    """Render upload and processing page"""
    
    st.markdown("## 📤 Upload & Process PPT Files")
    
    # Upload section
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Upload PPT File")
        
        uploaded_file = st.file_uploader(
            "Choose a PPT file",
            type=["pptx", "ppt", "odp"],
            help="Maximum file size: 200MB"
        )
        
        if uploaded_file:
            _upsert_recent_upload(uploaded_file.name, 0, "Selected")
            st.success(f"✅ File selected: {uploaded_file.name}")
            st.info(f"File size: {uploaded_file.size / 1024 / 1024:.2f} MB")
            
            # Processing options
            st.subheader("Processing Options")
            col_opt1, col_opt2 = st.columns(2)
            
            with col_opt1:
                dpi = st.slider("Image DPI", 72, 600, 300)
                extract_text = st.checkbox("Extract Text with OCR", value=True)
            
            with col_opt2:
                quantization = st.selectbox("Vector Quantization", ["None", "8-bit", "4-bit"])
                batch_size = st.number_input("Batch Size", 1, 64, 8)
            
            # Process button
            if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                progress_bar = st.progress(0)
                status_text = st.empty()
                with st.spinner("Processing PPT file... / 正在處理 PPT 檔案..."):
                    try:
                        import tempfile
                        import time
                        from pathlib import Path
                        
                        start_time = time.time()
                        status_text.text("⏳ [1/4] 儲存上傳的檔案...")
                        progress_bar.progress(10)
                        
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tf:
                            tf.write(uploaded_file.getvalue())
                            temp_path = tf.name
                        
                        status_text.text("🧠 [2/4] 初始化視覺攝取代理 (Vision Ingestion Agent)...")
                        progress_bar.progress(30)
                        
                        status_text.text("⚡ [3/4] 執行 ColPali 向量化提取與多模態對齊...")
                        progress_bar.progress(60)
                        
                        result = get_vision_agent().ingest_ppt(
                            ppt_path=temp_path,
                            batch_id=uploaded_file.name,
                            store_images=False
                        )
                        
                        Path(temp_path).unlink(missing_ok=True)
                        progress_bar.progress(90)
                        
                        elapsed = time.time() - start_time
                        
                        if result.get("success", False):
                            progress_bar.progress(100)
                            status_text.text("✅ [4/4] 處理完成！")
                            st.success(f"🎉 處理完成，總耗時 {elapsed:.1f} 秒")
                            st.balloons()

                            _upsert_recent_upload(
                                uploaded_file.name,
                                result.get("slides_processed", 0),
                                "Processed",
                            )
                            
                            slides_processed = result.get('slides_processed', 0)
                            features_cnt = slides_processed * 1024
                            
                            st.markdown("### 📊 處理摘要 (Processing Summary)")
                            col_r1, col_r2, col_r3 = st.columns(3)
                            with col_r1:
                                st.metric("簡報頁數", str(slides_processed))
                            with col_r2:
                                st.metric("特徵數量", f"{features_cnt:,}", delta="1024x128維度")
                            with col_r3:
                                st.metric("處理耗時", f"{elapsed:.1f}s")
                            
                            st.info("✅ PPT 已成功建立索引！您現在可以至 Search 頁面進行跨模態檢索。")
                        else:
                            _upsert_recent_upload(
                                uploaded_file.name,
                                result.get("slides_processed", 0),
                                "Failed",
                            )
                            st.error(f"❌ 處理失敗: {result.get('errors')}")
                            
                    except Exception as e:
                        _upsert_recent_upload(uploaded_file.name, 0, "Error")
                        import traceback
                        st.error(f"❌ 處理過程中發生錯誤: {str(e)}")
                        st.code(traceback.format_exc())
    
    with col2:
        st.subheader("Processing Status")
        
        with st.expander("View Processing Pipeline", expanded=True):
            st.markdown("""
            #### Step-by-Step Processing:
            
            1️⃣ **PPT Parsing**
            - Extract slides metadata
            - Parse layout information
            - Extract embedded images
            
            2️⃣ **Image Rendering**
            - Convert slides to PNG/JPG
            - Apply normalization
            - Verify quality
            
            3️⃣ **Feature Extraction**
            - ColPali model inference
            - Generate 1024×128 vectors
            - Confidence scoring
            
            4️⃣ **Multimodal Alignment**
            - ImageBind encoding
            - Vector space alignment
            - Cross-modality linking
            
            5️⃣ **Index & Store**
            - LanceDB vector storage
            - PostgreSQL metadata
            - Redis cache update
            """)
        
        # Recent uploads
        st.subheader("Recent Uploads")
        uploads = st.session_state.get("recent_uploads", [])

        if not uploads:
            st.info("尚無最近上傳紀錄。請先上傳並處理 PPT。")
        
        for upload in uploads:
            with st.expander(f"📄 {upload['name']}"):
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.metric("Slides", upload['slides'])
                with col_u2:
                    st.caption(f"Uploaded {upload['date']}")
                st.caption(f"Status: {upload.get('status', 'Unknown')}")
                
                if st.button(f"Use this PPT", key=f"use_{upload['name']}"):
                    st.success(f"Selected: {upload['name']}")
    
    st.markdown("---")
    
    # Batch processing
    st.subheader("Batch Processing")
    
    batch_mode = st.radio(
        "Batch Mode",
        ["Single File", "Multiple Files", "Folder"],
        horizontal=True,
    )
    
    if batch_mode == "Multiple Files":
        st.info("📁 Select multiple PPT files for batch processing")
    elif batch_mode == "Folder":
        folder_path = st.text_input("Folder path (for automated processing)")
        if folder_path and st.button("Scan Folder"):
            st.info(f"Would scan: {folder_path}")
