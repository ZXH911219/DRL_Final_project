# 真实模型集成指南 | Real Models Integration Guide

## 概览 | Overview

本文档说明如何使用三个真实模型组件构建完整的多代理检索系统：
1. **ColPali** - 多向量视觉提取
2. **MM-R5** - 链式思维推理
3. **Argos** - 视觉验证与幻觉检测

---

## 快速开始 | Quick Start

### 安装依赖 | Install Dependencies

```bash
# Core ML requirements
pip install transformers>=4.36.2 torch>=2.1.2

# Vision models
pip install timm pillow opencv-python

# MM-R5 (if using quantization)
pip install bitsandbytes

# OCR for verification
pip install paddleocr

# Vector storage
pip install lancedb pyarrow h5py
```

### 最小示例 | Minimal Example

```python
import numpy as np
from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
from src.agents.verification.argos_real import ArgosVerificationAgent

# Initialize agents
vision_agent = RealColPaliVisionAgent(device="cuda")
vision_agent.initialize()

reasoner = MM_R5ReasoningReranker(device="cuda")
verifier = ArgosVerificationAgent(device="cuda")
verifier.initialize()

# Process PPT
slide_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)

# 1. Extract ColPali features
multi_vectors, confidence = vision_agent.extractor.extract_features_from_image(slide_image)
print(f"ColPali features: {multi_vectors.shape}") # (1024, 128)

# 2. Generate reasoning
candidates = [{"slide_id": "slide_1", "content": "Sample content", "score": 0.85}]
reranked = reasoner.rerank_candidates(query="test query", candidates=candidates)
print(f"Reasoning confidence: {reranked[0]['reasoning']['confidence']}")

# 3. Verify results
report = verifier.verify_reasoning(
    slide_image=slide_image,
    reasoning_text=reranked[0]['reasoning']['chain'][0]['text'],
    reasoning_steps=[],
    original_score=reranked[0]['reranked_score'],
    slide_id="slide_1"
)
print(f"Hallucination risk: {report.hallucination_risk_score:.1%}")
```

---

## 模型详细说明 | Model Details

### 1. ColPali - 多向量视觉提取

**特性**：
- 输入：图像 (H, W, 3)
- 输出：1024×128 多向量表示（每像素一个特征块）
- 支持：量化、批处理、GPU/CPU

**使用示例**：

```python
from src.agents.vision_ingestion.colpali_real import RealColPaliExtractor

# 初始化
extractor = RealColPaliExtractor(model_path="vidore/colpali", device="cuda")
extractor.initialize()

# 单图像提取
image = cv2.imread("slide.png")
multi_vectors, confidence = extractor.extract_features_from_image(image)

# 批处理提取
wrapper = extractor
images = [img1, img2, img3]
batch_results = wrapper.extract_batch(images)
```

**模型参数**：
- 模型大小：4.5 GB
- 参数数：2B (20 亿)
- 推理时间：1-2 秒/页 (GPU)
- 输出维度：1024 patche × 128 dim

### 2. MM-R5 - 链式思维推理

**特性**：
- 输入：查询 + 文档内容
- 输出：5 步推理链 + 最终分数 [0.0-1.0]
- 支持：量化、并行处理

**使用示例**：

```python
from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker

# 初始化
reranker = MM_R5ReasoningReranker(device="cuda")

# 生成推理
query = "machine learning in finance"
slide_content = "Discussion of ML algorithms for risk assessment"

result = reranker.reasoner.generate_reasoning_chain(
    query=query,
    slide_content=slide_content,
    slide_id="slide_42"
)

# 访问推理步骤
for step in result.reasoning_chain:
    print(f"{step.step_name}: {step.reasoning_text}")
    print(f"  Score: {step.local_score:.2f}, Confidence: {step.confidence:.2f}")

print(f"\nFinal Score: {result.final_score:.2f}")
print(f"Confidence: {result.confidence_level}")
```

