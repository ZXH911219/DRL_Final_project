"""
API endpoint tests
"""

import pytest
import base64
import numpy as np
import cv2
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client"""
    from src.api.main import app
    return TestClient(app)


@pytest.fixture
def dummy_image_base64():
    """Create dummy image as base64"""
    image = np.random.randint(0, 256, (768, 1024, 3), dtype=np.uint8)
    _, buffer = cv2.imencode('.png', image)
    return base64.b64encode(buffer).decode('utf-8')


class TestRootEndpoints:
    """Test root and health check endpoints"""
    
    def test_root_endpoint(self, client):
        """Test GET /"""
        response = client.get("/")
        assert response.status_code == 200
        assert "name" in response.json()
        assert "version" in response.json()
        assert "endpoints" in response.json()
    
    def test_health_check(self, client):
        """Test GET /health"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
    
    def test_metrics_endpoint(self, client):
        """Test GET /metrics"""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
        assert "error_rate" in data


class TestVisionEndpoints:
    """Test vision extraction endpoints"""
    
    def test_vision_health(self, client):
        """Test vision health check"""
        response = client.get("/api/v1/vision/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_vision_warm_up(self, client):
        """Test vision warm-up endpoint"""
        response = client.post("/api/v1/vision/warm-up")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "time_ms" in data
    
    def test_vision_extraction(self, client, dummy_image_base64):
        """Test vision feature extraction"""
        request_data = {
            "image_base64": dummy_image_base64,
            "image_format": "png",
            "metadata": {"slide_id": "test_slide"}
        }
        
        response = client.post("/api/v1/vision/extract", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "multi_vectors_shape" in data
        assert "processing_time_ms" in data


class TestReasoningEndpoints:
    """Test reasoning reranker endpoints"""
    
    def test_reasoning_health(self, client):
        """Test reasoning health check"""
        response = client.get("/api/v1/reasoning/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_reasoning_warm_up(self, client):
        """Test reasoning warm-up endpoint"""
        response = client.post("/api/v1/reasoning/warm-up")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "time_ms" in data
    
    def test_reasoning_rerank(self, client):
        """Test reasoning reranking"""
        request_data = {
            "query": "machine learning in finance",
            "candidates": [
                {"slide_id": "slide_1", "content": "ML algorithms", "score": 0.8},
                {"slide_id": "slide_2", "content": "Traditional approach", "score": 0.6}
            ],
            "max_candidates": 2
        }
        
        response = client.post("/api/v1/reasoning/rerank", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "reranked_candidates" in data
    
    def test_reasoning_explain(self, client):
        """Test reasoning explanation"""
        response = client.post(
            "/api/v1/reasoning/explain-reasoning?query=test%20query&content=test%20content&slide_id=test"
        )
        assert response.status_code == 200
        data = response.json()
        assert "reasoning_chain" in data
        assert "final_score" in data


class TestVerificationEndpoints:
    """Test verification endpoints"""
    
    def test_verification_health(self, client):
        """Test verification health check"""
        response = client.get("/api/v1/verification/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
    
    def test_verification_warm_up(self, client):
        """Test verification warm-up endpoint"""
        response = client.post("/api/v1/verification/warm-up")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "time_ms" in data
    
    def test_verification_verify(self, client, dummy_image_base64):
        """Test verification"""
        request_data = {
            "slide_id": "test_slide",
            "image_base64": dummy_image_base64,
            "reasoning_text": "This slide shows a growth trend",
            "original_score": 0.85
        }
        
        response = client.post("/api/v1/verification/verify", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "verification_status" in data
        assert "hallucination_risk_score" in data


class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_image_base64(self, client):
        """Test invalid image base64"""
        request_data = {
            "image_base64": "invalid_base64_string",
            "image_format": "png"
        }
        
        response = client.post("/api/v1/vision/extract", json=request_data)
        assert response.status_code == 400
    
    def test_empty_candidates(self, client):
        """Test reranking with empty candidates"""
        request_data = {
            "query": "test",
            "candidates": []
        }
        
        response = client.post("/api/v1/reasoning/rerank", json=request_data)
        assert response.status_code == 400


class TestBatchOperations:
    """Test batch operations"""
    
    def test_batch_vision_extraction(self, client, dummy_image_base64):
        """Test batch vision extraction"""
        request_data = [
            {
                "image_base64": dummy_image_base64,
                "image_format": "png",
                "metadata": {"slide_id": f"slide_{i}"}
            }
            for i in range(3)
        ]
        
        response = client.post("/api/v1/vision/batch-extract", json=request_data)
        assert response.status_code == 200
        data = response.json()
        assert "successful" in data
        assert "results" in data


class TestEndpointIntegration:
    """Test integration between endpoints"""
    
    def test_complete_pipeline(self, client, dummy_image_base64):
        """Test complete pipeline: vision -> reasoning -> verification"""
        # Step 1: Extract vision features
        vision_response = client.post(
            "/api/v1/vision/extract",
            json={
                "image_base64": dummy_image_base64,
                "metadata": {"slide_id": "test"}
            }
        )
        assert vision_response.status_code == 200
        
        # Step 2: Rerank with reasoning
        reasoning_response = client.post(
            "/api/v1/reasoning/rerank",
            json={
                "query": "test query",
                "candidates": [
                    {"slide_id": "s1", "content": "test", "score": 0.8}
                ]
            }
        )
        assert reasoning_response.status_code == 200
        
        # Step 3: Verify reasoning
        verify_response = client.post(
            "/api/v1/verification/verify",
            json={
                "slide_id": "test",
                "image_base64": dummy_image_base64,
                "reasoning_text": "test reasoning",
                "original_score": 0.85
            }
        )
        assert verify_response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
