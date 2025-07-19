#!/usr/bin/env python3
"""
API Migration Script for Narrative Factory
Migrates deprecated Pydantic V1 and datetime APIs to modern equivalents.

Based on comprehensive Context7 research and following Pydantic V2 best practices.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


class APIMigrator:
    """Handles migration of deprecated API patterns to modern equivalents."""
    
    def __init__(self, project_root: str = "src"):
        self.project_root = Path(project_root)
        self.migration_log: List[str] = []
        self.files_modified: List[Path] = []
        
    def log_change(self, file_path: Path, change_description: str):
        """Log a migration change."""
        self.migration_log.append(f"✅ {file_path}: {change_description}")
        
    def migrate_pydantic_validators(self, content: str) -> Tuple[str, List[str]]:
        """
        Migrate Pydantic V1 validators to V2 field_validator.
        
        Based on Context7 research:
        - @validator -> @field_validator
        - Add @classmethod decorator where needed
        - Update import statements
        """
        changes = []
        
        # Pattern 1: Simple @validator decoration
        validator_pattern = r'@validator\((.*?)\)'
        if re.search(validator_pattern, content):
            content = re.sub(validator_pattern, r'@field_validator(\1)', content)
            changes.append("@validator -> @field_validator")
        
        # Pattern 2: Update import to include field_validator
        import_pattern = r'from pydantic import (.*?)validator(.*?)\n'
        if re.search(import_pattern, content):
            content = re.sub(
                import_pattern,
                r'from pydantic import \1field_validator\2\n',
                content
            )
            changes.append("Updated pydantic imports to include field_validator")
        
        # Pattern 3: Add @classmethod decorator for field_validator methods
        # Look for @field_validator followed by function definition
        field_validator_pattern = r'(@field_validator\([^)]+\))\s*\n\s*def\s+(\w+)\s*\(cls,'
        matches = re.finditer(field_validator_pattern, content)
        
        for match in matches:
            # Insert @classmethod before the function definition
            decorator_and_func = match.group(0)
            if '@classmethod' not in decorator_and_func:
                # Find the position after the @field_validator decorator
                decorator_end = match.start() + len(match.group(1))
                # Insert @classmethod on the next line
                content = (content[:decorator_end] + 
                          '\n    @classmethod' + 
                          content[decorator_end:])
                changes.append("Added @classmethod decorator to field_validator method")
        
        return content, changes
    
    def migrate_datetime_api(self, content: str) -> Tuple[str, List[str]]:
        """
        Migrate datetime.utcnow() to datetime.now(timezone.utc).
        
        Based on Context7 research:
        - datetime.utcnow() -> datetime.now(timezone.utc)
        - Add timezone import if needed
        """
        changes = []
        
        # Pattern 1: Replace datetime.utcnow() calls
        utcnow_pattern = r'datetime\.utcnow\(\)'
        if re.search(utcnow_pattern, content):
            content = re.sub(utcnow_pattern, 'datetime.now(timezone.utc)', content)
            changes.append("datetime.utcnow() -> datetime.now(timezone.utc)")
        
        # Pattern 2: Add timezone import if needed
        if 'datetime.now(timezone.utc)' in content:
            # Check if timezone is already imported
            if 'from datetime import' in content and 'timezone' not in content:
                # Add timezone to existing datetime import
                datetime_import_pattern = r'from datetime import ([^,\n]+(?:,[^,\n]+)*)'
                match = re.search(datetime_import_pattern, content)
                if match:
                    existing_imports = match.group(1)
                    if 'timezone' not in existing_imports:
                        new_imports = f"{existing_imports}, timezone"
                        content = re.sub(
                            datetime_import_pattern,
                            f'from datetime import {new_imports}',
                            content
                        )
                        changes.append("Added timezone to datetime imports")
            elif 'import datetime' in content and 'timezone' not in content:
                # If using 'import datetime', we need to ensure timezone is available
                # The pattern datetime.now(timezone.utc) works with 'import datetime'
                # as timezone is a member of the datetime module
                pass
        
        return content, changes
    
    def migrate_pydantic_base_model_methods(self, content: str) -> Tuple[str, List[str]]:
        """
        Migrate deprecated BaseModel methods to V2 equivalents.
        
        Based on Context7 research:
        - .dict() -> .model_dump()
        - .json() -> .model_dump_json()
        - .copy() -> .model_copy()
        - parse_obj() -> model_validate()
        """
        changes = []
        
        # Pattern 1: .dict() -> .model_dump()
        dict_pattern = r'\.dict\(\)'
        if re.search(dict_pattern, content):
            content = re.sub(dict_pattern, '.model_dump()', content)
            changes.append(".dict() -> .model_dump()")
        
        # Pattern 2: .json() -> .model_dump_json()
        json_pattern = r'\.json\(\)'
        if re.search(json_pattern, content):
            content = re.sub(json_pattern, '.model_dump_json()', content)
            changes.append(".json() -> .model_dump_json()")
        
        # Pattern 3: .copy() -> .model_copy()
        copy_pattern = r'\.copy\(\)'
        if re.search(copy_pattern, content):
            content = re.sub(copy_pattern, '.model_copy()', content)
            changes.append(".copy() -> .model_copy()")
        
        # Pattern 4: parse_obj() -> model_validate()
        parse_obj_pattern = r'\.parse_obj\('
        if re.search(parse_obj_pattern, content):
            content = re.sub(parse_obj_pattern, '.model_validate(', content)
            changes.append("parse_obj() -> model_validate()")
        
        return content, changes
    
    def migrate_file(self, file_path: Path) -> bool:
        """
        Migrate a single Python file.
        
        Returns True if the file was modified, False otherwise.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            content = original_content
            all_changes = []
            
            # Apply all migrations
            content, pydantic_changes = self.migrate_pydantic_validators(content)
            all_changes.extend(pydantic_changes)
            
            content, datetime_changes = self.migrate_datetime_api(content)
            all_changes.extend(datetime_changes)
            
            content, basemodel_changes = self.migrate_pydantic_base_model_methods(content)
            all_changes.extend(basemodel_changes)
            
            # Write back if changes were made
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                for change in all_changes:
                    self.log_change(file_path, change)
                
                self.files_modified.append(file_path)
                return True
            else:
                return False
                
        except Exception as e:
            self.migration_log.append(f"❌ Error migrating {file_path}: {str(e)}")
            return False
    
    def migrate_project(self) -> Dict[str, any]:
        """
        Migrate the entire project.
        
        Returns a summary of the migration results.
        """
        print("🔄 Starting API Migration...")
        
        # Find all Python files
        python_files = list(self.project_root.rglob("*.py"))
        
        # Filter out __pycache__ and other non-source files
        python_files = [
            f for f in python_files 
            if "__pycache__" not in str(f) and ".pyc" not in str(f)
        ]
        
        print(f"📁 Found {len(python_files)} Python files to scan")
        
        # Migrate each file
        files_modified = 0
        for file_path in python_files:
            if self.migrate_file(file_path):
                files_modified += 1
        
        # Generate summary
        summary = {
            "files_scanned": len(python_files),
            "files_modified": files_modified,
            "total_changes": len(self.migration_log),
            "modified_files": [str(f) for f in self.files_modified],
            "changes": self.migration_log
        }
        
        print(f"\n📊 Migration Summary:")
        print(f"  • Files scanned: {summary['files_scanned']}")
        print(f"  • Files modified: {summary['files_modified']}")
        print(f"  • Total changes: {summary['total_changes']}")
        
        if summary['total_changes'] > 0:
            print(f"\n📝 Changes made:")
            for change in self.migration_log:
                print(f"  {change}")
        
        return summary
    
    def validate_migrations(self) -> bool:
        """
        Validate that migrations were successful by checking for common issues.
        
        Returns True if validation passes, False otherwise.
        """
        print("\n🔍 Validating migrations...")
        
        issues = []
        
        # Check for remaining deprecated patterns
        for file_path in self.files_modified:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check for remaining @validator usage
                if '@validator' in content and '@field_validator' not in content:
                    issues.append(f"{file_path}: Still contains @validator without @field_validator")
                
                # Check for remaining datetime.utcnow() usage
                if 'datetime.utcnow()' in content:
                    issues.append(f"{file_path}: Still contains datetime.utcnow()")
                
                # Check for common V1 patterns
                v1_patterns = ['.dict()', '.json()', '.copy()', 'parse_obj(']
                for pattern in v1_patterns:
                    if pattern in content:
                        issues.append(f"{file_path}: Still contains deprecated pattern: {pattern}")
                
            except Exception as e:
                issues.append(f"{file_path}: Error during validation: {str(e)}")
        
        if issues:
            print("❌ Validation issues found:")
            for issue in issues:
                print(f"  • {issue}")
            return False
        else:
            print("✅ All migrations validated successfully!")
            return True


def main():
    """Main migration function."""
    migrator = APIMigrator()
    
    # Run migrations
    summary = migrator.migrate_project()
    
    # Validate results
    validation_passed = migrator.validate_migrations()
    
    # Exit with appropriate code
    if validation_passed:
        print("\n🎉 Migration completed successfully!")
        return 0
    else:
        print("\n⚠️  Migration completed with issues. Please review the output.")
        return 1


if __name__ == "__main__":
    exit(main())