# A2A Protocol Compliance Testing
## Agent invoke() Method with ResponseFormat(BaseModel)

### 🎯 **Objective**
Verify that an agent's `invoke()` method returns a `ResponseFormat(BaseModel)` object that is fully compliant with the A2A protocol. This test validates the attributes of the returned object, ensuring type safety and structural correctness.

---

## 🏗️ **Architecture: `ResponseFormat` Objects**

The new architecture requires that the agent's `invoke()` method returns an instance of a `ResponseFormat` class, which inherits from `pydantic.BaseModel` (or a mock equivalent for testing). This enforces a strict, type-safe contract between the agent and the executor.

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
    next_agent_schema: Optional[Dict[str, Any]] = None
```

### **3. Conditional Requirements:**
When `action` is `"call_next_agent"`, the following optional fields become **required**:
- `agent_name`: str - Name of the agent to call
- `next_agent_instruction`: str - Instruction for the next agent

**Key Point:** The test validates the **presence and types of the core A2A attributes** and the **conditional requirements** on the returned object.

---

## 🧪 **Testing Framework (`test_agent_a2a_compliance.py`)**

The updated test framework is designed to validate `ResponseFormat` objects.

#### **Key Features:**
- ✅ **Object Validation**: Checks if `invoke()` returns an object, not a dictionary.
- ✅ **Attribute Validation**: Verifies the presence of required A2A attributes (`action`, `status`, `message`).
- ✅ **Value Validation**: Ensures attributes have valid values (correct Literal values).
- ✅ **Conditional Validation**: Validates required fields for delegation scenarios.
- ✅ **Example Agents**: Includes examples of compliant and non-compliant agents using the `ResponseFormat` model.

---

## 🚀 **How to Run Tests**

### **1. Run the Test Suite Directly**
This will test the example agents included in the file.
```bash
cd unit_tests/test_invoke()_protocol_compliance
python test_agent_a2a_compliance.py
```

**Expected Output:**
```
🧪 A2A Protocol Compliance Tester (Updated ResponseFormat)
============================================================

A2A COMPLIANCE REPORT
============================================================
Agent Name: example-compliant-agent
Status: ✅ FULLY COMPLIANT
Compliance: 100.0% (4/4 passed)

--- TEST DETAILS ---

✅ Test 1: Hello, can you help me?
   - Status: PASSED
   - Response: action=answer, status=completed
   - Message: 'I have processed your request: Hello, can you help...'
✅ Test 2: What is 2 + 2?
   - Status: PASSED
   - Response: action=answer, status=completed
   - Message: 'I have processed your request: What is 2 + 2?...'
...
============================================================
```

### **2. Test Your Own Agent**
To test your agent, ensure its `invoke()` method returns an instance of your `ResponseFormat` class.
```python
# your_agent_test.py
import asyncio
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report
from your_agent_module import YourAgent # Import your agent

async def run_test():
    # 1. Instantiate your agent
    my_agent = YourAgent()

    # 2. Run the compliance test
    results = await A2AComplianceTester.test_agent_invoke_compliance(my_agent)

    # 3. Print the report
    print_compliance_report(results)

if __name__ == "__main__":
    asyncio.run(run_test())
```

---

## 🎨 **Example Implementations**

### **Compliant Agent (CORRECT):**
This agent correctly returns a `ResponseFormat` object.
```python
from response_format_module import ResponseFormat # Your BaseModel

class YourCompliantAgent:
    agent_name = "your-compliant-agent"
    
    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
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
                message=f"Processed: {query}"
            )
```

### **Non-Compliant Agent (DON'T DO THIS):**
This agent incorrectly returns a dictionary instead of a `ResponseFormat` object.
```python
class NonCompliantAgent:
    agent_name = "dict-returning-agent"
    
    async def invoke(self, query: str, session_id: str) -> dict:
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

    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
        # ❌ WRONG: Invalid action value
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

    async def invoke(self, query: str, session_id: str) -> ResponseFormat:
        # ❌ WRONG: Missing agent_name and next_agent_instruction for delegation
        return ResponseFormat(
            action="call_next_agent",
            status="completed", 
            message="Delegating task but missing required fields."
            # Missing agent_name and next_agent_instruction
        )
```

---

## 🚨 **Common Compliance Issues**

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
- **Symptom:** Test fails with `'action' must be one of ['answer', 'call_next_agent']`.
- **Solution:** Use only the allowed values for action and status fields.
```python
# ❌ WRONG
return ResponseFormat(action="respond", status="done", ...)

# ✅ CORRECT
return ResponseFormat(action="answer", status="completed", ...)
```

### **4. Missing Delegation Fields**
- **Symptom:** Test fails with `'agent_name' is required when action is 'call_next_agent'`.
- **Solution:** Include both `agent_name` and `next_agent_instruction` when delegating.
```python
# ❌ WRONG
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

---

## 🔍 **Executor Integration**

The `GenericAgentExecutor` expects the `ResponseFormat` object from `invoke()`. It will access the attributes of this object (`response.action`, `response.status`, `response.message`, etc.) to manage the task state. The object itself (or a dictionary representation of it) is what gets passed to `add_artifact()`.

---

## 🎯 **Success Criteria**

Your agent is A2A compliant when:
- ✅ **Returns Object**: `invoke()` consistently returns a `ResponseFormat` object.
- ✅ **A2A Attributes Present**: The object has all required A2A attributes.
- ✅ **Valid Values**: All A2A attributes have valid values from their allowed sets.
- ✅ **Conditional Fields**: Required conditional fields are present for delegation.
- ✅ **Passes Tests**: The `A2AComplianceTester` reports 100% compliance.

When all these criteria are met, your agent is ready for robust, type-safe integration with the executor. 