# A2A Protocol Compliance Unit Tests

This directory contains comprehensive unit tests for verifying A2A protocol compliance at two different levels:

1. **Agent `invoke()` Method Compliance** - Black box testing of agent responses
2. **Executor `execute()` Method Compliance** - Testing executor state management and Starlette integration

---

## 🎯 **Testing Philosophy**

### **Two-Layer Testing Approach**

```
┌─────────────────────────────────────────────────────────────┐
│                    A2A PROTOCOL COMPLIANCE                 │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Agent invoke() Method Testing                    │
│  ├── Black box testing of agent responses                  │
│  ├── Validates A2A response format                         │
│  ├── Type checking and logic validation                    │
│  └── Basic executor integration                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 2: Executor execute() Method Testing                │
│  ├── Assumes agent invoke() is compliant                   │
│  ├── Tests state management and streaming                  │
│  ├── Validates Starlette integration                       │
│  └── End-to-end workflow verification                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 **Directory Structure**

```
unit_tests/
├── README.md                                          # This file
├── test_invoke()_protocol_compliance/                 # Layer 1: Agent Testing
│   ├── Testing_agents_invoke().md                     # Documentation
│   ├── test_agent_a2a_compliance.py                   # Main test framework
│   └── basic_executor.py                              # Simplified executor
└── test_execute()_starlette_compliance/              # Layer 2: Executor Testing
    ├── Testing_execute()_starlette_compliance.md      # Documentation
    ├── mock_agent.py                                   # A2A compliant mock agent
    ├── unit_test_starlette.py                         # Starlette simulation
    └── manual_test_executor.py                        # Manual testing utilities
```

---

## 🧪 **Test Suite 1: Agent invoke() Compliance**

### **Purpose**
Verify that your agent's `invoke()` method returns A2A-compliant responses.

### **Location**
```bash
cd unit_tests/test_invoke()_protocol_compliance/
```

### **Quick Start**
```bash
# Run the compliance test
python test_agent_a2a_compliance.py

# Test your own agent
python -c "
from test_agent_a2a_compliance import A2AComplianceTester, print_compliance_report
from your_agent import YourAgent

agent = YourAgent()
results = await A2AComplianceTester.test_agent_invoke_compliance(agent)
print_compliance_report(results)
"
```

### **What It Tests**
- ✅ **Required Fields**: `is_task_complete`, `require_user_input`, `content`
- ✅ **Type Validation**: Correct types for all fields
- ✅ **Logic Validation**: No contradictory states
- ✅ **Error Handling**: Graceful error responses
- ✅ **Optional Fields**: Proper handling of `hang_up`, delegation fields

### **Example Output**
```
🧪 A2A Protocol Compliance Tester
============================================================

📋 Testing Example Compliant Agent:
============================================================
A2A COMPLIANCE REPORT
============================================================
Agent Name: your-agent
Total Tests: 5
Passed: 5
Failed: 0
Compliance: 100.0%
Status: ✅ FULLY COMPLIANT
```

### **Documentation**
📖 [**Full Documentation**](test_invoke()_protocol_compliance/Testing_agents_invoke().md)

---

## 🧪 **Test Suite 2: Executor execute() Compliance**

### **Purpose**
Verify that the executor properly handles A2A responses and integrates with Starlette.

### **Location**
```bash
cd unit_tests/test_execute()_starlette_compliance/
```

### **Quick Start**
```bash
# Run Starlette simulation test
python unit_test_starlette.py

# Run pytest tests
pytest mock_agent.py -v

# Manual testing
python manual_test_executor.py
```

### **What It Tests**
- ✅ **Task Management**: Proper task creation with unique IDs
- ✅ **State Transitions**: `working` → `completed`/`input_required`
- ✅ **Event Streaming**: Proper SSE event formatting
- ✅ **Artifact Creation**: Correct artifact handling on completion
- ✅ **Error Resilience**: Graceful error handling and recovery
- ✅ **Starlette Integration**: Ready for web application deployment

### **Example Output**
```
🧪 Testing GenericAgentExecutor with Starlette App
============================================================

🌐 Simulating Starlette Request
📨 Incoming Message: Hello, process this data
🚀 Executing agent: test-agent
📊 Status Update: working - Processing your request...
📦 Artifact Created: test-agent-result
✅ Task Completed: task-1234

