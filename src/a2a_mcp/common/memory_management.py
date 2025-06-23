from a2a.server.tasks import TaskStore
from a2a.types import Task
import asyncio
import logging
from typing import Dict, Any, Optional, List, Union
from a2a_mcp.common.types import ToolCall, ToolOutput
import copy

class ManageTask(Task):
    tool_calls: Optional[List[ToolCall]]
    tool_outputs: Optional[List[ToolOutput]]
    
    @classmethod
    def from_task(cls, task: Task) -> 'ManageTask':
        """Create ManageTask from regular Task."""
        return cls(
            id=task.id,
            contextId=task.contextId,
            status=task.status,
            kind=task.kind,
            history=task.history,
            artifacts=task.artifacts,
            metadata=task.metadata,
            tool_calls=None,
            tool_outputs=None
        )

class MemoryManagement(TaskStore):
    """
    Context memory implementation that extends TaskStore
    to provide enhanced memory management for agent conversations and context.
    """
    
    def __init__(self):
        self.contexts: Dict[str, Dict[str, ManageTask]] = {}
        self.lock = asyncio.Lock()

    async def save(self, task: Union[Task, ManageTask]) -> None:
        """Saves or updates a task in the context-grouped store."""
        # Convert Task to ManageTask if needed
        if isinstance(task, Task) and not isinstance(task, ManageTask):
            manage_task = ManageTask.from_task(task)
        else:
            manage_task = task
            
        # save ตาม context_id ใน self.contexts
        async with self.lock:
            context_id = manage_task.contextId
            task_id = manage_task.id
            
            if context_id not in self.contexts:
                self.contexts[context_id] = {}
            # save/update task ใน context
            self.contexts[context_id][task_id] = manage_task
            print(f'Task {task_id} saved in context {context_id}')

    async def get_tasks_by_context(self, context_id: str) -> Dict[str, ManageTask]:
        """Get all tasks for a specific context ID."""
        async with self.lock:
            if context_id in self.contexts:
                return self.contexts[context_id]
            return {}

    async def get(self, task_id: str) -> Optional[ManageTask]:
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
    
    async def get_all_context_tasks(self) -> Dict[str, Dict[str, ManageTask]]:
        """
        Get a deep copy of all context tasks, This method is thread safe and returns a deep-copy
        This method is good enough to push to external databases
        Any changes here will not affect task store
        """
        async with self.lock:
            return copy.deepcopy(self.contexts)