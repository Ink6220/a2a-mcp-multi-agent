from a2a.server.tasks import TaskStore
from a2a.types import Task
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from a2a_mcp.common.types import ToolCall, ToolOutput
import copy

class MemoryManagement(TaskStore):
    """
    Context memory implementation that extends TaskStore
    to provide enhanced memory management for agent conversations and context.
    """
    
    def __init__(self):
        self.contexts: Dict[str, Dict[str, Task]] = {}
        self.lock = asyncio.Lock()

    async def save(self, task: Union[Task, Task]) -> None:
        """Saves or updates a task in the context-grouped store."""
    
        async with self.lock:
            context_id = task.contextId
            task_id = task.id

            if context_id not in self.contexts:
                self.contexts[context_id] = {}
            # save/update task ใน context
            self.contexts[context_id][task_id] = task
            print(f'Task {task_id} saved in context {context_id}')

    async def get_task_by_context_and_id(self, context_id: str, task_id: str) -> Optional[Task]:
        """Get a specific task by context ID and task ID."""
        async with self.lock:
            if context_id in self.contexts:
                return self.contexts[context_id].get(task_id)
            return None

    async def get_tasks_by_context(self, context_id: str) -> Dict[str, Task]:
        """Get all tasks for a specific context ID."""
        async with self.lock:
            if context_id in self.contexts:
                return self.contexts[context_id]
            return {}

    async def get(self, task_id: str) -> Optional[Task]:
        """Retrieves a task from any context by task ID."""
        async with self.lock:
            for context_id, tasks in self.contexts.items():
                if task_id in tasks:
                    return tasks[task_id]
            return None

    async def delete(self, task_id: str) -> None:
        """Deletes a task from all context stores."""
        async with self.lock:
            # หา task ใน contexts ทั้งหมด
            for context_id, tasks in list(self.contexts.items()):
                if task_id in tasks:
                    del tasks[task_id]
                    print(f'Task {task_id} removed from context {context_id}')
                    
                    # ถ้า context นี้ไม่มี task เหลือแล้ว ให้ลบ context ออก
                    if not tasks:
                        del self.contexts[context_id]
                        print(f'Empty context {context_id} removed')
                    break
    
    def get_all_contexts(self) -> List[str]:
        """Get all context IDs that have tasks."""
        return list(self.contexts.keys())
    
    def get_context_count(self) -> int:
        """Get the number of contexts."""
        return len(self.contexts)
    
    def get_task_count_by_context(self, context_id: str) -> int:
        """Get the number of tasks in a specific context."""
        return len(self.contexts.get(context_id, {}))
    
    async def get_all_context_tasks(self) -> Dict[str, Dict[str, Task]]:
        """
        Get a deep copy of all context tasks, This method is thread safe and returns a deep-copy
        This method is good enough to push to external databases
        Any changes here will not affect task store
        """
        async with self.lock:
            return copy.deepcopy(self.contexts)