📡 Streaming Events (what client receives):
  1. task_created: {...}
  2. status_update: {...}
  3. artifact: {...}
  4. task_complete: {...}
```

### **Documentation**
📖 [**Full Documentation**](test_execute()_starlette_compliance/Testing_execute()_starlette_compliance.md)

---

## 🚀 **Getting Started**

### **Step 1: Test Your Agent's invoke() Method**
```bash
cd unit_tests/test_invoke()_protocol_compliance/
python test_agent_a2a_compliance.py
```

**If tests fail:**
1. Check the error messages in the report
2. Fix your agent's `invoke()` method to return proper A2A format
3. Re-run the test until 100% compliant

### **Step 2: Test Executor Integration**
```bash
cd unit_tests/test_execute()_starlette_compliance/
python unit_test_starlette.py
```

**If tests fail:**
1. Verify your agent passes Step 1
2. Check executor state management
3. Verify proper event streaming

### **Step 3: Deploy with Confidence**
Once both test suites pass, your agent is ready for production deployment with full A2A protocol compliance.

---

## 📋 **A2A Protocol Requirements Summary**

### **Agent invoke() Method Must Return:**
```python
{
    "is_task_complete": bool,      # True = done, False = continue
    "require_user_input": bool,    # True = needs input, False = processing
    "content": str,                # Message content
    "hang_up": bool               # Optional: end conversation
}
```

### **Validation Rules:**
1. **Required Fields**: All 3 core fields must be present
2. **Type Safety**: Booleans must be booleans, strings must be strings
3. **Logic Consistency**: Cannot have both `is_task_complete=True` and `require_user_input=True`
4. **Optional Fields**: Additional fields like `hang_up`, `call_next_agent` are allowed

### **Executor Must Provide:**
1. **Task Creation**: Unique task and context IDs
2. **Status Updates**: Initial `working` → final state
3. **Artifact Creation**: Only on task completion
4. **Event Streaming**: Proper SSE format for Starlette
5. **Error Handling**: Graceful error recovery

---

## 🔧 **Common Issues and Solutions**

### **Agent invoke() Issues**

| Issue | Example | Solution |
|-------|---------|----------|
| Missing Fields | `{"message": "hello"}` | Add `is_task_complete`, `require_user_input`, `content` |
| Wrong Types | `{"is_task_complete": "yes"}` | Use `True`/`False` instead of strings |
| Logic Error | `{"is_task_complete": True, "require_user_input": True}` | Cannot both be `True` |

### **Executor Integration Issues**

| Issue | Symptom | Solution |
|-------|---------|----------|
| Missing Task Creation | No events generated | Create task with `new_task()` |
| No Initial Status | Client sees no progress | Send initial `working` status |
| Missing Artifacts | Completion without content | Create artifact before `complete()` |
| Poor Error Handling | Crashes on agent errors | Wrap `invoke()` in try/catch |

---

## 🎯 **Success Criteria**

### **Your Agent is A2A Compliant When:**
- ✅ All invoke() compliance tests pass (100%)
- ✅ All executor integration tests pass
- ✅ Proper state transitions in all scenarios
- ✅ Clean error handling and recovery
- ✅ Ready for Starlette deployment

### **Ready for Production:**
- ✅ Agent invoke() method is 100% compliant
- ✅ Executor handles all response types correctly
- ✅ Event streaming works properly
- ✅ Error scenarios are handled gracefully
- ✅ Performance is acceptable under load

---

## 📚 **Additional Resources**

### **Documentation Files**
- [`Testing_agents_invoke().md`](test_invoke()_protocol_compliance/Testing_agents_invoke().md) - Complete agent testing guide
- [`Testing_execute()_starlette_compliance.md`](test_execute()_starlette_compliance/Testing_execute()_starlette_compliance.md) - Complete executor testing guide

### **Test Files**
- [`test_agent_a2a_compliance.py`](test_invoke()_protocol_compliance/test_agent_a2a_compliance.py) - Agent compliance tester
- [`basic_executor.py`](test_invoke()_protocol_compliance/basic_executor.py) - Simplified executor for agent testing
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