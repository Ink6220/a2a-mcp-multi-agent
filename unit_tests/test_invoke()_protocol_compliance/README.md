# A2A Protocol invoke() Compliance Testing

## 🎯 Overview

This directory contains tests for validating agent `invoke()` compliance with the A2A protocol:

1. **Type Compliance**: Ensures responses are valid `ResponseFormat` objects
2. **Behavioral Testing**: Validates LLM responses are semantically appropriate

## 📁 Files

| File | Purpose |
|------|---------|
| `test_agent_a2a_compliance.py` | Basic type and structure validation |
| `test_llm_behavior.py` | Semantic validation of LLM responses |
| `README.md` | This overview and quick start guide |

## 🚀 Quick Start

### Run Tests
```bash
# Navigate to test directory
cd unit_tests/test_invoke\(\)_protocol_compliance

# Run type compliance tests
python test_agent_a2a_compliance.py

# Run LLM behavior tests
python test_llm_behavior.py
```

### Expected Output
```
🧪 LLM BEHAVIOR TEST REPORT
==================================================
Agent Name: example-llm-agent
Status: PASSED
Tests Passed: 4/4

# Test scenarios include:
- Simple questions (expect direct answers)
- Code requests (expect proper delegation)
- Ambiguous queries (expect clarifying questions)
- Technical requests (expect specialized delegation)
```

## 🧪 Testing Your Agent

### 1. Type Compliance Test
```python
from test_agent_a2a_compliance import A2AComplianceTester

async def test_my_agent():
    results = await A2AComplianceTester.test_agent_invoke_compliance(your_agent)
    return results['status'] == 'PASSED'
```

### 2. Behavioral Test
```python
from test_llm_behavior import LLMBehaviorTester

async def test_my_agent():
    results = await LLMBehaviorTester.test_llm_behavior(your_agent)
    return results['status'] == 'PASSED'
```

## ✅ Success Criteria

### Type Compliance
1. Returns `ResponseFormat` instance
2. Required fields present and valid
3. Delegation fields included when needed

### Behavioral Compliance
1. Appropriate action selection
2. Contextually relevant responses
3. Proper delegation with clear instructions
4. Clarifying questions for ambiguous queries

## 🏗️ ResponseFormat Structure

```python
class ResponseFormat(BaseModel):
    # Required fields
    action: Literal["answer", "call_next_agent"]
    status: Literal["input_required", "completed", "failed"]
    message: str
    
    # Optional fields
    custom_status: Optional[str] = None
    agent_name: Optional[str] = None
    next_agent_instruction: Optional[str] = None
    artifacts: Optional[str] = None
```

## 🚨 Common Issues

### Invalid Response Type
```python
# ❌ WRONG
return {"action": "answer", "status": "completed", "message": "..."}

# ✅ CORRECT  
return ResponseFormat(action="answer", status="completed", message="...")
```

### Poor Delegation Instructions
```python
# ❌ WRONG - Vague instruction
return ResponseFormat(
    action="call_next_agent",
    status="completed",
    message="Delegating...",
    agent_name="code-agent",
    next_agent_instruction="Help with code"  # Too vague
)

# ✅ CORRECT - Clear instruction
return ResponseFormat(
    action="call_next_agent",
    status="completed",
    message="Delegating to Python specialist",
    agent_name="python-agent",
    next_agent_instruction="Help debug the Python script that's raising a TypeError in the list comprehension"
)
``` 