"""Backend logic layer for PawPal+."""

from dataclasses import dataclass, field
from datetime import date as _date, timedelta as _timedelta

# How far ahead the next occurrence of a recurring task is due, by frequency.
_RECURRENCE_STEP_DAYS = {"daily": 1, "weekly": 7}


@dataclass
class Task:
    task_id: int
    description: str
    duration_minutes: int
    priority: int  # 1 = highest priority
    frequency: str = "daily"  # "daily", "weekly", or "once"
    required: bool = True
    completed: bool = False
    preferred_time: str = None  # optional fixed "HH:MM" this task should happen at
    due_date: str = None  # "YYYY-MM-DD" this occurrence becomes due; None = due immediately
    last_completed_date: str = None  # "YYYY-MM-DD" of the last time this occurrence was done

    def mark_complete(self, date: str = None):
        """Mark this occurrence as done, recording the completion date if given."""
        self.completed = True
        if date is not None:
            self.last_completed_date = date

    def is_due(self, date: str) -> bool:
        """Return whether this task occurrence still needs to happen on the given date."""
        if self.completed:
            return False
        return self.due_date is None or self.due_date <= date

    def create_next_occurrence(self, completed_date: str) -> "Task":
        """For a "daily"/"weekly" task, return a fresh Task instance due at the next interval.

        Returns None for one-off tasks ("once" or any other non-recurring frequency).
        """
        step_days = _RECURRENCE_STEP_DAYS.get(self.frequency)
        if step_days is None:
            return None
        next_due = (_date.fromisoformat(completed_date) + _timedelta(days=step_days)).isoformat()
        return Task(
            task_id=self.task_id,
            description=self.description,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            frequency=self.frequency,
            required=self.required,
            preferred_time=self.preferred_time,
            due_date=next_due,
        )


