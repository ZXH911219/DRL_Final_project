# Specifications for next-generation multimodal system
_Exported on 5/3/2026 at 13:32:11 GMT+8 from Cursor (3.0.16)_

---

**User**

I have completed the `agents.md` (MAS Architecture) and `project.md` (Project Overview) for the "Next-Generation Multimodal PPT Vision and Reasoning Retrieval System". 

Now, I need you to act as a **Principal Software Architect** to generate a comprehensive `specs.md` file. This file will serve as the "Source of Truth" for development in Cursor.

### Requirements for `specs.md`:

1. **System Data Flow**: Detail the end-to-end lifecycle of a query, from multi-modal input (text/image) through the 4-agent pipeline to the verified output.
2. **Component Interface Definitions**: 
    - Define strict Pydantic schemas for data exchange between agents (e.g., `QueryPayload`, `RetrievalContext`, `VerificationReport`).
    - Specify the exact tensor shapes and metadata requirements for ColPali (1024x128) and ImageBind (1024-dim).
3. **Database Schema (LanceDB)**: 
    - Design the table schema for storing multi-vectors. 
    - Explain how to handle the 1024 vectors per slide efficiently (using LanceDB's specific features like IVF-PQ or fixed-size lists).
4. **Agent Coordination Logic**:
    - Describe the asynchronous execution flow (using FastAPI Background Tasks or Celery/Temporal).
    - Define the "Fallthrough/Fallback" logic if the Reasoning or Verification agent hits a timeout.
5. **MM-R5 & Argos Integration Logic**:
    - Specify the Prompt Templates for the Reasoning-Reranker.
    - Define the mathematical formula for the "Hallucination Risk Score" and how it triggers the "Down-weighting" mechanism.
6. **Performance & Hardware Constraints**:
    - Define VRAM management strategies for running ColPali (ViT) and MM-R5 (7B model) simultaneously.
    - Set specific latency targets for each sub-module based on the SLAs in `agents.md`.
7. **Frontend Requirements (Streamlit)**:
    - Describe the UI components for the "Evidence Map" (how to overlay bounding boxes/highlights on the original slide image).

### Output Style:
- Use clear Markdown headings.
- Provide Python code snippets for interface definitions.
- Use Mermaid.js diagrams for logic flow where helpful.
- Ensure all specifications strictly align with the 4-agent architecture defined in `agents.md`.

Please generate the `specs.md` now.
請一律用繁體中文回答

---

**Cursor**

正在閱讀 `agents.md`、`project.md` 與相關規格，以產出與架構對齊的 `specs.md`。



正在建立與 `agents.md` 完全對齊的 `openspec/specs/specs.md`。



正在將表格中的 `&lt;` 改為 `<`，以改善 Markdown 可讀性。



已為你建立 **SSOT 規格書**，路徑如下：

**`c:\Users\User\Desktop\ku\碩班課程\DRL\FinalProjectProposal\openspec\specs\specs.md`**

### 文件內容對照你的七項需求

1. **系統資料流**：說明 ingest 與線上查詢分離、四代理在生命週期中的角色，並附 **Mermaid** 流程圖與步驟語意表。  
2. **元件介面**：提供 **`QueryPayload`、`RetrievalContext`（含候選與證據 patch）、`ReasoningBundle`、`VerificationReport`、`VerifiedOutput`** 等 **Pydantic** 模型；並固定 **ColPali `float32 (1024, 128)`**、查詢 **`(Q, 128)`**、**ImageBind `(1024,)`** 與後設資料約束（並註明 512-dim 僅能作獨立欄位）。  
3. **LanceDB**：一 slide 一列、**固定長度巢狀／展平多向量**、`colpali_agg_128` + **IVF-PQ** 做粗檢索、**批次載入**完整多向量做 MaxSim。  
4. **代理協調**：**FastAPI / BackgroundTasks / Celery / Temporal** 的適用情境、序圖；**Reasoning 逾時**改為僅檢索分排序並打 **`reasoning_timeout`**；**Verification 逾時**為 **`UNKNOWN` + 保守降權 + audit**；並銜接 **`agents.md` 熔斷**。  
5. **MM-R5 與 Argos**：可貼進程式碼的 **System/User 提示模板**（五步驟 + JSON 尾行）、重排加權公式、與 **`agents.md` 完全一致**的幻覺風險式與 **`adjusted_score = s_orig × (1 - r^0.5)`** 降權。  
6. **效能與 VRAM**：子模組延遲表與 **`agents.md` SLA** 對齊；**程序隔離、lazy load、量化、佇列深度**等 ColPali + 7B 並存策略。  
7. **Streamlit 證據地圖**：側欄／結果列表／**PIL 半透明疊加**／圖例與 **patch 網格 → 像素 bbox** 的 Python 片段與快取鍵。

文末另有 **追溯矩陣**，方便在 Cursor 裡從本規格跳回 **`agents.md`** 對應章節。若你希望 `specs.md` 改放在專案根目錄（例如與 `openspec/` 平級），可以說一下目標路徑，我可以幫你調整或複製一份。

---

**User**

@openspec/specs/specs.md 
雖然文件非常出色，但在接下來開發時，建議注意以下幾點：

多向量展平後的 Reshape 規則 (Critical)：

在 §3.1 中提到「全系統只能選一種展平方案」。建議實作建議： 採用 fixed_size_list(float, 131072) (即 1024*128) 展平存儲，但在 Python 應用層獲取後立即 reshape(1024, 128)。這樣在 LanceDB 讀取時 I/O 效率最高，也最不容易出現 shape mismatch。

ImageBind 與 ColPali 的「空間對齊」陷阱：

雖然 §2.3 定義了 ImageBind 為 1024-dim，但要注意：ColPali 是基於 SigLIP/PaliGemma 的視覺空間，而 ImageBind 有自己的投影空間。這兩者物理上是不互通的。

建議：Lakehouse-Retrieval-Agent 在實作時，必須明確「文字查詢」走哪條路。如果是走 ColPali 文字編碼，就只能跟 ColPali 向量比對；如果是走 ImageBind 文字編碼，就只能跟 ImageBind 向量比對。絕對不能將 ImageBind 向量丟進 MaxSim 公式計算。

Argos 驗證的 Claims 解析：

§5.1 的 Prompt 要求 MM-R5 輸出 JSON。在實作時，需要一個強大的 Reasoning-Parser 來提取這些 Claims。建議在開發 Argos-Agent 時，增加一個 Claim-Normalizer，將模糊的視覺描述轉化為具體的座標區域需求。

---

**Cursor**

正在將這三項關鍵實作建議整合進 `specs.md` 的對應章節。



正在將三項關鍵實作注意事項寫入 `specs.md`：更新 §3.1/§3.2（展平與 reshape）、擴充 §2.3（ColPali／ImageBind 路由與 MaxSim 禁令），並新增 Argos 的 Reasoning-Parser 與 Claim-Normalizer 小節。



已將你提出的三點**寫回** `openspec/specs/specs.md`，並把文件版本標為 **1.1**。變更要點如下：

### 1. 多向量展平與 Reshape（§3.1.1，Critical）
- **建議定案**：Lance 使用 **`fixed_size_list(float, 131072)`** 存 ColPali 多向量。
- **展平順序**：邏輯張量 **`(1024, 128)` 的 C contiguous**（先 patch 0 的 128 維，再 patch 1…）。
- 附上 **`colpali_to_lance_flat` / `lance_flat_to_colpali`** 範例，要求讀出後**立刻** `reshape(1024, 128)` 再進 MaxSim。
- **§3.2** 的 `colpali_multi` 欄位已改為以上型別；**§3.3** 第 3、4 點改寫為與展平／§2.3.1 一致。

### 2. ColPali／ImageBind 空間不互通（§2.3.1 + 圖註 + §1.3）
- 新增 **§2.3.1**：說明 SigLIP／PaliGemma 空間與 ImageBind **不可互換**；**Lakehouse 強制路由表**（ColPali → `colpali_multi` + **允許 MaxSim**；ImageBind → `imagebind_vec` + **禁止 MaxSim**）。
- 文字／圖像查詢都必須**明確選路**；混合時只允許 **`agents.md` 式的分數級融合**，禁止把 ImageBind 內積當 ColPali patch 相似度。
- **§2.3** 表格移除易誤解的「ColPali 匯入 ImageBind」預設，改為**獨立欄位 + 可選對齊投影**（未驗證不得啟用）。
- **§1.2** Mermaid 下方加**實作註記**；**§1.3** 第一步改為指向 §2.3.1。

### 3. Argos：Reasoning-Parser 與 Claim-Normalizer（§5.1.1，Critical）
- **Reasoning-Parser**：從 `inference_text` **穩健抽 JSON**、驗證欄位、審計解析失敗。
- **Claim-Normalizer**：把模糊視覺描述變成 **region／spatial_hints／expected_substrings／patch_prior_bbox** 等可 grounding 規格。
- 附上 **`NormalizedClaim` Pydantic 草稿**；**§5.4** 改為建議 Argos **強制**吃 `NormalizedClaim[]`，並註明 `colpali_multi` 須依 §3.1.1 reshape。

### 其他
- **§8 追溯矩陣**新增 §2.3.1、§3.1.1、§5.1.1 對照列。
- **§7.1** 圖例行的 HTML entity 已改為一般 `>`。

若你希望 **`QueryPayload` 內加正式欄位**（例如 `retrieval_route: Literal["colpali_maxsim", "imagebind_ann", "hybrid_score_fusion"]`）方便 API 與審計，可以說一下偏好，我可以再補一版介面契約。

---

**User**

請根據 specs.md 第 2 節（元件介面定義），在 /src/schemas 目錄下建立對應的 Python 模組。請確保：

完整實現 QueryPayload, RetrievalContext, ReasoningBundle 與 VerifiedOutput 等模型。

包含所有的 Enum 定義（如 VerificationStatus, RiskLevel）。

實作規格書中要求的 field_validator（例如 QueryPayload 的文字與圖像互斥檢查）。

使用 Python 3.10+ 的型別註解風格。

---

**Cursor**

讀取 `specs.md` 第 2 節的完整內容，並建立 `/src/schemas` 下的 Python 模組。



建立 `src/schemas` 套件：採用 Pydantic v2，並以 `model_validator(mode="after")` 實作跨欄位驗證（因 `modality` 若晚於 `query_text` 驗證，`field_validator` 無法可靠取得完整資料）。另將 `modality` 置於前，並保留與規格等價的檢查邏輯。



改為相對匯入以提升可攜性，並移除規格未要求的 `ReasoningBundle` 非空限制。



已在專案中建立 `src/schemas`，並在根目錄加入 `pyproject.toml`（`requires-python >= 3.10`、`pydantic>=2`），與 **Python 3.10+** 的 `str | None`、`list[...]` 等註解一致。

### 目錄與模組

| 檔案 | 內容 |
|------|------|
| `src/schemas/enums.py` | `Modality`, `VerificationStatus`, `RiskLevel` |
| `src/schemas/query.py` | `QueryPayload` + `field_validator`（`query_text` 去空白）+ `model_validator`（依 `modality` 的必填／**文字與圖像互斥**；含 `MULTIMODAL` 雙必填） |
| `src/schemas/retrieval.py` | `EvidencePatch`, `RetrievalCandidate`, `RetrievalMetrics`, `RetrievalContext` + `request_id` 與 `query` 一致、`query_imagebind` 長度 1024、`query_colpali` 每列 128 |
| `src/schemas/reasoning.py` | `ReasoningStep`, `RankedCandidate`, `ReasoningBundle` |
| `src/schemas/verification.py` | `EvidenceRegion`, `VerifiedCandidate`, `VerificationReport`, `VerifiedOutput` + 全鏈路 `request_id` 一致檢查 |
| `src/schemas/__init__.py` | 匯出公開 API |
| `src/__init__.py` | 套件標記 |

### 設計說明

- **互斥與必填**：規格里的 `field_validator("query_text")` 在 Pydantic v2 若欄位順序不當，`modality` 可能尚未就緒；因此改為 **`modality` 置於 `query_text`／`query_image_bytes` 之前**，並以 **`model_validator(mode="after")`** 實作與規格等價且更穩定的檢查（含 **TEXT 僅文字、IMAGE 僅圖像、MULTIMODAL 兩者都要**）。
- **執行環境**：請用 **Python 3.10+**（已用 `py -3.12` 跑過匯入與 `VerifiedOutput` 最小建構測試）。若預設是 3.8，請升級或改用 `py -3.12`。

從專案根目錄執行時請設定 `PYTHONPATH` 為專案根目錄，例如：

`$env:PYTHONPATH = (Get-Location).Path`（PowerShell），再 `from src.schemas import QueryPayload, ...`。

---

**User**

接著處理 specs.md 第 3 節中關鍵的 LanceDB 儲存邏輯。
參考 specs.md 第 3 節與 project.md 的技術棧，實作 LanceDB 的資料管理模組 /src/storage/lancedb_manager.py。定義符合規格的 Table Schema，特別是 colpali_multi 的固定長度嵌套列表 fixed_size_list(fixed_size_list(float, 128), 1024)。實作第一階段粗檢索所需的 colpali_agg_128 向量生成與 IVF-PQ 索引建立邏輯。確保 RetrievalCandidate 的資料讀取符合 specs.md 的 Reshape 規則（讀取展平向量後還原為 1024x128）。

---

**Cursor**

正在閱讀 `specs.md` 第 3 節與 LanceDB 的 Python API，以實作 `lancedb_manager.py`。



實作完整模組：更新 `pyproject.toml` 依賴，並新增 `lancedb_manager.py`。



已依 `specs.md` §3 與 `project.md` 技術棧實作 **`src/storage/lancedb_manager.py`**，並更新 **`pyproject.toml`** 依賴（`lancedb`、`pyarrow`、`numpy`）。摘要如下。

### Schema（巢狀 `colpali_multi`）

- 使用 PyArrow：`pa.list_(pa.list_(pa.float32(), list_size=128), list_size=1024)`，對應規格中的 **`fixed_size_list(fixed_size_list(float, 128), 1024)`**（在 Arrow 中顯示為 `fixed_size_list<item: fixed_size_list<...>>`）。
- 其餘欄位對齊 §3.2：`slide_id`, `deck_id`, `page_index`, `source_path`, `created_at`, `colpali_agg_128`, 可為 null 的 `imagebind_vec`(1024)、`patch_bboxes`(1024×4)、`fts_text`, `quality_metrics`（JSON 字串）。

### 粗檢索（`colpali_agg_128` + IVF-PQ）

- **`compute_colpali_agg_128`**：對 `(1024,128)` 做 **patch-mean** → `(128,)`。
- **`build_ivf_pq_index_on_agg`**：在 **`colpali_agg_128`** 上建 **`IVF_PQ`**（`metric` 預設 `cosine`，`num_sub_vectors` 預設 `max(8, 128//8)=16`）。
- 若列數 **&lt; 256**（Lance PQ 訓練下限），會 **`warnings.warn` 並跳過建索引**；**`coarse_search` 仍可用無索引向量搜尋**（已用單測驗證）。

### Reshape／`RetrievalCandidate`

- **`colpali_multi_to_numpy`**：讀出值統一成 **`float32 (1024, 128)`**；支援 **巢狀 list**、**已是 (1024,128) 的 ndarray**、以及 **§3.1.1 長度 131072 展平** 的 `reshape`。
- **`get_colpali_multi` / `fetch_colpali_tensors`**：皆以 **`colpali_multi_to_numpy`** 還原，供 MaxSim。
- **`coarse_hits_to_retrieval_candidates`**：粗排結果轉成 **`RetrievalCandidate`**，`retrieval_stage="filtering"`、`evidence_patches=[]`；**`maxsim_score`** 由 Lance 的 cosine 距離經 **`coarse_distance_to_similarity_score`** 映射到 **[0,1]**（與 schema 中 `ge=0, le=1` 一致）。

### 其它

- **`normalize_slide_record`**：可接受 **`colpali_multi` 為 ndarray／巢狀 list／131072 展平**；自動補 **`colpali_agg_128`**、**`created_at`**；**剔除不在 schema 內的欄位**，避免 Lance 寫入錯誤。
- **`src/storage/__init__.py`** 匯出常用符號（含 **`CoarseSearchHit`**、`SLIDE_TABLE_FIELD_NAMES`、`colpali_multi_value_type`）。

使用方式（需將專案根目錄加入 `PYTHONPATH`）：

```python
from src.storage import LanceDBManager, slide_table_schema
import numpy as np

mgr = LanceDBManager("./data/lancedb", "slides")
mgr.db.create_table("slides", schema=slide_table_schema(), mode="create")
mgr.add([{... "colpali_multi": multi_np_or_flat_or_nested ...}])
mgr.build_ivf_pq_index_on_agg()  # 列數足夠時
hits = mgr.coarse_search(query_agg_128, k=500)
cands = mgr.coarse_hits_to_retrieval_candidates(hits)
maxsim_input = mgr.fetch_colpali_tensors([c.slide_id for c in cands])
```

---

**User**

I have successfully implemented the `src/storage/lancedb_manager.py` with full support for nested ColPali vectors (1024x128) and aggregate filtering. 

Now, please implement the **Vision-Ingestion-Agent** according to `agents.md` §1 and `specs.md` §1.2.

### Key Objectives:
1. **PPT to Image Pipeline**: 
    - Implement a structured reader using `python-pptx` for metadata[cite: 1].
    - Use `pdf2image` or `LibreOffice` (headless) to render high-fidelity PNGs at 600 DPI[cite: 1, 3].
2. **ColPali Integration**: 
    - Load the ColPali model to extract (1024, 128) multi-vectors from the rendered images[cite: 1].
    - Use the existing `LancedbManager` to save the results, ensuring `colpali_multi` is passed in a format supported by our `normalize_slide_record`.
3. **Multi-modal Alignment**: 
    - (Optional/Placeholder) Add an ImageBind encoding step to populate the `imagebind_vec` field if applicable[cite: 1, 3].
4. **Performance Compliance**: 
    - Ensure the pipeline adheres to the SLA: < 500ms for rendering and < 2s for feature extraction per page[cite: 3].

### Implementation Details:
- File location: `src/agents/vision_ingestion_agent.py`
- Utilize the `src/storage` module I just created for all DB operations.
- Ensure the `patch_coordinates` are correctly mapped to the 32x32 grid for future evidence mapping[cite: 1, 3].

Please generate the agent code and a simple ingestion CLI script.

---

**Cursor**

正在閱讀 `agents.md` §1、`specs.md` 相關段落與現有 `lancedb_manager`，以實作 Vision-Ingestion-Agent 與 CLI。



實作完整的 Vision-Ingestion-Agent（含 LibreOffice→PDF→`pdf2image` 渲染、ColPali 的 HF 與 stub 後端、32×32 patch 對齊與 LanceDB 寫入），並新增 CLI 腳本。



以下是本次實作摘要（繁體中文）。

### 新增／修改檔案

| 路徑 | 說明 |
|------|------|
| `src/agents/vision_ingestion_agent.py` | **Vision-Ingestion-Agent**：pptx 結構讀取、LibreOffice→PDF、`pdf2image` 高 DPI、32×32 patch 座標／`patch_bboxes`、ColPali（stub / HF）、ImageBind 占位、`LanceDBManager.add` |
| `src/agents/__init__.py` | 匯出主要型別與類別 |
| `scripts/ingest_pptx.py` | 命令列攝取腳本 |
| `pyproject.toml` | 加入 `python-pptx`、`pdf2image`、`Pillow`；可選 extra **`vision-ml`**（`torch`、`transformers`） |

### 行為對齊規格

1. **PPT → 圖像**  
   - `python-pptx`：`read_pptx_slide_metadata`（版面、備註等）。  
   - **LibreOffice headless** `soffice --convert-to pdf` → **`pdf2image`**（預設 **600 DPI**）。  
   - 找不到 `soffice` 時會丟出明確錯誤（需安裝 LibreOffice 並在 PATH，或常見 Windows 安裝路徑）。

2. **ColPali**  
   - **`StubColPaliEncoder`**：可重現 `(1024,128)`，預設打通管線。  
   - **`HFColPaliEncoder`**：`ColPaliForRetrieval` + `ColPaliProcessor`（預設 `vidore/colpali-v1.3-hf`）；若 token 數或 hidden 維度不是 1024×128，會**重採樣／截斷／補零**並 **warning**（與專案固定網格一致）。  
   - 環境變數：`COLPALI_BACKEND=stub|hf`、`COLPALI_MODEL`、`COLPALI_DEVICE`、`COLPALI_DTYPE`、`build_colpali_encoder_from_env()`。

3. **LanceDB**  
   - 寫入列含 `colpali_multi`（`ndarray` 交給既有 **`normalize_slide_record`**）、自動 **`colpali_agg_128`**、**`patch_bboxes`**（1024×4、0–1）、**`quality_metrics`**（含各段耗時與 DPI）。  
   - **`imagebind_vec`**：僅在 **`ImageBindEncoderPlaceholder(enabled=True)`** 時寫入全零占位（符合 specs 分路說明）。

4. **32×32 / 證據對齊**  
   - **`patch_index = gy * 32 + gx`**（gy 上→下，gx 左→右）。  
   - **`patch_coordinates`**：每 patch **左上角像素 (x,y)**。  
   - **`patch_bboxes`**：對應 **正規化 [x0,y0,x1,y1]**，與 `multi_vectors` 列順序一致。

5. **SLA**  
   - 對渲染鏈路（平均每頁）、ColPali 編碼、ImageBind 占位分別計時；超過 **500ms / 2s / 300ms** 時 **`logger.warning`**，並寫入 **`quality_metrics`**。

### CLI 用法

```text
set PYTHONPATH=.
python scripts/ingest_pptx.py --pptx .\deck.pptx --lancedb .\data\lancedb --deck-id mydeck --dpi 600
```

- **`--colpali-backend stub|hf|env`**（`env` 讀 `COLPALI_BACKEND`）。  
- **`--imagebind-placeholder`**：寫入零向量 `imagebind_vec`。  
- **`--build-ivf-pq`**：攝取後嘗試建 **`colpali_agg_128`** 的 IVF-PQ（仍受 Lance 最少列數等限制）。  

**系統需求**：LibreOffice、Poppler（給 `pdf2image`）；HF 路徑需 **`pip install -e ".[vision-ml]"`**（或自行安裝 `torch` / 支援 ColPali 的 `transformers`）。

---

**User**

請列出所有須安裝的依賴項

