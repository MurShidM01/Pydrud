"""
Static cross-class checks for the generated Java sources.

``tools/check_java.py`` parses each rendered template, which catches syntax
errors but not the far more common failure mode: a call to a method that
does not exist on a *sibling* Pydrud class — ``advanced.setEventDispatcher(d)``
when ``AdvancedViews`` has no such setter.  Those only surface minutes into
``pydrud run``, as a ``cannot find symbol`` from javac.

This module models the classes Pydrud itself generates (top-level *and*
nested) and resolves every call that can be attributed to one of them:

* unqualified calls — ``foo(...)`` inside a Pydrud class must be declared by
  that class, an enclosing class, or a Pydrud ancestor;
* qualified calls — ``x.foo(...)`` where ``x`` is a field, parameter or local
  whose declared type is a Pydrud class (arity is checked too);
* static calls — ``PydrudIcons.drawable(...)``;
* ``new Foo(...)`` — the constructor arity must exist.

Anything that touches a framework type (``View``, ``JSONObject``, …), extends
one, or cannot be resolved is deliberately ignored: the check is unsound on
purpose, tuned for zero false positives so it can gate every test run.

Requires ``javalang`` (a dev dependency); callers should treat an
``ImportError`` as "skip".
"""

from __future__ import annotations

from dataclasses import dataclass, field

import javalang
from javalang import tree as jtree

__all__ = ["ClassInfo", "Problem", "build_model", "check_sources"]


@dataclass
class ClassInfo:
    """Everything we know about one generated class or nested class."""

    #: dotted path within the file, e.g. ``PydrudNavigation.PydrudNavBar``
    qname: str
    simple: str
    source: str = ""
    extends: str | None = None
    enclosing: str | None = None
    static_nested: bool = False
    #: method name -> declared arities (``-1`` marks a varargs method)
    methods: dict[str, set[int]] = field(default_factory=dict)
    static_methods: set[str] = field(default_factory=set)
    #: field name -> declared (simple) type name
    fields: dict[str, str] = field(default_factory=dict)
    constructors: set[int] = field(default_factory=set)
    decl: object | None = None

    def add_method(self, decl) -> None:
        arity = len(decl.parameters)
        varargs = any(getattr(p, "varargs", False) for p in decl.parameters)
        self.methods.setdefault(decl.name, set()).add(-1 if varargs else arity)
        if "static" in decl.modifiers:
            self.static_methods.add(decl.name)


@dataclass(frozen=True)
class Problem:
    """A resolvable symbol error, formatted like javac's."""

    template: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.template}: {self.message}"


# ── Model building ──────────────────────────────────────────────────────────

def _type_name(node) -> str:
    """Simple name of a declared type (``List<View>`` -> ``List``,
    ``Outer.Inner`` -> ``Inner``)."""
    if node is None:
        return ""
    sub = getattr(node, "sub_type", None)
    if sub is not None:
        return _type_name(sub)
    name = getattr(node, "name", None)
    return name if isinstance(name, str) else ""


def _members(decl):
    """Direct body members, skipping anything nested deeper."""
    return list(decl.body or [])


def _collect(decl, enclosing: ClassInfo | None, source: str,
             model: dict[str, ClassInfo]) -> None:
    qname = f"{enclosing.qname}.{decl.name}" if enclosing else decl.name
    info = ClassInfo(
        qname=qname,
        simple=decl.name,
        source=source,
        extends=_type_name(getattr(decl, "extends", None)) or None,
        enclosing=enclosing.qname if enclosing else None,
        static_nested=bool(enclosing) and "static" in (decl.modifiers or set()),
        decl=decl,
    )
    model[qname] = info
    for member in _members(decl):
        if isinstance(member, jtree.MethodDeclaration):
            info.add_method(member)
        elif isinstance(member, jtree.ConstructorDeclaration):
            info.constructors.add(len(member.parameters))
        elif isinstance(member, jtree.FieldDeclaration):
            type_name = _type_name(member.type)
            for d in member.declarators:
                info.fields[d.name] = type_name
        elif isinstance(member, (jtree.ClassDeclaration,
                                 jtree.InterfaceDeclaration)):
            _collect(member, info, source, model)


def build_model(rendered: dict[str, str]) -> dict[str, ClassInfo]:
    """Parse ``{template name: java source}`` into a class model."""
    model: dict[str, ClassInfo] = {}
    for name, source in rendered.items():
        tree = javalang.parse.parse(source)
        for type_decl in tree.types:
            if isinstance(type_decl, (jtree.ClassDeclaration,
                                      jtree.InterfaceDeclaration)):
                _collect(type_decl, None, source=name, model=model)
    return model


def _by_simple(model: dict[str, ClassInfo]) -> dict[str, list[ClassInfo]]:
    index: dict[str, list[ClassInfo]] = {}
    for info in model.values():
        index.setdefault(info.simple, []).append(info)
    return index


# ── Resolution helpers ──────────────────────────────────────────────────────

