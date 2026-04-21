## ADDED Requirements

### Requirement: LanceDB 集群部署與管理
系統 SHALL 支援 LanceDB 向量資料庫集群的初始化、配置與監控。包括連接池管理、硬體資源分配（GPU 記憶體、磁碟 I/O）、索引狀態檢查與新鮮度驗證。

#### Scenario: 集群初始化
- **WHEN** 系統啟動時
- **THEN** LanceDB 連接池建立，連接數 >= 10，每個連接的健康狀態驗證通過

#### Scenario: 索引狀態檢查
- **WHEN** 執行檢索查詢前
- **THEN** 系統驗證 LanceDB 索引已構建頁載入，索引新鮮度（LastUpdate 時間戳相距現在 < 1 小時）驗證通過

#### Scenario: 資源分配與監控
- **WHEN** 系統運行中
- **THEN** GPU 記憶體分配 <= 80%，磁碟 I/O 使用率 <= 85%，若超過阈值則觸發告警

### Requirement: 第一階段向量篩選（粗檢索）
系統 SHALL 利用 IVF（倒排檔案）或 LSH（局部敏感哈希）快速篩選向量，在百萬級語料中返回前 K_1 = 100~500 個最相似的候選投影片。向量量化精度保持 8-16 bit，L2/Cosine 距離計算時間 < 50ms。

#### Scenario: IVF 索引的快速篩選
- **WHEN** 輸入查詢向量（128 維或 512 維，取決於 ColPali / ImageBind 編碼）
- **THEN** 系統利用 IVF 索引定位最近的叢集，在 < 50ms 內返回 Top-500 候選及其相似度分數

#### Scenario: 向量量化與精度權衡
- **WHEN** 執行大規模檢索（百萬級語料）
- **THEN** 原始 128 維向量量化為 8-bit，儲存空間減少 93.75%，檢索精度損失 < 2%，召回率 > 95%

#### Scenario: 全文檢索（FTS）可選過濾
- **WHEN** 查詢包含文字關鍵詞（如「金融風控」）
- **THEN** 系統同時執行 FTS 檢索投影片元資料，與向量結果取交集，進一步縮小候選集合至 Top-100

### Requirement: 第二階段 MaxSim 精細比對
系統 SHALL 實現 ColPali 核心的 MaxSim（Late Interaction）演算法，對第一階段的候選投影片進行精確的逐區塊相似度計算，返回排序後的前 K_2 = 10~20 個結果。

#### Scenario: 多向量相似度矩陣計算
- **WHEN** 輸入查詢多向量（Q×128）與文件多向量（Doc 1024×128）
- **THEN** 系統計算 Q×1024 的相似度矩陣，單次矩陣乘法耗時 < 100ms（GPU 加速）

#### Scenario: MaxSim 延遲交互演算法
- **WHEN** 相似度矩陣計算完成
- **THEN** 系統對每個查詢向量取最大值（axis=1），然後平均，公式：MaxSim(q,d) = (1/|Q|) × Σ max_j(sim(q_i, d_j))

#### Scenario: 精確排序與證據區域標記
- **WHEN** MaxSim 評分完成
- **THEN** 系統對候選投影片排序，並標記最高相似度所在的證據區塊座標，供後續推理與驗證層使用

### Requirement: 混合檢索融合策略
系統 SHALL 支援向量檢索與全文檢索的融合，允許用戶配置權重係數（α、β），融合公式：final_score = α × 向量分數 + β × 全文分數（α + β = 1）。

#### Scenario: 純向量檢索
- **WHEN** 查詢不含文字關鍵詞（例如上傳參考圖像）
- **THEN** 系統執行純向量檢索路徑，α = 1.0，β = 0，返回向量相似度排序結果

#### Scenario: 向量 + 全文融合檢索
- **WHEN** 查詢同時包含文字與圖像
- **THEN** 系統執行雙路徑檢索，α = 0.7，β = 0.3（預設權重），融合最終排序結果

#### Scenario: 權重動態調整
- **WHEN** 使用者指定檢索模式為「精確匹配優先」
- **THEN** 系統調整 α = 0.5，β = 0.5，提高全文檢索的權重

### Requirement: 檢索效能與 SLA
系統 SHALL 在生產環境達成以下 SLA：第一階段延遲 < 50ms，第二階段延遲 < 100ms，總檢索延遲 < 200ms（含 I/O）。Recall@100 > 95%，MRR@10 > 0.75，NDCG@10 > 0.78，支援 >= 100 並發查詢。

#### Scenario: 單次查詢端到端延遲
- **WHEN** 使用者提交檢索查詢（百萬級語料）
- **THEN** 系統在 < 200ms 內返回 Top-20 排序結果（包括 I/O、特徵化、IVF、MaxSim）

#### Scenario: 召回率測試
- **WHEN** 在標準測試集上執行召回率評估（100 個已知相關的投影片對）
- **THEN** Recall@100 (前 100 個候選中找到相關結果的比例) > 95%

#### Scenario: 並發查詢支援
- **WHEN** 同時提交 100 個查詢請求
- **THEN** 系統在 < 30 秒內完成所有查詢返回（P95 延遲 < 250ms，平均 < 200ms）

### Requirement: 審計日誌與監控
系統 SHALL 記錄每次檢索的完整審計日誌，包含查詢向量、篩選階段的候選數、MaxSim 排序結果、檢索延遲統計。監控儀表板實時展示檢索延遲分佈、命中率、索引新鮮度。

#### Scenario: 檢索結果日誌記錄
- **WHEN** 檢索完成
- **THEN** 系統記錄查詢、篩選結果數、精排結果、耗時等信息至日誌，格式化為 JSON，供離線分析

#### Scenario: 效能監控告警
- **WHEN** 系統運行中
- **THEN** 實時計算檢索延遲 P95 值，若超過 250ms 超過 5 分鐘則觸發告警「檢索性能下降」

### Requirement: 結果介面標準化
系統 SHALL 返回標準化的 `RetrievalResult` 物件，包含排序的投影片列表、MaxSim 分數、證據區塊座標、檢索耗時統計、索引狀態報告。每個 `RetrievalCandidate` 須包含 slide_id、page_index、maxsim_score、evidence_regions 等欄位。

#### Scenario: 完整檢索結果返回
- **WHEN** 檢索成功完成
- **THEN** 返回 RetrievalResult 物件，包含 `ranking` 列表（Top-20），每項含 slide_id、maxsim_score、stage（「filtering」或「reranking」）、metadata

#### Scenario: 結果分頁與偏移
- **WHEN** 使用者請求檢索結果的第 2 頁（每頁 10 項）
- **THEN** 系統返回 ranking[10:20] 的子集，total_count 指示總候選數
