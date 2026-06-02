# Task 12: Real Model Downloads & Integration

## Overview

This task involves downloading actual pre-trained models and integrating them into the DRL system. Current implementation uses mock models; this phase brings in real inference capabilities.

## Models to Download

### 1. ColPali (Vision Ingestion)
**Model**: ColPali-Base (Open-source, from HuggingFace)
- **Size**: ~4.5 GB
- **Purpose**: Extract 1024×128 multi-vectors from PPT images
- **Repository**: `allenai/ColPali-base`
- **Download Link**: https://huggingface.co/allenai/ColPali-base
- **Format**: PyTorch (.pt files)
- **Hash**: Verify authenticity after download

**Installation**:
```bash
# Method 1: Automatic (recommended)
huggingface-cli download allenai/ColPali-base --local-dir ./models/colpali

# Method 2: Manual
# Download from: https://huggingface.co/allenai/ColPali-base/tree/main
# Extract to: ./models/colpali/
```

**Files Expected**:
```
models/colpali/
├── config.json
├── model.safetensors
├── preprocessor_config.json
├── processor_config.json
├── README.md
└── tokenizer.json
```

**Verification**:
```python
from transformers import AutoModel
model = AutoModel.from_pretrained("./models/colpali", trust_remote_code=True)
print(f"Model loaded: {model}")
```

---

### 2. MM-R5 (Reasoning Reranker)
**Model**: MM-R5-Quantized (7B parameters, INT8 quantization)
- **Size**: ~6 GB (quantized), ~28 GB (full precision)
- **Purpose**: Generate 5-step reasoning chains and scoring
- **Repository**: `THUDM/ChatGLM-4V` or similar reasoning model
- **Download Link**: https://huggingface.co/microsoft/phi-3-quantized or similar
- **Format**: GGUF or SafeTensors
- **Quantization**: INT8 for faster inference

**Installation**:
```bash
# Method 1: Using ollama (recommended for quantized models)
ollama pull mm-r5-quantized

# Method 2: Manual HuggingFace download
huggingface-cli download models/mm-r5-quantized --local-dir ./models/reasoning

# Method 3: GGML format (for CPU+GPU acceleration)
# Download .gguf file from HuggingFace model card
```

**Files Expected**:
```
models/reasoning/
├── mm-r5-quantized.gguf  (or .safetensors)
├── tokenizer.model
├── config.yml
└── README.md
```

**Verification**:
```python
from transformers import AutoModelForCausalLM, AutoTokenizer
model = AutoModelForCausalLM.from_pretrained(
    "./models/reasoning/mm-r5-quantized",
    load_in_8bit=True,
    device_map="auto"
)
print(f"Model loaded with parameters: {model.num_parameters()}")
```

---

### 3. Argos (Verification Agent)
**Model**: Argos-Base or similar verification model
- **Size**: ~2 GB
- **Purpose**: Visual grounding, hallucination detection, evidence mapping
- **Repository**: Research implementation or custom model
- **Format**: PyTorch or ONNX
- **Training Data**: PPT-specific verification annotations

**Installation**:
```bash
# OAT checkpoint (if available)
huggingface-cli download resources/argos-base --local-dir ./models/verification

# Or use pre-trained vision-language model
from transformers import AutoModel
model = AutoModel.from_pretrained("./models/verification", trust_remote_code=True)
```

**Files Expected**:
```
models/verification/
├── config.json
├── model.pt or model.safetensors
├── processor_config.json
└── README.md
```

**Verification**:
```python
from torch import load
state_dict = load("./models/verification/model.pt")
print(f"Model parameters: {len(state_dict)}")
```

---

### 4. ImageBind (Multimodal Alignment)
**Model**: ImageBind-Large (Meta)
- **Size**: ~2.5 GB
- **Purpose**: Align all modalities (vision, text) to shared vector space
- **Repository**: `facebook/imagebind-huge`
- **Download Link**: https://github.com/facebookresearch/ImageBind
- **Format**: PyTorch / ONNX

**Installation**:
```bash
# Clone and install
git clone https://github.com/facebookresearch/ImageBind.git
cd ImageBind
pip install -e .

# Or download weights only
huggingface-cli download facebook/imagebind-huge --local-dir ./models/imagebind
```

---

## Download Procedure

### Prerequisites
- 150GB free disk space (100GB models + 50GB buffer)
- 32GB RAM (for model loading during testing)
- GPU with 24GB+ VRAM (recommended)
- HuggingFace account (free) for model access
- Stable internet connection

### Step 1: Configure HuggingFace Access
```bash
# Login to HuggingFace
huggingface-cli login
# Enter your token when prompted
# Token available at: https://huggingface.co/settings/tokens
```

### Step 2: Create Model Directory
```bash
# Create model structure
mkdir -p models/{colpali,reasoning,verification,imagebind}

# Verify permissions
ls -la models/
```

