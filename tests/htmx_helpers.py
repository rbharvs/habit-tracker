"""Helper functions for validating HTMX attributes in HTML responses.

These helpers use justhtml to parse HTML and assert on critical
HTMX attributes that must be preserved for client-side behavior.
"""

from justhtml import JustHTML


def parse_html(html: str) -> JustHTML:
    """Parse HTML string into JustHTML document."""
    return JustHTML(html, fragment=True)


def assert_htmx_form(
    doc: JustHTML,
    selector: str,
    *,
    hx_method: str,
    hx_target: str,
    hx_swap: str = "innerHTML",
) -> None:
    """Assert a form has required HTMX attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector for the form
        hx_method: Expected hx-post, hx-put, or hx-delete value
        hx_target: Expected hx-target value
        hx_swap: Expected hx-swap value (default: innerHTML)
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Form not found: {selector}"
    form = results[0]

    # Determine which hx- attribute to check
    if "hx-post" in form.attrs:
        assert form.attrs["hx-post"] == hx_method, f"Expected hx-post={hx_method}"
    elif "hx-put" in form.attrs:
        assert form.attrs["hx-put"] == hx_method, f"Expected hx-put={hx_method}"
    elif "hx-delete" in form.attrs:
        assert form.attrs["hx-delete"] == hx_method, f"Expected hx-delete={hx_method}"
    else:
        raise AssertionError(f"No HTMX method attribute found on {selector}")

    assert form.attrs.get("hx-target") == hx_target, f"Expected hx-target={hx_target}"
    assert form.attrs.get("hx-swap") == hx_swap, f"Expected hx-swap={hx_swap}"


def assert_htmx_button(
    doc: JustHTML,
    selector: str,
    *,
    hx_method: str,
    hx_target: str | None = None,
    hx_confirm: str | None = None,
) -> None:
    """Assert a button has required HTMX attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector for the button
        hx_method: Expected hx-delete or hx-post value
        hx_target: Expected hx-target value (optional)
        hx_confirm: Expected hx-confirm message substring (optional)
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Button not found: {selector}"
    button = results[0]

    if "hx-delete" in button.attrs:
        assert button.attrs["hx-delete"] == hx_method
    elif "hx-post" in button.attrs:
        assert button.attrs["hx-post"] == hx_method
    else:
        raise AssertionError(f"No HTMX method on button: {selector}")

    if hx_target:
        assert button.attrs.get("hx-target") == hx_target

    if hx_confirm:
        assert hx_confirm in button.attrs.get("hx-confirm", "")


def assert_data_attributes(
    doc: JustHTML,
    selector: str,
    **expected_attrs: str,
) -> None:
    """Assert an element has expected data-* attributes.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
        **expected_attrs: Expected data attributes (without 'data-' prefix)
            Example: habit_id="workout" checks data-habit-id="workout"
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Element not found: {selector}"
    element = results[0]

    for attr, value in expected_attrs.items():
        # Convert snake_case to kebab-case for data attributes
        data_attr = f"data-{attr.replace('_', '-')}"
        assert element.attrs.get(data_attr) == value, (
            f"Expected {data_attr}={value}, got {element.attrs.get(data_attr)}"
        )


def assert_element_exists(doc: JustHTML, selector: str) -> None:
    """Assert an element exists in the HTML.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
    """
    results = doc.query(selector)
    assert len(results) > 0, f"Element not found: {selector}"


def assert_element_count(doc: JustHTML, selector: str, count: int) -> None:
    """Assert a specific number of elements match the selector.

    Args:
        doc: Parsed HTML document
        selector: CSS selector
        count: Expected number of matches
    """
    elements = doc.query(selector)
    assert len(elements) == count, (
        f"Expected {count} elements matching {selector}, found {len(elements)}"
    )
