# 多代理系統架構（Multi-Agent System Architecture）

## 概述

本文檔詳細定義了驅動「次世代多模態 PPT 視覺與推理檢索系統」的四層多代理架構。各代理遵循單一責任原則（Single Responsibility Principle），通過明確定義的接口與異步通信協議組織協作，形成內聚的端到端系統。

---

## 代理 1：Vision-Ingestion-Agent（視覺攝取專家）

### 1.1 職責與目標

**核心使命**：徹底捨棄傳統的 `python-pptx` 文字解析流程，直接將 PPT 檔案渲染為高畫質圖像並執行強大的視覺特徵提取。

**關鍵目標**：
- 將每個 PPT 頁面轉換為 128 維的高密度多向量表示（1024 個視覺區塊）
- 保證向量品質與覆蓋率，建立統一的多模態特徵空間
- 支援增量式批處理，適應不斷增長的 PPT 語料庫

### 1.2 技術職責

#### 1.2.1 PPT 檔案解析與結構化讀取
```
Input:  PPT 檔案路徑
Output: 結構化的頁面元資料集合
  ├─ page_id
  ├─ page_index
  ├─ slide_layout
  ├─ source_path
  └─ timestamp
```
- 利用 `python-pptx` 與 LibreOffice 引擎解析 PPT 結構
- 提取頁面級元資訊（佈局、母版、備註等）
- 支援多格式輸入（.pptx, .odp，未來支援 .pdf）

#### 1.2.2 高保真圖像渲染
```
Input:  PPT 頁面結構
Output: 標準化高清圖像
  ├─ 解像度: 600 DPI （或 1024×768 標準化尺寸）
  ├─ 色彩空間: RGB / RGBA
  ├─ 格式: PNG / WebP （優化傳輸）
  └─ 品質檢查: 模糊度評估、色彩不均衡檢測
```
- 使用 LibreOffice headless 或 Pillow + PDF 中間表示進行高畫質渲染
- 執行圖像正規化（色彩校正、對比度均衡）
- 支援批量並行渲染，利用多進程/GPU 加速

#### 1.2.3 ColPali 視覺特徵提取
```
Input:  標準化圖像
Process: ColPali Vision-Language 模型
Output: 多向量表示（Multi-vector）
  ├─ 視覺區塊數: 1024 blocks
  ├─ 單個向量維度: 128
  ├─ 向量類型: float32 稠密向量
  └─ 空間元資訊: 每個區塊的圖像座標與相對位置
```
**演算法細節**：
- 將圖像分割為 32×32 = 1024 個固定視覺區塊（patch）
- 每個區塊通過 Vision Transformer (ViT) 編碼器轉換為 128 維稠密向量
- 維護向量的空間層級結構（patch 座標 → 圖像座標映射），支援後續的視覺定位

#### 1.2.4 ImageBind 多模態對齐
```
Input:  ColPali 提取的視覺向量 + 潛在的異質模態輸入
         (文字描述、參考圖像、音頻等)
Process: ImageBind 統一編碼層
Output:  共享向量空間中的特徵表示
  ├─ 向量維度: 1024 or 512 （根據 ImageBind 版本）
  ├─ 空間: 統一的多模態向量空間
  ├─ 可解釋性: 各模態間的語義相似度指標
  └─ 跨模態對齐分數: > 0.85
```
**功能**：
- 將 ColPali 視覺向量映射至 ImageBind 空間
- 支援文字查詢自動映射至同一空間（透過 CLIP-like 機制）
- 啟用跨模態檢索（用圖片查找文字描述不夠清楚的投影片）

### 1.3 工作流程（Workflow）

```
Vision-Ingestion-Agent 處理流程：

┌─ PPT 檔案輸入
│
├─ [Task 1] 結構化解析
│  ├─ 提取頁面元資訊
│  └─ 驗證檔案完整性
│
├─ [Task 2] 批量高清渲染
│  ├─ LibreOffice/Pillow 轉圖
│  ├─ 正規化與品質檢查
│  └─ 存儲中間圖像
│
├─ [Task 3] ColPali 視覺特徵提取
│  ├─ 初始化 ColPali 模型（GPU）
│  ├─ 分片處理（每張圖 1024 區塊）
│  ├─ 向量化與品質驗證
│  └─ 生成多向量集合
│
├─ [Task 4] ImageBind 空間對齐
│  ├─ 初始化 ImageBind 編碼器
│  ├─ 將 ColPali 向量映射至統一空間
│  ├─ 計算跨模態對齍分數
│  └─ 驗證對齐品質（分數 > 0.85）
│
└─ [Output] 序列化結果
   ├─ 多向量集合 (Parquet/HDF5)
   ├─ 元資料索引 (JSON/SQLite)
   ├─ 向量統計摘要 (統計指標)
   └─ 品質報告 (覆蓋率、缺陷率)
```

### 1.4 輸出介面（Output Interface）

