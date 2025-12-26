# Research: Highly-Upvoted Habit Trackers from Hacker News (2023-2025)

**Date**: 2025-12-26T16:47:02Z
**Branch**: N/A (no git repo)

## Research Question
Find the most highly up-voted habit trackers posted to Hacker News over the last 2 years. Clone them from GitHub and analyze each one thoroughly.

## Summary

I analyzed 6 habit tracker repositories that appeared on Hacker News or are highly-starred open-source projects. They represent a diverse range of approaches:

| Project | Stars | Language | Platform | Key Differentiator |
|---------|-------|----------|----------|-------------------|
| **Habitica** | 13,557 | JavaScript | Web/Mobile | Gamification (RPG mechanics) |
| **Loop Habit Tracker** | 9,407 | Kotlin | Android | Mature Android app, smart scoring |
| **dijo** | 2,904 | Rust | Terminal | Scriptable TUI, Vim-like |
| **BeaverHabits** | 1,600 | Python | Web (self-hosted) | NiceGUI, flexible storage backends |
| **E-Ink Habit Tracker** | 9 | Python | Raspberry Pi | Physical e-ink display |
| **Wheel Habit Tracker** | 29 | JavaScript | Web (browser) | Circular visualization |

## Detailed Findings

### 1. Habitica (HabitRPG/habitica)

**Location**: `/tmp/habit-tracker-habitica`
**GitHub**: https://github.com/HabitRPG/habitica
**Stars**: 13,557 | **Forks**: 4,376

**Architecture**:
- Full-stack JavaScript application
- Backend: Node.js + Express.js + MongoDB
- Frontend: Vue.js 2 + Bootstrap Vue
- Shared code between client/server in `/website/common/`

**Data Model** (`/website/server/models/task.js`):
- 4 task types: `habit`, `daily`, `todo`, `reward`
- Task value oscillates between -47.27 and 21.27 using inverse logarithmic formula
- Streak tracking for consecutive completions
- Checklist support for sub-tasks

**Gamification System** (`/website/server/libs/spells.js`, `/website/server/libs/cron.js`):
- RPG stats: HP, MP, EXP, GP (gold), Level
- 4 attributes: STR, CON, INT, PER
- 4 classes: Warrior, Rogue, Wizard, Healer
- Spell casting with mana costs
- Party quests with 4-player combat
- 100+ achievement badges

**Key Technical Decisions**:
- Cluster module for multi-core load balancing
- Daily cron job handles habit resets with timezone awareness
- Task scoring formula: `0.9747 ^ taskValue` for natural difficulty curve
- Discriminator pattern for polymorphic task storage in MongoDB

---

### 2. Loop Habit Tracker (iSoron/uhabits)

**Location**: `/tmp/habit-tracker-uhabits`
**GitHub**: https://github.com/iSoron/uhabits
**Stars**: 9,407 | **Forks**: 1,106

**Architecture**:
- Kotlin Multiplatform project (positioned for future iOS support)
- `/uhabits-core/` - Pure JVM business logic (105 Kotlin files)
- `/uhabits-android/` - Android UI layer (142 Kotlin files)

**Data Model** (`uhabits-core/src/jvmMain/java/org/isoron/uhabits/core/models/`):
- `Habit.kt` (166 lines): Core entity with composed lists
- `Entry.kt` (80 lines): 5 states - YES_MANUAL, YES_AUTO, NO, SKIP, UNKNOWN
- `Frequency.kt` (50 lines): Rational number (numerator/denominator) for flexible schedules
- `Score.kt` (51 lines): Exponential decay scoring prevents one bad day from destroying progress

**Intelligent Scoring Algorithm**:
```kotlin
// Score.compute() formula
multiplier = 0.5^(sqrt(frequency)/13)
// Higher frequency = faster decay = more responsive scoring
```

**Key Technical Decisions**:
- Custom reflection-based ORM with `@Table`/`@Column` annotations (`Repository.kt`, 256 lines)
- Command pattern for all state mutations with async execution
- Observer pattern for reactive UI updates
- HabitCardListCache (427 lines) optimizes rendering for 200+ habits

---

### 3. dijo (oppiliappan/dijo)

**Location**: `/tmp/habit-tracker-dijo`
**GitHub**: https://github.com/oppiliappan/dijo
**Stars**: 2,904 | **Forks**: 70

**Architecture**:
- ~2,100 lines of Rust across 17 source files
- Trait-based composition with polymorphic serialization
- Cursive TUI framework (ncurses-based)

