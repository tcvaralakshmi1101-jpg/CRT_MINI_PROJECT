import pytest
from backend.models.priority_queue import HospitalPriorityQueue
from backend.models.patient import Patient, PRIORITY_LABELS

@pytest.fixture
def pq():
    return HospitalPriorityQueue()

@pytest.fixture
def mp():
    """make_patient helper"""
    def _m(id, name, priority):
        return Patient(id=id, name=name, age=30, gender="Male",
                       condition="test", priority=priority,
                       priority_label=PRIORITY_LABELS[priority])
    return _m

@pytest.fixture
def loaded_pq(pq, mp):
    """Heap with 5 patients of different priorities"""
    for id, name, pri in [("p1","Ravi",5),("p2","Priya",4),
                           ("p3","Ankit",2),("p4","Suma",3),("p5","Dev",1)]:
        pq.insert(mp(id, name, pri))
    return pq

def test_insert_single_size_is_one(pq, mp):
    """Test that inserting one patient results in size 1."""
    pq.insert(mp("p1", "Test", 3))
    assert pq.size() == 1

def test_insert_multiple_size_correct(pq, mp):
    """Test that size increases correctly with multiple inserts."""
    for i in range(5):
        pq.insert(mp(f"p{i}", f"Patient{i}", 3))
    assert pq.size() == 5

def test_peek_returns_highest_priority(pq, mp):
    """Test that peek() returns the highest priority patient."""
    pq.insert(mp("p1", "Low", 1))
    pq.insert(mp("p2", "High", 5))
    pq.insert(mp("p3", "Mid", 3))
    top = pq.peek()
    assert top.priority == 5

def test_peek_does_not_remove(pq, mp):
    """Test that peek() does not modify the heap."""
    pq.insert(mp("p1", "Test", 5))
    size_before = pq.size()
    pq.peek()
    size_after = pq.size()
    assert size_before == size_after

def test_extract_max_returns_highest(pq, mp):
    """Test that extract_max() returns the highest priority patient."""
    pq.insert(mp("p1", "Low", 1))
    pq.insert(mp("p2", "High", 5))
    pq.insert(mp("p3", "Mid", 3))
    top = pq.extract_max()
    assert top.priority == 5

def test_extract_max_decreases_size(pq, mp):
    """Test that extract_max() decreases heap size."""
    pq.insert(mp("p1", "Test", 5))
    size_before = pq.size()
    pq.extract_max()
    size_after = pq.size()
    assert size_after == size_before - 1

def test_extract_sequential_order(loaded_pq):
    """Test extracting all patients returns them in priority order 5->4->3->2->1."""
    order = []
    while not loaded_pq.is_empty():
        order.append(loaded_pq.extract_max().priority)
    assert order == [5, 4, 3, 2, 1]

def test_extract_max_empty_raises_index_error(pq):
    """Test that extract_max() raises IndexError on empty heap."""
    with pytest.raises(IndexError):
        pq.extract_max()

def test_peek_empty_raises_index_error(pq):
    """Test that peek() raises IndexError on empty heap."""
    with pytest.raises(IndexError):
        pq.peek()

def test_to_sorted_list_descending_order(loaded_pq):
    """Test to_sorted_list returns patients sorted by priority descending."""
    sorted_list = loaded_pq.to_sorted_list()
    priorities = [p.priority for p in sorted_list]
    assert priorities == sorted(priorities, reverse=True)

def test_to_sorted_list_does_not_modify_heap(loaded_pq):
    """Test that to_sorted_list() does not modify the heap."""
    size_before = loaded_pq.size()
    loaded_pq.to_sorted_list()
    size_after = loaded_pq.size()
    assert size_before == size_after

def test_update_priority_moves_element_up(pq, mp):
    """Test update_priority() when priority is increased (bubble up)."""
    pq.insert(mp("p1", "Ravi", 1))
    pq.insert(mp("p2", "Priya", 5))
    pq.update_priority("p1", 5)
    top = pq.peek()
    # One of the two priority-5 patients should be at top
    assert top.priority == 5

def test_update_priority_moves_element_down(pq, mp):
    """Test update_priority() when priority is decreased (heapify down)."""
    pq.insert(mp("p1", "High", 5))
    pq.insert(mp("p2", "Low", 1))
    pq.insert(mp("p3", "Mid", 3))
    pq.update_priority("p1", 1)
    top = pq.peek()
    # p3 (priority 3) should now be at top
    assert top.priority == 3

def test_update_priority_invalid_id_returns_false(pq):
    """Test that update_priority() returns False for non-existent ID."""
    result = pq.update_priority("nonexistent", 5)
    assert result is False

def test_remove_existing_patient_returns_true(pq, mp):
    """Test that remove() returns True when patient is found."""
    pq.insert(mp("p1", "Test", 3))
    result = pq.remove("p1")
    assert result is True

def test_remove_reduces_size(pq, mp):
    """Test that remove() decreases heap size."""
    pq.insert(mp("p1", "Test", 3))
    size_before = pq.size()
    pq.remove("p1")
    size_after = pq.size()
    assert size_after == size_before - 1

def test_remove_invalid_id_returns_false(pq):
    """Test that remove() returns False for non-existent ID."""
    result = pq.remove("nonexistent")
    assert result is False

def test_large_queue_always_sorted(pq, mp):
    """Test that a large heap of 50 random patients stays sorted."""
    import random
    priorities = [random.randint(1, 5) for _ in range(50)]
    for i, pri in enumerate(priorities):
        pq.insert(mp(f"p{i}", f"Patient{i}", pri))
    
    sorted_list = pq.to_sorted_list()
    priorities_extracted = [p.priority for p in sorted_list]
    assert priorities_extracted == sorted(priorities_extracted, reverse=True)
