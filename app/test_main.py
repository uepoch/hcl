import pytest
import unittest

from app import main


class TestGreet(unittest.TestCase):

    def test_greet(self):
        self.assertEqual(main.greet(), "Hello Anonymous")
        self.assertEqual(main.greet("C3PO"), "Hello C3PO")


@pytest.mark.benchmark()
def test_greet(benchmark):
    benchmark.pedantic(
        main.greet, args=(b'[a B] foo',),
        iterations=10000, rounds=100)


if __name__ == '__main__':
    unittest.main()