**推理步骤**：
1. **Visual Perception** - 视觉元素识别
2. **Query Analysis** - 查询意图分析
3. **Semantic Alignment** - 语义对齐检查
4. **Deep Reasoning** - 关系推理
5. **Confidence Assessment** - 置信度评估

**重排示例**：

```python
# 批量重排多个候选
candidates = [
    {"slide_id": "s1", "content": "content1", "score": 0.85},
    {"slide_id": "s2", "content": "content2", "score": 0.75},
    {"slide_id": "s3", "content": "content3", "score": 0.65},
]

reranked = reranker.rerank_candidates(
    query="test query",
    candidates=candidates,
    max_candidates_to_reason=3
)

# 结果按重排分数排序
for i, result in enumerate(reranked, 1):
    print(f"{i}. {result['slide_id']}: {result['reranked_score']:.2f}")
```

**模型参数**：
- 模型大小：12 GB (完整) / 6 GB (8bit) / 3 GB (4bit)
- 参数数：6B (60 亿)
- 推理时间：1-3 秒/候选
- 输出：推理链 + 置信度

### 3. Argos - 视觉验证与幻觉检测

**特性**：
- 视觉定位：OCR + 对象识别
- 幻觉风险 [0.0-1.0]：低、中、高
- 自动分数调整

**使用示例**：

```python
from src.agents.verification.argos_real import ArgosVerificationAgent

# 初始化
verifier = ArgosVerificationAgent(device="cuda")
verifier.initialize()

# 验证推理结果
report = verifier.verify_reasoning(
    slide_image=slide_image,  # np.ndarray (H, W, 3)
    reasoning_text="The slide shows a growth trend chart...",
    reasoning_steps=[
        {"step": "Visual", "text": "Detected line chart"},
        {"step": "Analysis", "text": "Query asks for trends"}
    ],
    original_score=0.85,
    slide_id="slide_42"
)

# 检查验证结果
print(f"Status: {report.verification_status}")  # pass / warn / fail
print(f"Hallucination Risk: {report.hallucination_risk_score:.1%}")
print(f"Risk Level: {report.hallucination_risk_level}")  # low / medium / high

# 查看调整后的分数
print(f"Original Score: {report.original_score:.2f}")
print(f"Adjusted Score: {report.adjusted_score:.2f}")
print(f"Adjustment Factor: {report.adjustment_factor:.2f}")

# 查看验证的声明
print(f"Verified Claims: {len(report.verified_claims)}")
print(f"Unverified Claims: {len(report.unverified_claims)}")

# 查看证据区域
for evidence in report.evidence_regions:
    print(f"  {evidence.region_type} @ ({evidence.patch_x_min},{evidence.patch_y_min})")
```

**幻觉风险计算** :

```
hallucination_risk = 
    0.40 × (1 - coverage_ratio
) +
    0.35 × (1 - semantic_consistency) +
    0.25 × (unverified_claims / total_claims)

分数调整: adjusted = original × (1 - √risk)
```

**模型参数**：
- OCR 模型：PaddleOCR
- 视觉识别：ResNet-50
- 验证延迟：500-1000ms
- 输出：验证报告 + 证据地图

---

## 完整端到端示例 | Full E2E Example