@dataclass
class Pet:
    name: str
    species: str
    age: int
    notes: str = ""
    tasks: list = field(default_factory=list)

    def add_task(self, task: Task):
        """Append a task to this pet's task list."""
        self.tasks.append(task)

    def get_tasks(self) -> list:
        """Return this pet's task list."""
        return self.tasks

    def get_tasks_by_status(self, completed: bool) -> list:
        """Return this pet's tasks filtered by completion status."""
        return [task for task in self.tasks if task.completed == completed]

    def mark_task_complete(self, task: Task, date: str) -> Task:
        """Mark a task done and, if it recurs, add its next occurrence to this pet's tasks.

        Returns the newly created next-occurrence Task, or None for a one-off task.
        """
        task.mark_complete(date)
        next_task = task.create_next_occurrence(date)
        if next_task is not None:
            self.add_task(next_task)
        return next_task

    def update_info(self, **kwargs):
        """Update this pet's attributes from keyword arguments."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class Owner:
    def __init__(self, name: str, available_minutes: int, preferred_start_time: str, preferred_end_time: str):
        self.name = name
        self.available_minutes = available_minutes
        self.preferred_start_time = preferred_start_time
        self.preferred_end_time = preferred_end_time
        self.pets = []

    def add_pet(self, pet: Pet):
        """Add a pet to this owner's list of pets."""
        self.pets.append(pet)

    def get_all_tasks(self) -> list:
        """Return every task across all pets as (pet, task) pairs."""
        return [(pet, task) for pet in self.pets for task in pet.tasks]

    def filter_tasks(self, pet_name: str = None, completed: bool = None) -> list:
        """Return (pet, task) pairs filtered by pet name and/or completion status."""
        tasks = self.get_all_tasks()
        if pet_name is not None:
            tasks = [(pet, task) for pet, task in tasks if pet.name == pet_name]
        if completed is not None:
            tasks = [(pet, task) for pet, task in tasks if task.completed == completed]
        return tasks

    def get_tasks_by_pet(self, pet_name: str) -> list:
        """Return (pet, task) pairs belonging to the pet with the given name."""
        return self.filter_tasks(pet_name=pet_name)

    def get_tasks_by_status(self, completed: bool) -> list:
        """Return (pet, task) pairs across all pets filtered by completion status."""
        return self.filter_tasks(completed=completed)

    def update_info(self, **kwargs):
        """Update this owner's attributes from keyword arguments."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


class ScheduleItem:
    def __init__(self, pet: Pet, task: Task, start_time: str, end_time: str):
        self.pet = pet
        self.task = task
        self.start_time = start_time
        self.end_time = end_time

    def display(self) -> str:
        """Return a one-line human-readable rendering of this scheduled item."""
        return f"{self.start_time}-{self.end_time}  {self.pet.name}: {self.task.description}"


class DailyPlan:
    def __init__(self, date: str):
        self.date = date
        self.scheduled_items = []
        self.skipped_tasks = []
        self.total_minutes = 0
        self.warnings = []

    def add_item(self, item: ScheduleItem):
        """Add a scheduled item to the plan and track its minutes."""
        self.scheduled_items.append(item)
        self.total_minutes += item.task.duration_minutes

    def add_skipped(self, pet: Pet, task: Task):
        """Record a task that could not be fit into the plan."""
        self.skipped_tasks.append((pet, task))

    def get_items_for_pet(self, pet_name: str) -> list:
        """Return the scheduled items belonging to the pet with the given name."""
        return [item for item in self.scheduled_items if item.pet.name == pet_name]

    def has_conflict(self, start_time: str, end_time: str) -> bool:
        """Check whether the given time range overlaps any already-scheduled item."""
        return any(
            start_time < item.end_time and item.start_time < end_time
            for item in self.scheduled_items
        )

    def get_summary(self) -> str:
        """Return a multi-line human-readable summary of the plan."""
        lines = [f"Plan for {self.date} ({self.total_minutes} min scheduled)"]
        lines += [item.display() for item in self.scheduled_items]
        if self.skipped_tasks:
            lines.append("Skipped:")
            lines += [f"  {pet.name}: {task.description}" for pet, task in self.skipped_tasks]
        if self.warnings:
            lines.append("Warnings:")
            lines += [f"  {warning}" for warning in self.warnings]
        return "\n".join(lines)


class PlanExplanation:
    def __init__(self):
        self.reasons = []

    def add_reason(self, reason: str):
        """Record one reason behind a scheduling decision."""
        self.reasons.append(reason)

    def get_explanation(self) -> str:
        """Return all recorded reasons as a multi-line string."""
        return "\n".join(self.reasons)


class Scheduler:
    def generate_plan(self, owner: Owner, date: str) -> tuple:
        """Build a DailyPlan and PlanExplanation from all of the owner's pet tasks."""
        plan = DailyPlan(date)
        explanation = PlanExplanation()

        due_tasks = [pt for pt in owner.get_all_tasks() if pt[1].is_due(date)]
        not_due = [pt for pt in owner.get_all_tasks() if not pt[1].is_due(date)]
        for pet, task in not_due:
            explanation.add_reason(
                f"Skipped '{task.description}' for {pet.name}: not due yet (frequency={task.frequency})."
            )

        fixed_tasks = self.sort_by_time([pt for pt in due_tasks if pt[1].preferred_time])
        flexible_tasks = self.sort_tasks([pt for pt in due_tasks if not pt[1].preferred_time])

        remaining_time = owner.available_minutes
        current_time = owner.preferred_start_time

        # Fixed-time tasks are placed at their requested time first, since they anchor the day.
        for pet, task in fixed_tasks:
            start_time = max(task.preferred_time, current_time)
            end_time = self._add_minutes(start_time, task.duration_minutes)
            if plan.has_conflict(start_time, end_time):
                plan.add_skipped(pet, task)
                explanation.add_reason(
                    f"Skipped '{task.description}' for {pet.name}: conflicts with another task "
                    f"scheduled around {task.preferred_time}."
                )
                continue
            if not self.can_fit(task, remaining_time):
                plan.add_skipped(pet, task)
                explanation.add_reason(
                    f"Skipped '{task.description}' for {pet.name}: not enough time remaining."
                )
                continue
            plan.add_item(ScheduleItem(pet, task, start_time, end_time))
            explanation.add_reason(
                f"Scheduled '{task.description}' for {pet.name} at {start_time} "
                f"(fixed time, priority {task.priority})."
            )
            current_time = max(current_time, end_time)
            remaining_time -= task.duration_minutes

        for pet, task in flexible_tasks:
            start_time, end_time = self._next_open_slot(plan, current_time, task.duration_minutes)
            if not self.can_fit(task, remaining_time):
                plan.add_skipped(pet, task)
                explanation.add_reason(
                    f"Skipped '{task.description}' for {pet.name}: not enough time remaining."
                )
                continue
            plan.add_item(ScheduleItem(pet, task, start_time, end_time))
            explanation.add_reason(
                f"Scheduled '{task.description}' for {pet.name} at {start_time} "
                f"(priority {task.priority})."
            )
            current_time = end_time
            remaining_time -= task.duration_minutes

        plan.warnings = self.detect_conflicts(plan.scheduled_items)

        return plan, explanation

    def detect_conflicts(self, scheduled_items: list) -> list:
        """Scan scheduled items for time overlaps and return warning strings.

        This is a lightweight, crash-proof check: it never raises, it just reports
        every overlapping pair it finds (whether for the same pet or two different
        pets) as a human-readable warning message.

        Uses a sweep over items sorted by start_time, comparing each item only
        against the still-open items ahead of it, instead of checking every
        possible pair - O(n log n) instead of O(n^2) for schedules without
        heavy overlap.
        """
        required_attrs = ("start_time", "end_time", "pet", "task")
        valid_items = [item for item in scheduled_items if all(hasattr(item, attr) for attr in required_attrs)]
        by_start = sorted(valid_items, key=lambda item: item.start_time)

        warnings = []
        open_items = []  # items seen so far whose end_time hasn't passed yet
        for item in by_start:
            open_items = [other for other in open_items if other.end_time > item.start_time]
            warnings += [self._format_conflict(other, item) for other in open_items]
            open_items.append(item)
        return warnings

    @staticmethod
    def _format_conflict(a, b) -> str:
        """Build a human-readable warning for two schedule items known to overlap."""
        if a.pet.name == b.pet.name:
            return (
                f"Warning: {a.pet.name} is double-booked - '{a.task.description}' "
                f"({a.start_time}-{a.end_time}) overlaps '{b.task.description}' "
                f"({b.start_time}-{b.end_time})."
            )
        return (
            f"Warning: schedule conflict between pets - {a.pet.name}'s "
            f"'{a.task.description}' ({a.start_time}-{a.end_time}) overlaps "
            f"{b.pet.name}'s '{b.task.description}' ({b.start_time}-{b.end_time})."
        )

    def sort_tasks(self, pet_tasks: list) -> list:
        """Sort (pet, task) pairs by required-first, then priority."""
        return sorted(pet_tasks, key=lambda pt: (not pt[1].required, pt[1].priority))

    def sort_by_time(self, pet_tasks: list) -> list:
        """Sort (pet, task) pairs by their preferred_time "HH:MM" string, earliest first."""
        sorted_tasks = list(pet_tasks)
        sorted_tasks.sort(key=lambda pt: pt[1].preferred_time or "23:59")
        return sorted_tasks

    def can_fit(self, task: Task, remaining_time: int) -> bool:
        """Check whether a task's duration fits within the remaining time."""
        return task.duration_minutes <= remaining_time

    @staticmethod
    def _next_open_slot(plan: DailyPlan, earliest_start: str, duration_minutes: int) -> tuple:
        """Find the earliest start time at or after earliest_start with no conflict, honoring duration."""
        start_time = earliest_start
        while True:
            end_time = Scheduler._add_minutes(start_time, duration_minutes)
            conflicting_ends = [
                item.end_time
                for item in plan.scheduled_items
                if start_time < item.end_time and item.start_time < end_time
            ]
            if not conflicting_ends:
                return start_time, end_time
            start_time = max(conflicting_ends)

    @staticmethod
    def _add_minutes(time_str: str, minutes: int) -> str:
        """Add minutes to an "HH:MM" time string and return the result."""
        hours, mins = map(int, time_str.split(":"))
        total = hours * 60 + mins + minutes
        return f"{(total // 60) % 24:02d}:{total % 60:02d}"
