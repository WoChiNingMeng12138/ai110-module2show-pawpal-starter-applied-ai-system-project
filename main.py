"""Manual test harness for pawpal_system.py logic."""

from pawpal_system import Owner, Pet, Task, Scheduler, ScheduleItem

owner = Owner(
    name="Jordan",
    available_minutes=90,
    preferred_start_time="08:00",
    preferred_end_time="10:00",
)

dog = Pet(name="Mochi", species="dog", age=3, notes="Needs daily walk")
cat = Pet(name="Luna", species="cat", age=5, notes="Indoor only")

owner.add_pet(dog)
owner.add_pet(cat)

# Tasks are added out of time/priority order on purpose, to exercise sorting.
dog.add_task(Task(task_id=1, description="Morning walk", duration_minutes=30, priority=1, preferred_time="09:00"))
cat.add_task(Task(task_id=2, description="Feed breakfast", duration_minutes=15, priority=2, preferred_time="08:00"))
dog.add_task(Task(task_id=3, description="Give medication", duration_minutes=10, priority=1, preferred_time="08:30"))
cat.add_task(Task(task_id=4, description="Play time", duration_minutes=20, priority=3))
dog.add_task(Task(task_id=5, description="Evening walk", duration_minutes=25, priority=2, preferred_time="18:00"))

# Two tasks requested at the exact same time, to exercise conflict handling:
# "Brush fur" collides with Mochi's own "Morning walk" (same pet), and
# "Litter box cleanup" collides with Mochi's "Morning walk" too (different pet).
dog.add_task(Task(task_id=6, description="Brush fur", duration_minutes=15, priority=2, preferred_time="09:00"))
cat.add_task(Task(task_id=7, description="Litter box cleanup", duration_minutes=10, priority=2, preferred_time="09:00"))

# Mark a couple of tasks complete via Pet.mark_task_complete, which auto-creates
# the next occurrence for recurring ("daily"/"weekly") tasks.
medication_next = dog.mark_task_complete(dog.tasks[1], date="2026-07-06")  # "Give medication"
play_time_next = cat.mark_task_complete(cat.tasks[1], date="2026-07-06")  # "Play time"

print("=== Auto-created next occurrences after mark_task_complete ===")
print(f"Give medication -> next due {medication_next.due_date} (completed={medication_next.completed})")
print(f"Play time       -> next due {play_time_next.due_date} (completed={play_time_next.completed})")

scheduler = Scheduler()

print("=== All tasks sorted by time (sort_by_time) ===")
for pet, task in scheduler.sort_by_time(owner.get_all_tasks()):
    print(f"{task.preferred_time or '(none)'}  {pet.name}: {task.description}")

print("\n=== All tasks sorted by required/priority (sort_tasks) ===")
for pet, task in scheduler.sort_tasks(owner.get_all_tasks()):
    print(f"priority={task.priority}  required={task.required}  {pet.name}: {task.description}")

print("\n=== Completed tasks (filter_tasks completed=True) ===")
for pet, task in owner.filter_tasks(completed=True):
    print(f"{pet.name}: {task.description}")

print("\n=== Incomplete tasks (filter_tasks completed=False) ===")
for pet, task in owner.filter_tasks(completed=False):
    print(f"{pet.name}: {task.description}")

print("\n=== Mochi's tasks only (filter_tasks pet_name='Mochi') ===")
for pet, task in owner.filter_tasks(pet_name="Mochi"):
    print(f"{pet.name}: {task.description}")

print("\n=== Mochi's incomplete tasks (filter_tasks pet_name='Mochi', completed=False) ===")
for pet, task in owner.filter_tasks(pet_name="Mochi", completed=False):
    print(f"{pet.name}: {task.description}")

plan, explanation = scheduler.generate_plan(owner, date="2026-07-06")

print("\n=== Today's Schedule (2026-07-06) ===")
print(plan.get_summary())

print("\n=== Explanation ===")
print(explanation.get_explanation())

# generate_plan already resolves same-time requests by skipping the loser, so the
# resulting plan has no real overlaps - detect_conflicts on it should be empty.
print("\n=== Conflict warnings on the resolved plan (should be empty) ===")
print(plan.warnings or "(none - the scheduler skipped the double-booked tasks above)")

# To prove detect_conflicts itself works (and never crashes) on genuinely
# overlapping items, build a plan by hand that bypasses the scheduler's own
# conflict avoidance, then run the checker directly against it.
conflicted_plan_items = [
    ScheduleItem(dog, dog.tasks[0], "09:00", "09:30"),   # Mochi: Morning walk
    ScheduleItem(dog, dog.tasks[3], "09:00", "09:15"),   # Mochi: Brush fur (same pet overlap)
    ScheduleItem(cat, cat.tasks[2], "09:10", "09:20"),   # Luna: Litter box cleanup (cross-pet overlap)
]
print("\n=== Conflict warnings on a manually double-booked plan ===")
for warning in scheduler.detect_conflicts(conflicted_plan_items):
    print(warning)

# The completed occurrences should be due again tomorrow, proving the
# auto-created next-occurrence Tasks feed back into scheduling.
tomorrow_plan, tomorrow_explanation = scheduler.generate_plan(owner, date="2026-07-07")

print("\n=== Tomorrow's Schedule (2026-07-07) ===")
print(tomorrow_plan.get_summary())

print("\n=== Tomorrow's Explanation ===")
print(tomorrow_explanation.get_explanation())
