# Implementation Plan: Keyboard Entry for Habit Tracking

**Date**: 2025-12-30T03:54:52Z
**Git Commit**: 62fd8e6b8f07d09ace9729eeef8a75bc7d2056d9
**Branch**: main

## Overview

Add pure keyboard entry capability to the habit tracker's main entry UI. Users should be able to Tab between habit fields and use keyboard shortcuts (Y/N for binary, 1-9 for select types) to quickly enter values on desktop.

## Current State

The entry UI (`src/habit_tracker/templates/index.html`) renders habits in a form with these characteristics:

- **Structure**: Each habit is wrapped in `.habit-group` with `.habit-label` for the name
- **Auto-save**: `change` event listener triggers form submission via HTMX (lines 80-84)
- **Existing keyboard**: Only Ctrl+Enter to manually save (lines 87-91)
- **Habit types rendered**: binary (checkbox), single_select (radios), multi_select (checkboxes), journal (textarea), numeric (number input), time (time input)

Key file references:
- `src/habit_tracker/templates/index.html:17-70` - Habit rendering loop
- `src/habit_tracker/templates/base.html:11-86` - All CSS styles (inline)
- `docs/research/ui-mockup.html` - Visual design reference

## Desired End State

1. **Visual keyboard hints** - Desktop users see hints like "Press Y / N" for binary, "Press 1-4" for single select
2. **Option numbers** - Each option in select types shows its number (1, 2, 3...)
3. **Keyboard handlers** - When a habit group is focused:
   - Binary: `Y` checks, `N` unchecks
   - Single select: `1`-`9` selects corresponding option
   - Multi select: `1`-`9` toggles corresponding option
4. **Mobile-friendly** - Keyboard hints hidden on mobile (touch-first)
5. **Tab navigation** - Users can Tab between habit groups for keyboard flow

**Verification**: Tab to a binary habit and press Y, then Tab to a single select and press 2 - values should update and auto-save.

## What We're NOT Doing

- Global keyboard shortcuts (no shortcuts when not focused on a habit)
- Vim-style navigation (j/k to move between habits)
- Keyboard shortcuts for journal, numeric, or time habits (they use native input)
- Custom focus rings or accessibility enhancements beyond basic tabindex
- HTMX `hx-trigger` with key filters (plain JavaScript is simpler for this use case)

## Implementation Approach

Use vanilla JavaScript keyboard handlers attached to focusable `.habit-group` containers. When a habit group receives a keydown event, determine the habit type and handle appropriately. The existing auto-save mechanism (change event → requestSubmit) handles persistence.

---

## Phase 1: Add Keyboard Hint CSS Styles

### Overview
Add CSS classes for keyboard hints and option numbers to base.html.

### Changes Required

#### base.html
**File**: `src/habit_tracker/templates/base.html:18-19`
**Changes**: Add CSS for `.habit-header`, `.keyboard-hint`, `.option-item`, `.option-number`

Add after line 19 (after `.options label` rule):

```css
/* Keyboard entry styles */
.habit-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}
.keyboard-hint {
    font-size: 0.75rem;
    color: var(--pico-muted-color);
    background: var(--pico-secondary-background);
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-family: monospace;
}
.option-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.option-number {
    font-size: 0.7rem;
    color: var(--pico-muted-color);
    background: var(--pico-secondary-background);
    width: 1.25rem;
    height: 1.25rem;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 0.25rem;
    font-family: monospace;
}
/* Hide keyboard hints on mobile */
@media (max-width: 600px) {
    .keyboard-hint { display: none; }
    .option-number { display: none; }
}
```

### Success Criteria

#### Automated Verification:
- [x] Type check passes: `make fix`
- [x] Tests pass: `make test`

#### Manual Verification:
- [x] No visual changes yet (styles not applied to any elements)
- [x] Dev server runs: `make dev`

---

## Phase 2: Update Template Structure for Keyboard Hints

### Overview
Modify index.html to add keyboard hints and option numbers to the habit entry UI.

### Changes Required

#### index.html - Binary Habit
**File**: `src/habit_tracker/templates/index.html:18-26`
**Changes**: Add `.habit-header` with keyboard hint, make group focusable

Replace lines 18-26:

```html
{% for habit in habits %}
<div class="habit-group" tabindex="0" data-habit-type="{{ habit.type }}" data-habit-id="{{ habit.id }}">
    {% if habit.type == "binary" %}
    <div class="habit-header">
        <span class="habit-label">{{ habit.name }}</span>
        <span class="keyboard-hint">Press Y / N</span>
    </div>
    <label>
        <input type="checkbox" name="habit_{{ habit.id }}"
               {% if entries.get(habit.id) and entries[habit.id].value %}checked{% endif %}>
        Yes
    </label>
```

