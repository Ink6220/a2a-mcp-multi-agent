# A2A Protocol Compliance Testing
## Agent invoke() Method Compliance Verification

### 🎯 **Objective**
Verify that an agent's `invoke()` method returns responses that comply with the A2A protocol. This is a "black box" test that validates the output format without needing to understand the agent's internal implementation.

---

## ⚠️ **Important: A2A Protocol vs Custom Extensions**

### **A2A Protocol Requirements (REQUIRED):**
```python
{
    "is_task_complete": bool,     # True = task done, False = continue
    "require_user_input": bool,   # True = needs input, False = processing
    "content": str,               # Message content for user/artifact
}
```

### **Your Custom ResponseFormat Extensions (OPTIONAL):**
```python
{
    # A2A Core Protocol (required)
    "is_task_complete": bool,
    "require_user_input": bool,
    "content": str,
    
    # Your custom extensions (optional, not part of A2A spec)
    "hang_up": bool,              # Your custom field for conversation ending
    "call_next_agent": bool,      # Your delegation system
    "agent_name": str,            # Who to delegate to  
    "delegation_reason": str,     # Why delegating
    # ... any other custom fields from your ResponseFormat
}
```

**Key Point:** The A2A compliance tester ONLY validates the 3 core protocol fields. Your custom fields are allowed but not validated by the A2A spec.

---

## 🧪 **Testing Framework**

### **1. A2A Compliance Tester (`test_agent_a2a_compliance.py`)**

A comprehensive testing framework that validates agent responses against the **core A2A protocol requirements only**.

#### **Key Features:**
- ✅ **Black Box Testing**: Only tests the `invoke()` method output
- ✅ **Core A2A Validation**: Checks ONLY the 3 required A2A fields
- ✅ **Custom Fields Allowed**: Your ResponseFormat extensions are permitted but not validated
- ✅ **Batch Testing**: Tests multiple queries automatically
- ✅ **Detailed Reporting**: Shows both A2A compliance and custom field usage

#### **Validation Rules:**
1. **Required Fields**: `is_task_complete`, `require_user_input`, `content` (A2A protocol)
2. **Type Checking**: Booleans must be booleans, strings must be strings
3. **Logic Validation**: Cannot have both `is_task_complete=True` and `require_user_input=True`
4. **Custom Fields**: Any additional fields are allowed (hang_up, call_next_agent, etc.)

---

## 🚀 **How to Run Tests**

### **Method 1: Command Line Testing**
```bash
cd unit_tests/test_invoke()_protocol_compliance
python test_agent_a2a_compliance.py
```

**Output Example:**
```
🧪 A2A Protocol Compliance Tester
============================================================
ℹ️  Testing ONLY A2A core protocol fields:
   - is_task_complete, require_user_input, content
   - Custom fields (hang_up, call_next_agent, etc.) are allowed but not validated
============================================================

📋 Testing Example Compliant Agent:
============================================================
A2A COMPLIANCE REPORT
============================================================
Agent Name: example-compliant-agent
Total Tests: 5
Passed: 5
Failed: 0
Compliance: 100.0%
Status: ✅ FULLY COMPLIANT

============================================================
TEST DETAILS
============================================================

✅ Test 1: PASSED
   Query: Hello, can you help me?
   Response: is_complete=False, need_input=True
   Content: I'd be happy to help! What specifically do you...
   Custom fields: {'hang_up': False}
```

### **Method 2: Testing Your Own Agent**
```python
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report

# Test your agent
your_agent = YourAgentClass()
results = await A2AComplianceTester.test_agent_invoke_compliance(your_agent)

# Print detailed report
print_compliance_report(results)

# Check if A2A compliant
if results['is_fully_compliant']:
    print("✅ Your agent is A2A compliant!")
    print("💡 Custom fields are not validated but are allowed")
else:
    print(f"❌ {results['failed']} A2A protocol tests failed")
```

### **Method 3: Custom Test Queries**
```python
# Test with specific queries
custom_queries = [
    "Calculate 2 + 2",
    "What is the weather like?",
    "I need help with my homework"
]

results = await A2AComplianceTester.test_agent_invoke_compliance(
    your_agent, 
    test_queries=custom_queries
)
```

---

## 📋 **Test Scenarios Covered**

### **1. A2A Core Protocol Tests**
- **Task Completion**: `is_task_complete=True, require_user_input=False`
- **Input Required**: `is_task_complete=False, require_user_input=True`
- **Still Working**: `is_task_complete=False, require_user_input=False`
- **Error Handling**: Proper A2A response structure even on errors

