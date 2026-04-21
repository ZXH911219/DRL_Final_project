## ADDED Requirements

### Requirement: 統一多模態向量空間定義
系統 SHALL 建立統一的多模態向量空間，各模態（文字、圖像、視頻、音頻）的編碼器均將特徵映射至同一向量空間，維度為 512 或 1024。跨模態對齋分數（Cross-Modal Consistency）定義為隨機模態對的成對相似度平均值，目標 > 0.85。

#### Scenario: 向量空間初始化
- **WHEN** 系統啟動時
- **THEN** ImageBind 基礎編碼器加載，定義共享向量空間維度（例如 512），各模態編碼器初始化完成

#### Scenario: 文字編碼至統一空間
- **WHEN** 使用者輸入查詢文本「機器學習應用」
- **THEN** CLIP Text Encoder 將文本編碼為 512 維向量，映射至統一空間

#### Scenario: 圖像編碼至統一空間
- **WHEN** 使用者上傳參考圖像或投影片視覺向量輸入
- **THEN** ColPali 視覺編碼器（或 CLIP Vision）將圖像編碼為 512 維向量，映射至同一空間

### Requirement: 跨模態對齋驗證
系統 SHALL 定期驗證各模態在共享空間中的對齋品質。通過計算模態間相似度分佈（相關樣本對的相似度平均 > 0.75，無關樣本對的相似度平均 < 0.30），評估空間品質。若 Cross-Modal Consistency < 0.85，觸發對齋告警。

#### Scenario: 文義對齋驗證
- **WHEN** 系統運行中，每 1 小時執行一次對齋檢查
- **THEN** 計算 100 個相關文本-圖像對的相似度，例如「金融風控政策」文字與相應投影片圖像，相似度平均 > 0.85 標記為通過

#### Scenario: 對齋品質告警
- **WHEN** Cross-Modal Consistency 降至 0.80
- **THEN** 系統觸發告警「多模態空間對齋品質下降」，建議檢查編碼器或微調數據

#### Scenario: 單模態退化檢測
- **WHEN** 某編碼器效能劣化（如視覺編碼器）
- **THEN** 系統識別該模態導致的對齋失敗，建議更新或回滾該編碼器

### Requirement: 模態融合策略
系統 SHALL 支援混合模態查詢，例如同時提供文本「金融風控」與參考圖像。融合策略為加權平均：
fused_vector = α × text_vector + β × image_vector（α + β = 1，預設 0.5）
融合後向量保持在同一空間，可直接與語料庫向量比對。

#### Scenario: 純文本查詢
- **WHEN** 使用者僅輸入文本查詢
- **THEN** 直接使用文本編碼向量，不涉及融合

#### Scenario: 純圖像查詢
- **WHEN** 使用者僅上傳參考圖像
- **THEN** 直接使用圖像編碼向量，不涉及融合

#### Scenario: 文字 + 圖像混合查詢
- **WHEN** 使用者同時輸入文本「數據視覺化」與圖像範例
- **THEN** 分別編碼得到 text_vector、image_vector，融合 fused = 0.5 × text + 0.5 × image，用融合向量進行檢索

### Requirement: 向量空間品質監控與微調
系統 SHALL 監控向量空間品質，收集離線指標（Recall@K、MRR、向量分佈熵等）。若品質下降，支援輕量化微調：收集 ~10K 標註样本（投影片 + 文本描述對），微調編碼器參數，實現空間適應。

#### Scenario: 離線品質評估
- **WHEN** 每週執行品質評估任務
- **THEN** 在標準測試集上計算 Recall@10 = 0.78、MRR = 0.72、向量分佈熵 = 5.2，與基準對比

#### Scenario: 檢索品質下降檢測
- **WHEN** 在線 Recall@10 從 0.85 下降至 0.75
- **THEN** 系統識別品質下降，檢查輸入數據分佈是否變化，或編碼器性能是否劣化

#### Scenario: 域適應微調
- **WHEN** 收集 10K 投影片 + 文本描述對，標註相關性
- **THEN** 使用對比學習（Contrastive Learning）微調 ImageBind，5 個 epoch 後 Recall@10 恢復至 0.85

### Requirement: 向量空間擴展性與新模態支持
系統 SHALL 設計模態無關的編碼器接口，支援未來新增模態（如視頻片段、音頻轉錄）。新編碼器只需輸出與共享空間維度相同的向量，即可無縫集成。

#### Scenario: 新模態編碼器集成
- **WHEN** 需新增「投影片配音轉錄文本」模態
- **THEN** 開發 Speech-to-Text 編碼器，輸出 512 維向量，自動納入共享空間，無需修改已有編碼器

#### Scenario: 多模態向量聚合
- **WHEN** 自同一投影片產生多個模態向量（視覺、標題文本、備註文本）
- **THEN** 系統支援向量聚合（平均或注意力加權），生成單一的投影片表示向量

### Requirement: 效能與可靠性 SLA
系統 SHALL 提供以下 SLA：編碼延遲 < 200ms（文本）、< 500ms（圖像），跨模態相似度計算 < 100ms，Cross-Modal Consistency > 0.85 維持率 > 99%。向量空間維度統一性 100%（無異常維度輸出）。

#### Scenario: 文本編碼效能
- **WHEN** 編碼文本查詢「機器學習基礎」
- **THEN** 在 < 200ms 內輸出 512 維向量

#### Scenario: 圖像編碼效能
- **WHEN** 編碼投影片圖像（1024×768）
- **THEN** 在 < 500ms 內輸出 512 維向量（GPU 加速）

#### Scenario: 空間一致性監控
- **WHEN** 持續運行一週，執行 10K 次查詢
- **THEN** Cross-Modal Consistency 始終 > 0.85，無異常波動或空間漂移

### Requirement: 輸出介面標準化
系統 SHALL 暴露統一的向量化接口 `encode(input, modality='text'/'image'/'audio') -> np.ndarray (batch_size, 512)`。支援批量編碼、GPU 加速、向量緩存（常見查詢的向量預緩存以加快檢索）。

#### Scenario: 單個輸入編碼
- **WHEN** 調用 encode(text="金融預測", modality='text')
- **THEN** 返回形狀 (1, 512) 的 NumPy ndarray

#### Scenario: 批量編碼
- **WHEN** 調用 encode(texts=[sent1, sent2, ...], modality='text', batch_size=32)
- **THEN** 返回形狀 (N, 512) 的 ndarray，其中 N = len(texts)
