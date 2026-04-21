## ADDED Requirements

### Requirement: 推論-視覺映射檢查與定位
系統 SHALL 提取推理過程中提及的所有聲明（claims），利用 OCR 與視覺語言模型在原始投影片圖像中定位相應的視覺元素，計算覆蓋度比率（coverage_ratio）= (有視覺證據的區域) / (推理提及的區域)，閾值 >= 0.88 時標記為通過。

#### Scenario: 推理聲明提取
- **WHEN** 接收推理結果（含推理文本與中間步驟）
- **THEN** 系統提取所有聲明，例如「標題含 'Risk Management'」、「含有下降趨勢圖表」，構建證據需求清單

#### Scenario: 視覺定位與座標映射
- **WHEN** 視覺定位模型執行
- **THEN** 系統在投影片圖像中定位聲明涉及的元素，轉換為多向量 patch 座標（例如 [top_left: (15,2), bottom_right: (35,10)] in 32×32 grid）

#### Scenario: 覆蓋度計算與驗證
- **WHEN** 視覺定位完成
- **THEN** 系統計算 coverage_ratio = (定位到的區域數) / (推理提及的區域數)，若 >= 0.88 標記「PASS」，否則「WARN」

### Requirement: 語義一致性檢查
系統 SHALL 驗證推理內容與視覺元素的語義一致性。例如，若推理聲稱「圖表顯示上升趨勢」而實際圖表曲線向下，系統 SHALL 標記為語義矛盾，semantic_consistency_score <= 0.5 觸發幻覺警報。

#### Scenario: 趨勢方向驗證
- **WHEN** 推理提及「投影片展示營收增長趨勢」
- **THEN** 系統分析投影片中的圖表線條方向，若實際向下則矛盾，semantic_consistency = 0.2，標記為「語義矛盾❌」

#### Scenario: 實體引用驗證
- **WHEN** 推理提及「投影片展示 5 個關鍵風控指標」
- **THEN** 系統計數投影片中的文字「指標」或相應的視覺標記，若實際只有 3 個則不一致，semantic_consistency = 0.6（部分匹配）

### Requirement: 幻覺風險評估與動態降權
系統 SHALL 計算幻覺風險分數（hallucination_risk），公式為：
hallucination_risk = w_1 × (1 - coverage_ratio) + w_2 × (1 - semantic_consistency) + w_3 × (unreferenced_claims_ratio)
其中 w_1 = 0.4, w_2 = 0.35, w_3 = 0.25。風險級別分類：< 0.15 (LOW)、0.15-0.45 (MEDIUM)、>= 0.45 (HIGH)。

#### Scenario: 低風險評估
- **WHEN** coverage_ratio = 0.98, semantic_consistency = 0.92, unreferenced_claims = 0
- **THEN** hallucination_risk = 0.4 × 0.02 + 0.35 × 0.08 + 0 = 0.036 → "LOW RISK"（綠色）

#### Scenario: 高風險評估
- **WHEN** coverage_ratio = 0.60, semantic_consistency = 0.40, unreferenced_claims_ratio = 0.4
- **THEN** hallucination_risk = 0.4 × 0.40 + 0.35 × 0.60 + 0.25 × 0.4 = 0.43 → "HIGH RISK"（紅色，需重排或警告）

#### Scenario: 動態分數調整
- **WHEN** 原始推理分數 original_score = 0.9，hallucination_risk = 0.36
- **THEN** adjusted_score = 0.9 × (1 - √0.36) = 0.9 × 0.4 = 0.36，分數大幅下降反映高風險

### Requirement: 驗證結果分類與決策
系統 SHALL 根據驗證流程輸出三種驗證狀態：PASS（所有檢查通過），WARN（中等風險，標記但保留），FAIL（高風險，建議移出或降權）。相應調整結果在最終排序中的位置。

#### Scenario: PASS 驗證
- **WHEN** 驗證完成，verification_status = PASS
- **THEN** 保持原始排序，結果標記為「已驗證」，前端以完整標記展示

#### Scenario: WARN 驗證
- **WHEN** 驗證完成，hallucination_risk ∈ [0.15, 0.45)
- **THEN** 驗證狀態 = WARN，結果排序分數降低 10-20%，前端用黃色警告符號標記

#### Scenario: FAIL 驗證
- **WHEN** 驗證完成，hallucination_risk >= 0.45
- **THEN** 驗證狀態 = FAIL，結果排序分數大幅降低（乘以 0.3-0.5），或建議從最終結果集中移除，標記為「低置信度」

### Requirement: 審計日誌與完整追蹤
系統 SHALL 記錄完整的驗證過程，包括推理聲明提取、視覺定位結果、語義檢查過程、風險評分、最終決策。審計日誌格式為 JSON，包含 verification_id、timestamp、驗證步驟、風險評估數據。