**Data Model** (`src/habit/`):
- `traits.rs` (105 lines): Core `Habit` trait with associated `HabitType`
- Three implementations: `Bit` (binary), `Count` (numeric), `Float` (decimal with precision)
- `#[typetag::serde]` enables polymorphic JSON serialization

**Scriptability Features**:
- Auto-habits stored in separate JSON file with file watching
- External programs can track via: `dijo -c "track-up habit_name"`
- Enables git commit counting, shell hooks, etc.

**Key Technical Decisions**:
- Vim-like keybindings (hjkl navigation, : commands)
- ShadowView trait provides generic rendering for all habit types
- Date cursor prevents viewing future dates
- Separate regular/auto habit files for external script integration

---

### 4. BeaverHabits (daya0576/beaverhabits)

**Location**: `/tmp/habit-tracker-beaverhabits`
**GitHub**: https://github.com/daya0576/beaverhabits
**Stars**: 1,600 | **Forks**: 61

**Architecture**:
- ~7,181 lines of Python across 59 files
- FastAPI backend + NiceGUI reactive frontend (same Python process)
- Protocol-based abstraction for maximum flexibility

**Data Model** (`beaverhabits/storage/storage.py`):
- `Habit[R: CheckedRecord]` Protocol (lines 102-173)
- `HabitFrequency`: Pattern-based like "2/7D" (2 times per week)
- `HabitStatus` enum: active, archived, soft_delete

**Flexible Storage Backends** (`beaverhabits/storage/__init__.py`):
1. `SESSION` - In-memory (demo mode)
2. `USER_DISK` - JSON files per user
3. `USER_DATABASE` - PostgreSQL/SQLite via SQLAlchemy async

**Key Technical Decisions**:
- Observable dictionary pattern for automatic persistence
- Period-based completion calculation with moving window algorithm
- NiceGUI eliminates separate frontend build process
- Multi-stage Docker build strips unused NiceGUI libraries

---

### 5. E-Ink Habit Tracker (spetca/habit-tracker)

**Location**: `/tmp/habit-tracker-eink`
**GitHub**: https://github.com/spetca/habit-tracker
**Stars**: 9

**Architecture**:
- Single Python file (`habit.py`, 10,899 bytes)
- Raspberry Pi Zero W + Waveshare 2.13" e-ink display
- Dual mode: physical display + Flask web interface

**Data Model** (`habit_data.json`):
```json
{"2025-01-05": 1, "2025-01-06": 1, "2025-01-07": 1}
```
- Key: ISO date string
- Value: 1 (presence indicates completion)

**Display Logic**:
- 14-week rotating windows (4 periods per year)
- 14x7 grid (14 weeks x 7 days)
- Filled squares for completed, outlined for incomplete
- Updates every 24 hours, sleeps between updates

**Key Technical Decisions**:
- Thread-safe file operations with `threading.Lock()`
- Display caching prevents unnecessary e-ink refreshes
- Optimistic UI updates in web interface
- Systemd service with pigpiod dependency

---

### 6. Wheel Habit Tracker (anshulmittal712/habit-tracker)

**Location**: `/tmp/habit-tracker-wheel`
**GitHub**: https://github.com/anshulmittal712/habit-tracker
**Stars**: 29

**Architecture**:
- Vanilla JavaScript single-page application (488 lines)
- SVG-based circular visualization
- localStorage for persistence

**Data Model**:
```javascript
state = {
    month: 'YYYY-MM',
    dailyHabits: [],      // habit names
    weeklyHabits: [],
    monthlyHabits: [],
    dailyProgress: {},    // {habitIndex: [day1, day2, ...]}
    weeklyProgress: {},
    monthlyProgress: {}
};
```

**Wheel Visualization** (`habitTracker.js`, lines 79-175):
- 270-degree arc (leaves room for labels)
- Concentric rings per habit (radius decreases by 30px)
- Each day = one segment
- 7-color cycling palette

**Key Technical Decisions**:
- Complete wheel redraw on every toggle (simplicity over optimization)
- Polar-to-Cartesian coordinate conversion for segment placement
- Native `<input type="month">` for browser date picker
- No build tools or dependencies

---

## Architecture Notes

### Common Patterns Observed

1. **Data Storage Approaches**:
   - JSON files (dijo, e-ink, BeaverHabits disk mode)
   - SQLite (uhabits, BeaverHabits)
   - MongoDB (Habitica)
   - localStorage (wheel tracker)

2. **Scoring/Streak Algorithms**:
   - Binary yes/no (most simple trackers)
   - Frequency-based (uhabits: numerator/denominator)
   - Exponential decay (uhabits: prevents streak destruction)
   - Inverse logarithmic (Habitica: task value oscillation)