### **2. Validation Tests**
- **Missing A2A Fields**: Detects missing required A2A protocol fields
- **Wrong Types**: Catches type mismatches (string instead of boolean)
- **Logic Contradictions**: Prevents impossible A2A state combinations
- **Custom Fields**: Verifies custom fields don't break A2A compliance

### **3. Example Test Queries**
1. `"Hello, can you help me?"` - Basic greeting/assistance
2. `"What is 2 + 2?"` - Simple calculation
3. `"I need more information about this topic"` - Information request
4. `"Please process this data"` - Task processing
5. `"Can you delegate this task?"` - Delegation scenario

---

## 🔧 **Basic Executor Integration**

### **GenericAgentExecutor (`basic_executor.py`)**

A simplified "black box" executor that only calls the agent's `invoke()` method while maintaining full A2A protocol compliance.

#### **Key Features:**
- ✅ **Simplified**: Only calls `agent.invoke()` - no complex streaming logic
- ✅ **A2A Compliant**: Proper task management, status updates, artifacts
- ✅ **Custom Field Support**: Passes through your ResponseFormat extensions
- ✅ **Debug Ready**: Easy to trace and debug agent behavior

#### **Execution Flow:**
1. **Task Creation**: Creates task with unique IDs if none exists
2. **Initial Status**: Sends `working` status to client
3. **Agent Invocation**: Calls `agent.invoke(query, session_id)`
4. **Response Handling**: Processes A2A response + custom fields
5. **State Management**: Updates task state and creates artifacts as needed

---

## 📊 **A2A Protocol Compliance Verification**

### **Required A2A Protocol Elements**

| Requirement | Status | Implementation |
|-------------|---------|----------------|
| Task creation with unique IDs | ✅ | `new_task(context.message)` creates taskId, contextId |
| TaskUpdater for state management | ✅ | `TaskUpdater(event_queue, task.id, task.contextId)` |
| EventQueue for streaming updates | ✅ | Events queued via `updater.update_status()` |
| Status transitions | ✅ | `working` → `completed`/`input_required` |
| Artifact creation on completion | ✅ | `updater.add_artifact()` with TextPart |
| Proper error handling | ✅ | Try/catch with fallback status |

### **Client Experience Flow:**
1. **Initial**: `TaskState.working` - "Processing your request..."
2. **Completion**: `TaskState.completed` + artifact OR `TaskState.input_required`
3. **Error**: `TaskState.input_required` with error message

---

## 🎨 **Example Implementations**

### **A2A + Custom Extensions (CORRECT):**
```python
class YourCompliantAgent:
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        if "help" in query.lower():
            return {
                # A2A Core Protocol (required)
                "is_task_complete": False,
                "require_user_input": True,
                "content": "What specifically do you need help with?",
                
                # Your custom ResponseFormat extensions (optional)
                "hang_up": False,
                "call_next_agent": False,
                "agent_name": "",
                "confidence_score": 0.8,  # Any custom field you want
            }
        else:
            return {
                # A2A Core Protocol (required)
                "is_task_complete": True,
                "require_user_input": False,
                "content": f"I processed: {query}",
                
                # Your custom ResponseFormat extensions (optional)
                "hang_up": False,
                "call_next_agent": False,
                "processing_time": 1.2,  # Any custom field you want
            }
```

### **Non-Compliant Agent (DON'T DO THIS):**
```python
class NonCompliantAgent:
    async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
        return {
            "message": "This is missing A2A protocol fields",
            "status": "done",
            "hang_up": False,  # Custom fields are fine...
            "call_next_agent": True,  # Custom fields are fine...
            # ❌ Missing A2A CORE: is_task_complete, require_user_input, content
        }
```

---

## 🚨 **Common Compliance Issues**

### **1. Missing A2A Protocol Fields**
```python
# ❌ WRONG - Missing A2A core fields
return {
    "message": "Hello",
    "hang_up": False,  # Custom field OK
    "call_next_agent": True  # Custom field OK
    # Missing: is_task_complete, require_user_input, content
}

# ✅ CORRECT - A2A core + custom fields
return {
    "is_task_complete": True,     # A2A required
    "require_user_input": False,  # A2A required
    "content": "Hello",           # A2A required
    "hang_up": False,             # Your custom field
    "call_next_agent": True       # Your custom field
}
```

### **2. Wrong Field Types**
```python
# ❌ WRONG - A2A fields must have correct types
return {
    "is_task_complete": "yes",    # Should be boolean
    "require_user_input": "no",   # Should be boolean
    "content": "Hello",           # String is correct
    "hang_up": "false"            # Custom field - any type you want
}

# ✅ CORRECT - A2A fields with correct types
return {
    "is_task_complete": True,     # Boolean (A2A)
    "require_user_input": False,  # Boolean (A2A)
    "content": "Hello",           # String (A2A)
    "hang_up": "false"            # Custom field - any type you want
}
```