```python
class VisualFeatureBundle:
    """
    Vision-Ingestion-Agent 的標準輸出結構
    """
    slide_id: str                           # 唯一標識符
    page_index: int                          # 頁面序號
    multi_vectors: np.ndarray               # 形狀:(1024, 128)
    patch_coordinates: List[Tuple[int,int]] # 各 patch 在圖像中的座標
    imagebind_vector: np.ndarray            # 形狀:(1024,) 或 (512,)，共享空間
    metadata: Dict[str, Any]                # 來源、渲染時間等
    quality_metrics: Dict[str, float]       # 覆蓋率、幾何完整性等
```

### 1.5 性能指標與 SLA

| 指標 | 目標 | 備註 |
|------|------|------|
| 單頁面渲染時間 | < 500ms | GPU 加速情況 |
| 單頁面特徵提取時間 | < 2 秒 | ColPali 推理 |
| 多模態對齐時間 | < 300ms | ImageBind 編碼 |
| 向量品質（覆蓋率） | > 98% | 有效區塊數 / 總區塊數 |
| 批處理吞吐量 | > 100 頁/分鐘 | 包含 GPU 使用 |

---

## 代理 2：Lakehouse-Retrieval-Agent（大規模檢索管理員）

### 2.1 職責與目標

**核心使命**：專責管理 LanceDB 實例，設計與執行高效的兩層檢索策略，確保在百萬級投影片語料中實現毫秒級精確檢索。

**關鍵目標**：
- 設計雙層檢索管道，結合粗級篩選與細粒度 MaxSim 精比對
- 維持檢索效能 SLA（< 200ms 端到端延遲）
- 提供即時的增量索引與大規模資料同步能力

### 2.2 技術職責

#### 2.2.1 LanceDB 集群部署與管理
```
LanceDB 架構：

┌─────────────────────────────────────────────────┐
│        LanceDB Vector Database Cluster            │
├─────────────────────────────────────────────────┤
│                                                   │
│  ┌──────────────┐  ┌──────────────┐             │
│  │   Shard 1    │  │   Shard 2    │  ...  │
│  │ (Partial     │  │ (Partial     │             │
│  │  Vectors)    │  │  Vectors)    │             │
│  └──────────────┘  └──────────────┘             │
│                                                   │
│  ┌────────────────────────────────────┐         │
│  │    主索引（IVF/LSH 混合）          │         │
│  │  - 向量量化與分組                  │         │
│  │  - 快速粗級檢索                    │         │
│  └────────────────────────────────────┘         │
│                                                   │
│  ┌────────────────────────────────────┐         │
│  │    元資料存儲                       │         │
│  │  - 頁面 ID, 來源路徑, 時間戳       │         │
│  │  - FTS 索引（全文檢索）            │         │
│  └────────────────────────────────────┘         │
│                                                   │
└─────────────────────────────────────────────────┘
```

**職責**：
- 初始化 LanceDB 連接池與分佈式索引
- 配置硬體資源分配（GPU 記憶體、磁碟 I/O）
- 監控連接健康與性能指標

#### 2.2.2 第一階段：向量篩選（Vector Filtering Layer）
```
Input:  查詢向量 (query_vector)
        語料庫中的全部向量 (corpus_vectors: N × 128)

Process:
  1. 快速粗檢索
     ├─ 利用 IVF (Inverted File) 索引定位最近簇
     ├─ 或使用 LSH (Locality Sensitive Hashing) 快速篩選
     └─ 返回前 K_1 個候選 (K_1 = 100~500)

  2. 可選的全文檢索（FTS）過濾
     ├─ 如果查詢包含文字關鍵詞，同時檢索元資料
     ├─ 結合向量與 FTS 結果（交集或聯集）
     └─ 進一步縮小候選範圍

Output: 候選投影片集合 (Top-K_1)
        │
        ├─ slide_id_1
        ├─ slide_id_2
        ├─ ...
        └─ slide_id_K1 (相似度預估值)
```

**演算法細節**：
- 向量量化：將 128 維向量量化為 8/16 bits，加速檢索但保留精度
- 距離計算：使用優化的 L2/Cosine 距離實現
- 預期召回率：> 95%（在後續 MaxSim 階段前）

#### 2.2.3 第二階段：MaxSim 精細比對（MaxSim Fine-grained Matching）
```
Input:  候選投影片集合 (Top-K_1, 來自第一階段)
        查詢多向量 (query_multi_vectors: Q × 128)
        文件多向量 (doc_multi_vectors: 每張投影片 1024 × 128)

Process: MaxSim 延遲交互演算法
  
  對每個候選投影片 doc_i：
    1. 計算視覺特徵與查詢的逐塊相似度矩陣
       similarity_matrix = query_vectors @ doc_vectors_i.T
       # 形狀: (Q, 1024)
    
    2. 對每個查詢向量取最大相似度（Late Interaction）
       max_sim_scores = max(similarity_matrix, axis=1)
       # 形狀: (Q,)
    
    3. 取整個查詢的平均或加權最大值
       final_score_i = mean(max_sim_scores) or weighted_combination
    
    4. 保存最終排序分數

  排序全部候選
  返回前 K_2 個結果 (K_2 = 10~20)

Output: 精確排序的投影片列表
        │
        ├─ (slide_id_1, maxsim_score_1, evidence_regions)
        ├─ (slide_id_2, maxsim_score_2, evidence_regions)
        ├─ ...
        └─ (slide_id_K2, maxsim_score_K2, evidence_regions)
```