class _Resolver:
    def __init__(self, model: dict[str, ClassInfo]):
        self.model = model
        self.index = _by_simple(model)
        self.all_methods = {m for c in model.values() for m in c.methods}

    def lookup(self, simple: str, scope: ClassInfo | None = None):
        """Unambiguously resolve a simple type name to a Pydrud class."""
        candidates = self.index.get(simple, [])
        if scope is not None:
            same_file = [c for c in candidates if c.source == scope.source]
            if len(same_file) == 1:
                return same_file[0]
        if len(candidates) == 1:
            return candidates[0]
        return None  # unknown or ambiguous - stay silent

    def scope_chain(self, info: ClassInfo) -> list[ClassInfo]:
        """``info``, its Pydrud ancestors, and every enclosing class."""
        chain: list[ClassInfo] = []
        seen: set[str] = set()
        queue = [info]
        while queue:
            current = queue.pop()
            if current.qname in seen:
                continue
            seen.add(current.qname)
            chain.append(current)
            if current.extends:
                parent = self.lookup(current.extends, current)
                if parent is not None:
                    queue.append(parent)
            if current.enclosing and current.enclosing in self.model:
                queue.append(self.model[current.enclosing])
        return chain

    def inherits_foreign(self, info: ClassInfo) -> bool:
        """True when the class or an ancestor extends a non-Pydrud type."""
        for current in self.scope_chain(info):
            if current.extends and self.lookup(current.extends, current) is None:
                return True
        return False

    def methods_of(self, info: ClassInfo) -> dict[str, set[int]]:
        merged: dict[str, set[int]] = {}
        for current in self.scope_chain(info):
            for name, arities in current.methods.items():
                merged.setdefault(name, set()).update(arities)
        return merged


def _selector_invocations(decl) -> set[int]:
    """Ids of calls that are *selectors* of another expression.

    javalang models ``prefs.edit().clear().apply()`` as one invocation
    (``prefs.edit``) carrying ``clear``/``apply`` as selectors with an empty
    qualifier.  Those resolve against the chained receiver's type, which we
    do not track, so they must never be read as unqualified self-calls.
    """
    found: set[int] = set()
    for _path, node in decl:
        for selector in (getattr(node, "selectors", None) or []):
            if isinstance(selector, jtree.MethodInvocation):
                found.add(id(selector))
    return found


def _scope_vars(decl, info: ClassInfo) -> dict[str, str]:
    """Parameters and locals of a method/constructor, by simple type name."""
    names: dict[str, str] = {}
    for param in getattr(decl, "parameters", []) or []:
        names[param.name] = _type_name(param.type)
    for _, local in decl.filter(jtree.LocalVariableDeclaration):
        type_name = _type_name(local.type)
        for d in local.declarators:
            names[d.name] = type_name
    for _, catch in decl.filter(jtree.CatchClause):
        param = getattr(catch, "parameter", None)
        if param is not None:
            names[param.name] = ""
    for _, loop in decl.filter(jtree.EnhancedForControl):
        var = getattr(loop, "var", None)
        for d in getattr(var, "declarators", []) or []:
            names[d.name] = _type_name(getattr(loop, "type", None))
    return names


# ── The check itself ────────────────────────────────────────────────────────

def _check_class(info: ClassInfo, res: _Resolver,
                 problems: list[Problem]) -> None:
    decl = info.decl
    if decl is None:
        return
    foreign = res.inherits_foreign(info)
    own = res.methods_of(info)

    bodies = [m for m in _members(decl)
              if isinstance(m, (jtree.MethodDeclaration,
                                jtree.ConstructorDeclaration))]
    for member in bodies:
        where = f"{info.qname}.{getattr(member, 'name', '<init>')}()"
        scope = _scope_vars(member, info)
        chained = _selector_invocations(member)

        for _, call in member.filter(jtree.MethodInvocation):
            if id(call) in chained:
                continue
            qualifier = call.qualifier or ""
            arity = len(call.arguments or [])

            if not qualifier:
                # A class extending a framework type inherits unknown methods,
                # and so does any anonymous subclass declared inside it.
                if foreign or call.member not in res.all_methods:
                    continue
                if call.member not in own:
                    problems.append(Problem(
                        info.source,
                        f"{where}: cannot find symbol {call.member}() — "
                        f"not declared in {info.qname} or any Pydrud ancestor"))
                continue

            if "." in qualifier:
                continue  # chained / package-qualified: out of scope
            declared = scope.get(qualifier)
            if declared is None:
                declared = next((c.fields[qualifier]
                                 for c in res.scope_chain(info)
                                 if qualifier in c.fields), None)
            if declared is None:
                owner = res.lookup(qualifier, info)  # static call
                if owner is None:
                    continue
                static_call = True
            else:
                owner = res.lookup(declared, info)
                static_call = False
            if owner is None or res.inherits_foreign(owner):
                continue
            arities = res.methods_of(owner).get(call.member)
            if not arities:
                problems.append(Problem(
                    info.source,
                    f"{where}: cannot find symbol {call.member}() on "
                    f"{owner.qname} ({qualifier})"))
            elif -1 not in arities and arity not in arities:
                problems.append(Problem(
                    info.source,
                    f"{where}: {owner.qname}.{call.member}() takes "
                    f"{sorted(arities)} argument(s), called with {arity}"))
            elif static_call and call.member not in owner.static_methods:
                problems.append(Problem(
                    info.source,
                    f"{where}: non-static method {owner.qname}.{call.member}() "
                    "cannot be referenced from a static context"))

        for _, creation in member.filter(jtree.ClassCreator):
            if creation.body is not None:
                continue  # anonymous subclass
            owner = res.lookup(_type_name(creation.type), info)
            if owner is None or not owner.constructors:
                continue
            arity = len(creation.arguments or [])
            if arity not in owner.constructors:
                problems.append(Problem(
                    info.source,
                    f"{where}: no constructor {owner.qname} taking {arity} "
                    f"argument(s); available: {sorted(owner.constructors)}"))


def check_sources(rendered: dict[str, str]) -> list[Problem]:
    """Resolve every Pydrud-owned symbol used by the rendered sources."""
    model = build_model(rendered)
    res = _Resolver(model)
    problems: list[Problem] = []
    for info in model.values():
        _check_class(info, res, problems)
    return sorted(set(problems), key=lambda p: (p.template, p.message))
