#!/usr/bin/env python3
"""
Priority 1 Execution Script
Executes all Priority 1 fixes in the correct sequence to resolve critical system issues

CRITICAL ISSUES ADDRESSED:
1. Vector dimension mismatch (768→2048) causing HTTP 400 errors
2. UI tab navigation failures from selector inconsistencies  
3. Testing infrastructure gaps (missing dependencies)

EXECUTION SEQUENCE:
1. Dependency installation
2. Configuration fixes
3. Qdrant migration
4. UI system deployment
5. Comprehensive validation
6. System status verification

This script transforms the system from 🔴 NON-FUNCTIONAL to 🟢 FUNCTIONAL.
"""

import asyncio
import subprocess
import sys
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


class Priority1ExecutionManager:
    """Manages execution of all Priority 1 fixes in correct sequence."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.execution_log = []
        self.results = {
            "execution_started": datetime.now().isoformat(),
            "priority_1_sequence": [],
            "overall_success": False
        }
    
    def log_step(self, step_name: str, status: str, details: Any = None):
        """Log execution step."""
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "step": step_name,
            "status": status,
            "details": details
        }
        self.execution_log.append(log_entry)
        
        status_icon = "✅" if status == "success" else "❌" if status == "failed" else "🔄"
        print(f"{status_icon} [{timestamp.split('T')[1][:8]}] {step_name}: {status}")
        
        if details and status == "failed":
            print(f"   ERROR: {details}")
    
    async def install_dependencies(self) -> bool:
        """Install new dependencies added to pyproject.toml."""
        self.log_step("Installing dependencies", "in_progress")
        
        try:
            # Run uv sync to install new dependencies
            result = subprocess.run(
                ["uv", "sync"],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                self.log_step("Installing dependencies", "success", "All dependencies installed")
                return True
            else:
                self.log_step("Installing dependencies", "failed", result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            self.log_step("Installing dependencies", "failed", "Installation timed out")
            return False
        except Exception as e:
            self.log_step("Installing dependencies", "failed", str(e))
            return False
    
    def verify_config_changes(self) -> bool:
        """Verify that configuration changes were applied correctly."""
        self.log_step("Verifying config changes", "in_progress")
        
        try:
            # Check that vector_size was updated to 2048
            config_file = self.project_root / "src" / "config.py"
            
            if not config_file.exists():
                self.log_step("Verifying config changes", "failed", "config.py not found")
                return False
            
            with open(config_file, 'r') as f:
                config_content = f.read()
            
            # Check for the fix
            if "default=2048" in config_content and "Jina v4" in config_content:
                self.log_step("Verifying config changes", "success", "Vector size updated to 2048")
                return True
            else:
                self.log_step("Verifying config changes", "failed", "Config not properly updated")
                return False
                
        except Exception as e:
            self.log_step("Verifying config changes", "failed", str(e))
            return False
    
    async def execute_qdrant_migration(self) -> bool:
        """Execute the Qdrant migration script."""
        self.log_step("Executing Qdrant migration", "in_progress")
        
        try:
            # Run the migration script
            migration_script = self.project_root / "scripts" / "priority_1_qdrant_migration.py"
            
            if not migration_script.exists():
                self.log_step("Executing Qdrant migration", "failed", "Migration script not found")
                return False
            
            # Execute migration
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(migration_script),
                cwd=self.project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=600)  # 10 minute timeout
            
            if process.returncode == 0:
                self.log_step("Executing Qdrant migration", "success", "Migration completed")
                return True
            else:
                self.log_step("Executing Qdrant migration", "failed", stderr.decode())
                return False
                
        except asyncio.TimeoutError:
            self.log_step("Executing Qdrant migration", "failed", "Migration timed out")
            return False
        except Exception as e:
            self.log_step("Executing Qdrant migration", "failed", str(e))
            return False
    
    def deploy_reflex_ui(self) -> bool:
        """Deploy the new Reflex UI system."""
        self.log_step("Deploying Reflex UI", "in_progress")
        
        try:
            # Verify Reflex app file exists
            reflex_app = self.project_root / "src" / "web" / "reflex_app.py"
            
            if not reflex_app.exists():
                self.log_step("Deploying Reflex UI", "failed", "reflex_app.py not found")
                return False
            
            # Test that the app can be imported (basic validation)
            try:
                sys.path.append(str(self.project_root))
                from src.web.reflex_app import NarrativeFactoryState, main_interface
                
                # Test basic functionality
                state = NarrativeFactoryState()
                state.switch_tab("upload")
                
                if state.current_tab == "upload":
                    self.log_step("Deploying Reflex UI", "success", "UI system functional")
                    return True
                else:
                    self.log_step("Deploying Reflex UI", "failed", "Tab navigation not working")
                    return False
                    
            except ImportError as e:
                self.log_step("Deploying Reflex UI", "failed", f"Import error: {e}")
                return False
                
        except Exception as e:
            self.log_step("Deploying Reflex UI", "failed", str(e))
            return False
    
    async def run_validation_suite(self) -> bool:
        """Run comprehensive validation of all fixes."""
        self.log_step("Running validation suite", "in_progress")
        
        try:
            # Run validation script
            validation_script = self.project_root / "scripts" / "priority_1_validation_suite.py"
            
            if not validation_script.exists():
                self.log_step("Running validation suite", "failed", "Validation script not found")
                return False
            
            # Execute validation
            process = await asyncio.create_subprocess_exec(
                sys.executable, str(validation_script), "--save-report",
                cwd=self.project_root,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)  # 5 minute timeout
            
            if process.returncode == 0:
                self.log_step("Running validation suite", "success", "All validations passed")
                return True
            else:
                self.log_step("Running validation suite", "failed", "Some validations failed")
                print(f"Validation output:\n{stdout.decode()}")
                if stderr:
                    print(f"Validation errors:\n{stderr.decode()}")
                return False
                
        except asyncio.TimeoutError:
            self.log_step("Running validation suite", "failed", "Validation timed out")
            return False
        except Exception as e:
            self.log_step("Running validation suite", "failed", str(e))
            return False
    
    def verify_system_status(self) -> Dict[str, Any]:
        """Verify overall system status after fixes."""
        self.log_step("Verifying system status", "in_progress")
        
        status_report = {
            "config_fixed": False,
            "dependencies_available": False,
            "ui_functional": False,
            "migration_completed": False,
            "priority_1_resolved": False
        }
        
        try:
            # Check config
            try:
                sys.path.append(str(self.project_root))
                from src.config import settings
                vector_size = getattr(settings.qdrant, 'vector_size', 768)
                status_report["config_fixed"] = (vector_size == 2048)
            except:
                status_report["config_fixed"] = False
            
            # Check dependencies
            try:
                import reflex
                from pydantic_ai import Agent
                from jose import jwt
                status_report["dependencies_available"] = True
            except ImportError:
                status_report["dependencies_available"] = False
            
            # Check UI
            try:
                from src.web.reflex_app import NarrativeFactoryState
                state = NarrativeFactoryState()
                state.switch_tab("chat")
                status_report["ui_functional"] = (state.current_tab == "chat")
            except:
                status_report["ui_functional"] = False
            
            # Check migration (look for backup directory)
            migration_backups = list(self.project_root.glob("migration_backups/backup_*"))
            status_report["migration_completed"] = len(migration_backups) > 0
            
            # Overall assessment
            status_report["priority_1_resolved"] = all([
                status_report["config_fixed"],
                status_report["dependencies_available"],
                status_report["ui_functional"]
            ])
            
            if status_report["priority_1_resolved"]:
                self.log_step("Verifying system status", "success", "All Priority 1 issues resolved")
            else:
                failed_components = [
                    key for key, value in status_report.items() 
                    if not value and key != "priority_1_resolved"
                ]
                self.log_step("Verifying system status", "failed", f"Issues: {failed_components}")
            
        except Exception as e:
            self.log_step("Verifying system status", "failed", str(e))
            status_report["priority_1_resolved"] = False
        
        return status_report
    
    async def execute_complete_priority_1_sequence(self) -> Dict[str, Any]:
        """Execute complete Priority 1 fix sequence."""
        print("🚀 PRIORITY 1 EXECUTION SEQUENCE - NARRATIVE FACTORY REPAIR")
        print("=" * 70)
        print("TRANSFORMING: 🔴 NON-FUNCTIONAL → 🟢 FUNCTIONAL")
        print("=" * 70)
        print("Issues to resolve:")
        print("• HTTP 400 errors from vector dimension mismatch (768→2048)")
        print("• UI tab navigation failures (main.js:475-479 selector issues)")
        print("• Missing testing dependencies (python-jose)")
        print("=" * 70)
        
        execution_sequence = [
            ("Install Dependencies", self.install_dependencies),
            ("Verify Config Changes", self.verify_config_changes),
            ("Execute Qdrant Migration", self.execute_qdrant_migration),
            ("Deploy Reflex UI", self.deploy_reflex_ui),
            ("Run Validation Suite", self.run_validation_suite)
        ]
        
        all_successful = True
        
        for step_name, step_function in execution_sequence:
            print(f"\n📋 Step: {step_name}")
            print("-" * 40)
            
            try:
                if asyncio.iscoroutinefunction(step_function):
                    success = await step_function()
                else:
                    success = step_function()
                
                self.results["priority_1_sequence"].append({
                    "step": step_name,
                    "status": "success" if success else "failed",
                    "timestamp": datetime.now().isoformat()
                })
                
                if not success:
                    all_successful = False
                    print(f"❌ Step failed: {step_name}")
                    break
                    
            except Exception as e:
                self.log_step(step_name, "failed", str(e))
                self.results["priority_1_sequence"].append({
                    "step": step_name,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                all_successful = False
                break
        
        # Final system verification
        print(f"\n🔍 Final System Status Verification")
        print("-" * 40)
        system_status = self.verify_system_status()
        
        self.results["execution_completed"] = datetime.now().isoformat()
        self.results["overall_success"] = all_successful and system_status["priority_1_resolved"]
        self.results["system_status"] = system_status
        self.results["execution_log"] = self.execution_log
        
        # Final report
        print(f"\n" + "=" * 70)
        print("🎯 PRIORITY 1 EXECUTION SUMMARY")
        print("=" * 70)
        
        if self.results["overall_success"]:
            print("🎉 SUCCESS: Priority 1 fixes executed successfully!")
            print("✅ Vector database: 768→2048 dimensions (HTTP 400 errors resolved)")
            print("✅ UI Navigation: Server-side state (selector issues eliminated)")  
            print("✅ Dependencies: All frameworks available (testing functional)")
            print("✅ Integration: Complete system working together")
            print(f"\n🚀 SYSTEM STATUS: 🟢 FUNCTIONAL")
            print("📈 Ready for Priority 2 implementation (enhanced agents)")
        else:
            print("❌ EXECUTION ENCOUNTERED ISSUES")
            print("🔧 Some Priority 1 fixes need manual intervention")
            print("📋 Check execution log for details")
            print(f"\n⚠️  SYSTEM STATUS: 🔴 PARTIALLY FUNCTIONAL")
        
        return self.results
    
    def save_execution_report(self):
        """Save detailed execution report."""
        report_dir = self.project_root / "execution_reports"
        report_dir.mkdir(exist_ok=True)
        
        report_file = report_dir / f"priority_1_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n📋 Detailed execution report saved to: {report_file}")
        return report_file


async def main():
    """Main execution entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Priority 1 Fix Execution Manager")
    parser.add_argument("--dry-run", action="store_true", help="Show execution plan without running")
    parser.add_argument("--skip-migration", action="store_true", help="Skip Qdrant migration (for testing)")
    parser.add_argument("--save-report", action="store_true", help="Save detailed execution report")
    
    args = parser.parse_args()
    
    executor = Priority1ExecutionManager()
    
    if args.dry_run:
        print("🔍 DRY RUN - Execution plan:")
        print("1. Install dependencies (uv sync)")
        print("2. Verify configuration changes (vector_size: 2048)")
        print("3. Execute Qdrant migration (768→2048 dimensions)")
        print("4. Deploy Reflex UI (eliminate selector issues)")
        print("5. Run validation suite (comprehensive testing)")
        print("6. Verify system status (overall health check)")
        return True
    
    # Execute complete sequence
    results = await executor.execute_complete_priority_1_sequence()
    
    if args.save_report:
        executor.save_execution_report()
    
    return results["overall_success"]


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)