#### index.html - Single Select Habit
**File**: `src/habit_tracker/templates/index.html:28-39`
**Changes**: Add header with dynamic hint, add option numbers

Replace single_select block:

```html
{% elif habit.type == "single_select" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Press 1-{{ habit.options|length }}</span>
</div>
<fieldset>
    <div class="options">
    {% for option in habit.options %}
    <div class="option-item">
        <span class="option-number">{{ loop.index }}</span>
        <label>
            <input type="radio" name="habit_{{ habit.id }}" value="{{ option }}"
                   {% if entries.get(habit.id) and entries[habit.id].value == option %}checked{% endif %}>
            {{ option }}
        </label>
    </div>
    {% endfor %}
    </div>
</fieldset>
```

#### index.html - Journal Habit
**File**: `src/habit_tracker/templates/index.html:41-42`
**Changes**: Add header with hint for journal

Replace journal block:

```html
{% elif habit.type == "journal" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Tab to focus, type freely</span>
</div>
<textarea name="habit_{{ habit.id }}" rows="3">{{ entries.get(habit.id).value if entries.get(habit.id) else '' }}</textarea>
```

#### index.html - Numeric Habit
**File**: `src/habit_tracker/templates/index.html:44-50`
**Changes**: Add header with hint for numeric

Replace numeric block:

```html
{% elif habit.type == "numeric" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Tab to focus, enter number</span>
</div>
<div class="numeric-input">
    <input type="number" name="habit_{{ habit.id }}"
           value="{{ entries.get(habit.id).value if entries.get(habit.id) else '' }}"
           min="0" step="1" inputmode="numeric">
    {% if habit.unit %}<span class="unit">{{ habit.unit }}</span>{% endif %}
</div>
```

#### index.html - Time Habit
**File**: `src/habit_tracker/templates/index.html:52-54`
**Changes**: Add header with hint for time

Replace time block:

```html
{% elif habit.type == "time" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Tab to focus, enter time</span>
</div>
<input type="time" name="habit_{{ habit.id }}"
       value="{{ entries.get(habit.id).value.strftime('%H:%M') if entries.get(habit.id) else '' }}">
```

#### index.html - Multi Select Habit
**File**: `src/habit_tracker/templates/index.html:56-67`
**Changes**: Add header with dynamic hint, add option numbers

Replace multi_select block:

```html
{% elif habit.type == "multi_select" %}
<div class="habit-header">
    <span class="habit-label">{{ habit.name }}</span>
    <span class="keyboard-hint">Press 1-{{ habit.options|length }} to toggle</span>
</div>
<fieldset>
    <div class="options">
    {% for option in habit.options %}
    <div class="option-item">
        <span class="option-number">{{ loop.index }}</span>
        <label>
            <input type="checkbox" name="habit_{{ habit.id }}" value="{{ option }}"
                   {% if entries.get(habit.id) and option in entries[habit.id].value %}checked{% endif %}>
            {{ option }}
        </label>
    </div>
    {% endfor %}
    </div>
</fieldset>
{% endif %}
</div>
{% endfor %}
```

#### index.html - Remove old habit-label
**File**: `src/habit_tracker/templates/index.html:19`
**Changes**: Remove the standalone `<div class="habit-label">{{ habit.name }}</div>` line since it's now inside each habit type's header.

### Success Criteria

#### Automated Verification:
- [x] Type check passes: `make fix`
- [x] Tests pass: `make test`

#### Manual Verification:
- [x] Binary habit shows "Press Y / N" hint on desktop
- [x] Single select shows "Press 1-N" hint with option numbers
- [x] Multi select shows "Press 1-N to toggle" hint with option numbers
- [x] Journal/Numeric/Time show appropriate hints
- [x] Hints hidden on mobile (resize browser or use dev tools)
- [x] Habit groups are tabbable (Tab key moves focus between them)

---

## Phase 3: Implement Keyboard Event Handlers

### Overview
Add JavaScript to handle keyboard shortcuts for binary and select habit types.

### Changes Required

#### index.html - JavaScript
**File**: `src/habit_tracker/templates/index.html:78-92`
**Changes**: Add keyboard handler for habit groups

Add after the existing keyboard shortcut code (after line 91, before `</script>`):

