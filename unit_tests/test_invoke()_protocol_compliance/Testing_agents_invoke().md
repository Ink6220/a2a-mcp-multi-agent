# A2A Protocol Compliance Testing
## Agent invoke() Method with ResponseFormat(BaseModel)

### 🎯 **Objective**
Verify that an agent's `invoke()` method returns a `ResponseFormat(BaseModel)` object that is fully compliant with the A2A protocol. This comprehensive test suite validates:

1. **Basic A2A Compliance**: Proper ResponseFormat structure and values
2. **Pydantic Validation**: Type safety and field validation 
3. **Error Handling**: Graceful handling of validation and runtime errors
4. **Delegation Logic**: Conditional field requirements for agent delegation
5. **Type Safety**: Proper handling of optional fields and artifacts

---

## 🏗️ **Architecture: `ResponseFormat` Objects**

The new architecture requires that the agent's `invoke()` method returns an instance of a `ResponseFormat` class, which inherits from `pydantic.BaseModel`. This enforces a strict, type-safe contract between the agent and the executor, as demonstrated in `basic_executor_with_delegator.py`.

### **1. A2A Protocol Requirements on `ResponseFormat`:**
The returned `ResponseFormat` object **MUST** have these attributes:
```python
class ResponseFormat(BaseModel):
    action: Literal["answer", "call_next_agent"]
    status: Literal["input_required", "completed", "failed"]
    message: str
```

### **2. Optional Fields on `ResponseFormat`:**
Your optional fields for delegation, conversation control, etc., should be defined as optional attributes on your `ResponseFormat` model.
```python
class ResponseFormat(BaseModel):
    # A2A Core Attributes (required)
    action: Literal["answer", "call_next_agent"]
    status: Literal["input_required", "completed", "failed"] 
    message: str
    
    # Optional Extensions
    custom_status: Optional[str] = None
    agent_name: Optional[str] = None
    next_agent_instruction: Optional[str] = None
    artifacts: Optional[str] = None
```

### **3. Conditional Requirements & Type Safety:**
The `ResponseFormat` class includes a Pydantic `@model_validator` that enforces conditional requirements:

```python
@model_validator(mode="after")
def validate_required_fields(self) -> Self:
    if self.action == "call_next_agent":
        if not self.agent_name:
            raise ValueError("`agent_name` is required when action is 'call_next_agent'")
        if not self.next_agent_instruction:
            raise ValueError("`next_agent_instruction` is required when action is 'call_next_agent'")
    return self
```

When `action` is `"call_next_agent"`, the following optional fields become **required**:
- `agent_name`: str - Name of the agent to call
- `next_agent_instruction`: str - Instruction for the next agent

**Key Point:** The test validates the **presence and types of the core A2A attributes**, **conditional requirements**, and **Pydantic validation behavior** on the returned object.

---

## 🧪 **Enhanced Testing Framework (`test_agent_a2a_compliance.py`)**

The updated test framework now includes comprehensive validation testing:

#### **Key Features:**
- ✅ **Object Validation**: Checks if `invoke()` returns an object, not a dictionary.
- ✅ **Attribute Validation**: Verifies the presence of required A2A attributes (`action`, `status`, `message`).
- ✅ **Value Validation**: Ensures attributes have valid values (correct Literal values).
- ✅ **Conditional Validation**: Validates required fields for delegation scenarios.
- ✅ **Pydantic ValidationError Testing**: Tests type safety and field validation.
- ✅ **Error Handling Testing**: Tests agent behavior during errors.
- ✅ **Type Safety Testing**: Tests optional fields and artifacts handling.
- ✅ **Example Agents**: Includes examples of compliant and non-compliant agents using the `ResponseFormat` model.

### **New Test Categories:**

#### **1. Pydantic Validation Tests**
Tests the built-in type safety checker:
```python
validation_results = A2AComplianceTester.test_pydantic_validation_errors()
print_validation_report(validation_results)
```

Covers:
- Missing required fields
- Invalid action/status literals
- Missing delegation fields
- Conditional validation logic

#### **2. Error Handling Tests**
Tests agent behavior during errors:
```python
error_agent = ExampleErrorHandlingAgent()
error_queries = ["Normal query", "Please raise_error", "Test validation_error scenario"]
error_results = await A2AComplianceTester.test_agent_invoke_compliance(error_agent, error_queries)
```

#### **3. Type Safety Tests**
Tests optional field handling:
```python
type_safety_agent = ExampleTypeSafetyAgent()
type_queries = ["Normal query", "Query with artifacts", "Query with custom_status"]
type_results = await A2AComplianceTester.test_agent_invoke_compliance(type_safety_agent, type_queries)
```

---

## 🚀 **How to Run Tests**

### **1. Run the Enhanced Test Suite Directly**
This will test all validation scenarios and example agents.
```bash
cd unit_tests/test_invoke()_protocol_compliance
python test_agent_a2a_compliance.py
```