### Step 3: Download Models (Parallel)

**Script**: `scripts/download_models.py`
```python
#!/usr/bin/env python3
"""Download all models in parallel"""

import os
from pathlib import Path
from huggingface_hub import snapshot_download
from concurrent.futures import ThreadPoolExecutor, as_completed

# Model configurations
MODELS = {
    "colpali": {
        "repo_id": "allenai/ColPali-base",
        "local_dir": "models/colpali",
        "size_gb": 4.5,
    },
    "reasoning": {
        "repo_id": "microsoft/phi-3-quantized",  # or your reasoning model
        "local_dir": "models/reasoning",
        "size_gb": 6.0,
    },
    "verification": {
        "repo_id": "your-org/argos-verification",
        "local_dir": "models/verification",
        "size_gb": 2.0,
    },
    "imagebind": {
        "repo_id": "facebook/imagebind-huge",
        "local_dir": "models/imagebind",
        "size_gb": 2.5,
    }
}

def download_model(name, config):
    """Download single model"""
    print(f"[{name}] Starting download... (≈{config['size_gb']}GB)")
    try:
        path = snapshot_download(
            repo_id=config["repo_id"],
            local_dir=config["local_dir"],
            repo_type="model",
            local_dir_use_symlinks=False,  # Avoid symlinks on Windows
            allow_patterns=["*.pt", "*.safetensors", "*.json", "*.model"],
        )
        print(f"[{name}] ✓ Downloaded to {path}")
        return name, True
    except Exception as e:
        print(f"[{name}] ✗ Failed: {e}")
        return name, False

# Download all models in parallel
print("Downloading models in parallel...")
print("=" * 50)

with ThreadPoolExecutor(max_workers=2) as executor:
    futures = {
        executor.submit(download_model, name, config): name
        for name, config in MODELS.items()
    }
    
    results = {}
    for future in as_completed(futures):
        name, success = future.result()
        results[name] = success

print("\n" + "=" * 50)
print("Download Summary:")
for model, success in results.items():
    status = "✓ Success" if success else "✗ Failed"
    print(f"  {model}: {status}")

# Verify all models exist
print("\nVerifying model files...")
all_present = True
for name, config in MODELS.items():
    model_path = Path(config["local_dir"])
    if model_path.exists() and len(list(model_path.glob("**/*"))) > 0:
        print(f"  ✓ {name}")
    else:
        print(f"  ✗ {name} - missing or empty")
        all_present = False

if all_present:
    print("\n✓ All models successfully downloaded!")
else:
    print("\n✗ Some models failed to download")
    exit(1)
```

**Run Download**:
```bash
# Make executable (Unix/Linux/macOS)
chmod +x scripts/download_models.py

# Run
python scripts/download_models.py

# Expected output:
# [colpali] Starting download... (≈4.5GB)
# [reasoning] Starting download... (≈6.0GB)
# ... (parallel downloads)
# ✓ All models successfully downloaded!
```

**Estimated Time**: 
- With 100 Mbps connection: 45-60 minutes
- With Gigabit: 5-10 minutes

---

## Model Integration

### Step 1: Update Agent Configuration
**File**: `.env`
```env
# Model paths
VISION_MODEL_PATH=./models/colpali
REASONING_MODEL_PATH=./models/reasoning
VERIFICATION_MODEL_PATH=./models/verification
IMAGEBIND_MODEL_PATH=./models/imagebind

# Model configuration
DEVICE=cuda:0  # or 'cpu' for CPU-only
DTYPE=float32  # or 'float16' for lower memory
```

### Step 2: Update Agent Implementations
**File**: `src/agents/vision_agent.py`

Replace mock implementation with real models:
```python
from transformers import AutoModel, AutoProcessor

class VisionIngestAgent:
    def __init__(self, model_path: str, device: str = "cuda:0"):
        self.model_path = model_path
        self.device = device
        
        # Load real ColPali model
        self.model = AutoModel.from_pretrained(
            model_path,
            trust_remote_code=True,
            device_map=device
        )
        self.processor = AutoProcessor.from_pretrained(model_path)
    
    def extract_features(self, image):
        """Extract real ColPali features"""
        inputs = self.processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.patch_embeddings  # Shape: (1024, 128)
```

### Step 3: Test Model Integration
**Script**: `tests/test_real_models.py`