**數學表達**：
$$\text{MaxSim}(q, d) = \frac{1}{|Q|} \sum_{i=1}^{|Q|} \max_{j=1}^{|D|} \text{sim}(q_i, d_j)$$

其中 $q_i$ 是查詢的第 $i$ 個區塊向量，$d_j$ 是文件的第 $j$ 個區塊向量。

#### 2.2.4 混合檢索管道（Hybrid Retrieval Pipeline）
```
查詢路由與融合：

Input: 用戶查詢 (文字 + 可選圖像)

分支 A: 純向量檢索路徑
  ├─ 查詢向量化（CLIP/ImageBind 編碼）
  ├─ 第一階段粗檢索 (Top-K_1 = 500)
  ├─ 第二階段 MaxSim 精細比對 (Top-K_2 = 20)
  └─ 向量得分

分支 B: 文字關鍵詞路徑（可選）
  ├─ 關鍵詞抽取
  ├─ FTS 檢索投影片元資料
  └─ 文字匹配得分

融合：
  最終得分 = α × 向量得分 + β × 文字得分
           (α + β = 1, 可調整)

Output: 融合排序結果 (Top-K_final)
```

### 2.3 工作流程（Workflow）

```
Lakehouse-Retrieval-Agent 處理流程：

┌─ 查詢輸入（文字 / 圖像 / 混合）
│
├─ [Task 1] 查詢特徵化
│  ├─ 文字編碼（CLIP Text Encoder）
│  ├─ 圖像編碼（ColPali / 其他視覺編碼器）
│  └─ ImageBind 空間對齐
│
├─ [Task 2] 連接 LanceDB
│  ├─ 獲取連接池中的可用連接
│  ├─ 檢查索引狀態與新鮮度
│  └─ 初始化查詢上下文（分片、超時配置等）
│
├─ [Task 3] 第一階段粗檢索
│  ├─ 啟動 IVF/LSH 快速篩選
│  ├─ 檢索前 K_1 = 500 個候選
│  └─ 記錄檢索延遲與命中率
│
├─ [Task 4] 可選 FTS 過濾（如有文字查詢）
│  ├─ 分析查詢關鍵詞
│  ├─ 執行全文檢索於元資料
│  ├─ 與向量結果交集
│  └─ 縮小候選集合
│
├─ [Task 5] 第二階段 MaxSim 精檢索
│  ├─ 載入候選投影片的完整多向量
│  ├─ 執行逐塊相似度計算（GPU 加速）
│  ├─ 應用 MaxSim 延遲交互演算法
│  ├─ 生成最終排序分數
│  └─ 檢索證據區域（最大得分所在的投影片區塊）
│
├─ [Task 6] 結果彙總
│  ├─ 生成排序投影片列表（Top-K_2 = 20）
│  ├─ 計算檢索指標（MRR, NDCG, 延遲）
│  └─ 記錄審計日誌
│
└─ [Output] 排序結果集合
   ├─ 投影片 ID 列表（已排序）
   ├─ MaxSim 相似度分數
   ├─ 證據區域指示符（圖像區塊位置）
   ├─ 檢索耗時統計
   └─ 索引狀態報告
```

### 2.4 輸出介面（Output Interface）

```python
class RetrievalResult:
    """
    Lakehouse-Retrieval-Agent 的標準輸出結構
    """
    ranking: List[RetrievalCandidate]
    
class RetrievalCandidate:
    slide_id: str
    page_index: int
    maxsim_score: float              # [0.0, 1.0]
    evidence_regions: List[Tuple[int,int]]  # 證據區塊座標
    retrieval_stage: str             # "filtering" or "reranking"
    metadata: Dict[str, Any]

class RetrievalMetrics:
    total_latency_ms: float
    filter_stage_latency_ms: float
    maxsim_stage_latency_ms: float
    candidates_examined: int
    recall_at_10: float
    mrr: float
```

### 2.5 性能指標與 SLA

| 指標 | 目標 | 備註 |
|------|------|------|
| 第一階段延遲 | < 50ms | 粗檢索 (500 候選) |
| 第二階段延遲 | < 100ms | MaxSim 精檢索 (20 結果) |
| 總檢索延遲 | < 200ms | 包含 I/O 與通信 |
| Recall@100 | > 95% | 第一階段召回率 |
| MRR@10 | > 0.75 | 平均倒數排名 |
| NDCG@10 | > 0.78 | 歸一化折扣營利值 |
| P@1 | > 85% | 首名精度 |
| 並發支持 | ≥ 100 | 同時用戶查詢 |

---

## 代理 3：Reasoning-Reranker-Agent（推理重排專家）

### 3.1 職責與目標

**核心使命**：搭載 MM-R5 多模態推理模型，針對初步檢索結果生成詳細的思維鏈（Chain-of-Thought）推理過程，實現高度的決策透明度與可解釋性。

