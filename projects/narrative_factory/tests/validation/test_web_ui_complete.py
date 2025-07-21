"""
Complete Web UI Validation Suite

End-to-end testing to catch all potential bugs before they reach production.
This script performs comprehensive validation of the entire web UI workflow.
"""

import pytest
import asyncio
import aiohttp
import json
import time
from pathlib import Path
from typing import Dict, Any, List
import tempfile
import os

class WebUIValidator:
    """Comprehensive web UI validation with real API testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session = None
        self.test_files = []
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
        self.cleanup_test_files()
    
    def create_test_files(self) -> List[str]:
        """Create temporary test files for upload testing."""
        test_content = [
            ("character.txt", "Aragorn is a ranger from the North. He is the rightful king of Gondor."),
            ("setting.txt", "Rivendell is a hidden valley where elves dwell. It is a place of peace and wisdom."),
            ("plot.txt", "The Fellowship must destroy the One Ring to save Middle-earth from darkness.")
        ]
        
        temp_dir = tempfile.mkdtemp()
        file_paths = []
        
        for filename, content in test_content:
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, 'w') as f:
                f.write(content)
            file_paths.append(file_path)
            self.test_files.append(file_path)
        
        return file_paths
    
    def cleanup_test_files(self):
        """Clean up temporary test files."""
        for file_path in self.test_files:
            try:
                os.unlink(file_path)
            except OSError:
                pass
        self.test_files.clear()

    async def test_server_health(self) -> bool:
        """Test if the server is running and responding."""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                return response.status == 200
        except Exception as e:
            print(f"Server health check failed: {e}")
            return False

    async def test_api_endpoints_accessibility(self) -> Dict[str, bool]:
        """Test that all critical API endpoints are accessible."""
        endpoints = [
            "/api/ingestion/available-genres",
            "/api/ingestion/jobs",
            "/health",
            "/"  # Main page
        ]
        
        results = {}
        for endpoint in endpoints:
            try:
                async with self.session.get(f"{self.base_url}{endpoint}") as response:
                    results[endpoint] = response.status < 400
            except Exception as e:
                print(f"Endpoint {endpoint} failed: {e}")
                results[endpoint] = False
        
        return results

    async def test_genre_detection_api(self) -> bool:
        """Test the genre detection API endpoint."""
        try:
            test_content = "The wizard cast a spell to defeat the dragon in the ancient castle."
            payload = {"content": test_content}
            
            async with self.session.post(
                f"{self.base_url}/api/ingestion/detect-genre",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return (
                        "detected_genres" in data and
                        isinstance(data["detected_genres"], list) and
                        len(data["detected_genres"]) > 0
                    )
                return False
        except Exception as e:
            print(f"Genre detection test failed: {e}")
            return False

    async def test_file_upload_workflow(self) -> Dict[str, Any]:
        """Test the complete file upload workflow."""
        file_paths = self.create_test_files()
        
        try:
            # Prepare multipart form data
            data = aiohttp.FormData()
            
            # Add files
            for file_path in file_paths:
                with open(file_path, 'rb') as f:
                    data.add_field('files', f, filename=os.path.basename(file_path))
            
            # Add form fields
            data.add_field('genre_context', 'fantasy')
            data.add_field('processing_mode', 'pipeline')
            data.add_field('batch_size', '20')
            data.add_field('min_confidence_threshold', '0.7')
            data.add_field('enable_cross_references', 'true')
            
            # Upload files
            async with self.session.post(
                f"{self.base_url}/api/ingestion/upload",
                data=data
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"Upload failed with status {response.status}: {error_text}",
                        "job_id": None
                    }
                
                upload_result = await response.json()
                job_id = upload_result.get("job_id")
                
                if not job_id:
                    return {
                        "success": False,
                        "error": "No job_id returned from upload",
                        "job_id": None
                    }
                
                # Test progress tracking
                progress_success = await self.test_progress_tracking(job_id)
                
                # Wait for completion and test results
                results_success = await self.test_results_retrieval(job_id)
                
                return {
                    "success": True,
                    "job_id": job_id,
                    "upload_result": upload_result,
                    "progress_tracking": progress_success,
                    "results_retrieval": results_success
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Upload workflow failed: {str(e)}",
                "job_id": None
            }

    async def test_progress_tracking(self, job_id: str) -> bool:
        """Test progress tracking for a job."""
        try:
            max_attempts = 30  # 60 seconds max
            for attempt in range(max_attempts):
                async with self.session.get(
                    f"{self.base_url}/api/ingestion/progress/{job_id}"
                ) as response:
                    if response.status == 200:
                        progress = await response.json()
                        
                        # Verify progress structure
                        required_fields = [
                            "job_id", "status", "progress_percentage",
                            "current_stage", "materials_processed",
                            "materials_remaining", "estimated_time_remaining"
                        ]
                        
                        if not all(field in progress for field in required_fields):
                            return False
                        
                        # Check if job is complete
                        if progress["status"] in ["completed", "failed"]:
                            return progress["status"] == "completed"
                        
                        # Wait and retry
                        await asyncio.sleep(2)
                    else:
                        return False
            
            # Timeout
            return False
            
        except Exception as e:
            print(f"Progress tracking test failed: {e}")
            return False

    async def test_results_retrieval(self, job_id: str) -> bool:
        """Test results retrieval for a completed job."""
        try:
            # Wait a bit for job to complete
            await asyncio.sleep(5)
            
            async with self.session.get(
                f"{self.base_url}/api/ingestion/results/{job_id}"
            ) as response:
                if response.status == 200:
                    results = await response.json()
                    
                    # Verify results structure
                    required_fields = [
                        "job_id", "status", "results"
                    ]
                    
                    if not all(field in results for field in required_fields):
                        return False
                    
                    # Check LibrarianAgent integration
                    if "librarian_analysis" in results:
                        librarian_data = results["librarian_analysis"]
                        return (
                            "enhanced" in librarian_data and
                            "insights" in librarian_data and
                            isinstance(librarian_data["insights"], list)
                        )
                    
                    return True
                else:
                    return False
                    
        except Exception as e:
            print(f"Results retrieval test failed: {e}")
            return False

    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection for chat functionality."""
        try:
            # First get a demo token
            async with self.session.get(
                f"{self.base_url}/api/auth/demo-token?user_id=test_user"
            ) as response:
                if response.status != 200:
                    return False
                
                token_data = await response.json()
                token = token_data.get("token")
                if not token:
                    return False
            
            # Test WebSocket connection
            import aiohttp
            ws_url = f"ws://localhost:8000/ws/narrative"
            
            async with self.session.ws_connect(ws_url) as ws:
                # Send authentication
                auth_message = {
                    "type": "authenticate",
                    "token": token
                }
                await ws.send_str(json.dumps(auth_message))
                
                # Wait for auth response
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "authenticate":
                            return data.get("data", {}).get("status") == "authenticated"
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        return False
                    
                    # Timeout after first message
                    break
            
            return False
            
        except Exception as e:
            print(f"WebSocket test failed: {e}")
            return False

    async def test_job_management_api(self) -> bool:
        """Test job management API endpoints."""
        try:
            # Test job listing
            async with self.session.get(
                f"{self.base_url}/api/ingestion/jobs?limit=10"
            ) as response:
                if response.status != 200:
                    return False
                
                jobs_data = await response.json()
                
                # Verify structure
                if not all(field in jobs_data for field in ["jobs", "total", "limit", "offset"]):
                    return False
                
                # If there are jobs, test individual job operations
                if jobs_data["total"] > 0:
                    job = jobs_data["jobs"][0]
                    job_id = job["job_id"]
                    
                    # Test job status endpoint
                    async with self.session.get(
                        f"{self.base_url}/api/ingestion/status/{job_id}"
                    ) as status_response:
                        if status_response.status != 200:
                            return False
                
                return True
                
        except Exception as e:
            print(f"Job management API test failed: {e}")
            return False

    async def run_complete_validation(self) -> Dict[str, Any]:
        """Run complete validation suite."""
        print("🔍 Starting comprehensive web UI validation...")
        
        results = {
            "timestamp": time.time(),
            "server_health": False,
            "api_endpoints": {},
            "genre_detection": False,
            "file_upload_workflow": {},
            "websocket_connection": False,
            "job_management": False,
            "overall_success": False
        }
        
        # Test 1: Server Health
        print("1. Testing server health...")
        results["server_health"] = await self.test_server_health()
        if not results["server_health"]:
            print("❌ Server is not responding")
            return results
        print("✅ Server is healthy")
        
        # Test 2: API Endpoints
        print("2. Testing API endpoint accessibility...")
        results["api_endpoints"] = await self.test_api_endpoints_accessibility()
        failed_endpoints = [ep for ep, success in results["api_endpoints"].items() if not success]
        if failed_endpoints:
            print(f"❌ Failed endpoints: {failed_endpoints}")
        else:
            print("✅ All API endpoints accessible")
        
        # Test 3: Genre Detection
        print("3. Testing genre detection API...")
        results["genre_detection"] = await self.test_genre_detection_api()
        if results["genre_detection"]:
            print("✅ Genre detection working")
        else:
            print("❌ Genre detection failed")
        
        # Test 4: File Upload Workflow
        print("4. Testing complete file upload workflow...")
        results["file_upload_workflow"] = await self.test_file_upload_workflow()
        if results["file_upload_workflow"]["success"]:
            print("✅ File upload workflow successful")
        else:
            print(f"❌ File upload failed: {results['file_upload_workflow']['error']}")
        
        # Test 5: WebSocket Connection
        print("5. Testing WebSocket connection...")
        results["websocket_connection"] = await self.test_websocket_connection()
        if results["websocket_connection"]:
            print("✅ WebSocket connection working")
        else:
            print("❌ WebSocket connection failed")
        
        # Test 6: Job Management
        print("6. Testing job management API...")
        results["job_management"] = await self.test_job_management_api()
        if results["job_management"]:
            print("✅ Job management API working")
        else:
            print("❌ Job management API failed")
        
        # Overall Success
        critical_tests = [
            results["server_health"],
            results["genre_detection"],
            results["file_upload_workflow"]["success"],
            results["job_management"]
        ]
        
        results["overall_success"] = all(critical_tests)
        
        if results["overall_success"]:
            print("🎉 ALL VALIDATION TESTS PASSED!")
        else:
            print("💥 SOME VALIDATION TESTS FAILED!")
        
        return results


async def run_validation():
    """Run the complete validation suite."""
    async with WebUIValidator() as validator:
        return await validator.run_complete_validation()


if __name__ == "__main__":
    # Run validation
    results = asyncio.run(run_validation())
    
    # Print detailed results
    print("\n" + "="*50)
    print("DETAILED VALIDATION RESULTS")
    print("="*50)
    
    for test_name, result in results.items():
        if test_name == "timestamp":
            continue
        print(f"{test_name}: {result}")
    
    # Exit with appropriate code
    exit(0 if results["overall_success"] else 1)