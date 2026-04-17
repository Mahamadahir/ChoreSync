# ChoreSync - Comprehensive Project Plan

## Project Overview
ChoreSync is an intelligent chore synchronization application that assigns household tasks fairly based on user calendars, task history, preferences, and enables collaborative task management with real-time updates.

---

## Core Technology Stack
- **Backend:** Django + Django REST Framework + Django Channels (WebSockets)
- **Web Frontend:** Vue.js
- **Mobile:** Progressive Web App (PWA) from Vue.js
- **Database:** PostgreSQL (recommended for production)
- **Real-time:** WebSockets for live chat and notifications
- **External APIs:** Google Calendar API, Outlook Calendar API

---

## Data Models & Architecture

### 1. User Management
**User Model**
- Standard Django User (email, password, name)
- Profile extension: preferences, timezone, notification settings
- Linked calendar accounts (Google/Outlook tokens)

**Household/Group Model**
- Group name
- Created by (User)
- Members (many-to-many with User)
- Group settings:
  - Photo proof required (boolean)
  - Fairness algorithm type (enum: time-based, count-based, difficulty-based)
  - Task proposal voting required (boolean)

### 2. Task System

**TaskTemplate Model** (Parent)
- Title (e.g., "Take out trash")
- Description
- Category (cleaning, cooking, maintenance, etc.)
- Default assignee preference (optional)
- Recurrence pattern:
  - Frequency (daily, weekly, monthly, custom)
  - Days of week (for weekly)
  - Time of day
  - End date (optional)
- Estimated time to complete (minutes) - **for fairness calculation**
- Difficulty rating (1-5) - **for fairness calculation**
- Photo proof required (boolean) - overrides group setting if true
- Created by (User)
- Household (Group)
- Active status (boolean)

**TaskOccurrence Model** (Child - individual instances)
- Parent template (ForeignKey to TaskTemplate)
- Assigned to (User)
- Due date/time
- Status (pending, in_progress, snoozed, completed, overdue, reassigned)
- Completion timestamp
- Photo proof (image upload, optional)
- Snooze until (timestamp, for "I'll do it later")
- Points earned (calculated on completion)
- Original assignee (User) - tracks who it was first assigned to
- Reassignment reason (enum: swap, emergency, system_rebalance)
- Created at, Updated at

### 3. Task Swaps & Marketplace

**CLARIFICATION: Task Marketplace vs Task Swaps**

**Task Swaps (your original plan):**
- Direct 1-to-1 trade: "I'll do your dishes if you do my laundry"
- Both users must agree
- Happens between specific task occurrences

**Task Marketplace (extension):**
- User posts a task they want to get rid of: "I'll give 50 bonus points to anyone who takes my bathroom cleaning"
- ANY household member can claim it (first come, first served OR bidding system)
- More flexible than 1-to-1 swaps

**Recommendation:** Implement both
- Phase 1: Task Swaps (simpler, your original plan)
- Phase 2: Task Marketplace (advanced feature)

**TaskSwapProposal Model**
- Proposer (User)
- Proposer's task (TaskOccurrence)
- Target user (User)
- Target's task (TaskOccurrence) - nullable if marketplace listing
- Swap type (enum: direct_swap, marketplace_offer)
- Bonus points offered (integer, for marketplace)
- Status (pending, accepted, rejected, expired)
- Created at, Expires at (24-48 hours)

### 4. Gamification

**UserStats Model** (per user, per household)
- User (User)
- Household (Group)
- Current streak (days)
- Longest streak (days)
- Total tasks completed
- Total points
- Tasks completed this week/month
- On-time completion rate (%)

**Badge Model**
- Name (e.g., "Weekend Warrior", "30-Day Streak", "Cleaning Champion")
- Description
- Icon/image
- Criteria (JSON field with conditions)
  - Example: `{"streak_days": 30}` or `{"tasks_completed": 100}`
- Points value

**UserBadge Model** (achievements earned)
- User (User)
- Badge (Badge)
- Earned at (timestamp)
- Household (Group)

**Leaderboard** (calculated view, not stored)
- Aggregates UserStats per household
- Sortable by: points, streak, completion rate, tasks completed

