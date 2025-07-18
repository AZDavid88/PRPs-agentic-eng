#!/usr/bin/env python3
"""
Bootstrap data ingestion script for the Narrative Factory.
Processes JSON documents from memory_bootstrap/ and loads them into Qdrant.
"""

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.memory.qdrant import QdrantService
from src.memory.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ingest.log')
    ]
)
logger = logging.getLogger(__name__)


class BootstrapIngester:
    """Handles ingestion of bootstrap data into Qdrant Cloud."""
    
    def __init__(self, 
                 qdrant_url: Optional[str] = None,
                 qdrant_api_key: Optional[str] = None,
                 embedding_provider: str = "jina",
                 dry_run: bool = False):
        """
        Initialize the ingester for cloud deployment.
        
        Args:
            qdrant_url: Qdrant Cloud endpoint URL (optional, uses env var)
            qdrant_api_key: Qdrant Cloud API key (optional, uses env var)
            embedding_provider: Embedding provider ("jina", "openai", "local")
            dry_run: If True, process but don't actually ingest
        """
        self.dry_run = dry_run
        self.qdrant_service = QdrantService(url=qdrant_url, api_key=qdrant_api_key)
        self.embedding_service = EmbeddingService(provider=embedding_provider)
        
        # Document type mappings
        self.collection_mappings = {
            "character_sheets": "world_bible",
            "lore_documents": "world_bible", 
            "style_guides": "world_bible",
            "tension_reports": "story_so_far",
            "chapter_summaries": "story_so_far"
        }
        
    async def discover_documents(self, bootstrap_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
        """
        Discover and load all JSON documents from bootstrap directory.
        
        Args:
            bootstrap_dir: Path to memory_bootstrap directory
            
        Returns:
            Dictionary mapping doc types to document lists
        """
        documents_by_type = {}
        
        if not bootstrap_dir.exists():
            logger.error(f"Bootstrap directory not found: {bootstrap_dir}")
            return documents_by_type
        
        for doc_type_dir in bootstrap_dir.iterdir():
            if not doc_type_dir.is_dir():
                continue
                
            doc_type = doc_type_dir.name
            documents = []
            
            logger.info(f"Processing {doc_type} directory...")
            
            for json_file in doc_type_dir.glob("*.json"):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        doc_data = json.load(f)
                    
                    # Add metadata
                    doc_data["doc_type"] = doc_type.rstrip('s')  # character_sheets -> character_sheet
                    doc_data["source_file"] = str(json_file.relative_to(bootstrap_dir))
                    
                    # Ensure we have an ID and preserve original ID
                    if "id" not in doc_data:
                        doc_data["id"] = json_file.stem
                    
                    # Store original ID as metadata and generate UUID for Qdrant
                    doc_data["original_id"] = doc_data["id"]
                    doc_data["id"] = str(uuid.uuid4())
                    
                    # Extract content for embedding
                    content = self._extract_content(doc_data)
                    doc_data["content"] = content
                    
                    documents.append(doc_data)
                    logger.info(f"Loaded {json_file.name}")
                    
                except Exception as e:
                    logger.error(f"Failed to load {json_file}: {e}")
                    continue
            
            if documents:
                documents_by_type[doc_type] = documents
                logger.info(f"Loaded {len(documents)} documents from {doc_type}")
        
        return documents_by_type
    
    def _extract_content(self, doc_data: Dict[str, Any]) -> str:
        """
        Extract meaningful content from document for embedding.
        
        Args:
            doc_data: Document data dictionary
            
        Returns:
            Concatenated content string
        """
        content_parts = []
        
        # Common content fields
        for field in ["name", "title", "description", "summary", "content"]:
            if field in doc_data and doc_data[field]:
                content_parts.append(str(doc_data[field]))
        
        # Character sheet specific
        if "character_name" in doc_data:
            content_parts.append(f"Character: {doc_data['character_name']}")
        
        if "background" in doc_data:
            content_parts.append(doc_data["background"])
        
        if "personality" in doc_data:
            content_parts.append(f"Personality: {doc_data['personality']}")
        
        if "relationships" in doc_data and isinstance(doc_data["relationships"], list):
            content_parts.append(f"Related to: {', '.join(doc_data['relationships'])}")
        
        # Lore document specific
        if "rules" in doc_data and isinstance(doc_data["rules"], list):
            content_parts.extend(doc_data["rules"])
        
        if "key_locations" in doc_data and isinstance(doc_data["key_locations"], list):
            content_parts.extend(doc_data["key_locations"])
        
        # Style guide specific
        if "guidelines" in doc_data and isinstance(doc_data["guidelines"], dict):
            for category, guidelines in doc_data["guidelines"].items():
                if isinstance(guidelines, list):
                    content_parts.append(f"{category}: {'; '.join(guidelines)}")
                else:
                    content_parts.append(f"{category}: {guidelines}")
        
        # Fallback: convert entire document to string
        if not content_parts:
            content_parts.append(json.dumps(doc_data, ensure_ascii=False))
        
        return " | ".join(content_parts)
    
    def _enhance_metadata(self, doc_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance document metadata for better filtering.
        
        Args:
            doc_data: Original document data
            
        Returns:
            Enhanced document with additional metadata
        """
        enhanced = doc_data.copy()
        
        # Extract character relationships for spotlight filtering
        present_characters = []
        
        if "character_name" in doc_data:
            present_characters.append(doc_data["character_name"].lower())
        
        if "relationships" in doc_data and isinstance(doc_data["relationships"], list):
            present_characters.extend([name.lower() for name in doc_data["relationships"]])
        
        if "mentioned_characters" in doc_data and isinstance(doc_data["mentioned_characters"], list):
            present_characters.extend([name.lower() for name in doc_data["mentioned_characters"]])
        
        enhanced["present_characters"] = list(set(present_characters))
        
        # Add status for tension reports
        if doc_data.get("doc_type") == "tension_report":
            enhanced["status"] = doc_data.get("status", "unresolved")
            enhanced["severity"] = doc_data.get("severity", "medium")
        
        # Add searchable tags
        tags = []
        if "doc_type" in enhanced:
            tags.append(enhanced["doc_type"])
        
        if "character_name" in enhanced:
            tags.append(f"character:{enhanced['character_name'].lower()}")
        
        if "location" in enhanced:
            tags.append(f"location:{enhanced['location'].lower()}")
        
        enhanced["tags"] = tags
        
        return enhanced
    
    async def ingest_documents(self, documents_by_type: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """
        Ingest documents into appropriate Qdrant collections.
        
        Args:
            documents_by_type: Documents organized by type
            
        Returns:
            Dictionary with ingestion statistics
        """
        stats = {"total_processed": 0, "total_ingested": 0, "errors": 0}
        
        if not self.dry_run:
            # Create collections first
            await self.qdrant_service.create_collections()
        
        for doc_type, documents in documents_by_type.items():
            collection_name = self.collection_mappings.get(doc_type, "world_bible")
            
            logger.info(f"Processing {len(documents)} {doc_type} documents for {collection_name}")
            
            # Enhance metadata
            enhanced_docs = []
            for doc in documents:
                try:
                    enhanced = self._enhance_metadata(doc)
                    enhanced_docs.append(enhanced)
                    stats["total_processed"] += 1
                except Exception as e:
                    logger.error(f"Failed to enhance metadata for {doc.get('id', 'unknown')}: {e}")
                    stats["errors"] += 1
            
            if not enhanced_docs:
                logger.warning(f"No valid documents to ingest for {doc_type}")
                continue
            
            # Ingest to Qdrant
            if not self.dry_run:
                try:
                    await self.qdrant_service.ingest_documents(enhanced_docs, collection_name)
                    stats["total_ingested"] += len(enhanced_docs)
                    logger.info(f"Successfully ingested {len(enhanced_docs)} {doc_type} documents")
                except Exception as e:
                    logger.error(f"Failed to ingest {doc_type} documents: {e}")
                    stats["errors"] += len(enhanced_docs)
            else:
                logger.info(f"[DRY RUN] Would ingest {len(enhanced_docs)} {doc_type} documents to {collection_name}")
                stats["total_ingested"] += len(enhanced_docs)
        
        return stats
    
    async def validate_ingestion(self) -> bool:
        """
        Validate that documents were successfully ingested.
        
        Returns:
            True if validation passes
        """
        try:
            world_bible_info = await self.qdrant_service.get_collection_info("world_bible")
            story_so_far_info = await self.qdrant_service.get_collection_info("story_so_far")
            
            logger.info(f"world_bible collection: {world_bible_info.get('points_count', 0)} points")
            logger.info(f"story_so_far collection: {story_so_far_info.get('points_count', 0)} points")
            
            # Test a simple search
            test_results = await self.qdrant_service.search_by_content(
                query_text="character",
                collection_name="world_bible",
                limit=3
            )
            
            logger.info(f"Test search returned {len(test_results)} results")
            if test_results:
                logger.info(f"Sample result: {test_results[0].get('id', 'unknown')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return False
    
    async def close(self):
        """Clean up resources."""
        await self.qdrant_service.close()
        await self.embedding_service.close()


async def main():
    """Main ingestion script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Ingest bootstrap data into Qdrant")
    parser.add_argument("--bootstrap-dir", 
                       default="memory_bootstrap",
                       help="Path to bootstrap data directory")
    parser.add_argument("--qdrant-url",
                       help="Qdrant Cloud endpoint URL (uses QDRANT_URL env var if not provided)")
    parser.add_argument("--qdrant-api-key",
                       help="Qdrant Cloud API key (uses QDRANT_API_KEY env var if not provided)")
    parser.add_argument("--embedding-provider",
                       choices=["local", "jina", "openai"],
                       default="jina",
                       help="Embedding provider to use")
    parser.add_argument("--dry-run",
                       action="store_true",
                       help="Process documents but don't ingest")
    parser.add_argument("--validate",
                       action="store_true",
                       help="Run validation after ingestion")
    
    args = parser.parse_args()
    
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    bootstrap_dir = project_root / args.bootstrap_dir
    
    logger.info(f"Starting bootstrap ingestion...")
    logger.info(f"Bootstrap directory: {bootstrap_dir}")
    logger.info(f"Qdrant URL: {args.qdrant_url or 'Using env var'}")
    logger.info(f"Embedding provider: {args.embedding_provider}")
    logger.info(f"Dry run: {args.dry_run}")
    
    # Initialize ingester
    ingester = BootstrapIngester(
        qdrant_url=args.qdrant_url,
        qdrant_api_key=args.qdrant_api_key,
        embedding_provider=args.embedding_provider,
        dry_run=args.dry_run
    )
    
    try:
        # Discover documents
        logger.info("Discovering documents...")
        documents_by_type = await ingester.discover_documents(bootstrap_dir)
        
        if not documents_by_type:
            logger.error("No documents found to ingest")
            return 1
        
        total_docs = sum(len(docs) for docs in documents_by_type.values())
        logger.info(f"Found {total_docs} total documents across {len(documents_by_type)} types")
        
        # Ingest documents
        logger.info("Starting ingestion...")
        stats = await ingester.ingest_documents(documents_by_type)
        
        # Report results
        logger.info("Ingestion completed!")
        logger.info(f"Total processed: {stats['total_processed']}")
        logger.info(f"Total ingested: {stats['total_ingested']}")
        logger.info(f"Errors: {stats['errors']}")
        
        # Validate if requested
        if args.validate and not args.dry_run:
            logger.info("Running validation...")
            if await ingester.validate_ingestion():
                logger.info("Validation passed!")
            else:
                logger.error("Validation failed!")
                return 1
        
        return 0
        
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        return 1
        
    finally:
        await ingester.close()


async def ingest_bootstrap_data():
    """
    Simple function to be called from CLI for ingesting bootstrap data.
    Uses default settings for ease of use.
    """
    # Set up paths
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    bootstrap_dir = project_root / "memory_bootstrap"
    
    logger.info("Starting bootstrap ingestion from CLI...")
    
    # Initialize ingester with default settings
    ingester = BootstrapIngester(
        embedding_provider="jina",
        dry_run=False
    )
    
    try:
        # Discover documents
        logger.info("Discovering documents...")
        documents_by_type = await ingester.discover_documents(bootstrap_dir)
        
        if not documents_by_type:
            logger.error("No documents found to ingest")
            raise ValueError("No documents found in memory_bootstrap directory")
        
        total_docs = sum(len(docs) for docs in documents_by_type.values())
        logger.info(f"Found {total_docs} total documents across {len(documents_by_type)} types")
        
        # Ingest documents
        logger.info("Starting ingestion...")
        stats = await ingester.ingest_documents(documents_by_type)
        
        # Report results
        logger.info("Ingestion completed!")
        logger.info(f"Total processed: {stats['total_processed']}")
        logger.info(f"Total ingested: {stats['total_ingested']}")
        logger.info(f"Errors: {stats['errors']}")
        
        # Run basic validation
        logger.info("Running validation...")
        if await ingester.validate_ingestion():
            logger.info("Validation passed!")
        else:
            logger.warning("Validation had issues but continuing anyway")
        
    finally:
        await ingester.close()


if __name__ == "__main__":
    import sys
    exit_code = asyncio.run(main())
    sys.exit(exit_code)