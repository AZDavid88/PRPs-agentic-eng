#!/usr/bin/env python3
"""
Simple test script for the material ingestion pipeline.
"""

import asyncio
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_pipeline_basic():
    """Test basic pipeline functionality."""
    try:
        from src.ingestion.pipeline import MaterialIngestionPipeline, PipelineProgressUpdate
        from src.models.material_models import MaterialIngestionRequest
        
        print("✓ Successfully imported pipeline components")
        
        # Create a simple test request
        test_materials = [
            "Character: Ren, a young geomancer with the ability to manipulate stone and earth.",
            "Setting: The Ashfall Wastes, a desolate region covered in volcanic ash.",
            "System: Magic flows through ancient ley lines beneath the earth.",
        ]
        
        print(f"Testing with {len(test_materials)} sample materials...")
        
        # Simple progress callback
        def progress_callback(update: PipelineProgressUpdate) -> None:
            print(f"  Progress: {update.progress_percentage:.1f}% - {update.stage} - {update.message}")
        
        # Create request (filling in required fields)
        request = MaterialIngestionRequest(
            materials=test_materials,
            genre_context="fantasy",
            additional_genres=[],
            custom_categories=None,
            processing_mode="pipeline",
            batch_size=10,
            enable_cross_references=True,
            min_confidence_threshold=0.7,
            enable_progressive_disclosure=True,
            story_id=None,
            user_id=None
        )
        
        print("✓ Created test request successfully")
        
        # Test pipeline initialization
        pipeline = MaterialIngestionPipeline()
        print("✓ Pipeline initialized successfully")
        
        # Test health check
        health = await pipeline.health_check()
        print(f"✓ Health check completed: {health.get('pipeline_healthy', False)}")
        
        await pipeline.close()
        print("✓ Pipeline closed successfully")
        
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run the pipeline tests."""
    print("Material Ingestion Pipeline Test")
    print("=" * 50)
    
    success = await test_pipeline_basic()
    
    if success:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Tests failed!")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)