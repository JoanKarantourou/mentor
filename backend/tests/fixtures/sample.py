"""Sample Python module for testing code parsing."""


def calculate_fibonacci(n: int) -> list[int]:
    """Return the first n Fibonacci numbers."""
    if n <= 0:
        return []
    sequence = [0, 1]
    while len(sequence) < n:
        sequence.append(sequence[-1] + sequence[-2])
    return sequence[:n]


def is_prime(number: int) -> bool:
    """Check whether a number is prime."""
    if number < 2:
        return False
    for i in range(2, int(number**0.5) + 1):
        if number % i == 0:
            return False
    return True


class DataProcessor:
    """Simple data processor for demonstration."""

    def __init__(self, data: list) -> None:
        self.data = data

    def filter_positive(self) -> list:
        """Return only positive values."""
        return [x for x in self.data if x > 0]

    def compute_mean(self) -> float:
        """Compute the arithmetic mean."""
        if not self.data:
            return 0.0
        return sum(self.data) / len(self.data)
