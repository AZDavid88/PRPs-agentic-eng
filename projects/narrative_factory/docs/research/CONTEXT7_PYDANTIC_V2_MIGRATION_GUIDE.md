# Context7 Research: Pydantic V1→V2 Migration for Narrative Factory

**Research Date**: 2025-07-20  
**Context**: CodeFarm session validation identified Pydantic V1 validators causing deprecation warnings  
**Goal**: Document migration patterns specific to Narrative Factory codebase  
**Source**: Context7 `/context7/pydantic_dev` library with 2139 code snippets

---

## 🎯 **CRITICAL FINDINGS FOR NARRATIVE FACTORY**

### **Our Specific Issues Identified**:
1. **`@validator` decorators** in `src/models/material_models.py` (lines 256, 273, 291, 300)
2. **`@validator` decorators** in `src/web/websocket_manager.py` (lines 32, 44)
3. **Pydantic V1 style validation** causing deprecation warnings
4. **Legacy class-based config** warnings

### **Impact on Our Codebase**:
- Deprecation warnings cluttering test output
- Future compatibility risk with Pydantic V2+ 
- Potential performance degradation with V1 compatibility mode

---

## 🔧 **MIGRATION PATTERNS FOR OUR USE CASES**

### **1. Validator Decorator Migration**

**BEFORE (V1 - Our Current Code)**:
```python
from pydantic import BaseModel, validator

class MaterialClassification(BaseModel):
    primary_category: str
    
    @validator('primary_category')
    @classmethod
    def validate_primary_category(cls, v):
        return v.strip().lower()
```

**AFTER (V2 - Target Pattern)**:
```python
from pydantic import BaseModel, field_validator

class MaterialClassification(BaseModel):
    primary_category: str
    
    @field_validator('primary_category')
    @classmethod
    def validate_primary_category(cls, v: str) -> str:
        return v.strip().lower()
```

### **2. ValidationInfo Access Pattern**

**For Complex Validators Needing Context**:
```python
from pydantic import BaseModel, ValidationInfo, field_validator

class WebSocketMessage(BaseModel):
    type: str
    data: dict
    
    @field_validator('data')
    @classmethod
    def validate_data(cls, v: dict, info: ValidationInfo) -> dict:
        # Access field name: info.field_name
        # Access model config: info.config
        # Access other fields: cls.model_fields[info.field_name]
        return v
```

### **3. Model Configuration Migration**

**BEFORE (V1 Class-based Config)**:
```python
class Model(BaseModel):
    class Config:
        extra = "forbid"
        validate_assignment = True
```

**AFTER (V2 ConfigDict)**:
```python
from pydantic import BaseModel, ConfigDict

class Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True
    )
```

---

## 📁 **SPECIFIC FILES TO MIGRATE**

### **Priority 1: Active Warnings**

**`src/models/material_models.py`**:
```python
# Lines 256, 273, 291, 300 - Replace @validator with @field_validator
@field_validator('primary_category')
@classmethod  
def validate_primary_category(cls, v: str) -> str:
    # Migration logic here
    
@field_validator('secondary_categories')
@classmethod
def validate_secondary_categories(cls, v: list) -> list:
    # Migration logic here
    
@field_validator('category_confidence') 
@classmethod
def validate_category_confidence(cls, v: float) -> float:
    # Migration logic here
    
@field_validator('content_hash')
@classmethod
def validate_content_hash(cls, v: str) -> str:
    # Migration logic here
```

**`src/web/websocket_manager.py`**:
```python
# Lines 32, 44 - Replace @validator with @field_validator
@field_validator('type')
@classmethod
def validate_type(cls, v: str) -> str:
    # Migration logic here
    
@field_validator('data')
@classmethod
def validate_data(cls, v: dict) -> dict:
    # Migration logic here
```

### **Priority 2: Model Method Updates**

**Common Method Renames Needed**:
```python
# V1 → V2 Method Mapping
model.dict() → model.model_dump()
model.json() → model.model_dump_json()
Model.parse_obj() → Model.model_validate()
Model.schema() → Model.model_json_schema()
```

---

## 🚨 **CRITICAL COMPATIBILITY CONSIDERATIONS**

### **Type Annotation Requirements**:
Pydantic V2 requires more explicit type annotations:
```python
# V1 (loose typing)
@validator('field')
def validate_field(cls, v):
    return v

# V2 (strict typing required)
@field_validator('field')  
def validate_field(cls, v: str) -> str:
    return v
```

