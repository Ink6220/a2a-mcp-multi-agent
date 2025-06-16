from pydantic import BaseModel, Field
from typing import List
from a2a.types import (
    Task
)


class ContextMemory(BaseModel):
    """Class for storing context memory with task IDs"""
    
    tasks: List[Task] = Field(default_factory=list, description="List of tasks")
    
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
    
    def __len__(self) -> int:
        """Return the size of the context memory
        
        Returns:
            int: Number of tasks in the context
        """
        return self.size