```python
import numpy as np
from pathlib import Path

from src.agents.vision_ingestion.colpali_real import RealColPaliVisionAgent
from src.agents.reasoning_reranker.mm_r5_real import MM_R5ReasoningReranker
from src.agents.verification.argos_real import ArgosVerificationAgent
from src.agents.lakehouse_retrieval.retrieval_result import create_retrieval_result_example

# 配置
DEVICE = "cuda"

def end_to_end_pipeline(ppt_path: str, query: str):
    """Complete pipeline: Vision -> Reasoning -> Verification"""
    
    print("=" * 60)
    print("FULL E2E PIPELINE TEST")
    print("=" * 60)
    
    # 初始化所有代理
    print("\n[1/4] Initializing agents...")
    vision_agent = RealColPaliVisionAgent(device=DEVICE)
    vision_agent.initialize()
    
    reasoner = MM_R5ReasoningReranker(device=DEVICE)
    verifier = ArgosVerificationAgent(device=DEVICE)
    verifier.initialize()
    
    # 页面 1: 视觉提取
    print("\n[2/4] Stage 1: Vision Ingestion (ColPali)")
    print(f"  Processing PPT: {ppt_path}")
    
    # 模拟幻灯片图像
    slide_image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)
    multi_vectors, col_confidence = vision_agent.extractor.extract_features_from_image(
        slide_image
    )
    
    print(f"  ✓ Extracted features: {multi_vectors.shape}")
    print(f"  ✓ ColPali confidence: {col_confidence:.2f}")
    
    # 第 2 级：推理重排
    print("\n[3/4] Stage 2: Reasoning Reranking (MM-R5)")
    print(f"  Query: {query}")
    
    candidates = [
        {
            "slide_id": "slide_42",
            "content": "ML algorithms for risk assessment",
            "score": 0.85
        },
        {
            "slide_id": "slide_43",
            "content": "Traditional database approaches",
            "score": 0.60
        }
    ]
    
    reranked = reasoner.rerank_candidates(query=query, candidates=candidates)
    
    for i, result in enumerate(reranked, 1):
        reasoning = result['reasoning']
        print(f"\n  [{i}] {result['slide_id']}")
        print(f"      Original Score:  {result['original_score']:.2f}")
        print(f"      Reranked Score:  {result['reranked_score']:.2f}")
        print(f"      Confidence:      {reasoning['confidence']}")
        print(f"      Interpretability: {reasoning['interpretability']:.1%}")
        
        # 显示关键推理步骤
        for step in reasoning['chain'][:2]:  # 前 2 步
            print(f"      - {step['step']}: {step['score']:.2f}")
    
    # 第 3 级：验证
    print("\n[4/4] Stage 3: Verification (Argos)")
    
    best_result = reranked[0]
    report = verifier.verify_reasoning(
        slide_image=slide_image,
        reasoning_text=best_result['reasoning']['chain'][0]['text'],
        reasoning_steps=best_result['reasoning']['chain'],
        original_score=best_result['reranked_score'],
        slide_id=best_result['slide_id']
    )
    
    print(f"  Verification Status:    {report.verification_status.upper()}")
    print(f"  Hallucination Risk:     {report.hallucination_risk_score:.1%} ({report.hallucination_risk_level})")
    print(f"  Evidence Coverage:      {report.evidence_coverage_ratio:.1%}")
    print(f"  Semantic Consistency:   {report.semantic_consistency:.1%}")
    print(f"  ")
    print(f"  Score Adjustment:       {report.original_score:.2f} → {report.adjusted_score:.2f} (×{report.adjustment_factor:.2f})")
    print(f"  Verified Claims:        {len(report.verified_claims)}")
    print(f"  Unverified Claims:      {len(report.unverified_claims)}")
    
    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)
    
    return {
        "vision_features": multi_vectors,
        "reranked_results": reranked,
        "verification_report": report
    }

# 运行示例
if __name__ == "__main__":
    result = end_to_end_pipeline(
        ppt_path="example.pptx",
        query="machine learning in financial risk management"
    )
```

---

## 性能优化 | Performance Optimization

### GPU 内存管理

```python
# 使用量化模型以减少内存占用
from src.agents.vision_ingestion.colpali_real import ColPaliModelWrapper

wrapper = ColPaliModelWrapper()
wrapper.load_with_quantization(quantization_bits=8)  # 8-bit 量化
# 或
wrapper.load_with_quantization(quantization_bits=4)  # 4-bit 量化
```

### 批处理

