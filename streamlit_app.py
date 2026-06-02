from __future__ import annotations

import json
import os
import sys
import re
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

import streamlit as st
from PIL import Image, ImageDraw


ARTIFACTS_DIR = Path("artifacts")
UPLOADS_DIR = ARTIFACTS_DIR / "uploads"


def _initialize_artifacts_once_per_session() -> None:
    """Remove old files under `artifacts/slide_images` and `artifacts/uploads` once per session.

    This is intentionally aggressive: it will delete and recreate those directories to
    avoid leftover files from previous runs causing confusion.
    """
    key = "_initialized_artifacts"
    if st.session_state.get(key):
        return

    # Only operate inside the ARTIFACTS_DIR for safety
    targets = [ARTIFACTS_DIR / "slide_images", UPLOADS_DIR]
    for t in targets:
        try:
            if t.exists():
                # remove the directory and all contents
                shutil.rmtree(t, ignore_errors=True)
            # recreate empty directory
            t.mkdir(parents=True, exist_ok=True)
        except Exception:
            # Don't crash the app on cleanup failures; log to Streamlit
            st.warning(f"Failed to initialize artifacts directory: {t}")

    st.session_state[key] = True


def _is_local_lancedb_uri(uri: str) -> bool:
    return "://" not in uri


def _clear_lancedb_once_per_session(lance_uri: str) -> None:
    if not lance_uri.strip() or not _is_local_lancedb_uri(lance_uri):
        return

    cleared_key = "_cleared_lancedb_uri"
    if st.session_state.get(cleared_key) == lance_uri:
        return

    db_path = Path(lance_uri)
    if db_path.exists():
        shutil.rmtree(db_path, ignore_errors=True)
    db_path.mkdir(parents=True, exist_ok=True)
    st.session_state[cleared_key] = lance_uri