**關鍵目標**：
- 為每份候選投影片生成清晰的多步驟推理論證
- 基於推理過程的完整性與置信度進行精確重排
- 提供可視化的推理解釋，增強用戶信任度

### 3.2 技術職責

#### 3.2.1 MM-R5 推理模型初始化與推理管道
```
MM-R5 推理流程：

Input: 用戶查詢 + 候選投影片集合 (Top-K 來自 Lakehouse-Agent)

Process:

┌─ 初始化 MM-R5 模型
│  ├─ 加載預訓練權重（本地或雲端）
│  ├─ 配置推理參數（beam size, 溫度, top-k 採樣）
│  └─ 準備 GPU/CPU 推理環境
│
├─ 對每個候選投影片執行推理
│  ├─ 構建提示模板（Prompt Template）
│  │   包含: 查詢 + 投影片內容 + 推理目標
│  ├─ 調用 MM-R5 推理端點
│  ├─ 生成思維鏈推理過程
│  ├─ 提取推理文本與信度分數
│  └─ 存儲中間推理狀態
│
├─ 推理評分與整合
│  ├─ 分析推理過程的邏輯完整性
│  ├─ 評估與查詢的語義契合度
│  ├─ 計算推理信度分數 [0.0, 1.0]
│  └─ 生成重排分數 = α × 視覺相似度 + β × 推理信度
│
└─ 重排結果
   └─ 輸出排序列表 (按重排分數 降序)

Output: 推理-重排結果集合
```

#### 3.2.2 思維鏈（CoT）推理模塊
```
推理結構化流程：

查詢："機器學習在金融風控的應用"
投影片 #42 內容（文本提取或視覺描述）："...風險管理、算法模型、資料驅動..."

MM-R5 推理過程：

Step 1 - 視覺感知 (Visual Perception)
  ├─ 檢測投影片標題："Risk Management with AI"
  ├─ 識別關鍵視覺元素：圖表、演算法圖示
  ├─ 提取文本內容（結合 OCR 或視覺語言理解）
  └─ 感知結論："投影片包含風控相關的視覺與文字線索"

Step 2 - 查詢解析 (Query Understanding)
  ├─ 拆解查詢核心概念：["機械學習", "金融", "風控"]
  ├─ 分析查詢的意圖：尋找應用案例 / 技術闡述
  └─ 查詢解析結論："查詢尋求 ML + 金融風控 的關聯"

Step 3 - 語義對齐 (Semantic Alignment)
  ├─ 投影片標題與查詢核心詞的相似度：0.92 ✓ (高)
  ├─ 投影片內容與 "機器學習" 的相關性：0.88 ✓
  ├─ 投影片內容與 "金融風控" 的相關性：0.85 ✓
  └─ 對齐結論："三個核心概念均有對應匹配"

Step 4 - 深層推理 (Deep Reasoning)
  ├─ 推理角度 1：技術適用性
  │   └─ "此投影片展示 ML 演算法如何應用於風控場景"
  ├─ 推理角度 2：案例相關性
  │   └─ "內容涵蓋具體的風控指標與 ML 模型選擇"
  ├─ 推理角度 3：時效性
  │   └─ "內容涉及當前業界最佳實踐"
  └─ 綜合推理結論："此投影片是查詢的高度相關案例"

Step 5 - 信度評估 (Confidence Assessment)
  ├─ 推理幾何完整性：5/5 (完整性高)
  ├─ 視覺證據強度：4/5 (有力但非直接)
  ├─ 語義對齐確定性：5/5 (明確)
  └─ 最終信度分數：88.0% (高信度推薦)

推理過程輸出：
  推理鏈文本、中間分數、最終置信度、證據引用
```

#### 3.2.3 推理評分函數（Reasoning Scoring Function）
```
最終重排分數計算：

score_final = λ_1 × score_retrieval 
            + λ_2 × score_reasoning 
            + λ_3 × score_completeness

其中：
- score_retrieval: 來自 Lakehouse-Agent 的 MaxSim 分數 [0, 1]
- score_reasoning: MM-R5 推理信度分數 [0, 1]
- score_completeness: 推理邏輯鏈的完整性評分 [0, 1]
- λ_1, λ_2, λ_3: 權重係數（Σ λ_i = 1），典型值 (0.4, 0.4, 0.2)

動態權重調整：
- 若查詢複雜度高（多概念），增加 λ_2 權重
- 若用戶偏好可解釋性，增加 λ_3 權重
- 若精確性要求極高，增加 λ_1 權重

推理過程的可實現性指標：
  interpretability_score = 
    Σ(step_clarity) / num_steps 
    × (1 - hallucination_penalty)
    × coherence_factor
```

### 3.3 工作流程（Workflow）

