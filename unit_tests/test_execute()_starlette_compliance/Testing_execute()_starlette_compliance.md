# A2A Execute() Method Starlette Compliance Testing
## Testing New Executor Logic with ResponseFormat Objects

### 🎯 **Objective**
Test a **new `execute()` method** that properly handles `ResponseFormat` objects returned by agents and produces A2A-compliant output for Starlette web applications. This testing assumes that all agent `invoke()` methods are correct and focuses purely on **executor logic validation**.

---

## 🧪 **Testing Framework Overview**

### **Test Philosophy**
- ✅ **Agent invoke() is Always Correct**: All agents return proper `ResponseFormat` objects
- ✅ **Focus on Executor Logic**: Test how the executor translates `ResponseFormat` → A2A events
- ✅ **Starlette Integration**: Ensure output format works with Starlette SSE streaming
- ✅ **Forward-Looking Architecture**: Design and test the future executor implementation

### **Key Components**
1. **`mock_agent.py`**: ResponseFormat-compliant mock agents with configurable responses
2. **`unit_test_starlette.py`**: Complete test simulating Starlette integration with new executor

---

## 🏗️ **Test Architecture**

### **1. MockAgent with `ResponseFormat` (`mock_agent.py`)**

A fully xPResponseFormat-compliant mock agent that returns predictable objects for testing.

#### **Key Features:**
- ✅ **Returns `ResponseFormat` Objects**: Guarantees type-safe, structured output
- ✅ **Configurable Scenarios**: Pre-configured agents for completion, input required, delegation, and errors
- ✅ **A2A Compliant**: Always returns objects with proper A2A attributes (`action`, `status`, `message`)
- ✅ **Minimal Dependencies**: Self-contained for easy testing

#### **Usage Example:**
```python
from mock_agent import get_completion_agent, get_input_required_agent

# Get an agent that simulates successful completion
completion_agent = get_completion_agent()

# Get an agent that simulates needing user input
input_agent = get_input_required_agent()
```

### **2. New Executor Testing (`unit_test_starlette.py`)**

Tests a new `TestAgentExecutor` that demonstrates the ideal architecture for handling `ResponseFormat` objects.

#### **Features:**
- ✅ **Mock A2A Components**: Simulates `TaskUpdater`, `EventQueue`, `TaskState`
- ✅ **Event Streaming Capture**: Captures all streaming events for verification
- ✅ **ResponseFormat Handling**: Tests how the executor processes `ResponseFormat` objects
- ✅ **Multiple Scenarios**: Covers all response types and edge cases

#### **Test Flow:**
1. **Get Mock Agent**: Select the mock agent for the desired scenario (e.g., `get_completion_agent()`)
2. **Simulate Request**: Mock an incoming Starlette request
3. **Execute**: Run `TestAgentExecutor.execute()` with the mock agent
4. **Capture Events**: Collect all streaming events from the mock event queue
5. **Verify**: Check for proper A2A compliance and state transitions

---

## 🚀 **How to Run Tests**

### **Run New Executor Tests**
This runs through all test scenarios using ResponseFormat-compliant mock agents.
```bash
cd unit_tests/test_execute()_starlette_compliance
python unit_test_starlette.py
```

**Expected Output:**
```
🧪 Testing Executor with ResponseFormat Objects
============================================================
✅ Scenario: Successful Task Completion -- PASSED
✅ Scenario: User Input Required -- PASSED
✅ Scenario: Task Failed -- PASSED
✅ Scenario: Agent Delegation -- PASSED
✅ Scenario: Graceful Error Handling -- PASSED
============================================================
🎉 All executor test scenarios passed!
```

---

## 📋 **Test Scenarios Covered**

### **1. Successful Task Completion**
- **Agent Returns**: `ResponseFormat(action="answer", status="completed", ...)`
- **Expected Events**: `task_created` → `status_update(working)` → `artifact` → `task_complete`
- **Verification**: Artifact is created from the `ResponseFormat` object, and task is marked complete

### **2. User Input Required**
- **Agent Returns**: `ResponseFormat(action="answer", status="input_required", ...)`
- **Expected Events**: `task_created` → `status_update(working)` → `status_update(input_required)`
- **Verification**: No artifact is created, and the final status is `input_required`

### **3. Task Failed**
- **Agent Returns**: `ResponseFormat(action="answer", status="failed", ...)`
- **Expected Events**: `task_created` → `status_update(working)` → `status_update(failed)`
- **Verification**: Task is marked as failed with appropriate error handling

### **4. Agent Delegation**
- **Agent Returns**: `ResponseFormat(action="call_next_agent", status="input_required", ...)`
- **Expected Events**: `task_created` → `status_update(working)` → `status_update(input_required, final=True)`
- **Verification**: The message is passed up to the user (CLI client) with state `input_required`. Only after the delegated agent (expert) returns and the original agent finishes, the executor emits `completed`.

#### **Usage Example:**
```python
from mock_agent import get_delegation_agent
# Get an agent that simulates delegation (input_required)
delegation_agent = get_delegation_agent()
```

#### **State Mapping:**
- `action="call_next_agent"` (with `status="input_required"`) → `input_required` (delegation, message passed up)
- `status="completed"` (and not delegation) → Task completes, artifact created
- `status="input_required"` (and not delegation) → Task pauses, awaiting user input
- `status="failed"` → Task fails, error handling

