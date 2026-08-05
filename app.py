import streamlit as st

from pawpal_system import Owner, Pet, Task, Scheduler
from rag_advisor import RAGAdvisor, RAGAdvisorError


@st.cache_resource(show_spinner=False)
def get_advisor():
    return RAGAdvisor()

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app. Add pets, add tasks for them, and generate a
daily schedule using the backend logic in `pawpal_system.py`.
"""
)

st.divider()

PLAN_DATE = "2026-07-06"

# --- Owner: created once per session, then reused on every rerun ---
st.subheader("Owner")
owner_name = st.text_input("Owner name", value="Jordan")
available_minutes = st.number_input("Available minutes today", min_value=1, max_value=600, value=90)
col_start, col_end = st.columns(2)
with col_start:
    preferred_start_time = st.text_input("Preferred start time (HH:MM)", value="08:00")
with col_end:
    preferred_end_time = st.text_input("Preferred end time (HH:MM)", value="18:00")

if "owner" not in st.session_state:
    st.session_state.owner = Owner(
        name=owner_name,
        available_minutes=available_minutes,
        preferred_start_time=preferred_start_time,
        preferred_end_time=preferred_end_time,
    )
else:
    st.session_state.owner.update_info(
        name=owner_name,
        available_minutes=available_minutes,
        preferred_start_time=preferred_start_time,
        preferred_end_time=preferred_end_time,
    )

owner = st.session_state.owner

if "next_task_id" not in st.session_state:
    st.session_state.next_task_id = 1

st.divider()

# --- Adding a Pet ---
st.subheader("Adding a Pet")
pet_name = st.text_input("Pet name", value="Mochi")
species = st.selectbox("Species", ["dog", "cat", "other"])
age = st.number_input("Age", min_value=0, max_value=30, value=3)
notes = st.text_input("Notes", value="")

if st.button("Add pet"):
    if any(pet.name == pet_name for pet in owner.pets):
        st.warning(f"{pet_name} is already one of {owner.name}'s pets.")
    else:
        owner.add_pet(Pet(name=pet_name, species=species, age=int(age), notes=notes))
        st.success(f"Added {pet_name} the {species}.")

if owner.pets:
    st.write("Current pets:")
    st.table(
        [{"name": pet.name, "species": pet.species, "age": pet.age, "notes": pet.notes} for pet in owner.pets]
    )
else:
    st.info("No pets yet. Add one above.")

st.divider()

# --- AI Smart Care Plan (RAG) ---
st.subheader("AI Smart Care Plan")
st.caption(
    "AI-generated suggestions based on a general care guide, not a veterinary diagnosis. "
    "If your pet is showing signs of illness or injury, contact a vet instead of relying on this plan."
)

if owner.pets:
    ai_pet_name = st.selectbox("Pet to generate a plan for", [pet.name for pet in owner.pets], key="ai_pet_select")

    if st.button("Generate AI care plan"):
        target_pet = next(pet for pet in owner.pets if pet.name == ai_pet_name)
        try:
            with st.spinner("Retrieving care guidance and consulting Claude..."):
                advisor = get_advisor()
                advice, task_dicts = advisor.generate_smart_care_plan(target_pet)
            st.session_state.ai_advice = advice
            st.session_state.ai_task_dicts = task_dicts
            st.session_state.ai_task_pet_name = ai_pet_name
        except RAGAdvisorError as e:
            st.error(f"Could not generate an AI care plan: {e}")

    if st.session_state.get("ai_task_dicts") and st.session_state.get("ai_task_pet_name") == ai_pet_name:
        st.markdown(f"**AI advice for {ai_pet_name}:**")
        st.write(st.session_state.ai_advice)

        st.write("Proposed tasks:")
        st.table(st.session_state.ai_task_dicts)

        if st.button("Add these tasks to the schedule"):
            target_pet = next(pet for pet in owner.pets if pet.name == ai_pet_name)
            for task_dict in st.session_state.ai_task_dicts:
                target_pet.add_task(
                    Task(
                        task_id=st.session_state.next_task_id,
                        description=task_dict["description"],
                        duration_minutes=int(task_dict["duration_minutes"]),
                        priority=int(task_dict["priority"]),
                        frequency=task_dict["frequency"],
                        required=bool(task_dict["required"]),
                        preferred_time=task_dict.get("preferred_time"),
                    )
                )
                st.session_state.next_task_id += 1
            st.success(f"Added {len(st.session_state.ai_task_dicts)} AI-generated task(s) for {ai_pet_name}.")
            del st.session_state.ai_task_dicts
            del st.session_state.ai_advice
            del st.session_state.ai_task_pet_name
            st.rerun()
else:
    st.info("Add a pet before generating an AI care plan.")

st.divider()

# --- Scheduling a Task ---
st.subheader("Scheduling a Task")

if owner.pets:
    task_pet_name = st.selectbox("Pet", [pet.name for pet in owner.pets])
    col1, col2, col3 = st.columns(3)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col3:
        priority = st.selectbox("Priority", [1, 2, 3], index=0, help="1 = highest priority")

    col4, col5, col6 = st.columns(3)
    with col4:
        frequency = st.selectbox("Frequency", ["daily", "weekly", "once"], index=0)
    with col5:
        required = st.checkbox("Required", value=True)
    with col6:
        preferred_time = st.text_input(
            "Preferred time (HH:MM, optional)", value="", help="Leave blank for a flexible task."
        )

    if st.button("Add task"):
        target_pet = next(pet for pet in owner.pets if pet.name == task_pet_name)
        target_pet.add_task(
            Task(
                task_id=st.session_state.next_task_id,
                description=task_title,
                duration_minutes=int(duration),
                priority=priority,
                frequency=frequency,
                required=required,
                preferred_time=preferred_time or None,
            )
        )
        st.session_state.next_task_id += 1
        st.success(f"Added '{task_title}' for {task_pet_name}.")
else:
    st.info("Add a pet before scheduling tasks for it.")

st.divider()

# --- Task list: sorted + filterable, using the Scheduler/Owner helpers directly ---
st.subheader("Tasks")

all_tasks = owner.get_all_tasks()
if all_tasks:
    col_filter_pet, col_filter_status = st.columns(2)
    with col_filter_pet:
        pet_filter = st.selectbox("Filter by pet", ["All pets"] + [pet.name for pet in owner.pets])
    with col_filter_status:
        status_filter = st.selectbox("Filter by status", ["All", "Incomplete", "Completed"])

    filtered_tasks = owner.filter_tasks(
        pet_name=None if pet_filter == "All pets" else pet_filter,
        completed=None if status_filter == "All" else status_filter == "Completed",
    )

    # Same ordering the scheduler itself will use: required-first, then priority.
    sorted_tasks = Scheduler().sort_tasks(filtered_tasks)

    if sorted_tasks:
        st.table(
            [
                {
                    "pet": pet.name,
                    "task": task.description,
                    "priority": task.priority,
                    "required": task.required,
                    "duration_min": task.duration_minutes,
                    "frequency": task.frequency,
                    "preferred_time": task.preferred_time or "flexible",
                    "completed": task.completed,
                }
                for pet, task in sorted_tasks
            ]
        )
    else:
        st.info("No tasks match that filter.")

    incomplete_tasks = [(pet, task) for pet, task in filtered_tasks if not task.completed]
    if incomplete_tasks:
        st.write("Mark a task complete:")
        labels = [f"{pet.name}: {task.description}" for pet, task in incomplete_tasks]
        selected_label = st.selectbox("Task", labels, key="complete_task_select")
        selected_pet, selected_task = incomplete_tasks[labels.index(selected_label)]
        if st.button("Mark complete"):
            next_task = selected_pet.mark_task_complete(selected_task, PLAN_DATE)
            if next_task is not None:
                st.success(
                    f"Marked '{selected_task.description}' complete for {selected_pet.name}. "
                    f"Next occurrence scheduled for {next_task.due_date}."
                )
            else:
                st.success(f"Marked '{selected_task.description}' complete for {selected_pet.name}.")
            st.rerun()
else:
    st.info("No tasks yet. Add one above.")

st.divider()

# --- Build Schedule ---
st.subheader("Build Schedule")

if st.button("Generate schedule"):
    scheduler = Scheduler()
    plan, explanation = scheduler.generate_plan(owner, date=PLAN_DATE)
    st.session_state.plan = plan
    st.session_state.explanation = explanation

if "plan" in st.session_state:
    plan = st.session_state.plan
    explanation = st.session_state.explanation

    st.success(f"Plan for {plan.date}: {plan.total_minutes} minutes scheduled.")

    if plan.scheduled_items:
        st.write("Scheduled items:")
        st.table(
            [
                {
                    "start": item.start_time,
                    "end": item.end_time,
                    "pet": item.pet.name,
                    "task": item.task.description,
                    "priority": item.task.priority,
                }
                for item in plan.scheduled_items
            ]
        )
    else:
        st.info("Nothing was scheduled for this date.")

    if plan.skipped_tasks:
        st.warning(f"{len(plan.skipped_tasks)} task(s) could not be scheduled:")
        st.table(
            [
                {"pet": pet.name, "task": task.description, "priority": task.priority, "required": task.required}
                for pet, task in plan.skipped_tasks
            ]
        )

    if plan.warnings:
        for warning in plan.warnings:
            st.warning(warning)

    with st.expander("Why this plan?"):
        st.text(explanation.get_explanation())
