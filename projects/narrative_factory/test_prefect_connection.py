#!/usr/bin/env python3
"""Test script to verify Prefect Cloud connection."""

import os
import sys
from typing import Optional

import httpx
from dotenv import load_dotenv

# Load environment variables from .env.template
load_dotenv('.env.template')

def test_prefect_connection() -> None:
    """Test Prefect Cloud connection with current configuration."""
    
    # Get configuration from environment
    api_url = os.getenv('PREFECT_API_URL')
    api_key = os.getenv('PREFECT_API_KEY')
    
    print("🧪 Testing Prefect Cloud Connection")
    print("=" * 50)
    
    # Check if credentials are set
    if not api_url:
        print("❌ PREFECT_API_URL not found in environment")
        return
    
    if not api_key:
        print("❌ PREFECT_API_KEY not found in environment")
        return
    
    print(f"📡 API URL: {api_url}")
    print(f"🔑 API Key: {api_key[:8]}..." if len(api_key) > 8 else f"🔑 API Key: {api_key}")
    print()
    
    # Test 1: Check if URL needs conversion
    print("🔍 Test 1: URL Format Check")
    if 'app.prefect.cloud' in api_url:
        print("⚠️  Warning: URL appears to be dashboard format, not API format")
        
        # Convert dashboard URL to API URL
        if '/account/' in api_url and '/workspace/' in api_url:
            # Extract account and workspace IDs
            parts = api_url.split('/')
            account_idx = parts.index('account') + 1
            workspace_idx = parts.index('workspace') + 1
            
            if account_idx < len(parts) and workspace_idx < len(parts):
                account_id = parts[account_idx]
                workspace_id = parts[workspace_idx]
                
                api_url_converted = f"https://api.prefect.cloud/api/accounts/{account_id}/workspaces/{workspace_id}"
                print(f"🔄 Converted API URL: {api_url_converted}")
                
                # Use converted URL for testing
                test_url = api_url_converted
            else:
                print("❌ Could not extract account/workspace IDs")
                return
        else:
            print("❌ URL format not recognized")
            return
    else:
        test_url = api_url
        print("✅ URL appears to be in correct API format")
    
    print()
    
    # Test 2: Basic API connectivity
    print("🔍 Test 2: API Connectivity")
    try:
        # Test the /me endpoint to verify authentication
        headers = {"Authorization": f"Bearer {api_key}"}
        
        with httpx.Client(timeout=30.0) as client:
            # Use the correct API endpoint format for Prefect Cloud
            response = client.get("https://api.prefect.cloud/api/me", headers=headers)
            
            if response.status_code == 200:
                print("✅ API connection successful!")
                user_data = response.json()
                print(f"👤 Authenticated as: {user_data.get('email', 'Unknown')}")
                print(f"🆔 User ID: {user_data.get('id', 'Unknown')}")
            elif response.status_code == 401:
                print("❌ Authentication failed (401 Unauthorized)")
                print("   Check your API key is correct")
            elif response.status_code == 404:
                print("❌ API endpoint not found (404)")
                print("   Check your API URL format")
            else:
                print(f"❌ API request failed with status {response.status_code}")
                print(f"   Response: {response.text}")
                
    except httpx.TimeoutException:
        print("❌ Request timed out")
        print("   Check your internet connection")
    except httpx.RequestError as e:
        print(f"❌ Request error: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
    
    print()
    
    # Test 3: Workspace access
    print("🔍 Test 3: Workspace Access")
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        
        with httpx.Client(timeout=30.0) as client:
            # Test workspace access
            response = client.get("https://api.prefect.cloud/api/me/workspaces", headers=headers)
            
            if response.status_code == 200:
                workspaces = response.json()
                print(f"✅ Found {len(workspaces)} accessible workspace(s)")
                for ws in workspaces:
                    print(f"   - {ws.get('name', 'Unknown')} ({ws.get('id', 'Unknown')})")
            else:
                print(f"❌ Workspace access failed with status {response.status_code}")
                
    except Exception as e:
        print(f"❌ Workspace test error: {e}")
    
    print()
    
    # Test 4: Try importing Prefect and connecting
    print("🔍 Test 4: Prefect Client Test")
    try:
        # Set environment variables for Prefect client
        os.environ['PREFECT_API_URL'] = test_url
        os.environ['PREFECT_API_KEY'] = api_key
        
        from prefect import get_client
        
        async def test_prefect_client():
            async with get_client() as client:
                # Test basic client functionality
                response = await client.hello()
                print(f"✅ Prefect client connected successfully!")
                print(f"📋 Response: {response.json()}")
                return True
        
        import asyncio
        asyncio.run(test_prefect_client())
        
    except ImportError:
        print("❌ Prefect not installed or not importable")
    except Exception as e:
        print(f"❌ Prefect client test failed: {e}")
    
    print()
    print("🎯 Summary")
    print("=" * 50)
    if 'app.prefect.cloud' in os.getenv('PREFECT_API_URL', ''):
        print("📝 Recommendation: Update PREFECT_API_URL to use API format:")
        print(f"   {test_url}")
    else:
        print("✅ Configuration appears correct")

if __name__ == "__main__":
    test_prefect_connection()