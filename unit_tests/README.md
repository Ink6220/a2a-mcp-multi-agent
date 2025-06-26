# A2A Protocol Compliance Unit Tests

This directory contains comprehensive unit tests for verifying A2A protocol compliance for agents using a `ResponseFormat(BaseModel)` architecture.

1.  **Agent `invoke()` Method Compliance**: Validates that an agent's `invoke()` method returns a compliant `ResponseFormat` object.
2.  **Executor `execute()` Method Compliance**: Verifies that the executor correctly handles these `ResponseFormat` objects and produces a compliant A2A event stream for Starlette.

---

## 🏗️ **Testing Philosophy: `ResponseFormat` Object Architecture**

The entire testing suite is now based on the architecture that an agent's `invoke()` method **must return a `ResponseFormat(BaseModel)` object**, not a dictionary.

```
┌─────────────────────────────────────────────────────────────┐
│           A2A Compliance with ResponseFormat Objects        │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Agent invoke() -> ResponseFormat Object          │
│  ├── Must return a ResponseFormat(BaseModel) instance      │
│  ├── Validates object attributes (action, status, message) │
│  └── Ensures value validity and conditional requirements   │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Executor handles ResponseFormat Object           │
│  ├── Assumes agent returns a compliant object              │
│  ├── Reads attributes to manage state (response.status)    │
│  └── Creates artifacts from the object for Starlette       │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 **Directory Structure**

```
unit_tests/
├── README.md                                          # This file
├── test_invoke()_protocol_compliance/                 # Layer 1: Agent Testing
│   ├── Testing_agents_invoke().md                     # Documentation for ResponseFormat
│   └── test_agent_a2a_compliance.py                   # Tests for ResponseFormat objects
└── test_execute()_starlette_compliance/              # Layer 2: Executor Testing
    ├── Testing_execute()_starlette_compliance.md      # Documentation for executor
    ├── mock_agent.py                                  # Mock agent returns ResponseFormat objects
    ├── unit_test_starlette.py                         # Starlette simulation
```

---

## 🧪 **Test Suite 1: Agent `invoke()` returns `ResponseFormat`**

### **Purpose**
Verify that your agent's `invoke()` method returns a valid `ResponseFormat` object.

### **Location**
`unit_tests/test_invoke()_protocol_compliance/`

### **Quick Start**
```bash
# Run the compliance test with example agents
python test_agent_a2a_compliance.py
```

### **What It Tests**
- ✅ **Return Type**: `invoke()` must return an object, not a `dict`.
- ✅ **Required Attributes**: The object must have `action`, `status`, `message`.
- ✅ **Valid Values**: Validates that attributes have valid values from allowed sets.
- ✅ **Conditional Requirements**: Ensures delegation fields are present when needed.

### **Documentation**
📖 [**Full Documentation**](test_invoke()_protocol_compliance/Testing_agents_invoke().md)

---

## 🧪 **Test Suite 2: Executor handles `ResponseFormat`**

### **Purpose**
Verify that the executor correctly processes `ResponseFormat` objects and integrates with Starlette.

### **Location**
`unit_tests/test_execute()_starlette_compliance/`

### **Quick Start**
```bash
# Run the Starlette simulation with mock agents
python unit_test_starlette.py
```

### **What It Tests**
- ✅ **Object Handling**: Executor correctly reads attributes from the `ResponseFormat` object.
- ✅ **State Transitions**: Proper transitions based on `status` field values.
- ✅ **Artifact Creation**: Creates artifacts from the `ResponseFormat` object.
- ✅ **Event Streaming**: Produces a compliant SSE event stream for Starlette.
- ✅ **Error Resilience**: Gracefully handles agents that raise exceptions.
- ✅ **Delegation Support**: Handles delegation scenarios with required fields.

### **Documentation**
📖 [**Full Documentation**](test_execute()_starlette_compliance/Testing_execute()_starlette_compliance.md)

---

## 🚀 **Getting Started**

### **Step 1: Test Your Agent's `invoke()` Method**
Ensure your agent returns a `ResponseFormat` object and passes the agent-level compliance test.
```bash
cd unit_tests/test_invoke()_protocol_compliance/
python test_agent_a2a_compliance.py
```
**If tests fail:** Your agent is likely returning a `dict` or an object with missing/invalid attributes. See the documentation for common issues.

### **Step 2: Test Executor Integration**
Once your agent is compliant, run the executor test to ensure it's handled correctly.
```bash
cd unit_tests/test_execute()_starlette_compliance/
python unit_test_starlette.py
```
**If tests fail:** The issue is likely in the executor's logic for handling the object, not the agent itself.

---

## 📋 **`ResponseFormat` Requirements Summary**

### **Agent `invoke()` Method Must Return:**
An instance of your `ResponseFormat(BaseModel)` class.

### **`ResponseFormat` Class Must Contain:**
```python
class ResponseFormat(BaseModel):
    # --- A2A Core (Required) ---
    action: Literal["answer", "call_next_agent"]
    status: Literal["input_required", "completed", "failed"]
    message: str
    
    # --- Optional Extensions ---
    custom_status: Optional[str] = None
    agent_name: Optional[str] = None
    next_agent_instruction: Optional[str] = None
    next_agent_schema: Optional[Dict[str, Any]] = None
