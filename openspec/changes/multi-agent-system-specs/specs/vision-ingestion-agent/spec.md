## ADDED Requirements

### Requirement: PPT 檔案結構化解析
系統 SHALL 支援對 Microsoft PowerPoint 及 LibreOffice Impress 格式的動態讀取，提取頁面級元資訊（頁碼、佈局名稱、母版設定）及備註內容，並驗證檔案結構完整性。

#### Scenario: 成功解析標準 PPTX 檔案
- **WHEN** 輸入一個標準 .pptx 檔案（MS Office 2016+）
- **THEN** 系統返回結構化的頁面集合，包含每頁的佈局、母版、備註，以及元資訊時間戳

#### Scenario: 解析 ODP 格式並轉換
- **WHEN** 輸入一個 LibreOffice Impress .odp 檔案
- **THEN** 系統成功解析且返回與 .pptx 等價的結構化資訊

#### Scenario: 檔案完整性檢查失敗
- **WHEN** 輸入一個損壞的或不完整的 PPT 檔案
- **THEN** 系統傳回 HTTP 400 Bad Request，錯誤訊息指明損壞頁面的索引

### Requirement: 高保真圖像渲染
系統 SHALL 將每個 PPT 頁面渲染為高畫質、標準化的圖像。解像度設定為 600 DPI（或等效的 1024×768 像素標準化尺寸），色彩空間 RGB/RGBA，輸出格式 PNG 或 WebP。

#### Scenario: 渲染單個頁面
- **WHEN** 接收一個頁面的 PPT 元資訊
- **THEN** 系統在 < 500ms（GPU 加速）內輸出高清圖像，模糊度評估分數 > 0.95

#### Scenario: 色彩校正與正規化
- **WHEN** 輸入含有極端色彩對比（如黑底白字）的頁面
- **THEN** 系統執行自動色彩校正與對比度均衡，確保後續的視覺編碼器能有效識別

#### Scenario: 批量渲染效能
- **WHEN** 批量提交 1000 個頁面進行渲染
- **THEN** 系統在 < 10 分鐘內完成所有頁面的渲染（含 GPU 批處理），吞吐量 > 100 頁/分鐘

### Requirement: ColPali 視覺特徵提取
系統 SHALL 利用 ColPali Vision-Language 模型，將每個渲染的圖像分割為 1024 個固定視覺區塊（32×32 patch grid），並將每個區塊編碼為 128 維的稠密向量。向量類型為 float32，並維護每個區塊在原始圖像中的座標映射。

#### Scenario: 標準圖像特徵提取
- **WHEN** 輸入一個 1024×768 的 PPT 頁面圖像
- **THEN** 系統返回 1024×128 的多向量張量（Tensor），其中每一行代表一個 patch 的特徵向量

#### Scenario: 向量品質驗證
- **WHEN** 特徵提取完成
- **THEN** 系統計算向量覆蓋率 = (有效區塊數) / (總區塊數 1024)，若 > 98% 標記為通過，否則觸發品質告警

#### Scenario: 座標映射一致性
- **WHEN** 提取多個頁面的向量並執行反向檢驗（向量 → 原始圖像區域）
- **THEN** 映射誤差 < 5 像素，patch 座標與原始圖像座標的一致性保持在 > 99%

### Requirement: ImageBind 多模態對齊
系統 SHALL 支援 ImageBind 統一編碼層，將 ColPali 提取的視覺向量映射至統一的多模態向量空間（512 或 1024 維）。支援文字、圖像、音頻等異質模態的無縫對齷，對齷分數（Cross-Modal Consistency）> 0.85。

#### Scenario: 視覺向量至共享空間的映射
- **WHEN** 輸入 ColPali 提取的 1024×128 多向量
- **THEN** 系統經 ImageBind 編碼器映射為 1024 個 512 維（或 1024 維）的共享空間向量

#### Scenario: 文字查詢自編碼
- **WHEN** 使用者輸入文字查詢（如「機器學習應用案例」）
- **THEN** 系統透過 CLIP Text Encoder 將文字編碼至同一共享空間，向量維度與視覺向量一致

#### Scenario: 跨模態對齷品質驗證
- **WHEN** 計算文字向量與視覺向量間的歸一化內積（余弦相似度）
- **THEN** 對於相關的投影片，相似度分數 > 0.85；對於無關的投影片，相似度 < 0.30

### Requirement: 增量式批處理與容錯
系統 SHALL 支援增量式批處理，允許新增投影片無需重新處理舊資料。若處理中途失敗（如 OOM 或模型推理超時），系統 SHALL 自動重試（3 次，指數退避）或轉移至備用 OCR 模式。

#### Scenario: 新增投影片的增量索引
- **WHEN** 使用者上傳 100 個新的 PPT 檔案
- **THEN** 系統識別新檔案，僅對新檔案執行視覺特徵提取，不重新處理既有投影片

#### Scenario: 處理失敗與重試
- **WHEN** ColPali 推理因 GPU OOM 而中斷
- **THEN** 系統自動重試 3 次（等待時間：1s, 2s, 4s），若仍失敗則降級至備用 OCR 方案（臨時解決方案，告知使用者）

#### Scenario: 資料一致性
- **WHEN** 完成一個批次的特徵提取後檢查資料庫
- **THEN** 所有向量、元資料、座標映射三者完全一致，無孤立記錄

### Requirement: 效能與監控
系統 SHALL 在生產環境中達成以下效能 SLA：單頁渲染時間 < 500ms（GPU），單頁特徵提取時間 < 2 秒（ColPali），多模態對齊時間 < 300ms（ImageBind），批處理吞吐量 > 100 頁/分鐘。

#### Scenario: 單頁端到端效能
- **WHEN** 輸入一個 PPT 頁面
- **THEN** 完整流程（解析 + 渲染 + ColPali 特徵提取 + ImageBind 對齷）耗時 < 2.8 秒

#### Scenario: 大規模批量效能
- **WHEN** 批量提交 10,000 個頁面
- **THEN** 系統在 < 1.67 小時內完成，平均每頁 < 0.6 秒，達到 > 100 頁/分鐘的吞吐量

#### Scenario: 監控與告警
- **WHEN** 系統運行中
- **THEN** 實時收集渲染延遲、特徵提取成功率、GPU 記憶體使用率等指標，若 GPU 記憶體 > 90% 或失敗率 > 5% 則觸發告警

### Requirement: 輸出介面標準化
系統 SHALL 在完成視覺特徵提取後，生成標準化的 `VisualFeatureBundle` 物件，包含投影片 ID、頁面索引、多向量張量、patch 座標映射、ImageBind 共享空間向量、元資料及品質指標。

#### Scenario: 輸出完整性
- **WHEN** 特徵提取完成
- **THEN** 返回物件含所有欄位，無遺漏。slide_id 唯一，page_index ∈ [0, total_pages)

#### Scenario: 序列化與持久化
- **WHEN** 需將特徵儲存至磁碟
- **THEN** 系統支援 Parquet / HDF5 格式的序列化，確保向量精度不損失，元資料可完整恢復
