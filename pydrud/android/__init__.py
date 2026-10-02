"""The Android side of Pydrud.

``templates/`` holds the Java, Gradle and Python sources rendered into a
generated project; :mod:`pydrud.android.javacheck` statically validates the
Java templates (symbols, imports, dispatch wiring) without a JDK, so a
broken template fails in CI instead of in somebody's Gradle build.
"""

__all__ = ["javacheck"]
