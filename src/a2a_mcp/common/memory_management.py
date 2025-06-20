from a2a.server.tasks import InMemoryTaskStore
from a2a.types import Task
import logging
from typing import Dict, Any, Optional, List, Union
from a2a_mcp.common.base_agent.base_agent import ToolCall, ToolOutput
from pydantic import BaseModel, Field
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

class MemoryManagement(InMemoryTaskStore):
    """
    Context memory implementation that extends InMemoryTaskStore
    to provide enhanced memory management for agent conversations and context.
    """
    
    def __init__(self):
        super().__init__()
        self.contexts: Dict[str, Dict[str, ManageTask]] = {}

    async def save(self, task: Union[Task, ManageTask]) -> None:
        """Saves or updates a task in both the main store and context-grouped store."""
        # Convert Task to ManageTask if needed
        if isinstance(task, Task) and not isinstance(task, ManageTask):
            manage_task = ManageTask.from_task(task)
        else:
            manage_task = task
            
        # เรียก parent save method เพื่อ save ใน self.tasks
        await super().save(manage_task)
        
        # save ตาม context_id ใน self.context_tasks
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
    
    async def get_task_by_context_and_id(self, context_id: str, task_id: str) -> Optional[Task]:
        """Get a specific task by context ID and task ID."""
        async with self.lock:
            if context_id in self.contexts:
                return self.contexts[context_id].get(task_id)
            return None
    
    async def delete_from_context(self, task_id: str, context_id: str) -> bool:
        """Delete a task from a specific context. Returns True if task was found and deleted."""
        async with self.lock:
            if context_id in self.contexts and task_id in self.contexts[context_id]:
                del self.contexts[context_id][task_id]
                print('Task %s removed from context %s', task_id, context_id)
                
                # ถ้า context นี้ไม่มี task เหลือแล้ว ให้ลบ context ออก
                if not self.contexts[context_id]:
                    del self.contexts[context_id]
                    print('Empty context %s removed', context_id)
                return True
            return False
    
    async def delete(self, task_id: str) -> None:
        """Deletes a task from both the main store and all context stores."""
        # ก่อนลบจาก main store ให้หา context_id ของ task นี้
        task = await self.get(task_id)
        
        # ลบจาก main store
        await super().delete(task_id)
          # ลบจาก contexts ถ้า task มีอยู่
        if task:
            async with self.lock:
                context_id = task.contextId
                if context_id in self.contexts and task.id in self.contexts[context_id]:
                    del self.contexts[context_id][task.id]
                    # ถ้า context นี้ไม่มี task เหลือแล้ว ให้ลบ context ออก
                    if not self.contexts[context_id]:
                        del self.contexts[context_id]
                        print('Empty context %s removed', context_id)

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
        Get a deep copy of all context tasks, This method is thread safe and returns a copy
        This method is good enough to push to external databases
        """
        async with self.lock:
            return copy.deepcopy(self.contexts)