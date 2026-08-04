import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pawpal_system import DailyPlan, Owner, Pet, Scheduler, ScheduleItem, Task


def test_task_completion():
    task = Task(task_id=1, description="Give medication", duration_minutes=10, priority=1)
    assert task.completed is False

    task.mark_complete()

    assert task.completed is True


def test_task_addition():
    pet = Pet(name="Mochi", species="dog", age=3)
    assert len(pet.get_tasks()) == 0

    pet.add_task(Task(task_id=1, description="Morning walk", duration_minutes=30, priority=1))

    assert len(pet.get_tasks()) == 1


# ---------------------------------------------------------------------------
# Sorting correctness
# ---------------------------------------------------------------------------

def test_sort_tasks_orders_by_priority_normal_case():
    pet = Pet(name="Mochi", species="dog", age=3)
    low = Task(task_id=1, description="Low priority", duration_minutes=10, priority=3)
    high = Task(task_id=2, description="High priority", duration_minutes=10, priority=1)
    mid = Task(task_id=3, description="Mid priority", duration_minutes=10, priority=2)

    ordered = Scheduler().sort_tasks([(pet, low), (pet, high), (pet, mid)])

    assert [task.task_id for _, task in ordered] == [2, 3, 1]


def test_sort_tasks_required_tasks_come_before_optional_regardless_of_priority():
    pet = Pet(name="Mochi", species="dog", age=3)
    optional_high_priority = Task(
        task_id=1, description="Optional", duration_minutes=10, priority=1, required=False
    )
    required_low_priority = Task(
        task_id=2, description="Required", duration_minutes=10, priority=5, required=True
    )

    ordered = Scheduler().sort_tasks([(pet, optional_high_priority), (pet, required_low_priority)])

    assert [task.task_id for _, task in ordered] == [2, 1]


def test_sort_tasks_empty_list_returns_empty_list():
    assert Scheduler().sort_tasks([]) == []


def test_sort_by_time_orders_chronologically():
    pet = Pet(name="Mochi", species="dog", age=3)
    later = Task(task_id=1, description="Later", duration_minutes=10, priority=1, preferred_time="18:00")
    earlier = Task(task_id=2, description="Earlier", duration_minutes=10, priority=1, preferred_time="07:00")

    ordered = Scheduler().sort_by_time([(pet, later), (pet, earlier)])

    assert [task.task_id for _, task in ordered] == [2, 1]


def test_sort_by_time_missing_preferred_time_sorts_last():
    pet = Pet(name="Mochi", species="dog", age=3)
    no_time = Task(task_id=1, description="No time", duration_minutes=10, priority=1, preferred_time=None)
    with_time = Task(task_id=2, description="Has time", duration_minutes=10, priority=1, preferred_time="09:00")

    ordered = Scheduler().sort_by_time([(pet, no_time), (pet, with_time)])

    assert [task.task_id for _, task in ordered] == [2, 1]


# ---------------------------------------------------------------------------
# Recurrence logic
# ---------------------------------------------------------------------------

def test_daily_task_completion_creates_next_day_occurrence():
    task = Task(task_id=1, description="Feed", duration_minutes=10, priority=1, frequency="daily")

    next_task = task.create_next_occurrence("2026-07-07")

    assert next_task is not None
    assert next_task.due_date == "2026-07-08"
    assert next_task.completed is False
    assert next_task.task_id == task.task_id


def test_weekly_task_completion_creates_occurrence_seven_days_later():
    task = Task(task_id=1, description="Groom", duration_minutes=30, priority=2, frequency="weekly")

    next_task = task.create_next_occurrence("2026-07-07")

    assert next_task.due_date == "2026-07-14"


def test_once_task_completion_creates_no_next_occurrence():
    task = Task(task_id=1, description="Vet visit", duration_minutes=60, priority=1, frequency="once")

    assert task.create_next_occurrence("2026-07-07") is None


def test_mark_task_complete_on_pet_adds_recurring_task_to_pet_list():
    pet = Pet(name="Mochi", species="dog", age=3)
    task = Task(task_id=1, description="Feed", duration_minutes=10, priority=1, frequency="daily")
    pet.add_task(task)

    next_task = pet.mark_task_complete(task, "2026-07-07")

    assert task.completed is True
    assert next_task is not None
    assert len(pet.get_tasks()) == 2
    assert next_task in pet.get_tasks()