### 5. Smart Features

**TaskAssignmentHistory Model**
- User (User)
- Task template (TaskTemplate)
- Task occurrence (TaskOccurrence)
- Assigned at (timestamp)
- Completed (boolean)
- Completion time (timestamp)
- Was swapped (boolean)
- Was emergency reassign (boolean)

**UserTaskPreference Model**
- User (User)
- Task template (TaskTemplate)
- Preference score (-2 to +2)
  - +2 = love doing this
  - +1 = don't mind
  - 0 = neutral
  - -1 = dislike
  - -2 = hate doing this
- Last updated

### 6. Notifications & Reminders

**Notification Model**
- Recipient (User)
- Type (enum: deadline_reminder, swap_proposal, task_assigned, emergency_reassign, etc.)
- Title
- Message
- Related task occurrence (optional)
- Related swap proposal (optional)
- Read status (boolean)
- Sent at (timestamp)
- Action URL (optional)

### 7. Real-time Chat

**ChatMessage Model**
- Household (Group)
- Sender (User)
- Message text
- Timestamp
- Related task occurrence (optional) - for context
- Message type (enum: text, system_notification, task_update)

---

## Feature Specifications

### Feature 1: Task Assignment Algorithm (Smart & Fair)

**Inputs:**
1. User calendar availability (from Google/Outlook sync)
2. Task assignment history
3. Task swap history
4. User task preferences
5. Customizable fairness metric (selected by household)

**Customizable Fairness Algorithms:**

**Option A: Time-Based Fairness**
- Tracks total time spent on chores per user
- Uses `estimated_time_to_complete` from TaskTemplate
- Assigns tasks to balance total time across users
- **How it works:**
  - When creating TaskTemplate, user enters estimated duration
  - System calculates: User A = 120 min this week, User B = 80 min
  - Next task (30 min) → assigned to User B to balance

**Option B: Count-Based Fairness**
- Simple: counts number of tasks per user
- Assigns next task to user with fewest tasks
- Ignores task difficulty/duration

**Option C: Difficulty-Based Fairness**
- Uses difficulty rating (1-5 scale)
- Tracks total difficulty points per user
- Balances "hard" vs "easy" tasks
- Example: User A gets 2 hard tasks (5+5=10 points), User B gets 5 easy tasks (2+2+2+2+2=10 points)

**Option D: Weighted Fairness (Advanced)**
- Combines time × difficulty
- Formula: `points = estimated_time * difficulty_rating`
- Most comprehensive but requires accurate data entry

**How customization works:**
1. During household setup, admin selects fairness algorithm
2. Can be changed via group consensus vote
3. Historical data recalculated when algorithm changes

**Assignment Logic (Pseudocode):**
```
For each TaskTemplate due for a new occurrence:
  1. Check which users are available (calendar not blocked)
  2. Filter out users who were just assigned this task (rotation)
  3. Calculate fairness score for each eligible user
  4. Consider user preferences (bonus/penalty to score)
  5. Assign to user with lowest fairness burden
  6. If tie, assign to user with highest preference score
```

### Feature 2: Recurring Task Templates & Task Occurrences

**How it works:**
1. User creates TaskTemplate with recurrence pattern
2. System automatically generates TaskOccurrence instances:
   - At midnight, generate occurrences for next 7 days
   - Or on-demand when template is created
3. Each occurrence is independently assignable, completable, swappable

**Recurrence Options:**
- Daily (every N days)
- Weekly (specific days: Mon, Wed, Fri)
- Monthly (1st of month, last Sunday, etc.)
- Custom (every 10 days, twice weekly)
- One-time (no recurrence)

**Example:**
- TaskTemplate: "Take out trash"
  - Recurrence: Every Tuesday and Friday at 8 PM
  - Estimated time: 10 minutes
  - Difficulty: 2/5
- System generates:
  - TaskOccurrence #1: Tuesday, Feb 4, 8 PM → Assigned to User A
  - TaskOccurrence #2: Friday, Feb 7, 8 PM → Assigned to User B
  - TaskOccurrence #3: Tuesday, Feb 11, 8 PM → Assigned to User C
  - (continues...)

