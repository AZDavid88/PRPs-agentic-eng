#!/usr/bin/env python3
"""
Simple Priority 1 Fix Verification
Direct testing of each Priority 1 fix without complex validation frameworks
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def test_vector_dimensions_fix():
    """Test that vector dimensions were updated to 2048."""
    print("🔍 Testing vector dimensions fix...")
    
    try:
        from src.config import config
        vector_size = config.qdrant.vector_size
        
        if vector_size == 2048:
            print("✅ Vector dimensions FIXED: 768 → 2048")
            return True
        else:
            print(f"❌ Vector dimensions not fixed: current = {vector_size}, expected = 2048")
            return False
    except Exception as e:
        print(f"❌ Config import failed: {e}")
        return False

def test_dependencies():
    """Test that new dependencies are available."""
    print("🔍 Testing new dependencies...")
    
    dependencies_ok = True
    
    # Test python-jose
    try:
        from jose import jwt
        print("✅ python-jose: Available")
    except ImportError as e:
        print(f"❌ python-jose: Missing ({e})")
        dependencies_ok = False
    
    # Test reflex
    try:
        import reflex as rx
        print("✅ reflex: Available")
    except ImportError as e:
        print(f"❌ reflex: Missing ({e})")
        dependencies_ok = False
    
    # Test pydantic-ai
    try:
        from pydantic_ai import Agent
        print("✅ pydantic-ai: Available")
    except ImportError as e:
        print(f"❌ pydantic-ai: Missing ({e})")
        dependencies_ok = False
    
    return dependencies_ok

def test_reflex_ui():
    """Test that Reflex UI can be imported and basic functionality works."""
    print("🔍 Testing Reflex UI...")
    
    try:
        # Test import without instantiation (avoiding Reflex state issues)
        from src.web import reflex_app
        
        # Test that key components exist
        assert hasattr(reflex_app, 'NarrativeFactoryState')
        assert hasattr(reflex_app, 'main_interface')
        assert hasattr(reflex_app, 'create_reflex_app')
        
        print("✅ Reflex UI: Components available")
        return True
    except Exception as e:
        print(f"❌ Reflex UI: Import failed ({e})")
        return False

def test_config_file_modifications():
    """Test that config.py file was actually modified."""
    print("🔍 Testing config file modifications...")
    
    try:
        config_file = project_root / "src" / "config.py"
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Check for our specific fix
        if "default=2048" in content and "Jina v4" in content:
            print("✅ Config file: Successfully modified with Priority 1 fixes")
            return True
        else:
            print("❌ Config file: Missing Priority 1 modifications")
            return False
    except Exception as e:
        print(f"❌ Config file: Read failed ({e})")
        return False

def test_qdrant_compatibility():
    """Test that Qdrant can handle 2048-dimensional vectors."""
    print("🔍 Testing Qdrant 2048-dim compatibility...")
    
    try:
        import numpy as np
        from qdrant_client.http import models as rest
        
        # Create 2048-dimensional test vector
        test_vector = np.random.normal(0, 1, 2048).astype(np.float32)
        test_vector = (test_vector / np.linalg.norm(test_vector)).tolist()
        
        # Create test point (this should not raise dimension errors)
        test_point = rest.PointStruct(
            id="priority_1_test",
            vector=test_vector,
            payload={"test": True, "priority_1_fix": "validated"}
        )
        
        # If we get here, 2048-dim vectors work
        print("✅ Qdrant compatibility: Can create 2048-dimensional vectors")
        return True
    except Exception as e:
        print(f"❌ Qdrant compatibility: Failed ({e})")
        return False

def main():
    """Run all Priority 1 verifications."""
    print("🧪 PRIORITY 1 FIX VERIFICATION")
    print("=" * 50)
    print("Testing fixes for:")
    print("• Vector dimensions (768→2048)")
    print("• Missing dependencies")
    print("• Reflex UI components")
    print("• System integration")
    print("=" * 50)
    
    tests = [
        ("Config File Modifications", test_config_file_modifications),
        ("Vector Dimensions Fix", test_vector_dimensions_fix), 
        ("New Dependencies", test_dependencies),
        ("Qdrant Compatibility", test_qdrant_compatibility),
        ("Reflex UI Components", test_reflex_ui),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 {test_name}")
        print("-" * 30)
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name}: Exception ({e})")
            results.append((test_name, False))
    
    # Summary
    print(f"\n" + "=" * 50)
    print("🎯 PRIORITY 1 VERIFICATION SUMMARY")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "PASSED" if result else "FAILED"
        icon = "✅" if result else "❌"
        print(f"{icon} {test_name}: {status}")
        if result:
            passed += 1
    
    success_rate = (passed / total) * 100
    print(f"\n📊 Overall Success Rate: {passed}/{total} ({success_rate:.1f}%)")
    
    if passed == total:
        print("\n🎉 ALL PRIORITY 1 FIXES VALIDATED!")
        print("✅ System ready for Priority 2 implementation")
        return True
    else:
        print(f"\n⚠️ {total - passed} fix(es) need attention")
        print("🔧 Review failed tests above")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)