### **5. Error Handling**
- **Agent Action**: `invoke()` raises an exception
- **Expected Events**: `task_created` → `status_update(working)` → `status_update(input_required)`
- **Verification**: Executor catches the error and sets an `input_required` status with an error message

---

## 🔧 **New Executor's Role with `ResponseFormat`**

The new executor is the bridge between the agent's `ResponseFormat` object and the A2A event stream.

#### **Translation Flow:**
1. **Agent `invoke()`**: Returns a `ResponseFormat` object
2. **Executor Receives Object**: The `execute` method gets this object
3. **Executor Reads Attributes**: It accesses attributes like `response.status` and `response.action` to decide the next state
4. **Delegation**: If `action="call_next_agent"`, the executor emits `input_required` and passes the message up to the user. Only after the expert returns and the original agent finishes does it emit `completed`.
5. **Executor Creates Artifact**: It uses the `ResponseFormat` object (or its dictionary representation) as the payload for `updater.add_artifact()` (on completion)
6. **A2A Events**: The executor generates the standard A2A event stream for the client

#### **State Mapping:**
- `action="call_next_agent"` (with `status="input_required"`) → `input_required` (delegation, message passed up)
- `status="completed"` (and not delegation) → Task completes, artifact created
- `status="input_required"` (and not delegation) → Task pauses, awaiting user input
- `status="failed"` → Task fails, error handling

This architecture ensures that the agent's internal logic is cleanly separated from the A2A protocol implementation, with the `ResponseFormat` object serving as the contract.

---

## 🎯 **Design Principles for New Executor**

### **Core Assumptions**
1. **All agents return proper `ResponseFormat` objects** - No need to test agent compliance
2. **Focus on executor logic** - How to translate `ResponseFormat` → A2A events
3. **Starlette compatibility** - Events must work with SSE streaming
4. **Error resilience** - Graceful handling of unexpected scenarios

### **Key Benefits of This Approach**
- ✅ **Clean Architecture**: `ResponseFormat` provides clear contract between agent and executor
- ✅ **Easy Testing**: Mock agents with predictable responses
- ✅ **Type Safety**: Pydantic validation ensures correct object structure
- ✅ **Simplified Debugging**: Focus only on executor logic, not agent behavior
- ✅ **Future-Proof**: Ready for new agent implementations

---

## 🚨 **Common Integration Issues to Avoid**

### **1. Incorrect State Mapping**
- **Issue**: Wrong A2A status for `ResponseFormat.status`
- **Solution**: Follow the state mapping exactly (`completed` → artifact + complete, etc.)

### **2. Missing Artifact Content**
- **Issue**: Empty or malformed artifacts
- **Solution**: Always use `ResponseFormat.message` as artifact content

### **3. Delegation Field Handling**
- **Issue**: Missing delegation information in artifacts
- **Solution**: Preserve all `ResponseFormat` fields in delegation artifacts

### **4. Exception Handling**
- **Issue**: Unhandled agent exceptions crash the executor
- **Solution**: Wrap `agent.invoke()` in try-catch and return appropriate A2A status

---

## 🎯 **Success Criteria**

Your new executor is ready when:
- ✅ **Handles `ResponseFormat`**: Correctly processes `ResponseFormat` objects from agents
- ✅ **Correct State Transitions**: Enters the correct state based on `status` field
- ✅ **Proper Artifacts**: Creates meaningful artifacts from `ResponseFormat` objects on completion
- ✅ **Event Streaming**: Generates correct A2A event stream for all scenarios
- ✅ **Error Resilience**: Gracefully handles exceptions from agent `invoke()` method
- ✅ **Delegation Support**: Properly handles delegation scenarios with all required fields

When all tests in `unit_test_starlette.py` pass, your executor is confirmed to be compliant and ready for integration.

---

## 🚀 **Next Steps**

### **1. Run the Tests**
```bash
python unit_test_starlette.py
```

### **2. Verify All Scenarios Pass**
Check that all 5 test scenarios complete successfully

### **3. Implement Your Real Executor**
Use the `TestAgentExecutor` in `unit_test_starlette.py` as a reference for implementing your actual executor

### **4. Deploy to Starlette**
Once all tests pass, your executor is ready for integration with your Starlette application

---

## 📝 **Integration Template**

Use this template for integrating with your Starlette app:

```python
from starlette.responses import StreamingResponse
from your_agent import YourAgent
from your_new_executor import YourNewExecutor  # Based on TestAgentExecutor

async def handle_message(request):
    # Extract message from request
    data = await request.json()
    user_message = data.get('message')
    
    # Create context
    context = create_request_context(user_message)
    
    # Create event queue for streaming
    event_queue = EventQueue()
    
    # Create and execute
    agent = YourAgent()  # Returns ResponseFormat objects
    executor = YourNewExecutor(agent)
    
    # Execute in background
    asyncio.create_task(executor.execute(context, event_queue))
    
    # Stream events to client
    async def event_stream():
        async for event in event_queue:
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 🎉 **Ready for Development**

This testing framework provides:

- ✅ **Clear Architecture**: ResponseFormat-based design
- ✅ **Comprehensive Testing**: All A2A scenarios covered
- ✅ **Starlette Compliance**: Event streaming validated
- ✅ **Development Guidance**: Reference implementation provided
- ✅ **Error Handling**: Exception scenarios tested

Focus on implementing your new executor using `TestAgentExecutor` as a guide, and the tests will ensure A2A compliance! 