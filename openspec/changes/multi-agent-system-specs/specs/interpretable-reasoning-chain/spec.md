## ADDED Requirements

### Requirement: 結構化推理鏈框架
系統 SHALL 定義標準化的結構化推理鏈框架，包含 5 個連貫的推理步驟，每步輸出文本、局部得分、置信度。步驟依序為：(1) Visual Perception（視覺感知），(2) Query Understanding（查詢理解），(3) Semantic Alignment（語義對齷），(4) Deep Reasoning（深層推理），(5) Confidence Assessment（信度評估）。

#### Scenario: 標準推理結構
- **WHEN** MM-R5 對候選投影片執行推理
- **THEN** 生成 5 步驟的推理過程，每步 output 為 (text: str, local_score: float, confidence: float)

#### Scenario: 推理步驟的邏輯連接
- **WHEN** Step 1 的結論為「投影片含金融風控視覺元素」
- **THEN** Step 2-3 基於此結論進行查詢解析與對齷，形成邏輯層級

#### Scenario: 推理文本生成品質
- **WHEN** 生成推理文本
- **THEN** 文本應清晰、自然、人類可讀，避免機器生成的生硬表述，平均長度 50-100 詞/步

### Requirement: 多維度推理評分
系統 SHALL 為每個推理步驟計算多維度評分：清晰度（clarity）、證據強度（evidence_strength）、邏輯連貫性（coherence）、與查詢的相關性（relevance）。各維度得分 ∈ [0, 1]，最終綜合得分為加權平均。

#### Scenario: Step-level 評分計算
- **WHEN** 評估「Visual Perception 步驟」
- **THEN** 計算 clarity = 0.9（表述清楚），evidence_strength = 0.85（有視覺證據），coherence = 0.88（邏輯清晰），relevance = 0.92（與查詢相關），綜合 = avg([0.9, 0.85, 0.88, 0.92]) = 0.89

#### Scenario: 跨步驟評分傳遞
- **WHEN** Step 3 依賴 Step 2 的結論
- **THEN** 若 Step 2 的相關性低（relevance = 0.4），Step 3 的邏輯連貫性自動降低

### Requirement: 推理過程的可視化與逐步展開
系統 SHALL 支援推理過程的分層展示，使用者可逐步展開各推理步驟，查看詳細的推理文本、中間結果、評分。支援互動式 UI 元件（可折疊的步驟卡、懸停提示、色彩編碼的置信度指示）。

#### Scenario: 默認推理摘要
- **WHEN** 搜尋結果首次展示
- **THEN** 單行摘要：「該投影片高度相關（信度 0.88），主要原因是[2-3 詞總結]」

#### Scenario: 展開詳細推理過程
- **WHEN** 使用者點擊「查看推理過程」
- **THEN** UI 展開 5 個推理步驟，每步顯示：Step 標題、詳細推理文本、局部得分、置信度條形圖

#### Scenario: 步驟交互與證據跳轉
- **WHEN** 使用者懸停「Step 3: 語義對齷」
- **THEN** UI 高亮該步驟涉及的投影片區域（配合證據地圖），顯示「對齷命中：3 個核心概念」

### Requirement: 推理鏈的邏輯完整性驗證
系統 SHALL 驗證推理鏈中各步驟的邏輯連接，確保步驟間的推論是有效的、無矛盾的。例如，若 Step 3 結論與 Step 2 結論矛盾，系統標記為「邏輯不連貫」，降低該推理鏈的可信度。

#### Scenario: 邏輯連錯偵測
- **WHEN** 推理過程完成
- **THEN** 系統檢查各步驟間的依賴關係，若發現矛盾（例如 Step 2：「查詢不包含金融概念」，但 Step 3：「金融相關性高」），標記為矛盾，邏輯完整度評分減 0.2

#### Scenario: 邏輯完整性修復建議
- **WHEN** 驗證發現邏輯問題
- **THEN** 系統生成修復建議，例如「建議重新分析查詢意圖」或「推理步驟 X 需補充證據」

### Requirement: 推理鏈的可解釋性量化
系統 SHALL 定義一個可解釋性評分（Interpretability Score），基於推理過程的清晰度、證據充分性、論證完整性、用戶可理解度。評分 ∈ [0, 1]，> 0.90 標記為「高度可解釋」。

#### Scenario: 可解釋性評分計算
- **WHEN** 評估某推理鏈的可解釋性
- **THEN** 綜合評估：
  - 推理文本清晰度：0.95
  - 證據引用充分性：0.88
  - 邏輯連貫性：0.92
  - 用戶評價（基於反饋）：0.85
  - 可解釋性 = avg([0.95, 0.88, 0.92, 0.85]) = 0.90

