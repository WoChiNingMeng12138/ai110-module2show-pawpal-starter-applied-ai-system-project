# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- My initial UML design separated the PawPal+ system into three main parts: data models, scheduling logic, and the Streamlit user interface. The goal was to keep the core scheduling logic independent from the UI so that it would be easier to test and maintain.

The main classes in my design were:

Owner: Stores basic information about the pet owner.
Pet: Stores information about the pet, including the pet's name, species, age, and any special notes.
CareTask: Represents a pet care task. Each task includes a name, category, duration, priority, and whether the task is required.
Scheduler: Contains the main scheduling logic. It sorts tasks based on priority and checks whether each task can fit within the owner’s available time.
DailyPlan: Stores the final generated plan, including scheduled tasks, skipped tasks, and the total time used.
ScheduleItem: Represents one task placed into the daily schedule, including its start and end time.
PlanExplanation: Stores the reasoning behind the generated plan, such as why certain tasks were selected or skipped.

In this design, the user enters owner, pet, and task information through the Streamlit interface. The UI then sends that information to the Scheduler, which generates a DailyPlan. The final plan and explanation are displayed back to the user.

**b. Design changes**

- My design changed slightly during implementation. I planned to add a skipped_tasks list to the DailyPlan class. In the initial design, I only planned to store scheduled tasks. During implementation, I realized that skipped tasks were important because the app needs to explain why some tasks were not included.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- My scheduler considers several constraints:

- The owner’s total available minutes.
- The owner’s preferred start and end time.
- Whether a task is required or optional.
- The task’s priority level.
- The task’s duration.
- Whether the task has a preferred time.
- Whether the task is due on the selected date.
- Whether the task has already been completed.
- Conflicts between scheduled items.

- I decided that required tasks and due tasks should matter most because they represent essential pet care needs. After that, the scheduler considers priority, because higher-priority tasks should be scheduled before lower-priority ones.

**b. Tradeoffs**
- generate_plan uses a greedy algorithm: fixed-time tasks are scheduled chronologically and claim their slots sequentially, while flexible tasks are sorted by requirements or priority and slotted into the nearest available gaps. It does not backtrack, for instance, it won't displace and reschedule already-placed low-priority tasks to accommodate a high-priority, time-intensive one. This approach yields O(n log n) performance, but the trade-off is that, in certain scenarios, the resulting schedule may not maximize daily time utilization—it simply appears "reasonable."

---

## 3. AI Collaboration

**a. How you used AI**

- I used AI tools during several stages of the project, but I did not treat AI as the final decision-maker. I used it mainly as a brainstorming partner, debugging helper, and design reviewer.

The most helpful prompts were specific prompts that included my current design and asked for targeted feedback. For example, instead of asking “How do I build a scheduler?”, I asked questions like: “Given these classes, what edge cases should I test for my greedy scheduling algorithm?” or “Does this method belong in Scheduler or DailyPlan?”

**b. Judgment and verification**

- One moment where I did not accept an AI suggestion as-is was when AI suggested making the scheduler more complex by using backtracking or a more advanced optimization approach. While that could produce a more optimal schedule, I decided not to use it because it would make the system harder to understand and harder to explain in the project reflection.

- I also rejected suggestions to add too many extra classes, such as notification classes, database classes, or calendar-sync classes. Those features could be useful in a larger real-world app, but they were outside the scope of this project.

- To evaluate AI suggestions, I checked whether each suggestion matched my UML design, whether it made the code simpler or more complicated, and whether I could test it clearly.

---

## 4. Testing and Verification

**a. What you tested**

- I just test sorting correctness, recurrence logic and conflict detection and scheduling.
- These three areas contain the only "hidden logic" in the entire scheduler—sorting rules, date calculations, and time overlap checks are prone to errors at edge cases. Such errors often don't crash the program but instead silently produce incorrect schedules (e.g., missed tasks, duplicate tasks, or failure to flag a conflict), making automated testing essential rather than relying on manual inspection.

**b. Confidence**

- I am fairly confident that my scheduler works correctly for the main use cases, especially simple daily schedules with multiple pets and different task priorities. I am also confident that the system can explain skipped tasks and avoid obvious scheduling conflicts.
- I would like to test the empty input (pets with no tasks) or boundary values ​​(times meeting exactly end-to-end)—are easily overlooked during development but represent real-world scenarios users will encounter

---

## 5. Reflection

**a. What went well**

- The part I am most satisfied with is the separation between the data model and the scheduling logic. Classes like Owner, Pet, and Task store information, while Scheduler focuses on generating the plan. This made the system easier to understand and debug. I am also satisfied with adding PlanExplanation and skipped_tasks. These features make the app more transparent.

**b. What you would improve**

- If I had another iteration, I would improve the scheduler to handle more complex conflicts. For example, I could allow the scheduler to rearrange lower-priority flexible tasks if doing so would make room for an important required task. This would make the schedule closer to optimal, although it would also make the algorithm more complex.

**c. Key takeaway**

- One important thing I learned is that system design is about choosing clear responsibilities and making tradeoffs. A more complex algorithm is not always better if it makes the system harder to understand, test, or explain. For this project, a simple greedy scheduler was a good choice because it matched the project scope and made the behavior easier to reason about.