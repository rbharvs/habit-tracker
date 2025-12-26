# Research: Google Sheets Habit Tracker Example

**Date**: 2025-12-26

## Research Question

Analyze a habit tracker built in Google Sheets, understanding its structure, data model, and tracking methodology.

## Summary

This habit tracker is a Google Sheets-based system for tracking both daily and weekly habits. It uses a week-based grid layout with color coding to indicate habit completion status. The system tracks 7-8 daily habits and 4 weekly habits, with separate sheets for raw tracking data, helper calculations, and aggregate statistics.

## File Structure

```
habits/
├── dailies.html           # Daily habits tracking (main sheet)
├── dailies-helper.html    # Helper sheet with numeric values
├── weeklies-helper.html   # Weekly habits with numeric values
├── stats.html             # Aggregated statistics dashboard
└── resources/
    └── sheet.css          # Shared Google Sheets styling
```

## Detailed Findings

### Sheet Types and Purposes

#### 1. Daily Tracking Sheets

Primary tracking interface for daily habits. Structure:
- **Layout**: Habit sections stacked vertically, each with 7 day rows
- **Columns**: Week numbers (01-53) spanning the full year
- **Rows**: Days of week (Monday-Sunday) with date numbers
- **Color coding**: Visual status indicators (see Color System below)

#### 2. Helper Sheets

Contain the underlying numeric data:
- **Values**: Numeric counts (0, 1, 2...) instead of color-only
- **Purpose**: Source data for calculations and statistics
- Used for formula-based aggregation in the stats sheet

#### 3. Statistics Sheet

Dashboard aggregating daily habit performance:

| Column | Content | Example |
|--------|---------|---------|
| B | Habit name | "exercise" |
| C | Current completion % | "75%" |
| D | Goal/target % | "80%" |
| E | Days completed (count) | "120" |
| F | Current streak | "6" |

### Color Coding System

The spreadsheet uses conditional formatting with these background colors:

| Color | Hex Code | Meaning |
|-------|----------|---------|
| Green | `#d9ead3` | Habit completed/success |
| Red | `#f4cccc` | Habit not completed/failed |
| Yellow | `#fff2cc` | Partial completion |
| Gray | `#d9d9d9` | Not applicable (e.g., rest day) |
| White | `#ffffff` | Default/no data |

### Example Daily Habits

Example habits that could be tracked:
1. **exercise** - Workout sessions (GRAY used for rest days)
2. **read** - Daily reading time
3. **meditate** - Meditation practice
4. **drink water** - Hydration goal (YELLOW for partial)
5. **journal** - Daily journaling
6. **sleep by 11pm** - Bedtime goal
7. **no junk food** - Diet tracking (YELLOW for partial)

### Example Weekly Habits

Weekly habits tracked with completion counts per week:
1. **meal prep** - Weekly meal preparation
2. **review goals** - Weekly goal review
3. **clean house** - Weekly cleaning
4. **call family** - Weekly family call

### Grid Structure

```
Daily Habit Section Layout:
┌─────────────────────────────────────────────────────────────┐
│ [Habit Name]                                      (colspan) │
├─────────┬──────┬──────┬──────┬──────┬──────┬─────┬─────────┤
│         │  01  │  02  │  03  │  04  │  05  │ ... │   52    │ <- Week numbers
├─────────┼──────┼──────┼──────┼──────┼──────┼─────┼─────────┤
│  1 Mo   │ [04] │ [11] │ [18] │ [25] │      │     │         │ <- Date + color
│  2 Tu   │ [05] │ [12] │ [19] │ [26] │      │     │         │
│  3 We   │ [06] │ [13] │ [20] │ [27] │      │     │         │
│  4 Th   │ [07] │ [14] │ [21] │ [28] │      │     │         │
│  5 Fr   │ [08] │ [15] │ [22] │ [29] │      │     │         │
│  6 Sa   │ [09] │ [16] │ [23] │ [30] │      │     │         │
│  7 Su   │ [10] │ [17] │ [24] │ [31] │      │     │         │
└─────────┴──────┴──────┴──────┴──────┴──────┴─────┴─────────┘
```

### Data Entry Pattern

The user would:
1. Open the dailies sheet at the current week column
2. Color the appropriate day cell based on habit completion:
   - Select cell, apply green fill if completed
   - Apply red fill if not completed
   - Apply yellow for partial completion
   - Leave gray for N/A (like workout rest days)
3. Helper sheets use formulas to convert colors to numbers
4. Stats sheet pulls from helper sheets for aggregate calculations

### Technical Implementation

#### HTML Structure (Google Sheets Export)
- Each sheet exports as a single HTML table with `class="waffle"`
- CSS classes (s0, s1, s2, etc.) define cell styles including background colors
- Cells use `colspan` for section headers
- Row/column headers preserved with spreadsheet-style identifiers (A, B, C... and 1, 2, 3...)

#### Key CSS Classes
```css
.s7  { background-color: #d9d9d9; }  /* GRAY - N/A */
.s8  { background-color: #f4cccc; }  /* RED - failed */
.s9  { background-color: #fff2cc; }  /* YELLOW - partial */
.s10 { background-color: #d9ead3; }  /* GREEN - success */
```
Note: Class numbers vary between files; colors are consistent.

## Architecture Notes

### Design Patterns

1. **Week-based grid**: All daily habits organized by ISO week numbers (01-53)
2. **Color-first tracking**: Primary data entry via cell background color
3. **Separation of concerns**: Raw tracking, helper calculations, and stats in separate sheets
4. **Partial tracking**: YELLOW color allows for non-binary tracking on some habits

### Data Flow

```
Dailies Sheet (color entry)
         ↓
Dailies-Helper (formula converts to numbers)
         ↓
Stats Sheet (aggregates with COUNTIF/SUMIF)
```

### Calendar Alignment

- Uses ISO week numbering (Week 01 starts first Monday of year)
- 53-week support for leap years
- Days numbered 1-7 with abbreviations (Mo, Tu, We, Th, Fr, Sa, Su)

## Key Takeaways

1. Color-coded cells provide quick visual feedback
2. Week-based layout shows patterns over time
3. Helper sheets separate presentation from data
4. Stats sheet enables goal tracking and streaks
