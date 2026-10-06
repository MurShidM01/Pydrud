"""
Cross-class symbol resolution for the generated Java sources.

A missing method on a sibling class (``advanced.setEventDispatcher(d)`` with
no such setter on ``AdvancedViews``) used to escape the test suite entirely
and only blow up minutes into ``pydrud run``.  ``pydrud.android.javacheck``
resolves those statically; this module keeps it honest.
"""

from __future__ import annotations

import os
import unittest

from jinja2 import Environment, PackageLoader

try:
    from pydrud.android.javacheck import Problem, check_sources
    HAS_JAVALANG = True
except ImportError:  # pragma: no cover - optional dev dependency
    HAS_JAVALANG = False

CTX = {
    "project_name": "demo_app",
    "app_name": "DemoApp",
    "pydrud_app_name": "demo_app",
    "package": "com.example.demo_app",
    "package_path": "com/example/demo_app",
    "min_sdk": 24,
    "target_sdk": 35,
    "compile_sdk": 35,
    "build_tools_version": "36.0.0",
    "gradle_version": "8.7",
    "chaquopy_version": "15.0.1",
    "python_version": "3.11",
    "sdk_dir": "/opt/android-sdk",
    "python_executable": "python3",
    "ndk": "29.0.14206865",
    "scheme": "demoapp",
    "firebase": False,
    "night": False,
    "permissions": [],
    "abi_filters": ["arm64-v8a"],
    "pip_packages": [],
    "version_code": 1,
    "version_name": "1.0.0",
}


def render_all() -> dict:
    env = Environment(loader=PackageLoader("pydrud", "android/templates"),
                      trim_blocks=True, lstrip_blocks=True)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    folder = os.path.join(here, "pydrud", "android", "templates", "android")
    return {
        name: env.get_template("android/" + name).render(**CTX)
        for name in sorted(os.listdir(folder)) if name.endswith(".java.j2")
    }


@unittest.skipUnless(HAS_JAVALANG, "javalang not installed")
class TestJavaSymbols(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rendered = render_all()

    def test_generated_sources_resolve(self):
        problems = check_sources(self.rendered)
        self.assertEqual(
            [], problems,
            "unresolved Java symbols:\n  " +
            "\n  ".join(str(p) for p in problems))

    def test_detects_missing_method_on_sibling_class(self):
        """The regression that broke `pydrud run` in 1.5.1."""
        sources = {
            "A.java": "public class A { public void setX(int v) {} }",
            "B.java": ("public class B { private final A a = new A();"
                       " void go() { a.setY(1); } }"),
        }
        problems = check_sources(sources)
        self.assertTrue(any("setY" in p.message for p in problems), problems)

    def test_detects_missing_self_method(self):
        sources = {
            "A.java": "public class A { void go() { helper(); } }",
            "B.java": "public class B { void helper() {} }",
        }
        problems = check_sources(sources)
        self.assertTrue(any("helper" in p.message for p in problems), problems)

    def test_detects_wrong_arity_and_bad_constructor(self):
        sources = {
            "A.java": ("public class A { A(int a, int b) {}"
                       " public void only(int v) {} }"),
            "B.java": ("public class B { void go() { A a = new A(1);"
                       " a.only(1, 2); } }"),
        }
        problems = check_sources(sources)
        self.assertTrue(any("constructor" in p.message for p in problems),
                        problems)
        self.assertTrue(any("argument" in p.message for p in problems),
                        problems)

    def test_ignores_framework_and_chained_calls(self):
        """No false positives on inherited or chained-call syntax."""
        sources = {
            "A.java": ("public class A extends android.view.View {"
                       " void go() { invalidate();"
                       " prefs.edit().clear().apply(); } }"),
        }
        self.assertEqual([], check_sources(sources))

    def test_detects_lambda_shadowing_an_enclosing_local(self):
        """A lambda body shares the method's scope (a real javac error)."""
        sources = {
            "A.java": ("public class A { void go() {"
                       " int arr = 0;"
                       " run(() -> { int arr = 1; }); } }"),
        }
        problems = check_sources(sources)
        self.assertTrue(any("arr" in p.message for p in problems), problems)

    def test_detects_lambda_parameter_shadowing_a_method_parameter(self):
        sources = {
            "A.java": ("public class A { void go(String key) {"
                       " run(key -> System.out.println(key)); } }"),
        }
        problems = check_sources(sources)
        self.assertTrue(any("key" in p.message for p in problems), problems)

    def test_allows_a_lambda_local_in_a_sibling_scope(self):
        """A local inside a nested block is not in scope in a sibling lambda."""
        sources = {
            "A.java": ("public class A { void go(boolean c) {"
                       " if (c) { int x = 1; }"
                       " run(() -> { int x = 2; }); } }"),
        }
        self.assertEqual([], check_sources(sources))

    def test_allows_an_anonymous_class_local_with_the_same_name(self):
        sources = {
            "A.java": ("public class A { void go() { int x = 1;"
                       " Object o = new Object() { void run() { int x = 2; } };"
                       " } }"),
        }
        self.assertEqual([], check_sources(sources))

    def test_allows_two_sibling_lambdas_with_the_same_local(self):
        sources = {
            "A.java": ("public class A { void go() {"
                       " run(() -> { int x = 1; });"
                       " run(() -> { int x = 2; }); } }"),
        }
        self.assertEqual([], check_sources(sources))

    def test_problem_formats_like_javac(self):
        problem = Problem("X.java", "boom")
        self.assertEqual("X.java: boom", str(problem))


if __name__ == "__main__":
    unittest.main()
