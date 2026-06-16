class HospitalPriorityQueue:
    """
    Max-Heap Priority Queue for hospital patient triage.
    Parent node priority is always >= both children priorities.
    Rebuilt from PostgreSQL on server start via PatientService.rebuild_heap().
    All mutations write to DB first, then update the heap in memory.
    """

    PRIORITY_LABELS = {5:"Critical", 4:"Serious", 3:"Moderate", 2:"Mild", 1:"Minor"}

    def __init__(self):
        self._heap: list = []   # list of Patient dataclass instances

    def insert(self, patient) -> None:
        """Append patient and bubble up. Time: O(log n)"""
        self._heap.append(patient)
        self._bubble_up(len(self._heap) - 1)

    def extract_max(self):
        """Remove and return highest-priority patient. Time: O(log n)"""
        if self.is_empty():
            raise IndexError("Priority queue is empty")
        self._heap[0], self._heap[-1] = self._heap[-1], self._heap[0]
        max_patient = self._heap.pop()
        if self._heap:
            self._heapify_down(0)
        return max_patient

    def peek(self):
        """Return highest-priority patient without removing. Time: O(1)"""
        if self.is_empty():
            raise IndexError("Priority queue is empty")
        return self._heap[0]

    def update_priority(self, patient_id: str, new_priority: int) -> bool:
        """
        Find patient by id, update priority and label, re-heapify.
        Calls both _bubble_up and _heapify_down — only one will move it.
        Time: O(n) search + O(log n) heapify. Returns True if found.
        """
        for i, p in enumerate(self._heap):
            if p.id == patient_id:
                p.priority       = new_priority
                p.priority_label = self.PRIORITY_LABELS[new_priority]
                self._bubble_up(i)
                self._heapify_down(i)
                return True
        return False

    def remove(self, patient_id: str) -> bool:
        """
        Remove patient by id. Swap with last, pop, re-heapify.
        Time: O(n) search + O(log n) heapify. Returns True if found.
        """
        for i, p in enumerate(self._heap):
            if p.id == patient_id:
                if i == len(self._heap) - 1:
                    self._heap.pop()
                else:
                    self._heap[i] = self._heap.pop()
                    self._bubble_up(i)
                    self._heapify_down(i)
                return True
        return False

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def size(self) -> int:
        return len(self._heap)

    def to_sorted_list(self) -> list:
        """Return patients sorted by priority descending. Does NOT modify heap."""
        return sorted(self._heap, key=lambda p: p.priority, reverse=True)

    def _bubble_up(self, index: int) -> None:
        while index > 0:
            parent = (index - 1) // 2
            if self._heap[index].priority > self._heap[parent].priority:
                self._heap[index], self._heap[parent] = \
                    self._heap[parent], self._heap[index]
                index = parent
            else:
                break

    def _heapify_down(self, index: int) -> None:
        n = len(self._heap)
        while True:
            largest, left, right = index, 2*index+1, 2*index+2
            if left  < n and self._heap[left].priority  > self._heap[largest].priority:
                largest = left
            if right < n and self._heap[right].priority > self._heap[largest].priority:
                largest = right
            if largest != index:
                self._heap[index], self._heap[largest] = \
                    self._heap[largest], self._heap[index]
                index = largest
            else:
                break