3. **UI Architectures**:
   - Native mobile (uhabits - Android)
   - SPA with Vue/React (Habitica)
   - Server-rendered Python UI (BeaverHabits - NiceGUI)
   - Terminal UI (dijo - Cursive/ncurses)
   - Vanilla JS + SVG (wheel tracker)
   - Physical display (e-ink tracker)

4. **Extensibility Patterns**:
   - Command pattern for state mutations (uhabits)
   - Trait/Protocol abstraction (dijo, BeaverHabits)
   - Plugin/webhook systems (Habitica)
   - Scriptable CLI integration (dijo auto-habits)

### Technology Stack Comparison

| Feature | Habitica | uhabits | dijo | BeaverHabits | E-Ink | Wheel |
|---------|----------|---------|------|--------------|-------|-------|
| Language | JS | Kotlin | Rust | Python | Python | JS |
| Database | MongoDB | SQLite | JSON files | SQL/JSON | JSON | localStorage |
| Frontend | Vue.js 2 | Android Views | Cursive TUI | NiceGUI | Flask | Vanilla JS |
| Auth | JWT + Social | N/A | N/A | fastapi-users | N/A | N/A |
| Offline | PWA | Full offline | Full offline | Optional | Always | Full offline |
| Self-hosted | Yes | N/A | Yes | Yes | Yes | Yes |

## Code References

### Habitica
- `website/server/models/user/schema.js` - User model (26,459 bytes)
- `website/server/models/task.js` - Task discriminator pattern
- `website/server/libs/cron.js` (535 lines) - Daily reset logic
- `website/common/script/ops/scoreTask.js` - Core scoring math

### Loop Habit Tracker (uhabits)
- `uhabits-core/src/jvmMain/java/org/isoron/uhabits/core/models/Habit.kt` (166 lines)
- `uhabits-core/src/jvmMain/java/org/isoron/uhabits/core/models/ScoreList.kt` - Decay scoring
- `uhabits-core/src/jvmMain/java/org/isoron/uhabits/core/database/Repository.kt` (256 lines)
- `uhabits-core/src/jvmMain/java/org/isoron/uhabits/core/ui/screens/habits/list/HabitCardListCache.kt` (427 lines)

### dijo
- `src/habit/traits.rs` (105 lines) - Core trait definitions
- `src/command.rs` (244 lines) - Command parsing
- `src/app/impl_self.rs` (293 lines) - App business logic
- `src/views.rs` (204 lines) - ShadowView rendering

### BeaverHabits
- `beaverhabits/storage/storage.py` (278 lines) - Protocol definitions
- `beaverhabits/core/completions.py` - Period completion algorithm
- `beaverhabits/storage/user_file.py` - Observable dictionary pattern
- `beaverhabits/routes/api.py` - REST API endpoints

### E-Ink Tracker
- `habit.py` (all logic in single file)
- `templates/index.html` (308 lines) - Full-year web calendar

### Wheel Tracker
- `habitTracker.js` (488 lines) - Complete application
- `styles.css` (317 lines) - Responsive styling

## Open Questions

1. **Mobile-first vs Web-first**: uhabits (Android-native) vs Habitica (web-first with mobile apps) - which approach provides better UX?

2. **Gamification effectiveness**: Habitica's RPG mechanics are elaborate - does this complexity help or hinder habit formation?

3. **Self-hosting adoption**: BeaverHabits and dijo target self-hosters - what's the market size for privacy-focused habit trackers?

4. **E-ink displays**: The e-ink tracker is novel - could ambient/always-visible habit displays improve adherence?

5. **Scoring algorithms**: uhabits' exponential decay vs Habitica's oscillating values - which better models human behavior?

## Sources

- [Show HN: A free minimalist daily habit tracker](https://news.ycombinator.com/item?id=40893866) - 158 points
- [Show HN: Patterns – Habit Tracker App](https://news.ycombinator.com/item?id=38174614) - 73 points
- [Show HN: Habby – A straightforward bullet journal with habit tracking](https://news.ycombinator.com/item?id=42569014) - 63 points
- [Show HN: Minimal e-ink habit tracker](https://github.com/spetca/habit-tracker)
- [Loop Habit Tracker](https://github.com/iSoron/uhabits)
- [Habitica](https://github.com/HabitRPG/habitica)
- [dijo](https://github.com/oppiliappan/dijo)
- [BeaverHabits](https://github.com/daya0576/beaverhabits)
- [Wheel Habit Tracker](https://github.com/anshulmittal712/habit-tracker)
