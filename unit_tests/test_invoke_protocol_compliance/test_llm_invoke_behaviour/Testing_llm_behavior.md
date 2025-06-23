# LLM Behavior Testing Framework
## State Validation and Field Relationship Testing

### 🎯 **Objective**
Validate that an LLM agent's `invoke()` method produces responses with correct state transitions and field relationships, regardless of the actual content. This test suite focuses on:

1. **State Transitions**: Proper action and status combinations
2. **Field Relationships**: Required and forbidden fields for each state
3. **Behavioral Consistency**: Consistent responses across different scenarios
4. **Field Validation**: Proper field values and relationships
5. **Error States**: Proper handling of error conditions

---

## 🏗️ **Architecture: Test Scenarios**

The framework is built around predefined test scenarios that validate different aspects of LLM behavior. Each scenario tests a specific state combination and field relationship.

### **1. Test Scenario Structure:**
```python
TEST_SCENARIOS = [
    {
        "name": "Basic Answer State",
        "query": "Tell me a joke",
        "expected_state": {
            "action": "answer",
            "status": "completed",
            "required_fields": ["message"],
            "forbidden_fields": ["agent_name", "next_agent_instruction"]
        }
    },
    # ... more scenarios
]
```

### **2. Core Test Scenarios:**

#### **Basic Answer State**
- Tests simple completion responses
- Validates basic field requirements
- Ensures no delegation fields are present

#### **Delegation State**
- Tests agent delegation behavior
- Validates presence of required delegation fields
- Ensures proper field relationships

#### **Input Required State**
- Tests user interaction requests
- Validates proper status setting
- Ensures appropriate field presence/absence

#### **Failed State**
- Tests error handling
- Validates error status and messages
- Ensures proper error state fields

#### **Artifact State**
- Tests artifact generation
- Validates artifact field requirements
- Ensures proper artifact structure

---

## 🧪 **Testing Framework (`test_llm_behavior.py`)**

The test framework provides comprehensive state and field validation:

#### **Key Features:**
- ✅ **State Validation**: Verifies correct action/status combinations
- ✅ **Field Validation**: Checks required and forbidden fields
- ✅ **Relationship Testing**: Validates field dependencies
- ✅ **Error Detection**: Identifies invalid state combinations
- ✅ **Detailed Reporting**: Provides comprehensive test results
- ✅ **Scenario Coverage**: Tests all major behavioral states
- ✅ **Field Requirements**: Validates field value constraints

### **Core Components:**

#### **1. LLMBehaviorTester Class**
The main testing framework:
```python
class LLMBehaviorTester:
    @staticmethod
    def validate_response_state(response: ResponseFormat, expected_state: Dict) -> Dict[str, Any]:
        """Validate response state and field relationships"""
        # Validation logic
        
    @staticmethod
    async def test_llm_behavior(agent: Any) -> Dict[str, Any]:
        """Run state transition tests on an LLM agent"""
        # Test execution logic
```

#### **2. Test Result Structure**
Comprehensive test results format:
```python
results = {
    'agent_name': agent.agent_name,
    'total_tests': len(TEST_SCENARIOS),
    'passed_tests': count,
    'failed_tests': [
        {
            'scenario': name,
            'query': query,
            'issues': [issue_details],
            'response': response_state
        }
    ],
    'status': 'PASSED' | 'FAILED'
}
```

---

## 🚀 **How to Run Tests**

### **1. Direct Test Execution**
Run the test suite with your LLM agent:
```bash
cd unit_tests/test_invoke()_protocol_compliance
python test_llm_behavior.py
```

### **2. Test Your Own Agent**
Integrate the test suite with your LLM agent:
```python
import asyncio
from test_llm_behavior import LLMBehaviorTester, print_behavior_report
from your_llm_agent import YourLLMAgent

async def test_your_agent():
    agent = YourLLMAgent()
    results = await LLMBehaviorTester.test_llm_behavior(agent)
    print_behavior_report(results)

if __name__ == "__main__":
    asyncio.run(test_your_agent())
```

---

## 🎨 **Example Implementation**

### **Compliant LLM Agent:**
```python
class CompliantLLMAgent:
    agent_name = "compliant-llm-agent"
    
    async def invoke(self, query: str, context_id: str, task_id: str, history: str) -> ResponseFormat:
        # Basic answer state
        if "joke" in query.lower():
            return ResponseFormat(
                action="answer",
                status="completed",
                message="Here's a joke..."
            )
            
        # Delegation state
        if "python" in query.lower():
            return ResponseFormat(
                action="call_next_agent",
                status="completed",
                message="Delegating to Python expert",
                agent_name="python-expert",
                next_agent_instruction="Write Python code for the request"
            )
            
        # Input required state
        if "favorite" in query.lower():
            return ResponseFormat(
                action="answer",
                status="input_required",
                message="Could you be more specific?"
            )
            
        # Failed state
        if "fail" in query.lower():
            return ResponseFormat(
                action="answer",
                status="failed",
                message="Operation failed",
                custom_status="test_failure"
            )
            
        # Artifact state
        if "report" in query.lower():
            return ResponseFormat(
                action="answer",
                status="completed",
                message="Generated report",
                artifacts="[{\"type\": \"report\", \"content\": \"...\"}]"
            )
```

---

## 🚨 **Common Issues & Solutions**

### **1. Inconsistent State Transitions**
- **Issue:** Agent returns invalid action/status combinations
- **Solution:** Follow the state matrix:
```python
VALID_STATES = {
    "answer": ["completed", "input_required", "failed"],
    "call_next_agent": ["completed"]
}
```

### **2. Missing Required Fields**
- **Issue:** Required fields absent in specific states
- **Solution:** Check state requirements:
```python
if action == "call_next_agent":
    # Include delegation fields
    response.agent_name = "target-agent"
    response.next_agent_instruction = "instruction"
```

### **3. Invalid Field Combinations**
- **Issue:** Conflicting or inappropriate fields
- **Solution:** Follow field relationship rules:
```python
# Don't include delegation fields in answer states
if action == "answer":
    agent_name = None
    next_agent_instruction = None
```

### **4. Inconsistent Error States**
- **Issue:** Improper error handling
- **Solution:** Use proper error state format:
```python
return ResponseFormat(
    action="answer",
    status="failed",
    message="Error description",
    custom_status="error_type"
)
```

---

## 🎯 **Success Criteria**

Your LLM agent passes behavior testing when:
- ✅ **State Consistency**: All state transitions are valid
- ✅ **Field Compliance**: Required fields present, forbidden fields absent
- ✅ **Error Handling**: Proper error states and messages
- ✅ **Delegation Logic**: Correct delegation field handling
- ✅ **Artifact Management**: Proper artifact field usage
- ✅ **Test Coverage**: All test scenarios pass
- ✅ **Field Relationships**: Correct field dependencies maintained

---

## 📊 **Test Coverage Matrix**

| State Type | Action | Status | Required Fields | Optional Fields |
|------------|---------|---------|-----------------|-----------------|
| Basic Answer | answer | completed | message | custom_status |
| Delegation | call_next_agent | completed | message, agent_name, next_agent_instruction | custom_status |
| Input Required | answer | input_required | message | - |
| Failed | answer | failed | message | custom_status |
| Artifact | answer | completed | message, artifacts | custom_status |

This comprehensive testing ensures your LLM agent maintains consistent behavior and proper state management across all scenarios. 