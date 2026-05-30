
#!/usr/bin/env python3
"""CLI Todo List Manager"""

def add_task(tasks, task_name):
    """Add a new task with the given name. Task is initially not done."""
    tasks.append({"name": task_name, "done": False})
    print(f"Added task: '{task_name}'")

def remove_task(tasks, index):
    """Remove the task at the given 0-based index. Prints error if invalid."""
    if 0 <= index < len(tasks):
        removed = tasks.pop(index)
        print(f"Removed task: '{removed['name']}'")
    else:
        print(f"Error: Index {index} out of range. No task removed.")

def list_tasks(tasks):
    """Display all tasks with their index, name, and completion status."""
    if not tasks:
        print("No tasks in the list.")
        return
    print("\nCurrent tasks:")
    for i, task in enumerate(tasks):
        status = "[✓]" if task["done"] else "[ ]"
        print(f"  {i}. {status} {task['name']}")
    print()

if __name__ == "__main__":
    # Initialize empty task list
    todo_list = []

    # Demonstrate functionality
    print("=== Todo List Manager Demo ===\n")

    # Add 3 tasks
    add_task(todo_list, "Buy groceries")
    add_task(todo_list, "Read a book")
    add_task(todo_list, "Write code")

    # List tasks
    list_tasks(todo_list)

    # Mark the second task (index 1) as done
    print("Marking task 1 ('Read a book') as done...")
    todo_list[1]["done"] = True
    list_tasks(todo_list)

    # Remove the first task (index 0)
    remove_task(todo_list, 0)
    list_tasks(todo_list)

    print("=== End of Demo ===")
