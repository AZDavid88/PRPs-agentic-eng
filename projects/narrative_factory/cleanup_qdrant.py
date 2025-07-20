#!/usr/bin/env python3
"""
CodeFarm Qdrant Cleanup and Deduplication Utility

Provides comprehensive tools for:
1. Cleaning up test collections
2. Removing duplicates from production collections
3. Collection management and analysis
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def analyze_collection_duplicates(collection_name: str) -> Dict[str, Any]:
    """Analyze duplicates in a collection without removing them."""
    logger.info(f"🔍 Analyzing duplicates in collection: {collection_name}")
    
    try:
        from src.memory.qdrant import QdrantService
        
        qdrant_service = QdrantService()
        result = await qdrant_service.remove_duplicates_by_content_hash(
            collection_name=collection_name,
            dry_run=True  # Only analyze, don't delete
        )
        
        logger.info(f"📊 Analysis Results for {collection_name}:")
        logger.info(f"  Total points: {result['total_points']}")
        logger.info(f"  Unique content hashes: {result['unique_content_hashes']}")
        logger.info(f"  Duplicates found: {result['duplicates_found']}")
        logger.info(f"  Points to keep: {result['points_to_keep']}")
        
        if result['duplicates_found'] > 0:
            logger.info(f"  📝 Duplicate details:")
            for dup in result['duplicate_details'][:5]:  # Show first 5
                logger.info(f"    - ID: {dup['id']}, Material: {dup['material_id']}, Created: {dup['created_at']}")
            
            if len(result['duplicate_details']) > 5:
                logger.info(f"    ... and {len(result['duplicate_details']) - 5} more duplicates")
        
        await qdrant_service.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to analyze collection {collection_name}: {e}")
        return {"error": str(e)}

async def remove_duplicates_from_collection(collection_name: str, confirm: bool = False) -> Dict[str, Any]:
    """Remove duplicates from a collection."""
    logger.info(f"🧹 Removing duplicates from collection: {collection_name}")
    
    if not confirm:
        logger.warning("⚠️  This is a DRY RUN. Use confirm=True to actually remove duplicates.")
    
    try:
        from src.memory.qdrant import QdrantService
        
        qdrant_service = QdrantService()
        result = await qdrant_service.remove_duplicates_by_content_hash(
            collection_name=collection_name,
            dry_run=not confirm
        )
        
        if confirm and result['duplicates_found'] > 0:
            logger.info(f"✅ Successfully removed {result['duplicates_found']} duplicates from {collection_name}")
        elif result['duplicates_found'] > 0:
            logger.info(f"📋 Would remove {result['duplicates_found']} duplicates from {collection_name}")
        else:
            logger.info(f"✨ No duplicates found in {collection_name}")
        
        await qdrant_service.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to remove duplicates from {collection_name}: {e}")
        return {"error": str(e)}

async def cleanup_test_collections(confirm: bool = False) -> Dict[str, Any]:
    """Clean up test collections."""
    logger.info("🧪 Cleaning up test collections")
    
    if not confirm:
        logger.warning("⚠️  This is a DRY RUN. Use confirm=True to actually delete test collections.")
    
    try:
        from src.memory.qdrant import QdrantService
        
        qdrant_service = QdrantService()
        result = await qdrant_service.cleanup_test_collections(confirm=confirm)
        
        logger.info(f"📊 Test Collections Analysis:")
        logger.info(f"  Collections found: {result['test_collections_found']}")
        logger.info(f"  Collections to delete: {result['collections_to_delete']}")
        
        if confirm and result.get('successfully_deleted', 0) > 0:
            logger.info(f"✅ Successfully deleted {result['successfully_deleted']} test collections")
            for collection in result.get('deleted_collections', []):
                logger.info(f"  - Deleted: {collection}")
        
        if result.get('failed_deletions'):
            logger.warning("⚠️  Failed to delete some collections:")
            for failure in result['failed_deletions']:
                logger.warning(f"  - {failure}")
        
        await qdrant_service.close()
        return result
        
    except Exception as e:
        logger.error(f"❌ Failed to cleanup test collections: {e}")
        return {"error": str(e)}

async def list_all_collections() -> List[str]:
    """List all collections in Qdrant."""
    logger.info("📝 Listing all Qdrant collections")
    
    try:
        from src.memory.qdrant import QdrantService
        
        qdrant_service = QdrantService()
        collections = await qdrant_service.list_collections()
        
        logger.info(f"📊 Found {len(collections)} collections:")
        for i, collection in enumerate(collections, 1):
            try:
                info = await qdrant_service.get_collection_info(collection)
                points_count = info.get('points_count', 0)
                status = info.get('status', 'unknown')
                logger.info(f"  {i:2d}. {collection:30s} - {points_count:6d} points ({status})")
            except Exception as e:
                logger.info(f"  {i:2d}. {collection:30s} - Error getting info: {e}")
        
        await qdrant_service.close()
        return collections
        
    except Exception as e:
        logger.error(f"❌ Failed to list collections: {e}")
        return []

async def interactive_cleanup():
    """Interactive cleanup mode."""
    logger.info("🎮 Interactive Qdrant Cleanup Mode")
    
    while True:
        print("\n" + "="*60)
        print("QDRANT CLEANUP UTILITY")
        print("="*60)
        print("1. List all collections")
        print("2. Analyze duplicates in a collection")
        print("3. Remove duplicates from a collection (dry run)")
        print("4. Remove duplicates from a collection (CONFIRM)")
        print("5. Cleanup test collections (dry run)")
        print("6. Cleanup test collections (CONFIRM)")
        print("7. Exit")
        print("-"*60)
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == "1":
            await list_all_collections()
            
        elif choice == "2":
            collection_name = input("Enter collection name: ").strip()
            if collection_name:
                await analyze_collection_duplicates(collection_name)
            else:
                logger.warning("⚠️  Collection name cannot be empty")
                
        elif choice == "3":
            collection_name = input("Enter collection name: ").strip()
            if collection_name:
                await remove_duplicates_from_collection(collection_name, confirm=False)
            else:
                logger.warning("⚠️  Collection name cannot be empty")
                
        elif choice == "4":
            collection_name = input("Enter collection name: ").strip()
            if collection_name:
                confirm = input(f"⚠️  CONFIRM: Remove duplicates from '{collection_name}'? (yes/no): ").strip().lower()
                if confirm == "yes":
                    await remove_duplicates_from_collection(collection_name, confirm=True)
                else:
                    logger.info("❌ Operation cancelled")
            else:
                logger.warning("⚠️  Collection name cannot be empty")
                
        elif choice == "5":
            await cleanup_test_collections(confirm=False)
            
        elif choice == "6":
            confirm = input("⚠️  CONFIRM: Delete all test collections? (yes/no): ").strip().lower()
            if confirm == "yes":
                await cleanup_test_collections(confirm=True)
            else:
                logger.info("❌ Operation cancelled")
                
        elif choice == "7":
            logger.info("👋 Goodbye!")
            break
            
        else:
            logger.warning("⚠️  Invalid choice. Please enter 1-7.")

async def main():
    """Main function - run specific cleanup operations."""
    import sys
    
    if len(sys.argv) == 1:
        # No arguments - run interactive mode
        await interactive_cleanup()
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        await list_all_collections()
        
    elif command == "analyze" and len(sys.argv) > 2:
        collection_name = sys.argv[2]
        await analyze_collection_duplicates(collection_name)
        
    elif command == "deduplicate" and len(sys.argv) > 2:
        collection_name = sys.argv[2]
        confirm = len(sys.argv) > 3 and sys.argv[3].lower() == "confirm"
        await remove_duplicates_from_collection(collection_name, confirm=confirm)
        
    elif command == "cleanup-tests":
        confirm = len(sys.argv) > 2 and sys.argv[2].lower() == "confirm"
        await cleanup_test_collections(confirm=confirm)
        
    else:
        print("Usage:")
        print("  python cleanup_qdrant.py                           # Interactive mode")
        print("  python cleanup_qdrant.py list                      # List all collections")
        print("  python cleanup_qdrant.py analyze <collection>      # Analyze duplicates")
        print("  python cleanup_qdrant.py deduplicate <collection> [confirm]  # Remove duplicates")
        print("  python cleanup_qdrant.py cleanup-tests [confirm]   # Cleanup test collections")

if __name__ == "__main__":
    asyncio.run(main())