**Expected Output:**
```
🧪 A2A Protocol Compliance Tester (Enhanced with Validation Tests)
======================================================================

📋 Testing Pydantic ValidationError Handling:

============================================================
PYDANTIC VALIDATION TESTS
============================================================
Total Tests: 6
Passed: 6
Failed: 0
Success Rate: 100.0%
Status: ✅ ALL VALIDATION TESTS PASSED

============================================================
VALIDATION TEST DETAILS
============================================================

✅ Test 1: PASSED
   Description: Missing required fields
   Expected ValidationError: Field required [type=missing, input={}, url=...

✅ Test 2: PASSED
   Description: Invalid action literal
   Expected ValidationError: Input should be 'answer' or 'call_next_agent'...

📋 Testing Example Compliant Agent:

============================================================
A2A COMPLIANCE REPORT
============================================================
Agent Name: example-compliant-agent
Status: ✅ FULLY COMPLIANT
Compliance: 100.0% (4/4 passed)
...
```

### **2. Test Your Own Agent**
To test your agent, ensure its `invoke()` method returns an instance of your `ResponseFormat` class.
```python
# your_agent_test.py
import asyncio
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report, print_validation_report
from your_agent_module import YourAgent # Import your agent

async def run_test():
    # 1. Test Pydantic validation first
    validation_results = A2AComplianceTester.test_pydantic_validation_errors()
    print_validation_report(validation_results)
    
    # 2. Instantiate your agent
    my_agent = YourAgent()

    # 3. Run the compliance test
    results = await A2AComplianceTester.test_agent_invoke_compliance(my_agent)

    # 4. Print the report
    print_compliance_report(results)

if __name__ == "__main__":
    asyncio.run(run_test())
```

---

## 🎨 **Example Implementations**

### **Compliant Agent (CORRECT):**
This agent correctly returns a `ResponseFormat` object and handles all scenarios.
```python
from response_format_module import ResponseFormat # Your BaseModel

class YourCompliantAgent:
    agent_name = "your-compliant-agent"
    
    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> ResponseFormat:
        if "delegate" in query.lower():
            return ResponseFormat(
                action="call_next_agent",
                status="completed",
                message="Delegating to specialist.",
                agent_name="specialist-agent",
                next_agent_instruction="Please handle this specialized request"
            )
        elif "help" in query.lower():
            return ResponseFormat(
                action="answer",
                status="input_required",
                message="I need more information to help you. What specifically do you need?"
            )
        else:
            return ResponseFormat(
                action="answer",
                status="completed",
                message=f"Processed: {query}",
                artifacts='{"result": "processed_data"}'  # Optional JSON artifacts
            )
```

### **Error Handling Agent (BEST PRACTICE):**
This agent demonstrates proper error handling as seen in actual agent implementations:
```python
class ErrorHandlingAgent:
    agent_name = "error-handling-agent"
    
    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> ResponseFormat:
        try:
            # Main agent logic here
            result = await self.process_query(query)
            
            return ResponseFormat(
                action="answer",
                status="completed",
                message=f"Successfully processed: {result}"
            )
        except ValidationError as ve:
            # Handle Pydantic validation errors
            return ResponseFormat(
                action="answer",
                status="failed",
                message="Response format validation failed",
                custom_status="validation_error"
            )
        except Exception as e:
            # Handle other errors gracefully
            return ResponseFormat(
                action="answer",
                status="failed", 
                message="An error occurred while processing your request",
                custom_status="processing_error"
            )
```

### **Non-Compliant Agent (DON'T DO THIS):**
This agent incorrectly returns a dictionary instead of a `ResponseFormat` object.
```python
class NonCompliantAgent:
    agent_name = "dict-returning-agent"
    
    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> dict:
        # ❌ WRONG: Returns a dict, will fail the test.
        return {
            "action": "answer",
            "status": "completed",
            "message": "This is a dictionary, not a ResponseFormat object."
        }
```

### **Invalid Action Agent (DON'T DO THIS):**
This agent returns a `ResponseFormat` object with an invalid action value.
```python
class InvalidActionAgent:
    agent_name = "invalid-action-agent"

    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> ResponseFormat:
        # ❌ WRONG: Invalid action value - will trigger ValidationError
        return ResponseFormat(
            action="invalid_action",  # Must be "answer" or "call_next_agent"
            status="completed",
            message="This response has an invalid action."
        )
```

### **Missing Delegation Fields Agent (DON'T DO THIS):**
This agent tries to delegate but is missing required conditional fields.
```python
class MissingDelegationFieldsAgent:
    agent_name = "missing-delegation-agent"

    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> ResponseFormat:
        # ❌ WRONG: Missing agent_name and next_agent_instruction for delegation
        # This will trigger the @model_validator ValidationError
        return ResponseFormat(
            action="call_next_agent",
            status="completed", 
            message="Delegating task but missing required fields."
            # Missing agent_name and next_agent_instruction
        )
```

---