```

### **Conditional Requirements:**
When `action="call_next_agent"`, these fields become **required**:
- `agent_name`: str
- `next_agent_instruction`: str

### **Executor Must:**
1.  Receive the `ResponseFormat` object from the agent.
2.  Read its attributes (e.g., `response.status`, `response.action`) to determine task state.
3.  Create an artifact from the object's data upon completion.
4.  Generate a standard A2A event stream.

---

## 🔧 **Common Issues and Solutions**

| Issue | Symptom | Solution |
|---|---|---|
| **Wrong Return Type** | `AttributeError` in executor or `Response is not an object` in tests. | Ensure `invoke()` returns a `ResponseFormat` **instance**, not a `dict`. |
| **Missing Attribute** | `AttributeError` or `Missing A2A attribute` in tests. | Add the missing attribute (`action`, `status`, `message`) to your `ResponseFormat` class definition. |
| **Invalid Values** | `'action' must be one of ['answer', 'call_next_agent']` in tests. | Use only allowed values for `action` and `status` fields. |
| **Missing Delegation Fields** | `'agent_name' is required when action is 'call_next_agent'` in tests. | Include both `agent_name` and `next_agent_instruction` for delegation. |

---

## 🎯 **Success Criteria**

Your full agent system is compliant when:
- ✅ Your agent's `invoke()` method returns a valid `ResponseFormat` object and passes the **agent compliance test**.
- ✅ Your executor correctly processes this object and passes the **executor compliance test**.
- ✅ The end-to-end flow produces a valid A2A event stream for a Starlette client.

With this `ResponseFormat`-based architecture, you ensure a type-safe, robust, and easily debuggable system.

---

## 📚 **Additional Resources**

### **Documentation Files**
- [`Testing_agents_invoke().md`](test_invoke()_protocol_compliance/Testing_agents_invoke().md) - Complete agent testing guide
- [`Testing_execute()_starlette_compliance.md`](test_execute()_starlette_compliance/Testing_execute()_starlette_compliance.md) - Complete executor testing guide

### **Test Files**
- [`test_agent_a2a_compliance.py`](test_invoke()_protocol_compliance/test_agent_a2a_compliance.py) - Agent compliance tester
- [`mock_agent.py`](test_execute()_starlette_compliance/mock_agent.py) - Mock agent with pytest tests
- [`unit_test_starlette.py`](test_execute()_starlette_compliance/unit_test_starlette.py) - Starlette integration simulation

### **Usage Examples**
- Example compliant agents for reference
- Common error patterns and fixes
- Integration templates for Starlette
- Performance testing guidelines

---

## 🤝 **Contributing**

When adding new tests:

1. **Agent Tests**: Add to `test_invoke()_protocol_compliance/`
   - Focus on `invoke()` method output validation
   - Test edge cases and error conditions
   - Maintain black box approach

2. **Executor Tests**: Add to `test_execute()_starlette_compliance/`
   - Focus on state management and streaming
   - Test integration scenarios
   - Verify Starlette compatibility

3. **Documentation**: Update relevant `.md` files
   - Include usage examples
   - Document new test scenarios
   - Update requirements and criteria

---

## 🎉 **You're Ready!**

With these comprehensive test suites, you can:

- ✅ **Develop Confidently**: Know your agent is A2A compliant
- ✅ **Debug Effectively**: Pinpoint exactly what needs fixing
- ✅ **Deploy Safely**: Verify full integration before production
- ✅ **Maintain Quality**: Continuous testing as you evolve your agent

**Start with Step 1** and work your way through both test suites. When everything passes, you'll have a production-ready A2A-compliant agent! 🚀 