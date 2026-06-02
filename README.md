# 次世代多模態 PPT 視覺與推理檢索系統

這個專案的核心流程已經可在 stub 模式下運作。若你要在 Windows 上建立完整環境，建議採用以下「不依賴 Chocolatey」的手動安裝流程。

## 1. Windows 系統層套件

請先安裝下列系統工具，並確保它們可在 `cmd` 中被找到：

- LibreOffice
  - 用途：將 `.pptx` 轉成 PDF，供 `pdf2image` 使用。
  - 安裝後確認 `soffice.exe` 可用。
- Poppler
  - 用途：`pdf2image` 在 Windows 上需要的 PDF 轉圖元件。
  - 安裝後確認 `pdftoppm.exe` 可用。
- Tesseract binary
  - 用途：供 `pytesseract` 做 OCR。
  - 安裝後確認 `tesseract.exe` 可用。

### 1.1 LibreOffice

1. 到 LibreOffice 官方網站下載 Windows 安裝程式。
2. 直接使用預設安裝路徑即可，安裝完成後通常會有：
  - `C:\Program Files\LibreOffice\program\soffice.exe`
3. 把下列路徑加入 `PATH`：
  - `C:\Program Files\LibreOffice\program`

### 1.2 Poppler

1. 下載 Windows 版 Poppler 壓縮檔。
2. 解壓到固定資料夾，例如：
  - `C:\tools\poppler`
3. 找出實際包含 `pdftoppm.exe` 的資料夾，常見是其中一個：
  - `C:\tools\poppler\bin`
  - `C:\tools\poppler\Library\bin`
4. 把該資料夾加入 `PATH`。

### 1.3 Tesseract binary

1. 下載 Windows 版 Tesseract 安裝檔。
2. 建議使用預設安裝位置：
  - `C:\Program Files\Tesseract-OCR`
3. 確認下列檔案存在：
  - `C:\Program Files\Tesseract-OCR\tesseract.exe`
  - `C:\Program Files\Tesseract-OCR\tessdata`
4. 把下列路徑加入 `PATH`：
  - `C:\Program Files\Tesseract-OCR`
5. 若你使用自訂安裝路徑，額外設定 `TESSDATA_PREFIX`：
  - `C:\Program Files\Tesseract-OCR\tessdata`

### 1.4 建議安裝順序與驗證

建議順序：

1. 先安裝 LibreOffice。
2. 再安裝 Poppler。
3. 最後安裝 Tesseract binary。
4. 安裝完成後重開 `cmd`，再確認 PATH。

驗證命令：

```cmd
where soffice
where pdftoppm
where tesseract
soffice --version
tesseract -v
```

如果看不到結果，表示執行檔目錄還沒加入 PATH，或視窗尚未重新啟動。

## 2. Python 套件

系統層工具準備完成後，在專案根目錄執行：

```cmd
pip install -r requirements.txt
```

這份 `requirements.txt` 已包含：

- 核心資料與檢索：`pydantic`, `lancedb`, `pyarrow`, `numpy`
- 視覺處理：`python-pptx`, `pdf2image`, `Pillow`
- UI / 開發：`streamlit`, `watchdog`
- 推論：`torch`, `transformers`, `diffusers`
- OCR：`pytesseract`, `easyocr`
- 測試：`pytest`

### 2.1 注意事項

- `bitsandbytes` 未放入預設安裝清單，因為 Windows 上不穩定。
- `tantivy` 目前沒有接進專案程式流程，因此也未列入預設安裝。
- `pytesseract` 只是 Python wrapper，真正 OCR 還需要系統層的 Tesseract binary。

## 3. 快速驗證

### 3.1 檢查套件是否可匯入

```cmd
python -c "import lancedb, pyarrow, pptx, pdf2image, PIL, streamlit, watchdog, torch, transformers, pytesseract; print('ok')"
```

### 3.2 跑端到端測試

```cmd
python -m pytest -q tests/test_e2e_pipeline.py::test_end_to_end_pipeline
```

### 3.3 跑 OCR 測試

如果 OCR 後端可用：

```cmd
python -m pytest -q tests/test_ocr_grounding.py::test_ocr_grounding
```

若本機沒有安裝 Tesseract binary 或 EasyOCR 相關依賴，這個測試會自動跳過。

### 3.4 啟動 Streamlit

```cmd
set POPPLER_PATH=C:\tools\poppler\Library\bin
streamlit run streamlit_app.py
```

說明：

- `POPPLER_PATH` 可省略；若你的 VS Code 終端與系統 `cmd` 的 PATH 不一致，建議明確設定。
- 啟動後可在側欄輸入 `LanceDB URI` 與查詢文字，按 `Run Pipeline` 即可查看驗證結果與證據框。

## 4. 常見問題

### 4.1 `where soffice` / `where pdftoppm` / `where tesseract` 找不到

代表執行檔目錄還沒加入 PATH。請重新確認安裝位置，並把對應目錄加到系統環境變數：

- LibreOffice：`C:\Program Files\LibreOffice\program`
- Poppler：包含 `pdftoppm.exe` 的 `bin` 目錄
- Tesseract：`C:\Program Files\Tesseract-OCR`

如果你剛剛才更新 PATH，請先關掉目前所有 `cmd` 視窗，再重新開啟。

### 4.2 `pdf2image` 無法轉檔

通常是 Poppler 沒裝好，或 `pdftoppm.exe` 不在 PATH。

如果你想在 Python 中指定 Poppler 路徑，也可以額外設定 `poppler_path`。

本專案 `VisionIngestionAgent` 也支援使用環境變數 `POPPLER_PATH` 指定 Poppler 的 `bin` 目錄，適合 VS Code 終端和系統 `cmd` PATH 不一致的情境。

Windows 範例：

```cmd
set POPPLER_PATH=C:\tools\poppler\Library\bin
python -m pytest -q tests/test_e2e_pipeline.py::test_end_to_end_pipeline
```

### 4.3 OCR 測試跳過

代表本機沒有可用 OCR 後端。這不影響核心檢索與重排流程。
