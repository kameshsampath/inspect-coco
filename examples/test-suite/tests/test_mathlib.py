"""Test suite for mathlib - demonstrates multiple test functions."""

import pytest


def test_add_integers():
    from mathlib import add

    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(0, 0) == 0


def test_add_floats():
    from mathlib import add

    assert add(1.5, 2.5) == 4.0
    assert add(0.1, 0.2) == pytest.approx(0.3)


def test_subtract():
    from mathlib import subtract

    assert subtract(10, 3) == 7
    assert subtract(0, 5) == -5
    assert subtract(2.5, 1.0) == 1.5


def test_multiply():
    from mathlib import multiply

    assert multiply(3, 4) == 12
    assert multiply(0, 100) == 0
    assert multiply(-2, 3) == -6
    assert multiply(1.5, 2) == 3.0


def test_type_error_on_non_numeric():
    from mathlib import add, multiply, subtract

    with pytest.raises(TypeError):
        add("a", 1)

    with pytest.raises(TypeError):
        subtract(None, 1)

    with pytest.raises(TypeError):
        multiply([], 2)