### **3. Logical Contradictions in A2A Fields**
```python
# ❌ WRONG - A2A logic contradiction
return {
    "is_task_complete": True,
    "require_user_input": True,   # Cannot both be True in A2A
    "content": "Confused state",
    "call_next_agent": True       # Custom field - no restrictions
}

# ✅ CORRECT - Valid A2A logic
return {
    "is_task_complete": True,
    "require_user_input": False,  # Valid A2A combination
    "content": "Task completed",
    "call_next_agent": True       # Custom field - any value OK
}
```

---

## 🔍 **Understanding the Architecture**

### **Your Agent's Translation Layer:**
```python
async def invoke(self, query: str, session_id: str) -> Dict[str, Any]:
    # 1. Your LLM returns ResponseFormat (BaseModel)
    llm_response = await self.llm.call(query)  # Your ResponseFormat
    
    # 2. Your translation layer converts to A2A + extensions
    return {
        # A2A Protocol compliance (executor expects these)
        "is_task_complete": llm_response.status in ["completed", "hang_up"],
        "require_user_input": llm_response.status == "input_required",
        "content": llm_response.message,
        
        # Your custom extensions (delegation, etc.)
        "hang_up": llm_response.status == "hang_up",
        "call_next_agent": llm_response.action == "call_next_agent",
        "agent_name": llm_response.agent_name,
        "delegation_reason": "specialist_required",
        # ... any other fields from your ResponseFormat
    }
```

### **Executor Processes Both:**
- **A2A Fields**: Used for task state management and streaming
- **Custom Fields**: Passed through to artifacts and delegation system

---

## 🔍 **Debugging Your Agent**

### **Step 1: Run A2A Compliance Test**
```bash
python test_agent_a2a_compliance.py
```

### **Step 2: Check for A2A Protocol Failures**
Look for ❌ in the test output and check the error messages:
- `Missing required A2A field: 'field_name'`
- `'field_name' must be a boolean`
- `Invalid state: cannot both be True`

### **Step 3: Fix A2A Core Fields**
Update your agent's `invoke()` method to return the 3 required A2A fields with correct types.

### **Step 4: Verify Custom Fields Work**
Your custom fields should appear in the test output under "Custom fields:" and should not cause any failures.

### **Step 5: Test with Executor**
Once A2A compliant, test with the `GenericAgentExecutor`:
```python
from basic_executor import GenericAgentExecutor

executor = GenericAgentExecutor(your_agent)
# Test with mock context and event queue
```

---

## 📝 **Requirements for Your Agent**

### **Minimum A2A Requirements:**
1. **invoke() method**: `async def invoke(self, query: str, session_id: str) -> Dict[str, Any]`
2. **A2A Core Fields**: Must return dict with `is_task_complete`, `require_user_input`, `content`
3. **Type Compliance**: Correct types for A2A fields (bool, bool, str)
4. **Logic Compliance**: No contradictory A2A states

### **Your Custom Extensions (Encouraged):**
- **Delegation Support**: Add `call_next_agent`, `agent_name` fields
- **Conversation Control**: Add `hang_up` field for conversation ending
- **Rich Content**: Use additional fields for metadata, confidence scores, etc.
- **Session Management**: Use `session_id` for maintaining conversation state

---

## 🎯 **Success Criteria**

Your agent is A2A compliant when:

- ✅ **100% A2A Compliance**: All test queries return valid A2A core fields
- ✅ **Type Safety**: A2A fields have correct types (bool, bool, str)
- ✅ **Logic Consistency**: No contradictory A2A states
- ✅ **Custom Fields Work**: Your ResponseFormat extensions are preserved
- ✅ **Executor Integration**: Works seamlessly with `GenericAgentExecutor`

---

## 🚀 **Next Steps**

1. **Test Your Agent**: Run the A2A compliance tests on your agent
2. **Fix A2A Issues**: Address any core protocol failures
3. **Verify Custom Fields**: Ensure your ResponseFormat extensions work
4. **Test Integration**: Verify with `GenericAgentExecutor`
5. **Deploy Confidently**: Your agent is ready for A2A protocol usage

### **Ready for Production When:**
- All A2A compliance tests pass ✅
- Custom fields are preserved and functional ✅
- Executor integration works ✅
- Your agent handles various query types gracefully ✅

**Remember:** The A2A protocol is just the foundation. Your custom ResponseFormat extensions are what make your agent powerful for delegation and advanced features! 