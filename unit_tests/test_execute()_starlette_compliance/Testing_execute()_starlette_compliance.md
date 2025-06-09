# A2A Execute() Method Starlette Compliance Testing
## Ensuring Executor Output is A2A Compliant for Starlette Integration

### 🎯 **Objective**
Verify that the `GenericAgentExecutor.execute()` method produces A2A-compliant output that integrates seamlessly with Starlette web applications. This assumes the agent's `invoke()` method is already A2A compliant and focuses on testing the executor's state management and streaming capabilities.

---

## 🧪 **Testing Framework Overview**

### **Test Philosophy**
- ✅ **Agent invoke() is Correct**: We assume agent responses are already A2A compliant
- ✅ **Focus on Executor**: Test the executor's ability to handle A2A responses properly
- ✅ **Starlette Integration**: Ensure output format works with Starlette SSE streaming
- ✅ **State Management**: Verify proper task state transitions and event handling

### **Key Components**
1. **`mock_agent.py`**: A2A compliant mock agent with configurable responses
2. **`unit_test_starlette.py`**: Minimal test simulating Starlette integration
3. **`manual_test_executor.py`**: Manual testing utilities for debugging

---

## 🏗️ **Test Architecture**

### **1. MockAgent (`mock_agent.py`)**

A fully A2A-compliant mock agent that returns predictable responses for testing.

#### **Key Features:**
- ✅ **Configurable Responses**: Set exact response data for testing
- ✅ **A2A Compliant**: Always returns proper A2A format
- ✅ **Minimal Dependencies**: No external dependencies for testing
- ✅ **Multiple Scenarios**: Supports all A2A response types

#### **Usage Example:**
```python
# Test successful completion
mock_agent = MockAgent({
    "is_task_complete": True,
    "require_user_input": False,
    "content": "Task completed successfully!",
    "hang_up": False
})

# Test user input required
mock_agent = MockAgent({
    "is_task_complete": False,
    "require_user_input": True,
    "content": "Please provide more information.",
    "hang_up": False
})
```

### **2. Starlette Simulation (`unit_test_starlette.py`)**

A minimal simulation of how the executor would work in a Starlette application.

#### **Features:**
- ✅ **Mock A2A Components**: Simulated TaskUpdater, EventQueue, TaskState
- ✅ **Event Streaming**: Captures all streaming events for verification
- ✅ **Translation Layer Testing**: Tests agent response translation
- ✅ **Multiple Scenarios**: Covers all response types and edge cases

#### **Test Flow:**
1. **Request Simulation**: Mock incoming Starlette request
2. **Context Creation**: Create mock RequestContext
3. **Executor Execution**: Run GenericAgentExecutor.execute()
4. **Event Capture**: Collect all streaming events
5. **Verification**: Verify proper A2A compliance and state transitions

---

## 🚀 **How to Run Tests**

### **Method 1: Manual Testing (Recommended for Development)**
```bash
cd unit_tests/test_execute()_starlette_compliance
python unit_test_starlette.py
```

**Expected Output:**
```
🧪 Testing GenericAgentExecutor with Starlette App
============================================================

🌐 Simulating Starlette Request
📨 Incoming Message: Hello, process this data
🚀 Executing agent: test-agent
📝 User Query: Hello, process this data
🔄 Translation Layer Processing...
   Query: Hello, process this data
   Session: context-1234
   LLM Response: {...}
   A2A Response: {...}
🤖 Agent Response: {...}
📊 Status Update: working - Processing your request...
📦 Artifact Created: test-agent-result
✅ Task Completed: task-1234

📡 Streaming Events (what client receives):
  1. task_created: {...}
  2. status_update: {...}
  3. artifact: {...}
  4. task_complete: {...}
```

### **Method 2: Pytest Testing**
```bash
cd unit_tests/test_execute()_starlette_compliance
pytest mock_agent.py -v
```

### **Method 3: Manual Testing with Real Agent**
```bash
cd unit_tests/test_execute()_starlette_compliance  
python manual_test_executor.py
```

---

## 📋 **Test Scenarios Covered**

### **1. Successful Task Completion**
**Agent Response:**
```python
{
    "is_task_complete": True,
    "require_user_input": False,
    "content": "Task completed successfully!"
}
```

**Expected A2A Events:**
1. `task_created` - New task with unique ID
2. `status_update` - Initial "working" status
3. `artifact` - Result artifact with content
4. `task_complete` - Final completion event

