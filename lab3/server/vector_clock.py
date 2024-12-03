from typing import Self

class VectorClock():
    def __init__(self, n=1, entries=None):
        # TODO: Init vector clock with num and integer entries, you might want to create a copy of the entries
        pass

    # TODO: Increment the respective clock index when an event occurs on server i
    def increment(self, i):
        pass

    # TODO: Update our own entries based on the other clock
    def update(self, other: Self):
        pass

    # Todo: Implement me
    def from_list(entries : list) -> Self:
        return VectorClock()

    # Todo: Implement me
    def to_list(self) -> list:
        return []

    # Todo: Implement me
    def is_parallel(self, other):
        pass

    # Todo: Implement me
    def __lt__(self, other):
        # TODO: implement me if our clock is strictly smaller than the other one!
        return False

    # a simple copy function for now
    def copy(self : Self) -> Self:
        return VectorClock.from_list(self.to_list())


if __name__ == "__main__":

    # you could test your code here if you feel like, just execute it using python3 vector_clock.py then
    # please extend it to match all the requirements of vector clocks ;)

    c0 = VectorClock(n=1, entries=[0])

    c1 = c0.copy()
    c1.increment(0)

    c2 = c1.copy()
    c2.update(c0)

    assert c0 < c1
    assert c0 < c2
    assert not (c1 < c2)