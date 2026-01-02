# Implementation Plan: Client Timezone-Based "Today" Date

**Date**: 2026-01-02T01:44:47Z
**Git Commit**: 2c3e155ca1f31cdbcfcaaf302c8fa8adf948103b
**Branch**: main

## Overview

When a user lands on the index (`/`) page without a `day` query parameter, the page should show entries for "today" based on the client's timezone, not the server's. Currently, the server uses `date.today()` which returns the server's local date. A user in a timezone ahead or behind the server could see the wrong day's entries.

## Current State

- `src/habit_tracker/main.py:44` - Uses `date.today()` when no `day` param is provided
- `src/habit_tracker/main.py:58` - Compares `target_date == date.today()` to determine `is_today`
- The index page accepts an optional `day` query parameter in ISO format (`YYYY-MM-DD`)
- No client-side timezone detection currently exists

## Desired End State

1. Landing on `/` redirects to `/?day=YYYY-MM-DD` where the date is the client's local "today"
2. The `is_today` check accounts for the client's timezone, not the server's
3. Navigation and date display work correctly across timezone boundaries
4. The solution should be simple and use only client-side JavaScript (no cookies or server sessions)

### Verification

- A user whose browser is set to a timezone different from the server sees their local "today" when landing on `/`
- The "Next" navigation button is hidden when viewing the client's "today" (not the server's)
- Direct links with `?day=...` continue to work as expected

## What We're NOT Doing

- Storing user timezone preferences server-side
- Using cookies for timezone detection
- Changing how dates are stored or processed server-side (dates remain naive)
- Adding timezone awareness to the Python date/time models

## Implementation Approach

Use a simple client-side redirect pattern:
1. When the page loads without a `day` parameter, JavaScript detects the client's local date
2. If the current URL lacks a `day` parameter, redirect to `/?day={clientToday}`
3. Pass the client's "today" to the template to properly compute `is_today`

The cleanest approach: add a small JavaScript snippet that runs on page load and redirects if no `day` parameter is present.

---

## Phase 1: Client-Side "Today" Redirect

### Overview

Add JavaScript to detect the client's timezone and redirect to the correct date when landing on `/` without a day parameter.

### Changes Required

#### `src/habit_tracker/templates/base.html`

**File**: `src/habit_tracker/templates/base.html`
**Changes**: Add a script in `<head>` (before rendering) that redirects if no `day` param

```javascript
<script>
// Redirect to client's "today" if no day parameter specified
(function() {
    const params = new URLSearchParams(window.location.search);
    if (!params.has('day')) {
        const today = new Date().toISOString().split('T')[0];
        params.set('day', today);
        window.location.replace('?' + params.toString());
    }
})();
</script>
```

This script:
- Runs immediately before the page renders
- Checks if `day` is already in the URL
- If not, computes the client's local date in ISO format
- Redirects using `replace()` (no history entry) to `/?day=YYYY-MM-DD`

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix` (includes type check)
- [x] Lint passes: `make fix`

#### Manual Verification:
- [ ] Landing on `/` redirects to `/?day=YYYY-MM-DD` (client's today)
- [ ] Landing on `/?day=2025-12-25` does NOT redirect (day param present)
- [ ] The redirect is imperceptible (no flicker, uses `replace()`)

---

## Phase 2: Fix `is_today` Logic

### Overview

The server currently computes `is_today` using `date.today()` on the server. After Phase 1, this comparison becomes incorrect because `target_date` is now the client's "today" but `date.today()` is the server's "today".

Since the client always provides a `day` parameter after the redirect, we need to compute `is_today` client-side or pass the client's "today" to the server.

The simplest fix: compute `is_today` in JavaScript after page load, showing/hiding the "Next" link accordingly.

### Changes Required

#### `src/habit_tracker/main.py`

**File**: `src/habit_tracker/main.py:58`
**Changes**: Remove the `is_today` computation from Python (or always pass `False`)

```python
# Change from:
"is_today": target_date == date.today(),

# Change to:
"is_today": False,  # Computed client-side for timezone accuracy
```

#### `src/habit_tracker/templates/index.html`

**File**: `src/habit_tracker/templates/index.html`
**Changes**: Add JavaScript to compute `is_today` client-side and hide "Next" if true

The template currently shows/hides the "Next" link based on `is_today`:
```html
{% if not is_today %}
<a href="?day={{ next_date }}">Next &rarr;</a>
{% else %}
<span></span>
{% endif %}
```

Change to always render the "Next" link, but hide it via JavaScript if viewing today:

```html
<a href="?day={{ next_date }}" id="next-link">Next &rarr;</a>
```

Add JavaScript in the `{% block scripts %}`:
```javascript
// Hide "Next" link if viewing client's today
(function() {
    const params = new URLSearchParams(window.location.search);
    const viewingDate = params.get('day');
    const clientToday = new Date().toISOString().split('T')[0];
    if (viewingDate === clientToday) {
        document.getElementById('next-link').style.display = 'none';
    }
})();
```

### Success Criteria

#### Automated Verification:
- [x] Tests pass: `make test`
- [x] Type check passes: `make fix`
- [x] Lint passes: `make fix`

#### Manual Verification:
- [ ] When viewing the client's "today", "Next" link is hidden
- [ ] When viewing any other date, "Next" link is visible
- [ ] Navigation prev/next works correctly across dates

---

## Testing Strategy

### Existing Tests

No specific tests exist for timezone handling. The implementation is UI/JavaScript focused, so testing is primarily manual.

### Manual Testing Approach

1. **Simulate different timezones**: Use browser DevTools to override the date/time
   - Chrome: DevTools > Sensors > Override geolocation/locale
   - Or use `Date` mock in console

2. **Test scenarios**:
   - Server in UTC, client in UTC+12: Landing on `/` should show "tomorrow" from server's perspective
   - Server in UTC, client in UTC-12: Landing on `/` should show "yesterday" from server's perspective

### Edge Cases

- Midnight boundary: User loads page at 11:59 PM, date changes while on page
  - Not addressed: Page will show original day until refresh (acceptable behavior)
- URL manipulation: User manually enters future date
  - Still works, "Next" link will be visible (acceptable)

## Code References

- `src/habit_tracker/main.py:41-60` - Index route with `day` parameter and `is_today` logic
- `src/habit_tracker/templates/base.html` - Base template where redirect script goes
- `src/habit_tracker/templates/index.html:4-12` - Date navigation with `is_today` conditional

## Open Questions

None - the approach is straightforward client-side JavaScript.
