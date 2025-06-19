from pydantic import BaseModel, Field
from typing import List, Dict, Any
from a2a.types import (
    Task
)


class ContextMemory(BaseModel):
    """Class for storing context memory with task IDs"""
    
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    task_tools: Dict[str, Dict[str, Any]] = Field(default_factory=dict, description="Tool calls and outputs by task ID")
    
    @property
    def size(self) -> int:
        """Get the number of tasks in the context"""
        return len(self.tasks)
    
    def add_task(self, task: Task) -> None:
        """Add a task to the task list"""
        self.tasks.append(task)
    
    def get_task(self, task_id: str) -> Task | None:
        """Get a task from the task list by task ID
        
        Args:
            task_id: The ID of the task to retrieve
            
        Returns:
            Task | None: The task if found, None otherwise
        """
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def update_task(self, task_id: str, updated_task: Task) -> bool:
        """Update a task in the task list by task ID
        
        Args:
            task_id: The ID of the task to update
            updated_task: The new task object to replace the existing one
            
        Returns:
            bool: True if task was found and updated, False otherwise
        """
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks[i] = updated_task
                return True
        return False
    
    def update_task_tools(self, task_id: str, tool_calls: List[Any], tool_outputs: List[Any]) -> None:
        """Update tool information for a specific task
        
        Args:
            task_id: The ID of the task
            tool_calls: List of tool calls
            tool_outputs: List of tool outputs
        """
        self.task_tools[task_id] = {
            "tool_calls": tool_calls,
            "tool_outputs": tool_outputs
        }
    
    def get_task_tools(self, task_id: str) -> Dict[str, Any] | None:
        """Get tool information for a specific task
        
        Args:
            task_id: The ID of the task
            
        Returns:
            Dict containing tool_calls and tool_outputs, or None if not found
        """
        return self.task_tools.get(task_id)
    
    def has_task_tools(self, task_id: str) -> bool:
        """Check if task has tool information
        
        Args:
            task_id: The ID of the task
            
        Returns:
            bool: True if task has tool information
        """
        return task_id in self.task_tools

    def __len__(self) -> int:
        """Return the size of the context memory
        
        Returns:
            int: Number of tasks in the context
        """
        return self.size