## 🚨 **Common Compliance Issues & Solutions**

### **1. Returning a Dictionary Instead of an Object**
- **Symptom:** Test fails with `Response is not an object`.
- **Solution:** Ensure your `invoke()` method returns an instance of your `ResponseFormat` class, not a `dict`.
```python
# ❌ WRONG
return {"action": "answer", "status": "completed", ...}

# ✅ CORRECT
from your_models import ResponseFormat
return ResponseFormat(action="answer", status="completed", ...)
```

### **2. Missing Required A2A Attributes**
- **Symptom:** Test fails with `Response object missing required A2A attribute: '...'`.
- **Solution:** Ensure your `ResponseFormat` class definition includes `action`, `status`, and `message`.
```python
# ❌ WRONG
class ResponseFormat(BaseModel):
    content: str # Missing A2A attributes

# ✅ CORRECT
class ResponseFormat(BaseModel):
    action: Literal["answer", "call_next_agent"]
    status: Literal["input_required", "completed", "failed"]
    message: str
```

### **3. Invalid Action or Status Values**
- **Symptom:** Test fails with `'action' must be one of ['answer', 'call_next_agent']` or Pydantic ValidationError.
- **Solution:** Use only the allowed values for action and status fields.
```python
# ❌ WRONG
return ResponseFormat(action="respond", status="done", ...)

# ✅ CORRECT
return ResponseFormat(action="answer", status="completed", ...)
```

### **4. Missing Delegation Fields**
- **Symptom:** Test fails with `'agent_name' is required when action is 'call_next_agent'` or Pydantic ValidationError.
- **Solution:** Include both `agent_name` and `next_agent_instruction` when delegating.
```python
# ❌ WRONG - Will trigger @model_validator ValidationError
return ResponseFormat(action="call_next_agent", status="completed", message="...")

# ✅ CORRECT
return ResponseFormat(
    action="call_next_agent", 
    status="completed", 
    message="Delegating...",
    agent_name="target-agent",
    next_agent_instruction="Handle this request"
)
```

### **5. ValidationError Handling**
- **Symptom:** Agent crashes with ValidationError during runtime.
- **Solution:** Wrap ResponseFormat creation in try/catch blocks.
```python
# ✅ BEST PRACTICE
try:
    return ResponseFormat(
        action=parsed_action,
        status=parsed_status,
        message=parsed_message
    )
except ValidationError as ve:
    # Return a safe fallback response
    return ResponseFormat(
        action="answer",
        status="failed",
        message="Response validation failed"
    )
```

---

## 🔍 **Executor Integration**

The `GenericAgentExecutor` (as seen in `basic_executor_with_delegator.py`) expects the `ResponseFormat` object from `invoke()`. It will:

1. **Access Response Attributes**: `response.action`, `response.status`, `response.message`, etc.
2. **Handle Delegation**: Use `response.agent_name` and `response.next_agent_instruction` for task delegation
3. **Create Artifacts**: Use `response.artifacts` or `response.message` for artifact creation
4. **Manage State**: Update task state based on `response.status`
5. **Error Handling**: Gracefully handle ValidationErrors and other exceptions

The executor includes helper functions like `create_artifact_parts()` to handle JSON artifacts properly.

---

## 🎯 **Success Criteria**

Your agent is A2A compliant when:
- ✅ **Returns Object**: `invoke()` consistently returns a `ResponseFormat` object.
- ✅ **A2A Attributes Present**: The object has all required A2A attributes.
- ✅ **Valid Values**: All A2A attributes have valid values from their allowed sets.
- ✅ **Conditional Fields**: Required conditional fields are present for delegation.
- ✅ **Passes Validation Tests**: The Pydantic validation tests pass 100%.
- ✅ **Handles Errors**: The agent gracefully handles ValidationErrors and other exceptions.
- ✅ **Type Safety**: Optional fields and artifacts are handled correctly.
- ✅ **Passes Compliance Tests**: The `A2AComplianceTester` reports 100% compliance.

When all these criteria are met, your agent is ready for robust, type-safe integration with the executor as demonstrated in `basic_executor_with_delegator.py`.

---

## 📊 **Test Coverage Summary**

The enhanced test suite covers:

| Test Category | Coverage | Purpose |
|---------------|----------|---------|
| **Basic Compliance** | Core A2A attributes and values | Validates fundamental protocol adherence |
| **Pydantic Validation** | Type safety and field validation | Tests the ResponseFormat model validator |
| **Error Handling** | Exception scenarios and recovery | Ensures graceful error handling |
| **Type Safety** | Optional fields and artifacts | Validates proper typing and serialization |
| **Delegation Logic** | Conditional field requirements | Tests agent-to-agent delegation scenarios |
| **Edge Cases** | Invalid inputs and boundary conditions | Ensures robustness under stress |

This comprehensive testing ensures your agent will work correctly with the `basic_executor_with_delegator.py` and handle all scenarios defined in the A2A protocol. 