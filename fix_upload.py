import re

with open('ui/pages/upload.py', 'r', encoding='utf-8') as f:
    text = f.read()

pattern = r'# Process button.*?You can now search across its content\.\"\)'
match = re.search(pattern, text, re.DOTALL)
if match:
    old_text = match.group(0)
    new_text = '''# Process button
            if st.button("🚀 Start Processing", type="primary", use_container_width=True):
                with st.spinner("Processing PPT file..."):
                    try:
                        import tempfile
                        import time
                        from pathlib import Path
                        
                        start_time = time.time()
                        # Save uploaded file
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pptx") as tf:
                            tf.write(uploaded_file.getvalue())
                            temp_path = tf.name
                        
                        st.write("Initializing model ingestion pipeline...")
                        
                        result = get_vision_agent().ingest_ppt(
                            ppt_path=temp_path,
                            batch_id=uploaded_file.name,
                            store_images=False
                        )
                        
                        Path(temp_path).unlink(missing_ok=True)
                        
                        elapsed = time.time() - start_time
                        
                        if result.get("success", False):
                            st.success(f"✅ Processing completed in {elapsed:.1f}s")
                            st.balloons()
                            
                            slides_processed = result.get('slides_processed', 0)
                            features_cnt = slides_processed * 1024
                            
                            st.markdown("### Processing Summary")
                            col_r1, col_r2, col_r3 = st.columns(3)
                            with col_r1:
                                st.metric("Slides", str(slides_processed), delta="")
                            with col_r2:
                                st.metric("Features", f"{features_cnt:,}", delta="(1024x128)")
                            with col_r3:
                                st.metric("Time", f"{elapsed:.1f}s", delta="")
                            
                            st.info("🎯 PPT indexed successfully! You can now search across its content.")
                        else:
                            st.error(f"Processing failed: {result.get('errors')}")
                            
                    except Exception as e:
                        import traceback
                        st.error(f"Error during processing: {str(e)}")
                        st.code(traceback.format_exc())'''
    text = text.replace(old_text, new_text)
    with open('ui/pages/upload.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed upload.py")
else:
    print("Could not find pattern in upload.py")