#### Scenario: 低可解釋性警告
- **WHEN** 推理鏈的可解釋性 < 0.75
- **THEN** 系統標記為「可解釋性低」，建議使用者謹慎參考，或提示需人工審查

### Requirement: 推理鏈與投影片視覺內容的映射
系統 SHALL 為推理鏈中提及的每個關鍵元素建立與投影片視覺內容的映射。例如，推理提及「圖表顯示上升趨勢」時，系統應標記該圖表在投影片中的位置（patch 座標），支援視覺反饋。

#### Scenario: 元素與視覺區域映射
- **WHEN** 推理提及「標題：'AI 在金融中的應用'」
- **THEN** 系統標記該標題在投影片圖像中的位置，存儲 patch 座標，支援點擊查看原始位置

#### Scenario: 推理-視覺互動
- **WHEN** 使用者點擊推理中的關鍵短語（例如「圖表」）
- **THEN** 前端高亮投影片中對應的圖表區域，展示該區域的高清放大版本

### Requirement: 多層次推理細節與鑽探
系統 SHALL 支援對推理的多層次鑽探，使用者可深入查看各推理層級的細節，例如「語義對齷」步驟中具體哪些概念被匹配、得分多少、有什麼根據。

#### Scenario: 高層摘要
- **WHEN** 結果首次展示
- **THEN** 顯示一行總結推理結論

#### Scenario: 中層步驟詳情
- **WHEN** 使用者展開推理步驟
- **THEN** 顯示 5 步驟的文本、得分、置信度

#### Scenario: 低層概念匹配詳情
- **WHEN** 使用者深入「語義對齷」步驟
- **THEN** 展示概念對匹配表格，例如：
  | 查詢概念 | 投影片概念 | 相似度 |
  | 金融 | Finance | 0.95 |
  | 風控 | Risk Management | 0.92 |

### Requirement: 推理鏈的A/B測試與優化
系統 SHALL 支援推理模型（MM-R5）的 A/B 測試，例如測試不同的 prompt 模板、超參數、模型版本如何影響推理品質。收集用戶反饋（「此推理有幫助」/「誤導」），用於離線優化。

#### Scenario: 推理模板 A/B 測試
- **WHEN** 同時部署 Template A 和 Template B
- **THEN** 評估用戶對兩種推理文本的滿意度，選擇更佳模板

#### Scenario: 用戶反饋收集
- **WHEN** 展示推理結果
- **THEN** UI 提供「此推理有幫助/無幫助」按鈕，反饋用於模型改進

### Requirement: 推理錯誤與誤導檢測
系統 SHALL 實現推理錯誤的初步自動檢測，例如邏輯矛盾、事實性扭曲（推理聲稱「圖表顯示 X」但實際不含 X）。檢測到錯誤時自動降低推理信度，或觸發 Argos 驗證層的進一步檢查。

#### Scenario: 邏輯矛盾特徵偵測
- **WHEN** 推理過程執行中
- **THEN** 邏輯檢查模塊掃描推理文本，偵測自相矛盾的陳述（例如「圖表顯示增長」與「下降」在同一推理中出現），標記為「高風險邏輯問題」

#### Scenario: 事實性查證觸發
- **WHEN** 推理提及「投影片含 5 個關鍵指標」
- **THEN** 系統自動觸發 Argos 驗證層驗證此聲明，若實際只有 3 個則標記為誤導

### Requirement: 效能與SLA
系統 SHALL 達成：推理鏈生成延遲 1-3 秒/候選，推理文本完全率 > 95%（5 步驟均生成），可解釋性評分計算 < 100ms，推理透明度 > 90%，邏輯完整性 > 95%。

#### Scenario: 推理生成延遲
- **WHEN** 提交候選投影片進行推理
- **THEN** 系統在 1-3 秒內生成完整的 5 步驟推理文本

#### Scenario: 推理完全度測試
- **WHEN** 評估 1000 個推理樣本
- **THEN** > 95% 的樣本包含完整的 5 個推理步驟（無缺失步驟）

### Requirement: 輸出介面標準化
系統 SHALL 返回標準化的 `ReasoningChain` 物件，包含 5 個 `ReasoningStep` 物件序列，整體評分、可解釋性評分、邏輯完整度。支援 JSON 序列化與 Markdown 格式導出。

#### Scenario: ReasoningChain 物件結構
- **WHEN** 推理完成
- **THEN** 返回物件含：
  - steps：[ReasoningStep1, ReasoningStep2, ..., ReasoningStep5]
  - overall_score：float [0, 1]
  - interpretability_score：float [0, 1]
  - logic_completeness：float [0, 1]

#### Scenario: Markdown 導出
- **WHEN** 使用者請求導出推理過程為 Markdown
- **THEN** 系統生成格式化的 Markdown 文件，包含各步驟的文本、得分、證據引用，支援下載