**Verification Points:**
- ✅ Task created with unique `task_id` and `context_id`
- ✅ Initial `working` status sent to client
- ✅ Artifact created with `TextPart` content
- ✅ Task marked as complete

### **2. User Input Required**
**Agent Response:**
```python
{
    "is_task_complete": False,
    "require_user_input": True,
    "content": "Please provide more information."
}
```

**Expected A2A Events:**
1. `task_created` - New task with unique ID
2. `status_update` - Initial "working" status
3. `status_update` - Final "input_required" status with `final=True`

**Verification Points:**
- ✅ No artifact created (task not complete)
- ✅ No task completion event
- ✅ Final status marked as `input_required`
- ✅ Final status has `final=True` flag

### **3. Intermediate Working State**
**Agent Response:**
```python
{
    "is_task_complete": False,
    "require_user_input": False,
    "content": "Still processing..."
}
```

**Expected A2A Events:**
1. `task_created` - New task with unique ID
2. `status_update` - Initial "working" status
3. `status_update` - Additional "working" status with progress

**Verification Points:**
- ✅ Multiple working status updates
- ✅ No completion or final status
- ✅ Task remains active for further processing

### **4. Error Handling**
**Scenario:** Agent throws exception during invoke()

**Expected A2A Events:**
1. `task_created` - New task with unique ID
2. `status_update` - Initial "working" status
3. `status_update` - Error status as "input_required" with `final=True`

**Verification Points:**
- ✅ Graceful error handling
- ✅ Error message provided to user
- ✅ Task marked as requiring input (error state)

### **5. Delegation Scenario**
**Agent Response:**
```python
{
    "is_task_complete": True,
    "require_user_input": False,
    "content": "Delegating to specialist agent",
    "call_next_agent": True,
    "agent_name": "specialist-agent"
}
```

**Expected A2A Events:**
1. `task_created` - New task with unique ID
2. `status_update` - Initial "working" status
3. `artifact` - Delegation message
4. `task_complete` - Task completed (ready for delegation)

**Verification Points:**
- ✅ Delegation fields preserved in artifact
- ✅ Task marked as complete
- ✅ Ready for next agent in chain

---

## 🔧 **Mock Components**

### **MockTaskState**
```python
class MockTaskState:
    working = "working"
    input_required = "input_required"
    completed = "completed"
```

### **MockTaskUpdater**
```python
class MockTaskUpdater:
    def update_status(self, state, message, final=False):
        # Captures status update events
    
    def add_artifact(self, parts, name):
        # Captures artifact creation events
    
    def complete(self):
        # Captures task completion events
```

### **MockTextPart**
```python
class MockTextPart:
    def __init__(self, text: str):
        self.text = text
```

---

## 🎨 **Translation Layer Testing**

### **Your Agent Template (`YourTestAgent`)**

The test includes a template showing how to implement the translation layer between your LLM responses and A2A format.

#### **Translation Flow:**
1. **LLM Response**: Your agent's ResponseFormat (BaseModel)
2. **Translation Layer**: Convert to A2A + delegation superset
3. **A2A Output**: Properly formatted response for executor

#### **Example Translation:**
```python
def _translate_to_a2a(self, llm_response: Dict[str, Any]) -> Dict[str, Any]:
    # A2A Protocol fields
    a2a_response = {
        "is_task_complete": llm_response["status"] in ["completed", "hang_up"],
        "require_user_input": llm_response["status"] == "input_required", 
        "content": llm_response["message"],
        "hang_up": llm_response["status"] == "hang_up"
    }
    
    # Superset fields for delegation
    if llm_response.get("action") == "call_next_agent":
        a2a_response.update({
            "call_next_agent": True,
            "agent_name": llm_response.get("agent_name", ""),
            "delegation_reason": "specialist_required"
        })
    
    return a2a_response
```

---

## 🔍 **Starlette Integration Points**

### **1. Request Context**
```python
context = Mock()
context.get_user_input.return_value = user_message
context.current_task = None  # New request
context.message = Mock()
```

### **2. Event Queue for Streaming**
```python
event_queue = []  # Collects all streaming events
```

### **3. Executor Execution**
```python
executor = TestAgentExecutor(agent)
await executor.execute(context, event_queue)
```