```javascript
// Keyboard entry for habits
document.querySelectorAll('.habit-group').forEach(group => {
    group.addEventListener('keydown', (e) => {
        const habitType = group.dataset.habitType;
        const key = e.key.toLowerCase();

        // Ignore if typing in a text field
        if (['INPUT', 'TEXTAREA'].includes(e.target.tagName) &&
            !['checkbox', 'radio'].includes(e.target.type)) {
            return;
        }

        if (habitType === 'binary') {
            const checkbox = group.querySelector('input[type="checkbox"]');
            if (key === 'y') {
                checkbox.checked = true;
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                e.preventDefault();
            } else if (key === 'n') {
                checkbox.checked = false;
                checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                e.preventDefault();
            }
        } else if (habitType === 'single_select') {
            const num = parseInt(key);
            if (num >= 1 && num <= 9) {
                const radios = group.querySelectorAll('input[type="radio"]');
                if (num <= radios.length) {
                    radios[num - 1].checked = true;
                    radios[num - 1].dispatchEvent(new Event('change', { bubbles: true }));
                    e.preventDefault();
                }
            }
        } else if (habitType === 'multi_select') {
            const num = parseInt(key);
            if (num >= 1 && num <= 9) {
                const checkboxes = group.querySelectorAll('input[type="checkbox"]');
                if (num <= checkboxes.length) {
                    checkboxes[num - 1].checked = !checkboxes[num - 1].checked;
                    checkboxes[num - 1].dispatchEvent(new Event('change', { bubbles: true }));
                    e.preventDefault();
                }
            }
        }
    });
});
```

### Success Criteria

#### Automated Verification:
- [x] Type check passes: `make fix`
- [x] Tests pass: `make test`

#### Manual Verification:
- [x] Tab to binary habit, press Y - checkbox becomes checked, "Saved!" appears
- [x] Press N on same habit - checkbox unchecked, saves
- [x] Tab to single select, press 1 - first option selected, saves
- [x] Press 2 - second option selected, saves
- [x] Tab to multi select, press 1 - first option toggles on, saves
- [x] Press 1 again - first option toggles off, saves
- [x] Press 2 - second option toggles on (first still off)
- [x] Journal/Numeric/Time - can Tab to them and type normally
- [x] Pressing Y/N/1-9 while typing in textarea does NOT trigger shortcuts

---

## Phase 4: Polish and Focus Styling

### Overview
Add visual feedback for focused habit groups and ensure keyboard hints match mockup spacing.

### Changes Required

#### base.html - Focus styles
**File**: `src/habit_tracker/templates/base.html`
**Changes**: Add focus outline for habit groups

Add to the keyboard entry styles section:

```css
.habit-group:focus {
    outline: 2px solid var(--pico-primary);
    outline-offset: 4px;
    border-radius: 0.25rem;
}
.habit-group:focus-within {
    outline: 2px solid var(--pico-primary);
    outline-offset: 4px;
    border-radius: 0.25rem;
}
```

### Success Criteria

#### Automated Verification:
- [x] Type check passes: `make fix`
- [x] Tests pass: `make test`

#### Manual Verification:
- [x] Tabbing to a habit group shows a visible focus ring
- [x] Focus ring uses the primary color (blue by default)
- [x] Clicking into a text input within a habit also shows the group focus
- [x] Overall visual appearance matches the mockup image

---

## Testing Strategy

### Existing Tests
The current tests in `tests/test_main.py` test form submission behavior, which should continue to work since we're only adding UI enhancements.

### Manual Testing Checklist

| Scenario | Expected Result |
|----------|-----------------|
| Tab through all habits | Focus moves between habit groups |
| Binary: Press Y | Checkbox checked, auto-saves |
| Binary: Press N | Checkbox unchecked, auto-saves |
| Single select: Press 1 | First option selected, auto-saves |
| Single select: Press 4 on 3-option habit | Nothing happens (out of range) |
| Multi select: Press 1 | First option toggled, auto-saves |
| Multi select: Press 1 again | First option toggled off, auto-saves |
| Journal: Type text | Normal text entry works |
| Numeric: Type 42 | Normal number entry works |
| Time: Enter 22:30 | Normal time entry works |
| Mobile view (< 600px) | Keyboard hints hidden |
| Ctrl+Enter | Manual save still works |

### Edge Cases

- Habits with more than 9 options (only 1-9 accessible via keyboard)
- Empty form (no habits) - should not error
- Rapid key presses - should debounce via existing auto-save

---

## Code References

- `src/habit_tracker/templates/index.html:17-70` - Habit rendering loop
- `src/habit_tracker/templates/index.html:78-92` - Existing JavaScript
- `src/habit_tracker/templates/base.html:11-86` - All CSS styles
- `src/habit_tracker/templates/base.html:18-19` - Options styling
- `docs/research/ui-mockup.html:77-108` - CSS design reference
- `docs/research/ui-mockup.html:284-336` - HTML structure reference
- `docs/research/2025-12-27-ui-capabilities.md:52-77` - HTMX keyboard research

## Open Questions

None - all questions resolved during research.