def _safe_artifact_name(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip("._ ") or "slide"


def _extract_page_number(slide_id: str) -> int | None:
    match = re.search(r"\|p(\d{4})\|", slide_id)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _find_slide_image(slide_id: str) -> Path | None:
    deck_id = slide_id.split("|", 1)[0]
    slide_name = _safe_artifact_name(slide_id)
    deck_name = _safe_artifact_name(deck_id)
    candidates = [
        ARTIFACTS_DIR / "slide_images" / deck_name / f"{slide_name}.png",
        ARTIFACTS_DIR / "slide_images" / deck_name / f"{slide_name}.jpg",
        ARTIFACTS_DIR / f"{slide_id}.png",
        ARTIFACTS_DIR / f"{slide_id}.jpg",
        ARTIFACTS_DIR / slide_id,
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _draw_evidence_overlay(base: Image.Image, evidence_regions: list[dict[str, Any]]) -> Image.Image:
    img = base.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size

    for region in evidence_regions:
        bbox_norm = region.get("bbox_norm")
        if not bbox_norm or len(bbox_norm) != 4:
            continue
        x0 = int(float(bbox_norm[0]) * w)
        y0 = int(float(bbox_norm[1]) * h)
        x1 = int(float(bbox_norm[2]) * w)
        y1 = int(float(bbox_norm[3]) * h)

        conf = float(region.get("confidence", 0.0))
        if conf > 0.9:
            color = (34, 197, 94, 120)
        elif conf > 0.7:
            color = (250, 204, 21, 120)
        else:
            color = (239, 68, 68, 120)

        draw.rectangle([x0, y0, x1, y1], outline=color[:3], width=3)
        draw.rectangle([x0, y0, x1, y1], fill=color)

    return Image.alpha_composite(img, overlay).convert("RGB")


def _render_visual_summary(adjusted: float, risk: float, coverage: float) -> None:
    st.caption("Visual summary")
    st.write(f"Adjusted score: **{adjusted:.4f}**")
    st.progress(max(0.0, min(1.0, adjusted)))
    st.write(f"Hallucination risk: **{risk:.4f}** (lower is better)")
    st.progress(max(0.0, min(1.0, risk)))
    st.write(f"Evidence coverage: **{coverage:.4f}**")
    st.progress(max(0.0, min(1.0, coverage)))


def _render_slide_preview(image_path: Path, slide_id: str, regions: list[dict[str, Any]]) -> None:
    base_img = Image.open(image_path).convert("RGB")
    overlay_img = _draw_evidence_overlay(base_img, regions) if regions else base_img

    tab_original, tab_overlay = st.tabs(["Original slide", "Evidence overlay"])
    with tab_original:
        st.image(base_img, caption=f"Full slide: {slide_id}", use_container_width=True)
    with tab_overlay:
        st.image(overlay_img, caption=f"Evidence overlay: {slide_id}", use_container_width=True)


def _render_top_results(result: dict[str, Any], top_n: int = 5) -> None:
    verification = result.get("verification", {})
    per_slide = verification.get("per_slide", [])

    if not per_slide:
        st.warning("No verification results.")
        return

    st.subheader("Verification Results")
    for i, item in enumerate(per_slide[:top_n], start=1):
        slide_id = str(item.get("slide_id", "unknown"))
        page_number = item.get("page_index")
        if page_number is None:
            page_number = _extract_page_number(slide_id)
        status = item.get("verification_status", "unknown")
        adjusted = float(item.get("adjusted_score", 0.0))
        risk = float(item.get("hallucination_risk_score", 0.0))
        coverage = float(item.get("evidence_coverage_ratio", 0.0))

        image_path = _find_slide_image(slide_id)
        regions = item.get("evidence_regions", [])
        if page_number is not None:
            st.markdown(f"### {i}. 第 {page_number} 頁")
            st.caption(slide_id)
        else:
            st.markdown(f"### {i}. {slide_id}")
        left, right = st.columns([2.5, 1])
        with left:
            if image_path is not None:
                _render_slide_preview(image_path, slide_id, regions)
            else:
                if page_number is not None:
                    st.info(f"No image found under artifacts for 第 {page_number} 頁 (slide_id={slide_id})")
                else:
                    st.info(f"No image found under artifacts for slide_id={slide_id}")
        with right:
            c1, c2, c3 = st.columns(3)
            c1.metric("Status", str(status).upper())
            c2.metric("Adjusted", f"{adjusted:.4f}")
            c3.metric("Risk", f"{risk:.4f}")
            st.metric("Coverage", f"{coverage:.4f}")
            _render_visual_summary(adjusted, risk, coverage)
            
            # Display Gemini Reasoning text if available
            inference_text = item.get("inference_text", "")
            if inference_text and "Visual Perception:" not in inference_text:
                st.caption("🤖 **Gemini 推理分析：**")
                with st.expander("📝 點擊查看大模型視覺分析", expanded=False):
                    st.write(inference_text)
        with st.expander("Verified / Unverified Claims"):
            verified = item.get("verified_claims", [])
            unverified = item.get("unverified_claims", [])
            st.write("Verified claims:")
            st.write(verified if verified else ["(none)"])
            st.write("Unverified claims:")
            st.write(unverified if unverified else ["(none)"])


def _save_uploaded_pptx(uploaded_files: list[Any]) -> list[Path]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix.lower()
        stem = Path(uploaded.name).stem
        if suffix != ".pptx":
            continue
        target = UPLOADS_DIR / f"{stem}_{uuid4().hex[:8]}{suffix}"
        target.write_bytes(uploaded.getbuffer())
        saved_paths.append(target)
    return saved_paths


def _save_uploaded_pdf(uploaded_files: list[Any]) -> list[Path]:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    saved_paths: list[Path] = []
    for uploaded in uploaded_files:
        suffix = Path(uploaded.name).suffix.lower()
        stem = Path(uploaded.name).stem
        if suffix != ".pdf":
            continue
        target = UPLOADS_DIR / f"{stem}_{uuid4().hex[:8]}{suffix}"
        target.write_bytes(uploaded.getbuffer())
        saved_paths.append(target)
    return saved_paths


def _ingest_pptx_paths(pptx_paths: list[Path], lance_uri: str, dpi: int, progress_callback=None) -> tuple[int, list[str]]:
    # Ensure repository root is on sys.path so package imports and relative
    # imports inside `src` modules work (prevents
    # "attempted relative import with no known parent package").
    import sys
    repo_root = Path.cwd()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        # Import the vision ingestion agent as a package so relative imports resolve
        import importlib

        vision_mod = importlib.import_module("src.agents.vision_ingestion_agent")
    except Exception as exc:
        raise RuntimeError(
            "Failed loading vision ingestion module. If you see a DLL/pyarrow error, "
            "install pyarrow/lancedb from conda-forge or ensure VC++ redistributable is present: "
            f"{exc}"
        )

    try:
        ldb_mod = importlib.import_module("src.storage.lancedb_manager")
    except Exception as exc:
        raise RuntimeError(
            "LanceDB / pyarrow import failed. On Windows prefer conda-forge wheels. Try:\n"
            "  conda install -c conda-forge pyarrow lancedb -y\n"
            "or ensure the MSVC runtime is installed (Visual C++ Redistributable).\n"
            f"Original error: {exc}"
        )

    LanceDBManager = ldb_mod.LanceDBManager
    VisionIngestionAgent = vision_mod.VisionIngestionAgent
    build_colpali_encoder_from_env = vision_mod.build_colpali_encoder_from_env

    lance = LanceDBManager(lance_uri)
    ingestion = VisionIngestionAgent(
        lance=lance,
        colpali=build_colpali_encoder_from_env(),
        dpi=int(dpi),
    )

    ok = 0
    errors: list[str] = []
    for pptx_path in pptx_paths:
        try:
            ingestion.ingest_pptx(
                pptx_path,
                deck_id=pptx_path.stem,
                artifact_root=ARTIFACTS_DIR,
                progress_callback=progress_callback,
            )
            ok += 1
        except Exception as exc:
            errors.append(f"{pptx_path.name}: {exc}")
    return ok, errors


def _ingest_pdf_paths(pdf_paths: list[Path], lance_uri: str, dpi: int, progress_callback=None) -> tuple[int, list[str]]:
    """Ingest PDF files into LanceDB."""
    import sys
    repo_root = Path.cwd()
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        import importlib
        vision_mod = importlib.import_module("src.agents.vision_ingestion_agent")
    except Exception as exc:
        raise RuntimeError(
            "Failed loading vision ingestion module. If you see a DLL/pyarrow error, "
            "install pyarrow/lancedb from conda-forge or ensure VC++ redistributable is present: "
            f"{exc}"
        )

    try:
        ldb_mod = importlib.import_module("src.storage.lancedb_manager")
    except Exception as exc:
        raise RuntimeError(
            "LanceDB / pyarrow import failed. On Windows prefer conda-forge wheels. Try:\n"
            "  conda install -c conda-forge pyarrow lancedb -y\n"
            "or ensure the MSVC runtime is installed (Visual C++ Redistributable).\n"
            f"Original error: {exc}"
        )

    LanceDBManager = ldb_mod.LanceDBManager
    VisionIngestionAgent = vision_mod.VisionIngestionAgent
    build_colpali_encoder_from_env = vision_mod.build_colpali_encoder_from_env

    lance = LanceDBManager(lance_uri)
    ingestion = VisionIngestionAgent(
        lance=lance,
        colpali=build_colpali_encoder_from_env(),
        dpi=int(dpi),
    )

    ok = 0
    errors: list[str] = []
    for pdf_path in pdf_paths:
        try:
            ingestion.ingest_pdf(
                pdf_path,
                deck_id=pdf_path.stem,
                dpi=int(dpi),
                artifact_root=ARTIFACTS_DIR,
                progress_callback=progress_callback,
            )
            ok += 1
        except Exception as exc:
            errors.append(f"{pdf_path.name}: {exc}")
    return ok, errors


def _force_clear_all_data(lance_uri: str) -> None:
    targets = [ARTIFACTS_DIR / "slide_images", UPLOADS_DIR]
    for t in targets:
        try:
            if t.exists():
                shutil.rmtree(t, ignore_errors=True)
            t.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    if _is_local_lancedb_uri(lance_uri):
        db_path = Path(lance_uri)
        try:
            if db_path.exists():
                shutil.rmtree(db_path, ignore_errors=True)
            db_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

st.set_page_config(page_title="Multimodal PPT Retrieval", layout="wide")
st.title("Next-Gen Multimodal PPT Retrieval")
st.caption("Lakehouse Retrieval -> Reasoning Reranker -> Argos Verification")

# Ensure old artifacts are cleared on app start (once per session)
_initialize_artifacts_once_per_session()

with st.sidebar:
    st.header("Run Settings")
    lance_uri = st.text_input("LanceDB URI", value="./artifacts/lancedb")
    ingest_dpi = st.number_input("Ingest DPI", min_value=150, max_value=1000, value=600, step=50)
    query_text = st.text_area("Query Text", value="請找出包含市場成長趨勢的投影片")
    gemini_api_key = st.text_input("Gemini API Key (Optional for smart vision reranking)", value="", type="password")
    
    if gemini_api_key.strip():
        if gemini_api_key.strip().startswith("AIza") and len(gemini_api_key.strip()) > 30:
            os.environ["GEMINI_API_KEY"] = gemini_api_key.strip()
            st.success("✨ Gemini 視覺推理引擎已啟動！系統將使用大模型進行精準排序。")
        else:
            if "GEMINI_API_KEY" in os.environ:
                del os.environ["GEMINI_API_KEY"]
            st.error("❌ 錯誤的 API Key 格式。請確認它以 'AIza' 開頭。")
    else:
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        st.info("⚠️ 目前為純本地檢索模式 (未使用 Gemini)")
    risk_alpha = st.slider("Risk down-weight strength (lower = softer scoring)", 0.0, 1.0, 1.0, 0.1,
                            help="Controls how aggressively hallucination risk reduces final score. Default 1.0 applies full down-weighting; lower values are more lenient.")
    top_n = st.slider("Top N results to display", 1, 10, 5, 1)
    poppler_path = st.text_input("POPPLER_PATH (optional)", value=os.environ.get("POPPLER_PATH", ""))
    run = st.button("Run Pipeline", type="primary")
    st.divider()
    clear_data = st.button("🗑️ Clear All Data & Database", type="secondary")
    if clear_data:
        _force_clear_all_data(lance_uri.strip())
        st.success("All previous slides and database records have been cleared!")

_clear_lancedb_once_per_session(lance_uri.strip())
st.caption(f"Database reset on first load for this session: {lance_uri.strip()}")

st.subheader("Document Ingestion")
tab_pdf, tab_pptx, tab_folder = st.tabs(["Upload PDF (Recommended)", "Upload PPTX (Legacy)", "Ingest From Folder"])

with tab_pdf:
    if 'pdf_uploader_key' not in st.session_state:
        st.session_state['pdf_uploader_key'] = 0

    col1, col2 = st.columns([4, 1])
    with col1:
        uploaded_pdf_files = st.file_uploader(
            "Upload one or more .pdf files",
            type=["pdf"],
            accept_multiple_files=True,
            key=f"pdf_uploader_{st.session_state['pdf_uploader_key']}",
        )
    with col2:
        st.write("") # padding
        st.write("") # padding
        if st.button("🗑️ Clear Uploaded PDF", key="clear_pdf_btn"):
            st.session_state['pdf_uploader_key'] += 1
            st.rerun()
    ingest_pdf = st.button("Ingest Uploaded PDF", key="ingest_pdf")
    if ingest_pdf:
        if poppler_path.strip():
            os.environ["POPPLER_PATH"] = poppler_path.strip()
        if not uploaded_pdf_files:
            st.warning("Please upload at least one .pdf file.")
        else:
            with st.spinner("Saving and ingesting uploaded PDF..."):
                progress_bar = st.progress(0, text="準備轉檔中...")
                def _update_progress(current, total, text):
                    total = max(total, 1)
                    progress_bar.progress(min(current / total, 1.0), text=text)

                _force_clear_all_data(lance_uri.strip())
                try:
                    saved = _save_uploaded_pdf(uploaded_pdf_files)
                    success_count, errors = _ingest_pdf_paths(saved, lance_uri=lance_uri.strip(), dpi=int(ingest_dpi), progress_callback=_update_progress)
                except Exception as exc:
                    st.exception(exc)
                else:
                    progress_bar.empty()
                    st.success(f"Ingestion done. Success: {success_count}, Failed: {len(errors)}")
                    if errors:
                        with st.expander("Ingestion errors"):
                            for err in errors:
                                st.write(err)

with tab_pptx:
    if 'pptx_uploader_key' not in st.session_state:
        st.session_state['pptx_uploader_key'] = 0

    col1, col2 = st.columns([4, 1])
    with col1:
        uploaded_pptx_files = st.file_uploader(
            "Upload one or more .pptx files",
            type=["pptx"],
            accept_multiple_files=True,
            key=f"pptx_uploader_{st.session_state['pptx_uploader_key']}",
        )
    with col2:
        st.write("") # padding
        st.write("") # padding
        if st.button("🗑️ Clear Uploaded PPTX", key="clear_pptx_btn"):
            st.session_state['pptx_uploader_key'] += 1
            st.rerun()
    ingest_pptx = st.button("Ingest Uploaded PPTX", key="ingest_pptx")
    if ingest_pptx:
        if poppler_path.strip():
            os.environ["POPPLER_PATH"] = poppler_path.strip()
        if not uploaded_pptx_files:
            st.warning("Please upload at least one .pptx file.")
        else:
            with st.spinner("Saving and ingesting uploaded PPTX..."):
                progress_bar = st.progress(0, text="準備轉檔中...")
                def _update_progress(current, total, text):
                    total = max(total, 1)
                    progress_bar.progress(min(current / total, 1.0), text=text)

                _force_clear_all_data(lance_uri.strip())
                try:
                    saved = _save_uploaded_pptx(uploaded_pptx_files)
                    success_count, errors = _ingest_pptx_paths(saved, lance_uri=lance_uri.strip(), dpi=int(ingest_dpi), progress_callback=_update_progress)
                except Exception as exc:
                    st.exception(exc)
                else:
                    progress_bar.empty()
                    st.success(f"Ingestion done. Success: {success_count}, Failed: {len(errors)}")
                    if errors:
                        with st.expander("Ingestion errors"):
                            for err in errors:
                                st.write(err)

with tab_folder:
    folder_path = st.text_input("Folder path containing .pdf or .pptx files", value="")
    recursive = st.checkbox("Include subfolders", value=True)
    ingest_folder = st.button("Ingest Folder", key="ingest_folder")
    if ingest_folder:
        if poppler_path.strip():
            os.environ["POPPLER_PATH"] = poppler_path.strip()
        root = Path(folder_path.strip()) if folder_path.strip() else None
        if root is None or not root.exists() or not root.is_dir():
            st.error("Please provide a valid folder path.")
        else:
            pdf_paths = list(root.rglob("*.pdf")) if recursive else list(root.glob("*.pdf"))
            pptx_paths = list(root.rglob("*.pptx")) if recursive else list(root.glob("*.pptx"))
            all_paths = pdf_paths + pptx_paths
            
            if not all_paths:
                st.warning("No .pdf or .pptx files found in folder.")
            else:
                with st.spinner(f"Ingesting {len(all_paths)} files..."):
                    _force_clear_all_data(lance_uri.strip())
                    try:
                        total_ok = 0
                        total_errors = []
                        
                        if pdf_paths:
                            ok, errors = _ingest_pdf_paths(
                                pdf_paths,
                                lance_uri=lance_uri.strip(),
                                dpi=int(ingest_dpi),
                            )
                            total_ok += ok
                            total_errors.extend(errors)
                        
                        if pptx_paths:
                            ok, errors = _ingest_pptx_paths(
                                pptx_paths,
                                lance_uri=lance_uri.strip(),
                                dpi=int(ingest_dpi),
                            )
                            total_ok += ok
                            total_errors.extend(errors)
                    except Exception as exc:
                        st.exception(exc)
                    else:
                        st.success(f"Ingestion done. Success: {total_ok}, Failed: {len(total_errors)}")
                        if total_errors:
                            with st.expander("Ingestion errors"):
                                for err in total_errors:
                                    st.write(err)

if run:
    if not query_text.strip():
        st.error("Query text cannot be empty.")
    else:
        if poppler_path.strip():
            os.environ["POPPLER_PATH"] = poppler_path.strip()

        # 自動判斷與翻譯中文查詢
        expanded_query = query_text.strip()
        has_chinese = bool(re.search(r'[\u4e00-\u9fff]', expanded_query))
        
        if has_chinese:
            with st.spinner("偵測到中文，正在自動擴充英文關鍵字 (Auto-translating)..."):
                try:
                    from deep_translator import GoogleTranslator
                    translated = GoogleTranslator(source='auto', target='en').translate(expanded_query)
                    # 保留原本的中文並加上翻譯出的英文，讓 AI 兩邊的特徵都抓得到
                    expanded_query = f"{expanded_query} {translated}"
                    st.info(f"✨ 已自動擴充查詢字詞：`{expanded_query}`")
                except Exception as e:
                    st.warning(f"自動翻譯擴充失敗，將使用原始字詞 ({e})")

        with st.spinner("Running pipeline..."):
            progress_bar = st.progress(0, text="準備啟動檢索管線...")
            def _pipeline_progress(current, total, text):
                total = max(total, 1)
                # If Gemini is active, customize the text for the reranking stage
                if os.environ.get("GEMINI_API_KEY") and "第二階段" in text:
                    text = "第二階段：✨ 正在呼叫 Gemini 視覺大模型逐張審查圖片..."
                progress_bar.progress(min(current / total, 1.0), text=text)

            try:
                from pipeline_v1 import run_pipeline

                def _streamlit_image_loader(slide_id: str) -> Image.Image:
                    path = _find_slide_image(slide_id)
                    if path:
                        try:
                            return Image.open(path).convert("RGB")
                        except Exception:
                            pass
                    return Image.new("RGB", (1280, 720), color=(255, 255, 255))

                result = run_pipeline(
                    lance_uri=lance_uri.strip(), 
                    query_text=expanded_query, 
                    risk_alpha=risk_alpha, 
                    progress_callback=_pipeline_progress,
                    image_loader=_streamlit_image_loader
                )
            except ValueError as exc:
                if "Table" in str(exc) and "not found" in str(exc):
                    progress_bar.empty()
                    st.error("❌ **找不到資料庫或投影片資料！**\n\n這通常是因為您重新整理了網頁，系統為了保持測試環境乾淨而自動清空了資料庫。\n\n👉 **解決方法：** 請至上方的 `Document Ingestion` 區塊，重新上傳您的 PDF 或 PPTX 檔案，並點擊 `Ingest` 匯入，然後再試一次。")
                else:
                    st.exception(exc)
            except Exception as exc:
                st.exception(exc)
            else:
                progress_bar.empty()
                st.success("Pipeline completed.")
                _render_top_results(result, top_n)
                with st.expander("Raw JSON Output"):
                    st.code(json.dumps(result, ensure_ascii=False, indent=2, default=str), language="json")