### **Error Handling Changes**:
```python
# V2 doesn't auto-convert TypeError to ValidationError
@field_validator('field')
def validate_field(cls, v: str) -> str:
    try:
        return process_value(v)
    except TypeError as e:
        # Must explicitly handle - won't auto-convert
        raise ValueError(f"Invalid value: {e}")
```

---

## 🔬 **TESTING PATTERNS FOR MIGRATION**

### **Validation Testing Strategy**:
```python
import pytest
from pydantic import ValidationError

def test_field_validator_migration():
    """Test that migrated validators work correctly"""
    
    # Test valid input
    valid_model = MaterialClassification(primary_category="  FANTASY  ")
    assert valid_model.primary_category == "fantasy"
    
    # Test validation error
    with pytest.raises(ValidationError):
        MaterialClassification(primary_category="")
```

### **Backwards Compatibility Testing**:
```python
def test_model_dump_compatibility():
    """Ensure model serialization works post-migration"""
    model = MaterialClassification(primary_category="fantasy")
    
    # V2 method
    data = model.model_dump()
    assert isinstance(data, dict)
    
    # JSON serialization 
    json_data = model.model_dump_json()
    assert isinstance(json_data, str)
```

---

## 📋 **MIGRATION CHECKLIST FOR NARRATIVE FACTORY**

### **Phase 1: Critical Warnings (Immediate)**
- [ ] Replace `@validator` with `@field_validator` in `material_models.py`
- [ ] Replace `@validator` with `@field_validator` in `websocket_manager.py`
- [ ] Add proper type annotations to all validator functions
- [ ] Update class-based Config to ConfigDict where present

### **Phase 2: Method Updates (Next)**
- [ ] Search and replace `.dict()` → `.model_dump()`
- [ ] Search and replace `.json()` → `.model_dump_json()`
- [ ] Search and replace `.parse_obj()` → `.model_validate()`
- [ ] Update any schema generation calls

### **Phase 3: Testing & Validation (Final)**
- [ ] Run full test suite to catch migration issues
- [ ] Verify WebSocket message validation still works
- [ ] Confirm material classification pipeline functional
- [ ] Performance test to ensure no degradation

---

## 🛠 **IMPLEMENTATION COMMANDS**

### **Quick Fix for Immediate Warnings**:
```bash
# Navigate to project
cd /workspaces/PRPs-agentic-eng/projects/narrative_factory

# Find all @validator usage
grep -r "@validator" src/ --include="*.py"

# Apply the migration (manual review recommended)
# Replace in material_models.py and websocket_manager.py
```

### **Test Migration Success**:
```bash
# Run tests to verify no new failures
uv run pytest tests/ -v

# Check for remaining warnings  
uv run pytest tests/ -v 2>&1 | grep -i "pydantic\|deprecat"
```

---

## 📚 **ADDITIONAL CONTEXT7 RESOURCES**

### **Advanced Migration Patterns**:
- **Union Type Validation**: Updated syntax for `str | int` vs `Union[str, int]`
- **Custom Validators**: Use `@field_validator(mode='before')` for pre-processing
- **Model Serialization**: Enhanced control with `@field_serializer`
- **JSON Schema Generation**: Updated patterns for OpenAPI integration

### **Production Considerations**:
- **Performance**: V2 typically faster due to Rust core
- **Memory Usage**: More efficient than V1 
- **Error Messages**: More detailed and actionable
- **Type Safety**: Stricter validation catches more issues

---

## 🎯 **OUTCOME FOR NARRATIVE FACTORY**

### **Benefits Post-Migration**:
1. **Clean Test Output**: No more deprecation warnings
2. **Future Compatibility**: Ready for Pydantic V3+
3. **Better Performance**: Rust-based validation core
4. **Enhanced Type Safety**: Catch more validation issues early
5. **Improved Developer Experience**: Better error messages

### **Risk Mitigation**:
- **Incremental Migration**: Fix files one at a time
- **Comprehensive Testing**: Validate each component after migration
- **Rollback Plan**: Git-based reversion if issues arise

**Estimated Migration Time**: 2-3 hours for complete Narrative Factory codebase

---

**This migration will resolve the deprecation warnings identified during our CodeFarm validation while improving the overall robustness of the Narrative Factory's data validation layer.**