### Feature 3: Deadline Reminders

**Notification Schedule:**
- 24 hours before due
- 3 hours before due
- At due time
- 1 hour overdue (if not completed)

**Delivery Channels:**
- In-app notification
- Push notification (PWA)
- WebSocket real-time alert (if user is online)
- Optional: Email/SMS (future enhancement)

**Smart Reminders:**
- If task is snoozed, reminder adjusts to new time
- If user completes task early, future reminders canceled
- Escalating urgency in message tone

### Feature 4: Smart Suggestions

**Types of Suggestions:**

**1. Pattern Recognition:**
- "You usually do dishes on Sunday mornings. Want me to assign it to you?"
- Analyzes TaskAssignmentHistory for patterns
- Suggests auto-assignment based on historical data

**2. Availability-Based:**
- "You're free Saturday morning. Want to knock out these 3 tasks?"
- Checks calendar for free blocks
- Suggests batching compatible tasks

**3. Preference-Based:**
- "You rated 'Vacuuming' as a favorite. There's an open task—want it?"
- Monitors unassigned/marketplace tasks
- Notifies users about preferred tasks

**4. Fairness Rebalancing:**
- "You've done fewer tasks this month. Want to take on an extra one for bonus points?"
- Proactive suggestions to balance workload

**Implementation:**
- Background job (Django Celery) runs daily
- Generates suggestions stored in Notification model
- User can accept/dismiss from dashboard

### Feature 5: Streaks, Leaderboard & Badges

**Streaks:**
- **Current Streak:** Consecutive days with at least 1 completed task
- **Longest Streak:** Historical best
- Breaks if a day passes with 0 completions
- Displayed prominently in user profile

**Leaderboard:**
- Household-level only (no cross-household)
- Sortable columns:
  - Total points (this week/month/all-time)
  - Current streak
  - Tasks completed
  - On-time completion rate
- Refreshes in real-time via WebSocket
- Friendly competition, not shaming

**Badges (Examples):**
- **Streak Badges:** "7-Day Streak", "30-Day Warrior", "100-Day Legend"
- **Volume Badges:** "10 Tasks", "50 Tasks", "100 Tasks", "500 Tasks"
- **Specialty Badges:** "Kitchen King" (50 cooking tasks), "Bathroom Boss" (25 bathroom tasks)
- **Speed Badges:** "Early Bird" (complete 10 tasks before deadline)
- **Team Player:** "Accepted 10 emergency reassignments"
- **Negotiator:** "Completed 20 task swaps"

**Badge Notification:**
- Real-time pop-up when earned
- Shown on profile
- Can be shared in household chat

### Feature 6: "I'll Do It Later" (Snooze)

**How it works:**
1. User sees assigned task, clicks "I'll do it later"
2. System prompts: "When will you do it?"
   - In 1 hour
   - In 3 hours
   - Tonight (8 PM)
   - Tomorrow morning (9 AM)
   - Custom time
3. TaskOccurrence updated:
   - Status → `snoozed`
   - `snooze_until` → selected timestamp
4. Deadline reminder adjusted to snoozed time
5. Task reappears in user's task list at snoozed time

**Limits:**
- Maximum 2 snoozes per task (prevents infinite procrastination)
- Cannot snooze past original deadline + 24 hours
- Snoozing impacts on-time completion rate (for leaderboard)

### Feature 7: Emergency Reassign

**Use Cases:**
- "I'm sick and can't do my tasks today"
- "Unexpected work emergency"
- "Out of town"

**How it works:**
1. User clicks "Emergency Reassign" on their task(s)
2. System prompts: "Reason?" (optional text)
3. Broadcast to household:
   - WebSocket notification to all members
   - In-app alert: "User A needs help! Can someone take [Task]?"
4. First household member to accept gets the task
5. System records:
   - `reassignment_reason = emergency`
   - `original_assignee = User A`
6. User A's stats: doesn't hurt streak or completion rate (emergency exception)
7. Helper gets bonus points (+20% or configurable)