```python
import pytest
from src.agents.vision_agent import VisionIngestAgent
from src.agents.reasoning_agent import ReasoningRerankerAgent
from src.agents.verification_agent import ArgosVerificationAgent

@pytest.fixture(scope="session")
def vision_agent():
    """Initialize real vision agent"""
    return VisionIngestAgent(
        model_path="./models/colpali",
        device="cuda:0"
    )

@pytest.fixture(scope="session")
def reasoning_agent():
    """Initialize real reasoning agent"""
    return ReasoningRerankerAgent(
        model_path="./models/reasoning",
        device="cuda:0"
    )

@pytest.fixture(scope="session")
def verification_agent():
    """Initialize real verification agent"""
    return ArgosVerificationAgent(
        model_path="./models/verification",
        device="cuda:0"
    )

def test_vision_model_inference(vision_agent, sample_image):
    """Test real model inference"""
    features = vision_agent.extract_features(sample_image)
    assert features.shape == (1024, 128)
    assert features.dtype == torch.float32

def test_reasoning_model_inference(reasoning_agent, sample_query):
    """Test real reasoning model"""
    reasoning = reasoning_agent.generate_reasoning(sample_query)
    assert "steps" in reasoning
    assert len(reasoning["steps"]) == 5

def test_verification_model_inference(verification_agent, sample_content):
    """Test real verification model"""
    result = verification_agent.verify(sample_content)
    assert "hallucination_risk" in result
    assert 0 <= result["hallucination_risk"] <= 1
```

### Step 4: Production Deployment
**Update docker-compose.yml**:
```yaml
services:
  api:
    volumes:
      - ./models:/app/models  # Mount model directory
    environment:
      - VISION_MODEL_PATH=/app/models/colpali
      - REASONING_MODEL_PATH=/app/models/reasoning
      - VERIFICATION_MODEL_PATH=/app/models/verification
```

---

## Testing & Validation

### Unit Tests
```bash
# Test individual model loading
pytest tests/test_real_models.py::test_vision_model_inference -v

# Test reasoning model
pytest tests/test_real_models.py::test_reasoning_model_inference -v

# Test verification model
pytest tests/test_real_models.py::test_verification_model_inference -v
```

### E2E Pipeline Test
```bash
# Full pipeline with real models
pytest tests/test_e2e_pipeline.py::test_vision_to_verification_pipeline -v

# Expected output:
# Vision Extraction: 2.1s
# Lakehouse Retrieval: 0.15s
# Reasoning Reranking: 4.2s
# Verification: 1.8s
# Total E2E: 8.25s
```

### Performance Benchmarking
```bash
# Run latency benchmarks
python scripts/benchmark_models.py

# Output example:
# Model           | Latency(ms) | Throughput(req/s) | VRAM(GB)
# ColPali         | 1,200       | 0.83              | 8.5
# MM-R5           | 2,800       | 0.36              | 14.2
# Argos           | 600         | 1.67              | 4.3
```

---

## Troubleshooting

### Issue 1: Model Download Fails
**Problem**: `huggingface_hub._errors.EntryNotFoundError`
**Solution**:
```bash
# Verify HuggingFace access
huggingface-cli login

# Try manual download
huggingface-cli download allenai/ColPali-base --local-dir ./models/colpali

# Check permissions
chmod -R 755 ./models/
```

### Issue 2: CUDA Out of Memory
**Problem**: `RuntimeError: CUDA out of memory`
**Solution**:
```env
# Use lower precision
DTYPE=float16  # Instead of float32

# Or use quantization
QUANTIZATION=int8  # 8-bit quantization

# Or fall back to CPU
DEVICE=cpu
```

### Issue 3: Slow Inference
**Problem**: Model inference taking > 10 seconds
**Solution**:
```python
# Enable TorchScript compilation
model = torch.jit.script(model)

# Or use ONNX for faster inference
import onnx
onnx_model = convert_torch_to_onnx(model)
```

---

## Success Criteria

- [ ] All 4 models downloaded successfully (~15 GB total)
- [ ] Models verified and checksums match
- [ ] Model paths configured in `.env`
- [ ] Vision agent loads ColPali without errors
- [ ] Reasoning agent loads MM-R5 without errors
- [ ] Verification agent loads Argos without errors
- [ ] ImageBind alignment working correctly
- [ ] E2E pipeline completes successfully
- [ ] Inference latency < 10 seconds per image
- [ ] All 87+ tests still passing
- [ ] Docker deployment with real models working

---

## Next Phase: Performance Optimization

After models are integrated:

1. **Latency Optimization**
   - Profile inference time
   - Identify bottlenecks
   - Implement caching

2. **Throughput Optimization**
   - Batch processing
   - Parallel model loading
   - Connection pooling

3. **Memory Optimization**
   - Model quantization
   - Gradient checkpointing
   - GPU memory management

---

## Estimated Timeline

| Phase | Duration | Tasks |
|-------|----------|-------|
| Prerequisites | 10 min | Install HF CLI, login |
| Downloads | 45-60 min | 4 models in parallel |
| Integration | 30 min | Update 4 agent files |
| Testing | 20 min | Run 15+ tests |
| Validation | 15 min | Performance metrics |
| **Total** | **2-2.5 hours** | |

---

**Task 12 Readiness**: ✅ Complete
**Status**: Ready for execution
**Priority**: High (enables real inference)
**Depends On**: Task 11 completed ✅

