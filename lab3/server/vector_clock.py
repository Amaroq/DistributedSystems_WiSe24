from typing import Self
from functools import total_ordering
import copy

class VectorClock():
    def __init__(self, n=1, entries=None):
        # TODO: Init vector clock with num and integer entries, you might want to create a copy of the entries
        if entries == None:
            self.clock = [0] * n
        elif len(entries) == n:
            self.clock = copy.deepcopy(entries)
        else:
            raise ValueError(f"length of entries must be {n}")
        pass

    # TODO: Increment the respective clock index when an event occurs on server i
    def increment(self, i):
        self.clock[i] += 1
        pass

    # TODO: Update our own entries based on the other clock
    def update(self, other: Self):
        for i in range(len(self.clock)):
            self.clock[i] = max(self.clock[i], other.clock[i])
        pass

    # Todo: Implement me
    @classmethod
    def from_list(cls, entries : list) -> Self:
        vectorclock = cls()
        vectorclock.clock = copy.deepcopy(entries)
        vectorclock.n = len(entries)
        return vectorclock

    # Todo: Implement me
    def to_list(self) -> list:
        return copy.deepcopy(self.clock)

    # Todo: Implement me
    # two clocks are parallel when neither has entries that are all smaller or equal to the other?
    # ta and tb concurrent iff ta !<= tb AND tb !<= tb
    def is_parallel(self, other):
        if (not self.__lt_or_eq__(other)) and (not other.__lt_or_eq__(self)):
            return True
        else:
            return False

    # Todo: Implement me
    # self strictly smaller than other (compare each pair of entries)
    @total_ordering
    def __lt__(self, other):
        # TODO: implement me if our clock is strictly smaller than the other one!
        for s, o in zip(self.clock, other.clock):
            if s > o:
                return False
        # at least one entry in self strictly smaller than other
        for s, o in zip(self.clock, other.clock):
            if s < o:
                return True
        return False
    
    # self less than or equal to other (compare each pair of entries)
    def __lt_or_eq__(self, other):
        for s, o in zip(self.clock, other.clock):
            if s > o:
                return False
        return True

    # a simple copy function for now
    def copy(self : Self) -> Self:
        entries = self.to_list()
        copyClock = VectorClock(len(entries), entries)
        return copyClock
    
    def __str__(self):
        return f"VectorClock({self.clock})"


if __name__ == "__main__":

    # you could test your code here if you feel like, just execute it using python3 vector_clock.py then
    # please extend it to match all the requirements of vector clocks ;)

    c0 = VectorClock(n=3, entries=[0,0,0])
    c1 = c0.copy()
    c2 = c0.copy()# c0=[2,0,0], c1=[0,1,0], c2=[0,0,0]
    assert not (c0 < c1)
    assert not (c1 < c0)
    c0.increment(0)
    c0.increment(0)
    c1.increment(1) # c0=[2,0,0], c1=[0,1,0], c2=[0,0,0]
    assert c2 < c1
    assert c2 < c0
    assert not (c1 < c2)
    assert not (c0 < c1)
    assert not (c1 < c0)
    
    c2.update(c0) #c0=[2,0,0], c1=[0,1,0], c2=[2,0,0]
    assert not c2 < c0
    assert not c2 < c1
    c2.update(c1) #c0=[2,0,0], c1=[0,1,0], c2=[2,1,0]
    assert c1 < c2
    assert c0 < c2
    
    c3 = VectorClock(n=3, entries=[1,1,3])
    c4 = VectorClock(n=3, entries=[1,4,2])
    c5 = VectorClock(n=3, entries=[0,10,0])
    assert not c4.__lt__(c3)
    assert not c3.__lt__(c4)
    assert c4.is_parallel(c3)
    assert not c4.is_parallel(c4)
    
    #print(c3.to_list())
    
    c6 = VectorClock(n=5)
    #print(c6)
    
    c8 = VectorClock(n=3, entries=[0,0,0])
    c9 = VectorClock(n=3, entries=[0,0,0])
    assert not c8.__lt__(c8)
    assert not c9.__lt__(c8)
    
    c10 = VectorClock(n=4, entries=[10, 12, 14, 26] )
    c11 = VectorClock(n=4, entries=[9, 11, 25, 0]  )
    assert c10 > c8
    assert c8 < c10
    
    