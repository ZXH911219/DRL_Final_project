## ADDED Requirements

### Requirement: MM-R5 推理模型初始化與管理
系統 SHALL 支援 MM-R5 多模態推理模型（~7B 參數）的加載、配置、推理管道初始化。包括權重下載（本地或雲端倉庫）、推理超參數設定（beam size、採樣溫度、top-k）、GPU/CPU 環境驗證。

#### Scenario: 模型加載與驗證
- **WHEN** 系統啟動時
- **THEN** MM-R5 模型權重成功加載，推理管道預熱（1 次測試推理完成< 3 秒），GPU 記憶體配置確認

#### Scenario: 超參數配置
- **WHEN** 初始化推理引擎
- **THEN** beam_size = 3，temperature = 0.7，top_k = 50，確保推理的多樣性與品質平衡

#### Scenario: 備用 CPU 推理
- **WHEN** GPU 記憶體不足（< 4GB 可用）
- **THEN** 系統自動降級至 CPU 推理模式，推理延遲增加至 5-10 秒/候選，告知使用者延遲可能增加

### Requirement: 思維鏈推理過程生成
系統 SHALL 為每個候選投影片生成多步驟的思維鏈（Chain-of-Thought）推理過程。推理流程包括 5 個標準步驟：(1) 視覺感知，(2) 查詢解析，(3) 語義對齷，(4) 深層推理，(5) 信度評估。

#### Scenario: 標準推理流程
- **WHEN** 輸入查詢與候選投影片
- **THEN** 系統生成 5 步驟的推理過程，每步含推理文本、局部得分、置信度，最終輸出完整推理鏈文本 (< 300 詞)

#### Scenario: 視覺感知步驟
- **WHEN** 推理開始
- **THEN** 系統檢測投影片標題、識別關鍵視覺元素（圖表、演算法圖示、文字區域），生成描述性文本

#### Scenario: 語義對齷與匹配計數
- **WHEN** 執行語義對齷步驟
- **THEN** 系統計算投影片與查詢的核心概念重疊度（例如查詢「金融風控」涉及 3 個概念，投影片覆蓋 3 個 → 100% 對齷），評分 0.0-1.0

### Requirement: 推理評分函數與重排
系統 SHALL 計算最終重排分數，融合檢索分數、推理信度分數、推理邏輯完整性，加權公式為：
score_final = λ_1 × score_retrieval + λ_2 × score_reasoning + λ_3 × score_completeness
其中 λ_1, λ_2, λ_3 為可配置的權重係數（Σ λ_i = 1），預設值 (0.4, 0.4, 0.2)。

#### Scenario: 預設權重重排
- **WHEN** 接收 20 個檢索候選
- **THEN** 系統對每個候選執行推理，計算 score_retrieval（MaxSim）、score_reasoning（MM-R5 信度）、score_completeness（推理步驟完整性），融合成 score_final，重新排序

#### Scenario: 動態權重調整
- **WHEN** 使用者指定「高可解釋性優先」模式
- **THEN** 系統調整 λ_1 = 0.2，λ_2 = 0.3，λ_3 = 0.5，增加推理邏輯完整性的影響力

#### Scenario: 推理失敗回退
- **WHEN** MM-R5 推理因超時或異常而失敗
- **THEN** 系統保留該候選的檢索排序（score_retrieval），跳過推理評分，標記為「partial」結果

### Requirement: 結果置信度分類與標籤
系統 SHALL 根據推理信度分數將結果分類為三個置信度級別：HIGH（信度 > 0.8）、MEDIUM（0.6-0.8）、LOW（< 0.6）。每個結果附加置信度標籤供前端展示與使用者參考。

#### Scenario: 高置信結果
- **WHEN** 推理產生信度分數 0.9
- **THEN** 結果標籤為 HIGH，前端以綠色高亮展示，推薦加入最終結果集

#### Scenario: 低置信結果
- **WHEN** 推理產生信度分數 0.45
- **THEN** 結果標籤為 LOW，前端用黃色警告色展示，提示使用者結果可能不甚準確

### Requirement: 批量推理執行與並行化
系統 SHALL 支援批量推理，對初步檢索的 20 個候選投影片並行執行 MM-R5 推理。推理延遲每候選 1-3 秒，批量 20 個候選的平均耗時 < 1.5 分鐘（含 GPU 批處理開銷）。

#### Scenario: 批量推理吞吐
- **WHEN** 提交 20 個候選進行推理
- **THEN** 系統在 < 90 秒內完成所有推理，平均每候選 4.5 秒（考慮 GPU 批處理的共享開銷）

#### Scenario: GPU 批處理優化
- **WHEN** 批量執行推理時
- **THEN** 系統將候選分組為 batch_size = 4，並行推理，GPU 利用率 > 80%

#### Scenario: 推理隊列與非阻塞
- **WHEN** 檢索完成，推理隊列中已有待處理任務
- **THEN** 系統優先返回檢索結果至使用者，推理在後台異步進行，使用者可輪詢或訂閱推理完成事件

### Requirement: 推理過程審計與中間狀態保存
系統 SHALL 保存每次推理的完整中間狀態，包含推理步驟文本、局部得分、置信度。審計日誌格式化為 JSON，支援完整的決策追蹤與重放。

#### Scenario: 推理審計日誌記錄
- **WHEN** 推理完成
- **THEN** 系統記錄推理 ID、候選 slide_id、5 個推理步驟的詳細文本、得分、時間戳，存儲至審計資料庫

#### Scenario: 推理結果重放
- **WHEN** 使用者查詢某個過往的推理結果
- **THEN** 系統重新組織審計日誌中的中間狀態，生成可視化的推理鏈展示（支援逐步展開）

### Requirement: 效能與 SLA
系統 SHALL 達成以下效能指標：推理透明度分數 > 90%（SHAP-style 可解釋性量化），推理-檢索對齷度 > 85%（人工評估一致性），推理邏輯完整性 > 95%（多步驟涵蓋率），端到端可解釋性 > 95%（所有結果均含推理）。

#### Scenario: 推理透明度評估
- **WHEN** 評估推理過程的可解釋性
- **THEN** 量化為 0-100% 的分數，基於推理步驟的清晰度、證據引用、邏輯連貫性，目標 > 90%

#### Scenario: 人工評估對齷度
- **WHEN** 人類評審員評估推理與檢索結果的對齷度（1-10 分制）
- **THEN** 平均評分 > 8.5 分（折合 > 85%），代表推理理由與檢索排序高度一致

### Requirement: 輸出介面標準化
系統 SHALL 返回 `ReasoningResult` 物件，包含重排後的 `RankedCandidate` 列表。每個候選含 slide_id、original_rank、reranked_score、retrieval_score、reasoning_score、inference_text、reasoning_steps、confidence_level、key_evidence_phrases 等欄位。

#### Scenario: 完整推理結果返回
- **WHEN** 推理重排完成
- **THEN** 返回 ReasoningResult 物件，ranking 列表包含 Top-20 候選，每項含所有欄位，inference_text 為完整推理鏈（300 詞左右）

#### Scenario: 結構化推理步驟
- **WHEN** reasoning_steps 欄位包含 5 個推理步驟
- **THEN** 每個步驟為 ReasoningStep 物件，含 step_id、step_name、reasoning_text、local_score、confidence