```python
# 批量处理多个图像
images = [img1, img2, img3, img4]
batch_results = wrapper.extract_batch(images)

# 批量重排
candidates_batch = [
    {"slide_id": "s1", "content": "c1", "score": 0.8},
    {"slide_id": "s2", "content": "c2", "score": 0.7},
    # ...
]
reranked_batch = reasoner.rerank_candidates(
    query=query,
    candidates=candidates_batch,
    max_candidates_to_reason=10  # 限制推理候选数
)
```

### 缓存

```python
from src.models.model_manager import get_model_cache, get_model_loader

# 检查缓存状态
cache = get_model_cache()
usage = cache.get_cache_usage()
print(f"Cache usage: {usage['total_gb']:.1f} GB")

# 加载已缓存的模型
loader = get_model_loader()
model = loader.load_model("colpali")

# 清理内存
loader.cleanup_memory()
```

---

## 故障排除 | Troubleshooting

### 问题 1：CUDA 内存不足

**解决方案**：
```python
# 使用 CPU
agent = RealColPaliVisionAgent(device="cpu")

# 或使用量化
wrapper = ColPaliModelWrapper()
wrapper.load_with_quantization(quantization_bits=4)

# 或批处理较小的数据
images_small = images[:5]  # 处理更小的批次
```

### 问题 2：模型下载失败

**解决方案**：
```python
from src.models.model_manager import get_model_downloader

downloader = get_model_downloader()
# 强制重新下载
path = downloader.download_model("colpali", force_download=True)
```

### 问题 3：推理输出不稳定

**解决方案**：
```python
# 降低采样温度以获得更一致的输出
reasoner.reasoner.tokenizer.pad_token = reasoner.reasoner.tokenizer.eos_token
# 在模型调用中设置 do_sample=False
```

---

## 模型下载 | Model Downloads

### 预配置模型

使用模型管理器自动下载：

```python
from src.models.model_manager import get_model_downloader

downloader = get_model_downloader()

# 下载单个模型
colpali_path = downloader.download_model("colpali")
mm_r5_path = downloader.download_model("mm_r5")

# 下载所有模型
all_paths = downloader.download_all_models()
```

### 手动下载（替代方法）

```bash
# ColPali (4.5 GB)
huggingface-cli download vidore/colpali --repo-type model

# MM-R5 (需要指定正确的模型 ID)
huggingface-cli download meta-llama/Llama-2-7b ...

# 或通过 Python
from huggingface_hub import snapshot_download
snapshot_download("vidore/colpali", cache_dir="./models")
```

---

## 测试 | Testing

运行集成测试：

```bash
# 所有测试
pytest tests/test_e2e_real_models.py -v

# 特定测试
pytest tests/test_e2e_real_models.py::TestRealColPaliIntegration -v
pytest tests/test_e2e_real_models.py::TestRealMM_R5Integration -v
pytest tests/test_e2e_real_models.py::TestArgosVerificationIntegration -v

# 端到端管道测试
pytest tests/test_e2e_real_models.py::TestEndToEndPipeline -v
```

---

## 部署 | Deployment

### Docker 容器化

```dockerfile
FROM pytorch/pytorch:2.1.2-cuda12.1-runtime-ubuntu22.04

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 加载模型
COPY . .
RUN python -c "from src.models.model_manager import get_model_downloader; get_model_downloader().download_all_models()"

# 启动 API
CMD ["python", "src/api/main.py"]
```

### API 端点（计划）

```
POST /api/vision/extract
  - 输入：图像
  - 输出：多向量特征

POST /api/reasoning/rerank
  - 输入：查询 + 候选
  - 输出：重排结果 + 推理链

POST /api/verification/verify
  - 输入：推理结果 + 图像
  - 输出：验证报告 + 幻觉风险
```

---

## 贡献 | Contributing

改进建议：
1. 添加自定义推理模板
2. 实现不同的验证策略
3. 优化多模分割模型
4. 添加多语言支持

---

## 许可 | License

[Your License Here]