```
Reasoning-Reranker-Agent 處理流程：

┌─ 接收檢索候選集合
│  └─ 來自 Lakehouse-Retrieval-Agent (Top-20 投影片)
│
├─ [Task 1] MM-R5 初始化
│  ├─ 加載模型權重（~7B 參數）
│  ├─ 配置推理超參數
│  ├─ 驗證 GPU 記憶體充足
│  └─ 預熱推理管道
│
├─ [Task 2] 構建推理提示
│  ├─ 格式化查詢文本
│  ├─ 轉換投影片內容為自然語言描述或提取關鍵文字
│  ├─ 設計系統提示（System Prompt），引導推理方向
│  └─ 生成候選-查詢配對
│
├─ [Task 3] 批量推理執行
│  ├─ 對每個投影片候選並行調用 MM-R5
│  ├─ 記錄推理過程文本與中間狀態
│  ├─ 監控推理延遲（每個樣本 ~1-3 秒）
│  └─ 錯誤處理（推理失敗回退至檢索分數）
│
├─ [Task 4] 推理評分與分析
│  ├─ 提取置信度分數與邏輯完整性評分
│  ├─ 計算各維度得分（視覺感知、語義對齐等）
│  ├─ 檢測潛在的推理錯誤或幻覺（初步檢測）
│  └─ 應用動態權重融合
│
├─ [Task 5] 重排與排序
│  ├─ 基於最終重排分數排序候選
│  ├─ 生成置信度排序標籤（高 / 中 / 低）
│  └─ 嘗試多樣性重排（Diversity Reranking，可選）
│
└─ [Output] 推理-重排結果
   ├─ 重排投影片列表 (Top-K, 按新排序)
   ├─ 完整推理鏈文本 (每個候選)
   ├─ 推理分數與置信度 (可視化)
   ├─ 構成推理的關鍵句子與引用
   └─ 推理過程審計日誌
```

### 3.4 輸出介面（Output Interface）

```python
class ReasoningResult:
    """
    Reasoning-Reranker-Agent 的標準輸出結構
    """
    ranking: List[RankedCandidate]
    
class RankedCandidate:
    slide_id: str
    original_rank: int                     # 來自檢索階段的排名
    reranked_score: float                  # [0.0, 1.0]
    retrieval_score: float                 # MaxSim 分數
    reasoning_score: float                 # MM-R5 推理信度
    inference_text: str                    # 完整推理鏈文本
    reasoning_steps: List[ReasoningStep]   # 結構化推理步驟
    confidence_level: Literal["high", "medium", "low"]
    key_evidence_phrases: List[str]        # 推理中提及的關鍵句子
    
class ReasoningStep:
    step_id: int
    step_name: str                         # "Visual Perception", "Semantic Alignment" 等
    reasoning_text: str
    local_score: float                     # 該步驟的得分
    confidence: float                      # 該步驟的置信度
```

### 3.5 性能指標與 SLA

| 指標 | 目標 | 備註 |
|------|------|------|
| 單推理延遲 | 1-3 秒 | MM-R5 模型推理 |
| 批量推理吞吐 | 5-10 候選/分鐘 | 並行處理 |
| 推理透明度分數 | > 90% | SHAP-style 可解釋性量化 |
| 推理-檢索對齐度 | > 85% | 人工評估一致性 |
| 推理邏輯完整性 | > 95% | 多步驟推理的覆蓋率 |
| 端到端可解釋性 | > 95% | 能為所有結果生成推理 |

---

## 代理 4：Argos-Verification-Agent（視覺證據驗證官）

### 4.1 職責與目標

**核心使命**：作為系統輸出的最後把關者，融合 Argos 框架的驗證邏輯。檢查 Reasoning-Reranker-Agent 的推理結果是否與投影片的真實視覺內容完全對齊，徹底消除視覺幻覺。

**關鍵目標**：
- 驗證推理內容是否在投影片中有真實的視覺或文字證據
- 自動偵測並降權缺乏證據支撐的推論
- 生成可視化的「證據地圖」，展示推理對應的投影片區域
- 確保最終輸出結果的 100% 準確性與可追蹤性

### 4.2 技術職責

#### 4.2.1 推論-視覺映射檢查（Reasoning-to-Visual Grounding）
```
驗證流程：

Input: 推理結果 (包含推理文本與中間步驟)
       原始投影片圖像 & 多向量表示
       推理中提及的關鍵實體與概念

Process:

┌─ 推理內容解析
│  ├─ 提取推理中所有提及的視覺元素
│  │  例："標題中包含 'Risk Management'"
│  │      "圖表展示下降趨勢"
│  │      "左側文字區塊描述算法"
│  ├─ 轉換為結構化查詢
│  │  {element: "標題", keyword: "Risk Management", 
│  │   expected_region: "top_center", confidence: 0.95}
│  └─ 記錄推理的證據需求清單
│
├─ 視覺定位 (Spatial Grounding)
│  ├─ 利用 OCR/視覺語言模型在投影片中定位關鍵元素
│  │  - 文字搜尋："Risk Management" 在圖像中的位置
│  │  - 圖形偵測：識別圖表類型 & 空間位置
│  │  - 區域分類：投影片分割為 [標題, 圖表, 文字, 其他] 區域
│  ├─ 映射到視覺區塊座標 (patch coordinates)
│  │  例：[top_left: (15,2), bottom_right: (35,10)] in patch grid
│  └─ 計算覆蓋度 (Coverage Ratio)
│      覆蓋度 = (有視覺證據的區域數) / (推理中提及的區域數)
│
├─ 證據驗證
│  ├─ 定量檢查：覆蓋度 ≥ 0.88 ? "通過" : "警告"
│  ├─ 定性檢查：視覺元素是否與推理描述語義一致
│  │  例：推理說 "增長趨勢" 但圖表顯示 "下降" → 矛盾❌
│  ├─ 信度評估：基於視覺清晰度與定位精度
│  └─ 生成驗證結果 (Pass / Warn / Fail)
│
└─ 幻覺風險評估
   ├─ 若驗證失敗，計算 hallucination_risk_score [0, 1]
   ├─ 幻覺風險高時，標記為 "LOW_CONFIDENCE"
   └─ 記錄缺失的證據與推理-視覺差距

Output: 驗證報告
  ├─ 驗證狀態 (pass / warn / fail)
  ├─ 證據覆蓋度百分比
  ├─ 幻覺風險分數
  ├─ 視覺定位結果 (區塊座標)
  ├─ 缺失證據列表 (若有)
  └─ 調整後的結果信度
```

