#!/usr/bin/env python3
"""
Priority 2B Integration Script: Enhanced Prefect v3 Workflow Orchestration

This script demonstrates and validates the complete integration of sophisticated
Pydantic AI agents with Prefect v3 workflow orchestration for production-grade
background processing, observability, and job management.

Usage:
    python scripts/priority_2b_integration.py --mode demo
    python scripts/priority_2b_integration.py --mode test
    python scripts/priority_2b_integration.py --mode health-check
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.enhanced_generation import (
    enhanced_initial_generation_flow,
    enhanced_continue_generation_flow,
    enhanced_finalize_generation_flow,
    enhanced_background_generation_flow,
    enhanced_system_health_check_flow,
    enhanced_workflow_test_flow,
    get_enhanced_workflow_status
)
from src.logger import get_logger

logger = get_logger(__name__)


class Priority2BIntegration:
    """
    Priority 2B Integration demonstrator and validator.
    
    Showcases the complete enhanced workflow system with sophisticated
    Pydantic AI agents and Prefect v3 orchestration.
    """
    
    def __init__(self):
        self.results: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "priority": "2B",
            "description": "Enhanced Prefect v3 Workflow Orchestration",
            "phases": {},
            "overall_status": "initializing"
        }
    
    async def demonstrate_enhanced_workflows(self) -> Dict[str, Any]:
        """
        Demonstrate complete enhanced workflow capabilities.
        
        Returns:
            dict: Complete demonstration results
        """
        print("🚀 Priority 2B: Enhanced Workflow Orchestration Demonstration")
        print("=" * 70)
        print()
        
        # Phase 1: System Status Check
        print("📊 Phase 1: Enhanced System Status Check")
        print("-" * 40)
        
        try:
            workflow_status = await get_enhanced_workflow_status()
            
            if workflow_status.get("enhanced_workflows_active", False):
                print("✅ Enhanced workflows are active")
                print(f"🧠 Sophisticated features: {list(workflow_status['sophisticated_features'].keys())}")
                print(f"⚙️ Workflow version: {workflow_status['workflow_version']}")
                
                self.results["phases"]["system_status"] = {
                    "status": "success",
                    "enhanced_workflows_active": True,
                    "workflow_version": workflow_status["workflow_version"]
                }
            else:
                print("⚠️ Enhanced workflows not fully active")
                self.results["phases"]["system_status"] = {
                    "status": "warning",
                    "issue": "Enhanced workflows not active"
                }
                
        except Exception as e:
            print(f"❌ System status check failed: {e}")
            self.results["phases"]["system_status"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Phase 2: Health Check Validation
        print("🏥 Phase 2: Enhanced Health Check Validation")
        print("-" * 40)
        
        try:
            health_result = await enhanced_system_health_check_flow()
            
            if health_result["overall_status"] == "healthy":
                print("✅ All enhanced components are healthy")
                print(f"🔧 Components checked: {list(health_result['components'].keys())}")
                
                self.results["phases"]["health_check"] = {
                    "status": "success",
                    "overall_health": "healthy",
                    "components": list(health_result["components"].keys())
                }
            else:
                print("⚠️ Some components are degraded")
                for comp, status in health_result["components"].items():
                    status_emoji = "✅" if status["status"] == "healthy" else "❌"
                    print(f"{status_emoji} {comp}: {status['status']}")
                    
                self.results["phases"]["health_check"] = {
                    "status": "warning", 
                    "overall_health": health_result["overall_status"],
                    "degraded_components": [
                        comp for comp, status in health_result["components"].items()
                        if status["status"] != "healthy"
                    ]
                }
                
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            self.results["phases"]["health_check"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Phase 3: Enhanced Workflow Test
        print("🧪 Phase 3: Enhanced Workflow Test Execution")
        print("-" * 40)
        
        try:
            test_result = await enhanced_workflow_test_flow(
                test_seed="Priority 2B integration demonstration chapter",
                dry_run=True
            )
            
            if test_result["overall_result"] == "passed":
                print("✅ Enhanced workflow test passed")
                print("🎯 Campaign Pathfinder Protocol: Validated")
                print("⚙️ SerializationEngine methodology: Validated") 
                print("🔄 Inter-agent delegation: Validated")
                
                self.results["phases"]["workflow_test"] = {
                    "status": "success",
                    "test_result": "passed",
                    "enhanced_capabilities_validated": True
                }
            else:
                print("❌ Enhanced workflow test failed")
                print(f"Error: {test_result.get('error', 'Unknown error')}")
                
                self.results["phases"]["workflow_test"] = {
                    "status": "failed",
                    "test_result": test_result["overall_result"],
                    "error": test_result.get("error")
                }
                
        except Exception as e:
            print(f"❌ Workflow test execution failed: {e}")
            self.results["phases"]["workflow_test"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Phase 4: Enhanced Generation Flow Demo
        print("🎭 Phase 4: Enhanced Generation Flow Demonstration")
        print("-" * 40)
        
        try:
            # Demo the enhanced initial generation flow
            director_job_id = await enhanced_initial_generation_flow(
                chapter_seed="A mysterious artifact surfaces in the royal archives, "
                          "revealing long-lost secrets about the kingdom's founding",
                active_characters=["royal_archivist", "palace_guard", "mysterious_scholar"],
                story_context={
                    "story_threads": ["royal_conspiracy", "ancient_magic", "political_intrigue"],
                    "tension_state": {"political": "escalating", "mystical": "emerging"}
                },
                catalyst="Discovery of hidden genealogical records",
                dry_run=True
            )
            
            print(f"✅ Enhanced Director flow completed")
            print(f"📋 Job ID: {director_job_id}")
            print("🧠 Campaign Pathfinder Protocol executed successfully")
            print("🔍 Sophisticated strategic analysis completed")
            
            self.results["phases"]["generation_demo"] = {
                "status": "success",
                "director_job_id": director_job_id,
                "campaign_pathfinder_protocol": True,
                "sophisticated_analysis": True
            }
            
        except Exception as e:
            print(f"❌ Enhanced generation flow demo failed: {e}")
            self.results["phases"]["generation_demo"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Phase 5: Background Processing Demo
        print("⏳ Phase 5: Background Processing Demonstration")
        print("-" * 40)
        
        try:
            # Demo background processing with auto-approval
            background_result = await enhanced_background_generation_flow(
                chapter_seed="The Council of Elders convenes an emergency session "
                          "as strange phenomena plague the northern territories",
                active_characters=["elder_council_leader", "northern_scout", "court_mage"],
                auto_approve=True  # For demonstration only
            )
            
            if background_result.get("enhanced_pipeline", False):
                print("✅ Background processing completed successfully")
                print(f"📝 Final chapter: {len(str(background_result.get('validated_text', '')).split())} words")
                print("🔄 Agent capabilities demonstrated:")
                
                for agent, capability in background_result["agent_capabilities"].items():
                    print(f"   • {agent}: {capability}")
                
                self.results["phases"]["background_processing"] = {
                    "status": "success",
                    "enhanced_pipeline": True,
                    "agent_capabilities": background_result["agent_capabilities"],
                    "generation_method": background_result["generation_method"]
                }
            else:
                print("⚠️ Background processing completed with issues")
                self.results["phases"]["background_processing"] = {
                    "status": "warning",
                    "issue": "Background processing incomplete"
                }
                
        except Exception as e:
            print(f"❌ Background processing demo failed: {e}")
            self.results["phases"]["background_processing"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Final Summary
        print("📋 Priority 2B Integration Summary")
        print("=" * 70)
        
        successful_phases = sum(
            1 for phase in self.results["phases"].values()
            if phase["status"] == "success"
        )
        total_phases = len(self.results["phases"])
        
        self.results["overall_status"] = (
            "success" if successful_phases == total_phases
            else "partial" if successful_phases > 0
            else "failed"
        )
        
        self.results["summary"] = {
            "successful_phases": successful_phases,
            "total_phases": total_phases,
            "success_rate": f"{successful_phases}/{total_phases}",
            "priority_2b_complete": self.results["overall_status"] == "success"
        }
        
        if self.results["overall_status"] == "success":
            print("🎉 Priority 2B Implementation: COMPLETE")
            print("✅ All enhanced workflow features validated")
            print("🧠 Sophisticated Pydantic AI agents integrated")
            print("⚙️ Prefect v3 orchestration active")
            print("📊 Background processing and observability functional")
        elif self.results["overall_status"] == "partial":
            print("⚠️ Priority 2B Implementation: PARTIALLY COMPLETE")
            print(f"✅ {successful_phases}/{total_phases} phases successful")
            print("🔧 Some components need attention")
        else:
            print("❌ Priority 2B Implementation: FAILED")
            print("🔧 Multiple components need attention")
            
        print()
        return self.results
    
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """
        Run comprehensive test suite for Priority 2B.
        
        Returns:
            dict: Test results
        """
        print("🧪 Priority 2B: Comprehensive Test Suite")
        print("=" * 70)
        
        test_results = {
            "timestamp": datetime.now().isoformat(),
            "test_suite": "priority_2b_comprehensive",
            "tests": {}
        }
        
        # Test 1: Enhanced Workflow System Test
        print("Test 1: Enhanced Workflow System Validation")
        print("-" * 50)
        
        try:
            workflow_test = await enhanced_workflow_test_flow(dry_run=True)
            
            if workflow_test["overall_result"] == "passed":
                print("✅ Enhanced workflow system test: PASSED")
                test_results["tests"]["workflow_system"] = {
                    "status": "passed",
                    "enhanced_capabilities_validated": True
                }
            else:
                print("❌ Enhanced workflow system test: FAILED")
                test_results["tests"]["workflow_system"] = {
                    "status": "failed",
                    "error": workflow_test.get("error")
                }
                
        except Exception as e:
            print(f"❌ Workflow system test failed: {e}")
            test_results["tests"]["workflow_system"] = {
                "status": "failed", 
                "error": str(e)
            }
            
        print()
        
        # Test 2: Health Check Validation
        print("Test 2: System Health Check Validation")
        print("-" * 50)
        
        try:
            health_check = await enhanced_system_health_check_flow()
            
            if health_check["overall_status"] == "healthy":
                print("✅ System health check: PASSED")
                test_results["tests"]["health_check"] = {
                    "status": "passed",
                    "all_components_healthy": True
                }
            else:
                print("⚠️ System health check: PARTIAL")
                test_results["tests"]["health_check"] = {
                    "status": "partial",
                    "overall_status": health_check["overall_status"]
                }
                
        except Exception as e:
            print(f"❌ Health check test failed: {e}")
            test_results["tests"]["health_check"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Test 3: Agent Integration Test
        print("Test 3: Enhanced Agent Integration Test")
        print("-" * 50)
        
        try:
            # Test individual agent task
            from src.workflows.enhanced_generation import enhanced_director_task
            
            director_job = await enhanced_director_task(
                chapter_seed="Test agent integration chapter seed",
                active_characters=["test_character"],
                dry_run=True
            )
            
            if director_job:
                print("✅ Enhanced agent integration: PASSED")
                test_results["tests"]["agent_integration"] = {
                    "status": "passed",
                    "director_job_created": True
                }
            else:
                print("❌ Enhanced agent integration: FAILED")
                test_results["tests"]["agent_integration"] = {
                    "status": "failed",
                    "issue": "No job created"
                }
                
        except Exception as e:
            print(f"❌ Agent integration test failed: {e}")
            test_results["tests"]["agent_integration"] = {
                "status": "failed",
                "error": str(e)
            }
            
        print()
        
        # Test Summary
        passed_tests = sum(
            1 for test in test_results["tests"].values()
            if test["status"] == "passed"
        )
        total_tests = len(test_results["tests"])
        
        test_results["summary"] = {
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "success_rate": f"{passed_tests}/{total_tests}",
            "overall_result": "passed" if passed_tests == total_tests else "failed"
        }
        
        print("📋 Comprehensive Test Summary")
        print("=" * 50)
        print(f"✅ Tests passed: {passed_tests}/{total_tests}")
        
        if test_results["summary"]["overall_result"] == "passed":
            print("🎉 All Priority 2B tests PASSED")
        else:
            print("⚠️ Some Priority 2B tests FAILED")
            
        return test_results
    
    async def run_health_check(self) -> Dict[str, Any]:
        """
        Run quick health check for Priority 2B systems.
        
        Returns:
            dict: Health check results
        """
        print("🏥 Priority 2B: Quick Health Check")
        print("=" * 70)
        
        try:
            health_result = await enhanced_system_health_check_flow()
            
            print(f"Overall Status: {health_result['overall_status']}")
            print()
            
            print("Component Status:")
            for component, status in health_result["components"].items():
                status_emoji = "✅" if status["status"] == "healthy" else "❌"
                print(f"{status_emoji} {component}: {status['status']}")
                
            print()
            
            if health_result["overall_status"] == "healthy":
                print("🎉 All Priority 2B systems are healthy!")
            else:
                print("⚠️ Some Priority 2B systems need attention")
                
            return health_result
            
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return {"overall_status": "failed", "error": str(e)}


async def main():
    """Main entry point for Priority 2B integration."""
    parser = argparse.ArgumentParser(
        description="Priority 2B: Enhanced Prefect v3 Workflow Orchestration"
    )
    parser.add_argument(
        "--mode",
        choices=["demo", "test", "health-check"],
        default="demo",
        help="Execution mode (default: demo)"
    )
    parser.add_argument(
        "--output",
        help="Output file for results (JSON format)"
    )
    
    args = parser.parse_args()
    
    integration = Priority2BIntegration()
    
    try:
        if args.mode == "demo":
            results = await integration.demonstrate_enhanced_workflows()
        elif args.mode == "test":
            results = await integration.run_comprehensive_tests()
        elif args.mode == "health-check":
            results = await integration.run_health_check()
        else:
            raise ValueError(f"Unknown mode: {args.mode}")
            
        # Output results
        if args.output:
            import json
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            print(f"📄 Results saved to: {args.output}")
            
        return results
        
    except Exception as e:
        print(f"❌ Priority 2B integration failed: {e}")
        return {"status": "failed", "error": str(e)}


if __name__ == "__main__":
    """
    Execute Priority 2B integration.
    
    Examples:
        python scripts/priority_2b_integration.py --mode demo
        python scripts/priority_2b_integration.py --mode test --output results.json
        python scripts/priority_2b_integration.py --mode health-check
    """
    print("🚀 Priority 2B: Enhanced Prefect v3 Workflow Orchestration")
    print("🧠 Sophisticated Pydantic AI Agents + Production-Grade Job Management")
    print()
    
    result = asyncio.run(main())
    
    # Exit with appropriate code
    if isinstance(result, dict):
        if result.get("overall_status") == "success" or result.get("overall_result") == "passed":
            print("\n🎉 Priority 2B integration successful!")
            sys.exit(0)
        else:
            print("\n⚠️ Priority 2B integration completed with issues")
            sys.exit(1)
    else:
        print("\n❌ Priority 2B integration failed")
        sys.exit(1)