#### Scenario: 驗證審計記錄
- **WHEN** 驗證完成
- **THEN** 系統記錄完整的驗證過程至審計資料庫，JSON 格式，包含：
  - verification_id、timestamp、slide_id
  - verification_steps（證據提取、視覺定位、一致性檢查）
  - 每步的提取_claims、located_elements、unlocated_claims

#### Scenario: 決策理由追蹤
- **WHEN** 查詢某結果的驗證詳情
- **THEN** 系統返回完整的審計日誌，包括為何標記為 PASS/WARN/FAIL 的詳細理由，hallucination_risk 的計算過程

### Requirement: 可視化證據地圖生成
系統 SHALL 生成投影片的互動式證據地圖，將推理步驟與視覺證據對應展示。包括區塊著色（綠色 > 0.9 信度，黃色 0.7-0.9，紅色 <= 0.7，灰色未引用），推理步驟編號與箭頭指向，整體驗證狀態與幻覺風險進度條。

#### Scenario: 證據區塊著色
- **WHEN** 生成證據地圖
- **THEN** 將投影片的 1024 個 patch 按置信度著色：
  - 綠色：confidence > 0.9，有強視覺支撐
  - 黃色：0.7 < confidence <= 0.9，中等支撐
  - 紅色：confidence <= 0.7，弱支撐
  - 灰色：未被推理引用

#### Scenario: 互動式推理步驟標註
- **WHEN** 使用者在證據地圖上懸停某推理步驟
- **THEN** 地圖高亮該步驟相關的視覺區域，顯示置信度分數、證據短語

#### Scenario: 風險視覺指示
- **WHEN** 生成證據地圖
- **THEN** 在右上角顯示整體驗證狀態 (PASS/WARN/FAIL)、幻覺風險條（0-100%），提供快速的視覺反饋

### Requirement: OCR 與視覺識別集成
系統 SHALL 集成 OCR 引擎與視覺識別模型（基於 CLIP 或 ViT）用於視覺定位。支援文字搜尋（定位標題、段落、標籤），圖形偵測（識別圖表、圖示、圖片及其空間位置），面積分類（投影片分割為標題、圖表、文字、其他區域）。

#### Scenario: 文字搜尋與定位
- **WHEN** 推理聲稱「標題包含 'Machine Learning'」
- **THEN** OCR 引擎掃描投影片，定位 'Machine Learning' 文本在投影片中的像素座標與 patch 座標

#### Scenario: 圖表偵測與分類
- **WHEN** 推理提及「圖表顯示下降趨勢」
- **THEN** 視覺識別模型在投影片中偵測圖表，判斷圖表類型（折線圖、柱狀圖等），分析趨勢方向

#### Scenario: 區域分割
- **WHEN** 執行視覺定位前
- **THEN** 系統對投影片執行語義分割，標記各區域為「標題」、「圖表」、「文字」、「其他」，以優化後續定位

### Requirement: 效能與準確度 SLA
系統 SHALL 達成以下指標：單驗證延遲 500-1000ms，幻覺檢測准確度 > 92%，視覺證據定位精度 > 95%（patch 級），證據覆蓋率 > 98%，假陽性率 < 5%，假陰性率 < 2%，審計日誌完整性 100%。

#### Scenario: 驗證延遲測試
- **WHEN** 輸入推理結果進行驗證
- **THEN** 系統在 500-1000ms 內返回驗證結果（包括 OCR、視覺識別、風險計算）

#### Scenario: 幻覺偵測準確度評估
- **WHEN** 在標準測試集（100 個手工標註的幻覺樣本）上執行驗證
- **THEN** 正確識別率（Precision + Recall）> 92%，混淆矩陣誤分類 < 8%

#### Scenario: 視覺定位精度驗證
- **WHEN** 對定位結果與手工標註對比
- **THEN** 平均定位誤差 < 5 個 patch 單位，正確率 > 95%

### Requirement: 輸出介面標準化
系統 SHALL 返回 `VerificationResult` 物件，包含 `verified_ranking`（調整後的候選列表）和 `verification_audit_trail`。每個 `VerifiedCandidate` 含 slide_id、original_reranked_score、adjusted_score、verification_status、hallucination_risk_score、hallucination_risk_level、evidence_coverage_ratio、semantic_consistency、verified_claims、unverified_claims、evidence_regions、evidence_map_url。

#### Scenario: 完整驗證結果返回
- **WHEN** 驗證完成
- **THEN** 返回 VerificationResult，包括 verified_ranking（Top-20，已調整）、驗證審計日誌（JSON）、證據地圖 URL

#### Scenario: 可視化資源生成
- **WHEN** 生成證據地圖
- **THEN** 系統生成互動式 HTML/Canvas，上傳至靜態資源伺服器，evidence_map_url 指向該資源，用戶可在前端直接開啟查看