#### 4.2.2 幻覺偵測與動態降權
```
幻覺風險評估模型：

hallucination_risk = 
    w_1 × (1 - evidence_coverage_ratio)
  + w_2 × (1 - semantic_consistency_score)
  + w_3 × (number_of_unreferenced_claims / total_claims)

其中：
- evidence_coverage_ratio: 有視覺支撐的推理內容比例 [0, 1]
- semantic_consistency_score: 推理與視覺內容的語義一致度 [0, 1]
- number_of_unreferenced_claims: 沒有視覺指向的聲明數
- w_1, w_2, w_3: 權重係數 (Σ w_i = 1)，典型值 (0.4, 0.35, 0.25)

風險級別分類：
  hallucination_risk < 0.15  → "低風險" (綠色)
  0.15 ≤ risk < 0.45         → "中風險" (黃色，須標記)
  risk ≥ 0.45                → "高風險" (紅色，需重排或警告)

動態分數調整：
  adjusted_score = original_score × (1 - hallucination_risk ^ 0.5)
  
  例：original_score = 0.9, hallucination_risk = 0.36
      adjusted_score = 0.9 × (1 - √0.36) = 0.9 × 0.4 = 0.36
      (分數大幅下降，反映高幻覺風險)
```

#### 4.2.3 審計日誌與決策追蹤
```
審計日誌結構：

{
  "verification_id": "v-20240417-123456",
  "timestamp": "2024-04-17T10:23:45Z",
  "slide_id": "ppt_#42",
  "reasoning_text": "此投影片展示 ML 演算法...",
  
  "verification_steps": [
    {
      "step": "evidence_extraction",
      "extracted_claims": [
        {"claim": "標題含 'Risk Management'", "confidence": 0.95},
        {"claim": "含有演算法圖表", "confidence": 0.88}
      ]
    },
    {
      "step": "visual_grounding",
      "located_elements": [
        {"element": "標題", "patch_coords": [15, 2, 35, 10], "confidence": 0.98},
        {"element": "圖表", "patch_coords": [40, 15, 70, 40], "confidence": 0.85}
      ],
      "unlocated_claims": []
    },
    {
      "step": "consistency_check",
      "semantic_alignment": 0.92,
      "coverage_ratio": 0.98,
      "consistency_verdict": "PASS"
    }
  ],
  
  "hallucination_assessment": {
    "risk_score": 0.08,
    "risk_level": "LOW",
    "unreferenced_claims": 0,
    "recommendation": "ACCEPT"
  },
  
  "final_verdict": {
    "status": "VERIFIED",
    "adjusted_score": 0.88,
    "confidence": "HIGH",
    "evidence_map_url": "..."
  }
}
```

#### 4.2.4 可視化證據地圖（Evidence Map Visualization）
```
證據地圖呈現：

原始投影片圖像
│
├─ 層 1：区塊著色
│  ├─ 綠色塊：有強視覺支撐的區域 (confidence > 0.9)
│  ├─ 黃色塊：有中等支撐的區域 (0.7 < confidence ≤ 0.9)
│  ├─ 紅色塊：有弱支撐的區域 (confidence ≤ 0.7)  
│  └─ 灰色塊：未被推理引用的區域
│
├─ 層 2：標註與箭頭
│  ├─ 推理步驟編號 → 對應視覺區域
│  └─ 證據短語標籤
│
└─ 層 3：信度指示
   ├─ 整體驗證狀態 (PASS/WARN/FAIL)
   ├─ 幻覺風險條 (0% 到 100%)
   └─ 可點擊詳情卡
```

### 4.3 工作流程（Workflow）