**Abuse Prevention:**
- Limit: 3 emergency reassigns per month
- Pattern detection: frequent emergency reassigns triggers admin review

### Feature 8: Task Swaps (Your Original Plan)

**Workflow:**
1. User A sees their assigned "Vacuum living room" task
2. Clicks "Propose Swap"
3. Selects target User B
4. Selects one of User B's tasks: "Do dishes"
5. Adds optional message: "I hate vacuuming, happy to do dishes instead!"
6. System creates TaskSwapProposal (status = pending)
7. User B receives notification
8. User B accepts or rejects
9. If accepted:
   - TaskOccurrence assignees swapped
   - Both tasks updated: `reassignment_reason = swap`
   - TaskAssignmentHistory logged
10. If rejected or expires (48 hours), proposal deleted

**Swap History:**
- Tracked in TaskAssignmentHistory
- Counts toward fairness algorithm (swap frequency per user)
- Prevents gaming the system

### Feature 9: Task Marketplace (Extension of Swaps)

**Workflow:**
1. User A wants to offload "Clean bathroom" (doesn't want to swap, just wants it gone)
2. Clicks "List on Marketplace"
3. Optionally offers bonus points (e.g., "I'll give 50 points to whoever takes this")
4. Task appears in household "Marketplace" tab
5. Any household member can claim it (first come, first served)
6. Claimer gets the task + bonus points
7. Original assignee loses points or gets fairness penalty (configurable)

**Marketplace Rules:**
- Can only list tasks assigned to you
- Cannot list tasks due in <2 hours (prevents last-minute dumps)
- Marketplace listings expire after 24 hours
- If unclaimed, task returns to original assignee

### Feature 10: Google & Outlook Calendar Sync

**Your Plan: Calendar Events (Not Tasks API)**
- ✅ Correct approach! Google Tasks API has limitations
- Use Calendar API to:
  - **Read:** Check user availability (blocked times)
  - **Write:** Create calendar events for each TaskOccurrence

**Implementation:**

**OAuth Flow:**
1. User connects Google/Outlook account in settings
2. Store access/refresh tokens securely (encrypted in DB)
3. Request scopes: `calendar.readonly` (read availability) + `calendar.events` (write events)

**Read Availability:**
- Daily background job checks user calendars
- Identifies free blocks for smart assignment
- Flags conflicts: "User has meeting during typical chore time"

**Write Task Events:**
- When TaskOccurrence is created/assigned:
  - Create calendar event: "ChoreSync: Take out trash"
  - Set time: task's due date/time
  - Add description: link to ChoreSync task
  - Set reminder: 30 min before
- When task is completed: mark calendar event as completed
- When task is snoozed/swapped: update calendar event

**Sync Frequency:**
- Read: Every 4 hours (or on-demand when assigning tasks)
- Write: Immediately when task changes

### Feature 11: Photo Proof

**Group Setting (Configurable):**
- **Global Photo Proof:** Household admin enables for all tasks
- **Task-Level Override:** Individual TaskTemplates can require photo even if global setting is off
- **Group Consensus Voting:** Household votes to enable/disable (requires >50% approval)

**How it works:**
1. User completes a task
2. If photo proof required:
   - "Complete" button disabled
   - "Upload Photo" prompt appears
3. User takes/uploads photo (before/after preferred)
4. Photo stored with TaskOccurrence
5. Task marked complete
6. Other household members can view photo in task history

**Photo Proof Enforcement:**
- Tasks without required photo remain status = `in_progress`
- Cannot earn points/badges without photo
- Optional: household members can challenge completion if photo is unclear

**Privacy:**
- Photos only visible to household members
- Stored securely (Django media storage)
- Can be deleted after 30 days (configurable retention)

### Feature 12: Stats Dashboard

**Household-Level Stats:**
- Total tasks completed (all-time, this month, this week)
- Average completion time
- Most/least popular tasks
- Task completion rate (% of tasks done on time)
- Fairness metric visualization:
  - Time-based: Bar chart showing total minutes per user
  - Count-based: Pie chart showing task distribution
  - Difficulty-based: Stacked bar showing difficulty points per user

**Individual User Stats:**
- Personal task completion rate
- Tasks completed vs assigned
- Most completed task type
- Favorite tasks (by preference score)
- Swap/reassignment frequency
- Points earned over time (line graph)
- Streak history

**Visualizations (Vue.js + Chart.js):**
- Line graph: Tasks completed over time
- Bar chart: Task distribution by category
- Pie chart: Time spent per task category
- Heatmap: Task completion by day of week

**Customizable Fairness Dashboard:**
- Shows current fairness algorithm in use
- Real-time view of fairness scores per user
- Ability to simulate: "What if we switched to time-based fairness?"
- Admin can change algorithm with household vote

### Feature 13: AI Chatbot Assistant ✅ Backend implemented

**What it is:**
A conversational assistant for creating and managing tasks via natural language, running locally on-device using **Ollama + Phi-3 Mini** (no external API costs, no rate limits).

**Infrastructure:**
- Ollama installed as a systemd service (`sudo systemctl enable ollama`)
- Model: `phi3:mini` — ~2.3GB, optimised for structured JSON extraction, fast on CPU
- Runs on CPU using system RAM (no GPU required)
- Response time: ~5–15s per message
- `httpx` used for HTTP calls to Ollama

**Backend endpoint (implemented):**
```
POST /api/groups/{group_id}/assistant/
Body: { "message": "Add a weekly task to clean the bathroom on Fridays" }
```

**Current capabilities:**
- Create task template from natural language
- Parse recurrence, day of week, difficulty, category, estimated time
- Assign to a named group member (by username match)
- Immediately generates occurrences + auto-assigns on creation

**Planned conversational flows (not yet built):**

*Flow 1 — Can't do a task:*
```
User:  "I can't do 'Clean bathroom' today, I'm sick"
Bot:   "Sorry to hear that. You have 2 emergency reassigns remaining this month.
        What would you like to do?
        1. Emergency reassign (broadcast to group)
        2. List on marketplace (offer bonus points)
        3. Swap with a specific person"
User:  "Swap with Jamie"
Bot:   "Swap request sent to Jamie for 'Clean bathroom'. I'll let you know when they respond."
```

*Flow 2 — Task creation:*
```
User:  "Add a weekly task to clean the bathroom on Fridays"
Bot:   "Done! Created 'Clean bathroom' (weekly, Fridays). Assigned to you for this week."
```

**What's needed to complete the chatbot:**
1. **Frontend** — `ChatbotView.vue` chat interface + Vue router entry
2. **Group context in prompt** — inject member names + existing templates so the model can resolve "swap with Jamie" and avoid duplicate templates
3. **Conversation history** — pass prior messages to Ollama so the bot remembers context mid-flow
4. **Action intents** — detect "can't do task X" intent → present options → execute chosen action (emergency reassign / marketplace / swap) via existing service methods
5. **Task lookup** — resolve "task X" from natural language to a specific `TaskOccurrence` for the requesting user

---

## Feature Prioritization (Phased Approach)

### Phase 1: MVP (Core Features) ✅
1. User authentication & household management
2. TaskTemplate & TaskOccurrence models
3. Basic task assignment (manual + simple rotation)
4. Calendar sync (read availability)
5. Task completion tracking
6. Basic WebSocket chat
7. Deadline reminders

### Phase 2: Smart Assignment & Swaps ✅
1. User task preferences
2. Smart assignment algorithm (fairness)
3. Task swap proposals
4. Emergency reassign
5. Assignment history tracking
6. Calendar events (write tasks to calendar)

### Phase 3: Gamification ✅
1. Streaks tracking
2. Points system
3. Leaderboard
4. Badges
5. "I'll do it later" (snooze)

### Phase 4: Advanced Features ✅
1. Smart suggestions (ML/pattern recognition)
2. Task marketplace
3. Photo proof
4. Stats dashboard
5. Customizable fairness algorithms
6. Group consensus voting system

### Phase 5: AI Chatbot (In Progress)
1. ✅ Local LLM infrastructure (Ollama + Phi-3 Mini)
2. ✅ Task creation via natural language
3. ⬜ Frontend chat view
4. ⬜ Group context injection (member names, existing templates)
5. ⬜ Conversational task management (can't do task → reassign/swap/marketplace)
6. ⬜ Conversation history within a session

### Phase 6: Polish & Scaling
1. Mobile PWA optimization
2. Performance optimization
3. Advanced notifications (email/SMS)
4. Multi-language support
5. Accessibility improvements

---

## Technical Implementation Notes

### WebSocket Architecture (Django Channels)
**Channels/Groups:**
- `household_{id}` → All members of a household
- `user_{id}` → Individual user notifications
- `chat_{household_id}` → Live chat messages

**Events:**
- `task.assigned` → User gets new task
- `task.completed` → Update leaderboard in real-time
- `swap.proposed` → Notify target user
- `emergency.help` → Broadcast to household
- `chat.message` → Live chat messages
- `notification.new` → Real-time alerts

### Background Jobs (Django Celery)
**Scheduled Tasks:**
- Generate recurring task occurrences (daily at midnight)
- Send deadline reminders (every 15 minutes check)
- Sync calendar availability (every 4 hours)
- Calculate leaderboard rankings (every hour)
- Generate smart suggestions (daily)
- Clean up expired swap proposals (daily)
- Update badge achievements (on task completion)

### API Endpoints Structure

**Authentication:**
- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/logout/`
- `GET /api/auth/user/`

**Households:**
- `GET /api/households/` → List user's households
- `POST /api/households/` → Create new household
- `GET /api/households/{id}/` → Household details
- `PATCH /api/households/{id}/` → Update settings
- `POST /api/households/{id}/invite/` → Invite member
- `GET /api/households/{id}/members/` → List members
- `GET /api/households/{id}/leaderboard/` → Leaderboard data
- `GET /api/households/{id}/stats/` → Household stats

**Task Templates:**
- `GET /api/households/{id}/task-templates/` → List templates
- `POST /api/households/{id}/task-templates/` → Create template
- `GET /api/task-templates/{id}/`
- `PATCH /api/task-templates/{id}/`
- `DELETE /api/task-templates/{id}/`

**Task Occurrences:**
- `GET /api/households/{id}/tasks/` → List all tasks (filterable)
- `GET /api/tasks/{id}/`
- `PATCH /api/tasks/{id}/` → Update status, snooze, etc.
- `POST /api/tasks/{id}/complete/` → Mark complete (with optional photo)
- `POST /api/tasks/{id}/snooze/` → Snooze task
- `POST /api/tasks/{id}/emergency-reassign/` → Emergency reassign
- `GET /api/users/me/tasks/` → Current user's tasks

**Task Swaps:**
- `POST /api/tasks/{id}/propose-swap/` → Create swap proposal
- `POST /api/swap-proposals/{id}/accept/`
- `POST /api/swap-proposals/{id}/reject/`
- `GET /api/users/me/swap-proposals/` → Pending proposals

**Marketplace:**
- `POST /api/tasks/{id}/list-marketplace/` → List on marketplace
- `GET /api/households/{id}/marketplace/` → View marketplace
- `POST /api/marketplace/{id}/claim/` → Claim task

**Preferences:**
- `GET /api/users/me/preferences/` → User task preferences
- `PATCH /api/users/me/preferences/` → Update preferences

**Calendar:**
- `POST /api/users/me/calendar/connect/` → OAuth flow initiation
- `GET /api/users/me/calendar/availability/` → Check availability
- `POST /api/users/me/calendar/sync/` → Force sync

**Stats & Gamification:**
- `GET /api/users/me/stats/` → User stats
- `GET /api/users/me/badges/` → Earned badges
- `GET /api/households/{id}/stats/` → Household stats

**Notifications:**
- `GET /api/users/me/notifications/` → List notifications
- `PATCH /api/notifications/{id}/read/` → Mark as read

**Chat:**
- `GET /api/households/{id}/chat/messages/` → Chat history (paginated)
- WebSocket handles real-time sending

**AI Assistant:**
- `POST /api/groups/{id}/assistant/` → Send message, get reply + action executed

---

## Security & Privacy Considerations

1. **Authentication:**
   - JWT tokens for API auth
   - Secure WebSocket connections (wss://)
   - OAuth tokens encrypted in database

2. **Authorization:**
   - Users can only access their households
   - Household-level permissions (admin vs member)
   - Task-level permissions (can only modify assigned tasks)

3. **Data Privacy:**
   - Calendar data only read, never stored (except availability flags)
   - Photos stored securely, household-scoped
   - Chat messages encrypted in transit (WSS)

4. **Rate Limiting:**
   - API endpoints rate-limited (Django Ratelimit)
   - WebSocket message throttling
   - Photo upload size limits (5MB max)

5. **Abuse Prevention:**
   - Emergency reassign limits
   - Swap proposal expiration
   - Marketplace listing frequency limits

---

## Open Questions & Decisions Needed

1. **Points System Values:**
   - How many points per task? (base 10, +difficulty modifier?)
   - Bonus point values (emergency help, marketplace, etc.)
   - Point decay over time? (or permanent?)

2. **Fairness Algorithm Default:**
   - Which algorithm should be default? (recommend: Time-based)
   - Allow households to switch mid-use?

3. **Photo Proof:**
   - Should it be opt-in or opt-out?
   - Storage limit per household?

4. **Task Marketplace:**
   - Phase 2 or Phase 4?
   - Bidding system or first-come-first-served?

5. **Notification Preferences:**
   - Let users customize which notifications they receive?
   - Quiet hours settings?

---

## Success Metrics (for launch)

1. **Engagement:**
   - Daily active users (DAU)
   - Tasks completed per household per week
   - Average streak length

2. **Fairness:**
   - Standard deviation of task distribution (lower = more fair)
   - User satisfaction surveys

3. **Collaboration:**
   - Task swap acceptance rate
   - Emergency reassign help rate
   - Chat message frequency

4. **Retention:**
   - 7-day retention rate
   - 30-day retention rate
   - Households still active after 90 days

---

## Questions Answered

### Q: Is Task Marketplace the same as Task Swaps?
**A:** No, it's an extension:
- **Swaps** = 1-to-1 trade between two specific users
- **Marketplace** = One user offers a task to anyone who wants it (with optional bonus)
- Recommend implementing Swaps first, Marketplace as Phase 4 enhancement

### Q: How does customizable fairness work?
**A:** Household selects algorithm type (time/count/difficulty/weighted):
- System tracks metrics based on selected algorithm
- Each user has a fairness score
- Tasks assigned to user with lowest score
- Can be visualized in stats dashboard
- Requires accurate time estimates when creating TaskTemplates

### Q: Photo Proof - who decides if it's required?
**A:** Three-tier system:
1. **Household-level:** Group admin enables globally (with optional group vote)
2. **Task-level:** Individual templates can override and require photos
3. **Enforcement:** Task cannot be marked complete without photo if required

### Q: Should we use Google Tasks API?
**A:** No, stick with Calendar API:
- Google Tasks API is limited (no recurrence, no time of day)
- Calendar Events API is more flexible
- You can create events with all the metadata you need
- Users already check their calendars more than Google Tasks

---

## Next Steps

1. **Database Schema Design:** Create Django models based on this plan
2. **API Specification:** Define detailed endpoint contracts (OpenAPI/Swagger)
3. **UI/UX Wireframes:** Sketch out key screens (dashboard, task list, swap flow, etc.)
4. **Calendar Integration POC:** Test Google/Outlook OAuth + Calendar API
5. **WebSocket POC:** Test Django Channels setup for real-time features
6. **Fairness Algorithm Testing:** Prototype assignment logic with sample data

---

**Total Estimated Development Time (rough):**
- Phase 1 (MVP): 8-10 weeks
- Phase 2 (Smart + Swaps): 4-6 weeks
- Phase 3 (Gamification): 3-4 weeks
- Phase 4 (Advanced): 4-6 weeks
- Phase 5 (Polish): 2-3 weeks

**Total: ~6-7 months for full feature set**

Start with Phase 1, get users testing, iterate based on feedback before building later phases!