def test_mark_task_complete_on_pet_does_not_add_task_for_one_off():
    pet = Pet(name="Mochi", species="dog", age=3)
    task = Task(task_id=1, description="Vet visit", duration_minutes=60, priority=1, frequency="once")
    pet.add_task(task)

    next_task = pet.mark_task_complete(task, "2026-07-07")

    assert next_task is None
    assert len(pet.get_tasks()) == 1


# ---------------------------------------------------------------------------
# Conflict detection / scheduling edge cases
# ---------------------------------------------------------------------------

def test_generate_plan_pet_with_no_tasks_produces_empty_plan():
    owner = Owner(name="Alex", available_minutes=120, preferred_start_time="08:00", preferred_end_time="20:00")
    owner.add_pet(Pet(name="Mochi", species="dog", age=3))

    plan, explanation = Scheduler().generate_plan(owner, "2026-07-07")

    assert plan.scheduled_items == []
    assert plan.skipped_tasks == []
    assert plan.warnings == []
    assert explanation.get_explanation() == ""


def test_detect_conflicts_returns_no_warnings_for_non_overlapping_items():
    pet = Pet(name="Mochi", species="dog", age=3)
    task_a = Task(task_id=1, description="Walk", duration_minutes=30, priority=1)
    task_b = Task(task_id=2, description="Feed", duration_minutes=30, priority=1)
    owner = Owner(name="Alex", available_minutes=120, preferred_start_time="08:00", preferred_end_time="20:00")
    pet.add_task(task_a)
    pet.add_task(task_b)
    owner.add_pet(pet)

    plan, _ = Scheduler().generate_plan(owner, "2026-07-07")

    assert plan.warnings == []
    assert len(plan.scheduled_items) == 2


def test_generate_plan_staggers_two_fixed_tasks_requested_at_the_same_time():
    """generate_plan never lets fixed-time tasks land on the same slot: since
    current_time only ever advances, the second task is pushed right after the
    first rather than being skipped as a conflict."""
    pet = Pet(name="Mochi", species="dog", age=3)
    task_a = Task(
        task_id=1, description="Walk", duration_minutes=30, priority=1, preferred_time="09:00"
    )
    task_b = Task(
        task_id=2, description="Vet call", duration_minutes=30, priority=1, preferred_time="09:00"
    )
    owner = Owner(name="Alex", available_minutes=120, preferred_start_time="08:00", preferred_end_time="20:00")
    pet.add_task(task_a)
    pet.add_task(task_b)
    owner.add_pet(pet)

    plan, _ = Scheduler().generate_plan(owner, "2026-07-07")

    assert len(plan.scheduled_items) == 2
    assert plan.skipped_tasks == []
    assert plan.warnings == []
    times = sorted((item.start_time, item.end_time) for item in plan.scheduled_items)
    assert times == [("09:00", "09:30"), ("09:30", "10:00")]


def test_has_conflict_detects_true_overlap_directly():
    plan = DailyPlan("2026-07-07")
    task = Task(task_id=1, description="Walk", duration_minutes=30, priority=1)
    pet = Pet(name="Mochi", species="dog", age=3)
    plan.add_item(ScheduleItem(pet, task, "09:00", "09:30"))

    assert plan.has_conflict("09:15", "09:45") is True
    assert plan.has_conflict("09:30", "10:00") is False


def test_detect_conflicts_flags_manually_overlapping_items_from_different_pets():
    pet_a = Pet(name="Mochi", species="dog", age=3)
    pet_b = Pet(name="Whiskers", species="cat", age=2)
    task_a = Task(task_id=1, description="Walk", duration_minutes=30, priority=1)
    task_b = Task(task_id=2, description="Litter box", duration_minutes=30, priority=1)

    item_a = ScheduleItem(pet_a, task_a, "09:00", "09:30")
    item_b = ScheduleItem(pet_b, task_b, "09:15", "09:45")

    warnings = Scheduler().detect_conflicts([item_a, item_b])

    assert len(warnings) == 1
    assert "Mochi" in warnings[0] and "Whiskers" in warnings[0]


def test_detect_conflicts_back_to_back_items_are_not_conflicts():
    pet = Pet(name="Mochi", species="dog", age=3)
    task_a = Task(task_id=1, description="Walk", duration_minutes=30, priority=1)
    task_b = Task(task_id=2, description="Feed", duration_minutes=30, priority=1)

    item_a = ScheduleItem(pet, task_a, "09:00", "09:30")
    item_b = ScheduleItem(pet, task_b, "09:30", "10:00")

    warnings = Scheduler().detect_conflicts([item_a, item_b])

    assert warnings == []