```
Argos-Verification-Agent 處理流程：

┌─ 接收推理-重排結果
│  └─ 來自 Reasoning-Reranker-Agent
│
├─ [Task 1] 驗證準備
│  ├─ 載入投影片原始圖像
│  ├─ 初始化視覺定位模型（OCR + 視覺識別）
│  ├─ 配置驗證閾值與風險模型參數
│  └─ 驗證 GPU/CPU 資源充足
│
├─ [Task 2] 推理內容解析
│  ├─ 提取推理文本中的所有聲明 (Claims)
│  ├─ 識別實體與關鍵概念
│  ├─ 標準化為結構化查詢
│  └─ 構建「證據需求清單」
│
├─ [Task 3] 視覺定位與區域標準化
│  ├─ 利用 OCR 搜尋文字聲明
│  │  └─ 定位標題、段落、標籤文字
│  ├─ 利用視覺識別偵測圖形元素
│  │  └─ 定位圖表、圖示、圖片
│  ├─ 計算視覺元素 → 多向量區塊的映射
│  │  └─ 轉換為投影片區塊座標 (patch 網格)
│  └─ 評估定位置信度
│
├─ [Task 4] 證據驗證與一致性檢查
│  ├─ 比對推理聲明 vs. 視覺定位結果
│  ├─ 計算覆蓋度比率與語義一致性
│  ├─ 生成定性驗證結論
│  └─ 標記未被證實的聲明 (claims without evidence)
│
├─ [Task 5] 幻覺風險評估
│  ├─ 應用幻覺風險模型
│  ├─ 計算 hallucination_risk_score
│  ├─ 分類風險級別 (低/中/高)
│  ├─ 計算分數調整因子 (discount_factor)
│  └─ 生成降權後的信度信息
│
├─ [Task 6] 結果調整與決策
│  ├─ 若驗證結果為 PASS
│  │  └─ 保持原始排序不變，標記為「已驗證」
│  ├─ 若驗證為 WARN (中風險)
│  │  └─ 降低結果排序分數，添加警告標籤
│  ├─ 若驗證為 FAIL (高風險)
│  │  └─ 大幅降低分數或從排序中移除，推薦人工審查
│  └─ 生成決策理由
│
├─ [Task 7] 證據地圖生成
│  ├─ 生成投影片的視覺化標註版本
│  ├─ 將推理步驟映射至視覺區域
│  ├─ 編碼為互動式 HTML/Canvas 模板
│  └─ 準備可視化資源 URL
│
└─ [Output] 最終驗證結果
   ├─ 驗證狀態 (PASS / WARN / FAIL)
   ├─ 調整後的排序結果
   ├─ 幻覺風險評分
   ├─ 證據覆蓋度報告
   ├─ 審計日誌 (JSON)
   ├─ 證據地圖 URL (可視化資源)
   └─ 用戶可讀的驗證摘要
```

### 4.4 輸出介面（Output Interface）

```python
class VerificationResult:
    """
    Argos-Verification-Agent 的標準輸出結構
    """
    verified_ranking: List[VerifiedCandidate]
    verification_audit_trail: Dict[str, Any]
    
class VerifiedCandidate:
    slide_id: str
    original_reranked_score: float       # 來自 Reasoning-Agent
    adjusted_score: float                 # 驗證後的分數
    verification_status: Literal["pass", "warn", "fail"]
    hallucination_risk_score: float      # [0.0, 1.0]
    hallucination_risk_level: Literal["low", "medium", "high"]
    evidence_coverage_ratio: float       # [0.0, 1.0]
    semantic_consistency: float          # [0.0, 1.0]
    verified_claims: List[str]           # 已驗證的聲明
    unverified_claims: List[str]         # 缺乏證據的聲明
    evidence_regions: List[EvidenceRegion]  # 視覺證據位置
    evidence_map_url: Optional[str]      # 可視化地圖 URL
    
class EvidenceRegion:
    patch_coords: Tuple[int, int, int, int]  # [top-left_x, top-left_y, bottom-right_x, bottom-right_y]
    region_type: Literal["text", "chart", "image", "other"]
    referenced_claim: str
    confidence: float
```

### 4.5 性能指標與 SLA

| 指標 | 目標 | 備註 |
|------|------|------|
| 單驗證延遲 | 500-1000ms | OCR + 視覺定位 |
| 幻覺檢測準確度 | > 92% | 混淆矩陣精度 |
| 視覺證據定位精度 | > 95% | 區塊級覆蓋率 |
| 證據覆蓋率 | > 98% | 推理聲明的支撐率 |
| 假陽性率 | < 5% | 誤標為幻覺的比例 |
| 假陰性率 | < 2% | 漏檢幻覺的比例 |
| 證據地圖生成時間 | < 200ms | 可視化資源準備 |
| 審計日誌完整性 | 100% | 每次驗證均記錄 |

---

## 5. 多代理協調與通訊協議

### 5.1 代理間的消息流（Inter-Agent Message Flow）

```
系統端到端流程：

用戶 (查詢)
  │
  ↓
[Query Router / Load Balancer]
  │
  ├─→ Vision-Ingestion-Agent ─────→ LanceDB
  │   (新增 PPT 時觸發)
  │
  └─→ Lakehouse-Retrieval-Agent
      ├─→ 第一階段過濾 (IVF/LSH indexed search)
      ├─→ 第二階段 MaxSim (colpali late interaction)
      │
      └─→ Reasoning-Reranker-Agent
          ├─→ MM-R5推理调用
          ├─→ 推理評分與重排
          │
          └─→ Argos-Verification-Agent
              ├─→ 視覺定位驗證
              ├─→ 幻覺偵測與降權
              │
              └─→ [最終結果] → 用戶

異步消息格式標準：

{
  "message_id": "msg-uuid",
  "timestamp": "2024-04-17T10:23:45.123Z",
  "source_agent": "Lakehouse-Retrieval-Agent",
  "target_agent": "Reasoning-Reranker-Agent",
  "payload": {
    "query": "...",
    "candidates": [
      {"slide_id": "...", "maxsim_score": 0.92, ...}
    ],
    "metadata": {...}
  },
  "priority": "high",
  "timeout_ms": 30000
}
```

