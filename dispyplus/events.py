"""
Custom event handling utilities for Discord bots.
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Union
from datetime import datetime
import discord


class CustomEvent:
    """
    Represents a custom event that can be dispatched and handled.
    """
    
    def __init__(self, name: str, **kwargs):
        self.name = name
        self.data = kwargs
        self.timestamp = datetime.utcnow()
        self.cancelled = False
    
    def cancel(self) -> None:
        """Cancel this event."""
        self.cancelled = True
    
    def is_cancelled(self) -> bool:
        """Check if this event is cancelled."""
        return self.cancelled
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get event data by key."""
        return self.data.get(key, default)
    
    def __getitem__(self, key: str) -> Any:
        """Get event data by key using bracket notation."""
        return self.data[key]
    
    def __setitem__(self, key: str, value: Any) -> None:
        """Set event data by key using bracket notation."""
        self.data[key] = value
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists in event data."""
        return key in self.data


class EventHandler:
    """
    Enhanced event handler that supports custom events, priorities, and conditions.
    """
    
    def __init__(self, bot: discord.Client = None):
        self.bot = bot
        self._listeners: Dict[str, List[Dict[str, Any]]] = {}
        self._middleware: List[Callable] = []
    
    def listen(
        self,
        event_name: str = None,
        *,
        priority: int = 0,
        condition: Callable = None,
        once: bool = False
    ):
        """
        Decorator to register an event listener.
        
        Args:
            event_name: Name of the event to listen for
            priority: Priority of the listener (higher = executed first)
            condition: Optional condition function that must return True
            once: Whether to remove the listener after first execution
        """
        def decorator(func: Callable):
            nonlocal event_name
            if event_name is None:
                event_name = func.__name__
            
            listener_info = {
                'func': func,
                'priority': priority,
                'condition': condition,
                'once': once,
                'executed': False
            }
            
            if event_name not in self._listeners:
                self._listeners[event_name] = []
            
            self._listeners[event_name].append(listener_info)
            # Sort by priority (higher first)
            self._listeners[event_name].sort(key=lambda x: x['priority'], reverse=True)
            
            return func
        
        return decorator
    
    def add_middleware(self, middleware: Callable) -> None:
        """
        Add middleware that runs before all event handlers.
        
        Args:
            middleware: Middleware function that receives (event_name, *args, **kwargs)
        """
        self._middleware.append(middleware)
    
    async def dispatch(self, event_name: str, *args, **kwargs) -> CustomEvent:
        """
        Dispatch a custom event to all registered listeners.
        
        Args:
            event_name: Name of the event to dispatch
            *args: Positional arguments to pass to listeners
            **kwargs: Keyword arguments to pass to listeners
            
        Returns:
            The CustomEvent object that was dispatched
        """
        event = CustomEvent(event_name, args=args, kwargs=kwargs)
        
        # Run middleware first
        for middleware in self._middleware:
            try:
                result = await middleware(event_name, event, *args, **kwargs)
                if result is False or event.is_cancelled():
                    return event
            except Exception as e:
                print(f"Error in middleware: {e}")
        
        # Get listeners for this event
        listeners = self._listeners.get(event_name, [])
        to_remove = []
        
        for i, listener_info in enumerate(listeners):
            if listener_info['once'] and listener_info['executed']:
                to_remove.append(i)
                continue
            
            # Check condition if provided
            if listener_info['condition']:
                try:
                    if not await self._call_condition(listener_info['condition'], event, *args, **kwargs):
                        continue
                except Exception as e:
                    print(f"Error in event condition: {e}")
                    continue
            
            # Call the listener
            try:
                await self._call_listener(listener_info['func'], event, *args, **kwargs)
                listener_info['executed'] = True
                
                if event.is_cancelled():
                    break
                    
            except Exception as e:
                print(f"Error in event listener {listener_info['func'].__name__}: {e}")
        
        # Remove one-time listeners that have been executed
        for i in reversed(to_remove):
            listeners.pop(i)
        
        return event
    
    async def _call_condition(self, condition: Callable, event: CustomEvent, *args, **kwargs) -> bool:
        """Call a condition function, handling both sync and async."""
        if asyncio.iscoroutinefunction(condition):
            return await condition(event, *args, **kwargs)
        else:
            return condition(event, *args, **kwargs)
    
    async def _call_listener(self, func: Callable, event: CustomEvent, *args, **kwargs) -> None:
        """Call a listener function, handling both sync and async."""
        if asyncio.iscoroutinefunction(func):
            await func(event, *args, **kwargs)
        else:
            func(event, *args, **kwargs)
    
    def remove_listener(self, event_name: str, func: Callable) -> bool:
        """
        Remove a specific listener function.
        
        Args:
            event_name: Name of the event
            func: The listener function to remove
            
        Returns:
            True if listener was found and removed, False otherwise
        """
        if event_name not in self._listeners:
            return False
        
        listeners = self._listeners[event_name]
        for i, listener_info in enumerate(listeners):
            if listener_info['func'] == func:
                listeners.pop(i)
                return True
        
        return False
    
    def clear_listeners(self, event_name: str = None) -> None:
        """
        Clear all listeners for a specific event or all events.
        
        Args:
            event_name: Name of the event to clear, or None to clear all
        """
        if event_name is None:
            self._listeners.clear()
        elif event_name in self._listeners:
            self._listeners[event_name].clear()
    
    def get_listeners(self, event_name: str) -> List[Callable]:
        """
        Get all listener functions for a specific event.
        
        Args:
            event_name: Name of the event
            
        Returns:
            List of listener functions
        """
        return [
            listener_info['func'] 
            for listener_info in self._listeners.get(event_name, [])
        ]
    
    def has_listeners(self, event_name: str) -> bool:
        """
        Check if there are any listeners for a specific event.
        
        Args:
            event_name: Name of the event
            
        Returns:
            True if there are listeners, False otherwise
        """
        return event_name in self._listeners and len(self._listeners[event_name]) > 0