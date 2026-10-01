"""
Forms and validation.

A login or checkout screen is mostly plumbing: keep every field's value,
validate on submit (but re-validate a field as soon as the user fixes it),
show the first error under the right input, and disable the button until the
form is valid.  :class:`Form` does all of that.

::

    form = Form(
        TextField(name="email", label="Email", validators=[required(), email()]),
        TextField(name="password", label="Password", obscure=True,
                  validators=[required(), min_length(8)]),
        on_submit=lambda values: login(**values),
    )

``Form`` is a normal widget: put it in a Column, call ``form.submit()`` from a
button, and read ``form.values`` / ``form.errors`` at any time.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable, Optional

from pydrud.widgets.base import Widget
from pydrud.widgets.theme import Colors

Validator = Callable[[Any], Optional[str]]

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_PHONE_RE = re.compile(r"^\+?[0-9 ()\-]{7,20}$")
_URL_RE = re.compile(r"^https?://[^\s/$.?#].[^\s]*$", re.IGNORECASE)


# ──────────────────────────────────────────────────────────────────────────
# Validators — each returns None when valid, or an error message.
# ──────────────────────────────────────────────────────────────────────────


def required(message: str = "This field is required") -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value is None:
            return message
        if isinstance(value, str) and not value.strip():
            return message
        if isinstance(value, (list, tuple, dict, set)) and not value:
            return message
        if value is False:
            return message
        return None

    return _validate


def min_length(n: int, message: Optional[str] = None) -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        if len(str(value)) < n:
            return message or f"Must be at least {n} characters"
        return None

    return _validate


def max_length(n: int, message: Optional[str] = None) -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        if len(str(value)) > n:
            return message or f"Must be at most {n} characters"
        return None

    return _validate


def email(message: str = "Enter a valid email address") -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return None if _EMAIL_RE.match(str(value).strip()) else message

    return _validate


def phone(message: str = "Enter a valid phone number") -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return None if _PHONE_RE.match(str(value).strip()) else message

    return _validate


def url(message: str = "Enter a valid URL") -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return None if _URL_RE.match(str(value).strip()) else message

    return _validate


def numeric(message: str = "Enter a number") -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        try:
            float(str(value).strip())
        except (TypeError, ValueError):
            return message
        return None

    return _validate


def between(low: float, high: float, message: Optional[str] = None) -> Validator:
    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return message or "Enter a number"
        if number < low or number > high:
            return message or f"Must be between {low} and {high}"
        return None

    return _validate


def pattern(regex: str, message: str = "Invalid format") -> Validator:
    compiled = re.compile(regex)

    def _validate(value: Any) -> Optional[str]:
        if value in (None, ""):
            return None
        return None if compiled.match(str(value)) else message

    return _validate


def matches(other_field: str, message: Optional[str] = None) -> Validator:
    """Cross-field check, e.g. "confirm password". Bound by the Form."""

    def _validate(value: Any) -> Optional[str]:
        # The Form injects the sibling value via the `_peer` attribute.
        peer = getattr(_validate, "_peer", None)
        if peer is None or value == peer:
            return None
        return message or f"Must match {other_field}"

    _validate._field = other_field  # type: ignore[attr-defined]
    return _validate


def custom(fn: Callable[[Any], bool], message: str = "Invalid value") -> Validator:
    """Wrap a boolean predicate as a validator."""

    def _validate(value: Any) -> Optional[str]:
        try:
            return None if fn(value) else message
        except Exception:
            return message

    return _validate


# ──────────────────────────────────────────────────────────────────────────
# Form
# ──────────────────────────────────────────────────────────────────────────


class FormField(Widget):
    """Wraps an input widget with a label, helper text and an error slot."""

    _widget_type = "FormField"

    def __init__(
        self,
        name: str,
        control: Widget,
        *,
        label: Optional[str] = None,
        helper: Optional[str] = None,
        validators: Optional[Iterable[Validator]] = None,
        initial: Any = None,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key or f"field_{name}", **kwargs)
        if not name:
            raise ValueError("FormField requires a name")
        self.name = name
        self.label = label
        self.helper = helper
        self.validators: list[Validator] = list(validators or [])
        self.error: Optional[str] = None
        self.touched = False
        self.value: Any = initial if initial is not None \
            else _read_value(control)
        self.children = [control]
        self._control = control
        self._wire(control)

    @property
    def control(self) -> Widget:
        return self._control

    def _wire(self, control: Widget) -> None:
        """Chain our value tracker in front of any user on_change handler."""
        user_handler = control.event_handlers.get("change")

        def _on_change(event):
            self.value = _event_value(event, self.value)
            self.touched = True
            if self.error:           # re-validate as soon as they fix it
                self.validate()
            if user_handler is not None:
                user_handler(event)

        control.event_handlers["change"] = _on_change

    def validate(self) -> Optional[str]:
        """Run the validators; store and return the first error."""
        self.error = None
        for validator in self.validators:
            message = validator(self.value)
            if message:
                self.error = message
                break
        return self.error

    @property
    def valid(self) -> bool:
        return self.error is None

    def reset(self, value: Any = None) -> None:
        self.value = value
        self.error = None
        self.touched = False

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "name": self.name,
            "label": self.label,
            "helper": self.helper,
            "error": self.error,
            "errorColor": Colors.ERROR,
            "required": any(getattr(v, "__name__", "") == "_validate"
                            and v(None) is not None for v in self.validators),
        })
        return {k: v for k, v in props.items() if v is not None}


class Form(Widget):
    """A validating container for input widgets."""

    _widget_type = "Form"

    def __init__(
        self,
        *fields: Widget,
        on_submit: Optional[Callable[[dict], Any]] = None,
        on_change: Optional[Callable[[dict], Any]] = None,
        spacing: float = 12,
        validate_on_change: bool = False,
        key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(key=key, **kwargs)
        self.style.setdefault("spacing", spacing)
        self.style.setdefault("mainAxis", "vertical")
        self.fields: dict[str, FormField] = {}
        self._on_submit = on_submit
        self._on_change = on_change
        self.validate_on_change = validate_on_change
        self.submitted = False
        for field in fields:
            self.add_field(field)

    # ── composition ──────────────────────────────────────────────────────

    def add_field(self, widget: Widget) -> "Form":
        """Add a FormField, or any widget carrying ``name=``/``validators=``."""
        field = widget if isinstance(widget, FormField) else _promote(widget)
        if field is None:
            self.children.append(widget)       # plain decoration (Text, Divider)
            return self
        if field.name in self.fields:
            raise ValueError(f"Duplicate form field name {field.name!r}")
        self.fields[field.name] = field
        self.children.append(field)
        self._hook_change(field)
        return self

    def _hook_change(self, field: FormField) -> None:
        control = field.control
        chained = control.event_handlers.get("change")

        def _on_change(event):
            if chained is not None:
                chained(event)
            if self.validate_on_change or self.submitted:
                self.validate()
            if self._on_change is not None:
                self._on_change(self.values)

        control.event_handlers["change"] = _on_change

    # ── data ─────────────────────────────────────────────────────────────

    @property
    def values(self) -> dict:
        return {name: field.value for name, field in self.fields.items()}

    @property
    def errors(self) -> dict:
        return {name: field.error for name, field in self.fields.items()
                if field.error}

    @property
    def valid(self) -> bool:
        """True when a *fresh* validation pass finds no errors."""
        return not self.validate()

    @property
    def dirty(self) -> bool:
        return any(field.touched for field in self.fields.values())

    def field(self, name: str) -> Optional[FormField]:
        return self.fields.get(name)

    def set_value(self, name: str, value: Any) -> "Form":
        field = self.fields.get(name)
        if field is None:
            raise KeyError(f"No form field named {name!r}")
        field.value = value
        _write_value(field.control, value)
        return self

    def set_error(self, name: str, message: Optional[str]) -> "Form":
        """Attach a server-side error to a field."""
        field = self.fields.get(name)
        if field is not None:
            field.error = message
        return self

    # ── actions ──────────────────────────────────────────────────────────

    def validate(self) -> dict:
        """Validate every field and return ``{name: error}`` (empty = valid)."""
        values = self.values
        for field in self.fields.values():
            for validator in field.validators:
                peer_name = getattr(validator, "_field", None)
                if peer_name is not None:
                    validator._peer = values.get(peer_name)  # type: ignore[attr-defined]
            field.validate()
        return self.errors

    def submit(self, event: Any = None) -> bool:
        """Validate and, when clean, call ``on_submit(values)``."""
        self.submitted = True
        errors = self.validate()
        if errors:
            return False
        if self._on_submit is not None:
            self._on_submit(self.values)
        return True

    def reset(self) -> "Form":
        for field in self.fields.values():
            field.reset()
            _write_value(field.control, "" if isinstance(field.value, str) else None)
        self.submitted = False
        return self

    def _serialise_props(self) -> dict:
        props = dict(self._extra)
        props.update({
            "fields": sorted(self.fields),
            "valid": not self.errors,
            "submitted": self.submitted,
        })
        return props


# ──────────────────────────────────────────────────────────────────────────
# helpers
# ──────────────────────────────────────────────────────────────────────────


def _event_value(event: Any, fallback: Any) -> Any:
    """Read the new value from an Event, a raw data dict, or a bare value."""
    value = getattr(event, "value", None)
    if value is not None:
        return value
    if isinstance(event, dict):
        data = event.get("data") if isinstance(event.get("data"), dict) else event
        for name in ("value", "checked", "selected"):
            if name in data:
                return data[name]
    return fallback


def _promote(widget: Widget) -> Optional[FormField]:
    """Turn ``TextField(name=..., validators=[...])`` into a FormField."""
    extra = getattr(widget, "_extra", {}) or {}
    name = extra.pop("name", None) or getattr(widget, "name", None)
    if not name:
        return None
    validators = extra.pop("validators", None)
    if validators is None:
        validators = getattr(widget, "validators", None)
    label = extra.pop("label", None) or getattr(widget, "label", None)
    helper = extra.pop("helper", None)
    return FormField(str(name), widget, label=label, helper=helper,
                     validators=validators or [])


def _read_value(control: Widget) -> Any:
    for attr in ("value", "_value", "checked", "text"):
        if hasattr(control, attr):
            return getattr(control, attr)
    props = control._serialise_props()
    for attr in ("value", "checked", "text"):
        if attr in props:
            return props[attr]
    return None


def _write_value(control: Widget, value: Any) -> None:
    for attr in ("value", "_value", "checked"):
        if hasattr(control, attr):
            try:
                setattr(control, attr, value)
            except AttributeError:
                continue
            return