### 5.2 容錯與降級策略

```
容錯樹：

若 Vision-Ingestion-Agent 失敗
  ├─ 重試 3 次，指數退避
  └─ 若仍失敗 → 降級至備用 OCR 方案（臨時解決）

若 Lakehouse-Retrieval-Agent 失敗
  ├─ 快速轉移至副本索引
  └─ 若無副本 → 拒絕查詢，返回服務不可用

若 Reasoning-Reranker-Agent 超時
  ├─ 跳過推理，使用檢索排序結果
  └─ 標記結果為「未推理」

若 Argos-Verification-Agent 偵測高幻覺風險
  ├─ 降低排序權重，添加警告標籤
  └─ 建議用戶優化查詢或人工審查

全系統熔斷機制：
  若錯誤率 > 10% 或延遲 > 2 秒
    └─ 啟動熔斷，返回快速降級結果
```

---

## 6. 監控、日誌與可觀測性

### 6.1 關鍵監控指標（Key Performance Indicators）

```yaml
監控儀表板指標：

1. 檢索層 (Retrieval)
   - 平均檢索延遲（ms）
   - MRR / NDCG / Recall@K
   - 索引新鮮度

2. 推理層 (Reasoning)
   - 推理延遲（秒/候選）
   - 推理成功率（%）
   - 推理透明度分數

3. 驗證層 (Verification)
   - 幻覺檢測準確度
   - 證據覆蓋率
   - 驗證延遲

4. 系統健康
   - 端到端延遲
   - 錯誤率
   - 各代理的可用性
```

### 6.2 結構化日誌格式

```json
{
  "timestamp": "2024-04-17T10:23:45.123Z",
  "request_id": "req-uuid",
  "query": "...",
  "stages": [
    {
      "stage_name": "Lakehouse-Retrieval",
      "duration_ms": 150,
      "candidates_count": 500,
      "status": "success"
    },
    {
      "stage_name": "Reasoning-Reranker",
      "duration_ms": 4500,
      "processed_count": 20,
      "status": "success"
    },
    {
      "stage_name": "Argos-Verification",
      "duration_ms": 800,
      "verification_results": {
        "pass_count": 18,
        "warn_count": 2,
        "fail_count": 0
      },
      "status": "success"
    }
  ],
  "final_result_count": 20,
  "total_latency_ms": 5450
}
```

---

## 7. 系統集成與部署考量

### 7.1 容器化與微服務架構

```docker
# Docker Compose 配置示例

services:
  vision-ingestion:
    image: drl-vision-agent:latest
    env: GPU-required
    volumes: [ppt-data, vector-output]
    
  lakehouse-retrieval:
    image: drl-lakehouse-agent:latest
    depends_on: [lancedb]
    
  reasoning-reranker:
    image: drl-reasoning-agent:latest
    env: GPU-required (7B 模型)
    
  argos-verification:
    image: drl-argos-agent:latest
    env: GPU-optional
    
  lancedb:
    image: lancedb:latest
    volumes: [vector-store]
    
  api-gateway:
    image: fastapi-gateway:latest
    ports: [8000:8000]
```

### 7.2 部署拓撲

```
┌──────────────────────────────────────────┐
│         用戶界面層 (Streamlit)            │
└────────────┬─────────────────────────────┘
             │
┌────────────▼─────────────────────────────┐
│ API Gateway / Load Balancer (FastAPI)    │
└─────────────┬──────────────────────────────┘
              │
    ┌─────────┴────────────────────────┐
    │                                  │
┌───▼──────────────────┐    ┌────────▼────────────┐
│ Retrieval Pipeline   │    │ Reasoning Pipeline  │
│ (Lakehouse-Agent)    │    │ (MM-R5 on GPU)      │
│ (GPU optional)       │    │                     │
└───┬──────────────────┘    └────────┬────────────┘
    │                               │
    └───────────┬───────────────────┘
                │
        ┌───────▼──────────────┐
        │ Verification Pipeline│
        │ (Argos-Agent)        │
        │ (GPU optional)       │
        └───────┬──────────────┘
                │
        ┌───────▼──────────────┐
        │ LanceDB Vector Store │
        └──────────────────────┘
```

---

## 總結

本四層多代理系統架構代表了現代企業級多模態檢索系統的最佳實踐，結合了最新的學術進展（ColPali, ImageBind, MM-R5, Argos）與工業級可靠性設計。每個代理專注其核心職責，通過清晰的通訊協議與容錯機制形成有機整體，為用戶提供準確、可解釋、零幻覺的簡報檢索體驗。