### **4. Event Stream Processing**
```python
for event in event_queue:
    if event['type'] == 'status_update':
        # Handle status updates
    elif event['type'] == 'artifact':
        # Handle artifact creation
    elif event['type'] == 'task_complete':
        # Handle task completion
```

---

## 🚨 **Common Integration Issues**

### **1. Missing Task Creation**
```python
# ❌ WRONG - No task created
context.current_task = None
# Missing: event_queue.enqueue_event(task)

# ✅ CORRECT - Proper task creation
if not context.current_task:
    task = new_task(context.message)
    event_queue.enqueue_event(task)
```

### **2. Improper Status Transitions**
```python
# ❌ WRONG - Missing initial working status
result = await agent.invoke(query, session_id)
if result['is_task_complete']:
    updater.complete()

# ✅ CORRECT - Proper status flow
updater.update_status(TaskState.working, "Processing...")
result = await agent.invoke(query, session_id)
if result['is_task_complete']:
    updater.add_artifact([part], name="result")
    updater.complete()
```

### **3. Artifact Creation Issues**
```python
# ❌ WRONG - Missing artifact on completion
if result['is_task_complete']:
    updater.complete()  # No artifact!

# ✅ CORRECT - Artifact before completion
if result['is_task_complete']:
    part = TextPart(text=result['content'])
    updater.add_artifact([part], name=f'{agent.agent_name}-result')
    updater.complete()
```

---

## 📊 **Event Verification Checklist**

### **For Task Completion:**
- [ ] Task created with unique ID
- [ ] Initial `working` status sent
- [ ] Artifact created with proper content
- [ ] Task marked as complete
- [ ] No `input_required` status sent

### **For Input Required:**
- [ ] Task created with unique ID
- [ ] Initial `working` status sent
- [ ] Final `input_required` status with `final=True`
- [ ] No artifact created
- [ ] No task completion event

### **For Working State:**
- [ ] Task created with unique ID
- [ ] Initial `working` status sent
- [ ] Additional `working` status with progress
- [ ] No final status sent
- [ ] Task remains active

### **For Error Handling:**
- [ ] Task created with unique ID
- [ ] Initial `working` status sent
- [ ] Error handled gracefully
- [ ] `input_required` status with error message
- [ ] `final=True` flag set

---

## 🎯 **Success Criteria**

Your executor is Starlette-ready when:

- ✅ **Proper Task Management**: Creates tasks with unique IDs
- ✅ **Status Flow**: Initial working → appropriate final state
- ✅ **Artifact Handling**: Creates artifacts only on completion
- ✅ **Event Streaming**: All events properly formatted for SSE
- ✅ **Error Resilience**: Graceful handling of agent errors
- ✅ **State Consistency**: No contradictory states or missing transitions

---

## 🚀 **Next Steps**

### **1. Run the Tests**
```bash
python unit_test_starlette.py
```

### **2. Verify All Scenarios Pass**
Check that all 4 test scenarios complete successfully:
- ✅ Successful completion
- ✅ User input required  
- ✅ Agent delegation
- ✅ Error handling

### **3. Test with Your Agent**
Replace `YourTestAgent` with your actual agent implementation and verify the translation layer works correctly.

### **4. Deploy to Starlette**
Once all tests pass, your executor is ready for integration with your Starlette application.

---

## 📝 **Integration Template**

Use this template for integrating with your Starlette app:

```python
from starlette.responses import StreamingResponse
from your_agent import YourAgent
from src.a2a_mcp.common.agent_executor import GenericAgentExecutor

async def handle_message(request):
    # Extract message from request
    data = await request.json()
    user_message = data.get('message')
    
    # Create context
    context = create_request_context(user_message)
    
    # Create event queue for streaming
    event_queue = EventQueue()
    
    # Create and execute
    agent = YourAgent()
    executor = GenericAgentExecutor(agent)
    
    # Execute in background
    asyncio.create_task(executor.execute(context, event_queue))
    
    # Stream events to client
    async def event_stream():
        async for event in event_queue:
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 🎉 **Ready for Production**

When all tests pass, your executor provides:

- ✅ **A2A Protocol Compliance**: Full adherence to A2A specifications
- ✅ **Starlette Integration**: Seamless SSE streaming support
- ✅ **Error Resilience**: Graceful handling of all edge cases
- ✅ **State Management**: Proper task lifecycle management
- ✅ **Event Streaming**: Real-time updates to clients
- ✅ **Delegation Support**: Ready for multi-agent workflows 