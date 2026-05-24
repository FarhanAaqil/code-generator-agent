"""
20 HumanEval-style benchmark problems spanning easy/medium/hard difficulties.
Each problem is a dict with: id, difficulty, entry_point, prompt, test
"""

PROBLEMS = [
    # ===== EASY =====
    {
        "id": 1,
        "difficulty": "easy",
        "entry_point": "add",
        "prompt": "Write a Python function called `add(a, b)` that returns the sum of two numbers.",
        "test": """
assert add(1, 2) == 3
assert add(-1, 1) == 0
assert add(0, 0) == 0
assert add(100, 200) == 300
print('PASS')
"""
    },
    {
        "id": 2,
        "difficulty": "easy",
        "entry_point": "is_palindrome",
        "prompt": "Write a Python function `is_palindrome(s)` that returns True if the string s is a palindrome (same forwards and backwards), False otherwise. Ignore case.",
        "test": """
assert is_palindrome("racecar") == True
assert is_palindrome("hello") == False
assert is_palindrome("A") == True
assert is_palindrome("Madam") == True
assert is_palindrome("") == True
print('PASS')
"""
    },
    {
        "id": 3,
        "difficulty": "easy",
        "entry_point": "fizzbuzz",
        "prompt": "Write a Python function `fizzbuzz(n)` that returns a list of strings from 1 to n. For multiples of 3 use 'Fizz', multiples of 5 use 'Buzz', multiples of both use 'FizzBuzz', otherwise the number as string.",
        "test": """
result = fizzbuzz(15)
assert result[0] == '1'
assert result[2] == 'Fizz'
assert result[4] == 'Buzz'
assert result[14] == 'FizzBuzz'
assert len(result) == 15
print('PASS')
"""
    },
    {
        "id": 4,
        "difficulty": "easy",
        "entry_point": "count_vowels",
        "prompt": "Write a Python function `count_vowels(s)` that counts the number of vowels (a, e, i, o, u) in a string, case-insensitive.",
        "test": """
assert count_vowels("hello") == 2
assert count_vowels("AEIOU") == 5
assert count_vowels("rhythm") == 0
assert count_vowels("") == 0
assert count_vowels("Python") == 1
print('PASS')
"""
    },
    {
        "id": 5,
        "difficulty": "easy",
        "entry_point": "factorial",
        "prompt": "Write a Python function `factorial(n)` that returns the factorial of a non-negative integer n. factorial(0) = 1.",
        "test": """
assert factorial(0) == 1
assert factorial(1) == 1
assert factorial(5) == 120
assert factorial(10) == 3628800
print('PASS')
"""
    },
    {
        "id": 6,
        "difficulty": "easy",
        "entry_point": "reverse_list",
        "prompt": "Write a Python function `reverse_list(lst)` that returns a new list that is the reverse of the input list, without using built-in reverse methods.",
        "test": """
assert reverse_list([1, 2, 3]) == [3, 2, 1]
assert reverse_list([]) == []
assert reverse_list([1]) == [1]
assert reverse_list(['a', 'b', 'c']) == ['c', 'b', 'a']
print('PASS')
"""
    },
    {
        "id": 7,
        "difficulty": "easy",
        "entry_point": "celsius_to_fahrenheit",
        "prompt": "Write a Python function `celsius_to_fahrenheit(c)` that converts Celsius to Fahrenheit using the formula F = (C * 9/5) + 32. Round to 2 decimal places.",
        "test": """
assert celsius_to_fahrenheit(0) == 32.0
assert celsius_to_fahrenheit(100) == 212.0
assert celsius_to_fahrenheit(-40) == -40.0
assert celsius_to_fahrenheit(37) == 98.6
print('PASS')
"""
    },
    {
        "id": 8,
        "difficulty": "easy",
        "entry_point": "flatten",
        "prompt": "Write a Python function `flatten(lst)` that takes a list of lists and returns a single flattened list containing all elements.",
        "test": """
assert flatten([[1, 2], [3, 4], [5]]) == [1, 2, 3, 4, 5]
assert flatten([[], [1], [2, 3]]) == [1, 2, 3]
assert flatten([]) == []
assert flatten([[1, 2, 3]]) == [1, 2, 3]
print('PASS')
"""
    },
    # ===== MEDIUM =====
    {
        "id": 9,
        "difficulty": "medium",
        "entry_point": "two_sum",
        "prompt": "Write a Python function `two_sum(nums, target)` that returns the indices of two numbers in the list that add up to the target. Return a list [i, j] where i < j. Assume exactly one solution exists.",
        "test": """
assert two_sum([2, 7, 11, 15], 9) == [0, 1]
assert two_sum([3, 2, 4], 6) == [1, 2]
assert two_sum([1, 5, 3, 7], 8) == [1, 3]
print('PASS')
"""
    },
    {
        "id": 10,
        "difficulty": "medium",
        "entry_point": "is_anagram",
        "prompt": "Write a Python function `is_anagram(s1, s2)` that returns True if s1 and s2 are anagrams of each other (same characters, same frequency), case-insensitive, ignoring spaces.",
        "test": """
assert is_anagram("listen", "silent") == True
assert is_anagram("hello", "world") == False
assert is_anagram("Astronomer", "Moon starer") == True
assert is_anagram("a", "a") == True
print('PASS')
"""
    },
    {
        "id": 11,
        "difficulty": "medium",
        "entry_point": "max_subarray_sum",
        "prompt": "Write a Python function `max_subarray_sum(nums)` that finds the contiguous subarray with the largest sum and returns that sum. Use Kadane's algorithm. Handle all-negative arrays.",
        "test": """
assert max_subarray_sum([-2, 1, -3, 4, -1, 2, 1, -5, 4]) == 6
assert max_subarray_sum([1]) == 1
assert max_subarray_sum([-1, -2, -3]) == -1
assert max_subarray_sum([5, 4, -1, 7, 8]) == 23
print('PASS')
"""
    },
    {
        "id": 12,
        "difficulty": "medium",
        "entry_point": "group_by_frequency",
        "prompt": "Write a Python function `group_by_frequency(lst)` that takes a list of elements and returns a dict where keys are frequency counts and values are sorted lists of elements appearing that many times.",
        "test": """
result = group_by_frequency([1, 1, 2, 3, 3, 3])
assert result[1] == [2]
assert result[2] == [1]
assert result[3] == [3]
result2 = group_by_frequency(['a', 'b', 'a'])
assert result2[1] == ['b']
assert result2[2] == ['a']
print('PASS')
"""
    },
    {
        "id": 13,
        "difficulty": "medium",
        "entry_point": "longest_common_prefix",
        "prompt": "Write a Python function `longest_common_prefix(words)` that finds the longest common prefix string among a list of strings. Return empty string if none exists.",
        "test": """
assert longest_common_prefix(["flower", "flow", "flight"]) == "fl"
assert longest_common_prefix(["dog", "racecar", "car"]) == ""
assert longest_common_prefix(["interview", "interact", "interface"]) == "inter"
assert longest_common_prefix(["abc"]) == "abc"
print('PASS')
"""
    },
    {
        "id": 14,
        "difficulty": "medium",
        "entry_point": "merge_intervals",
        "prompt": "Write a Python function `merge_intervals(intervals)` that merges all overlapping intervals. Input: list of [start, end] pairs. Output: sorted merged list of [start, end] pairs.",
        "test": """
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([[1,4],[2,3]]) == [[1,4]]
assert merge_intervals([[1,2]]) == [[1,2]]
print('PASS')
"""
    },
    {
        "id": 15,
        "difficulty": "medium",
        "entry_point": "rolling_max",
        "prompt": "Write a Python function `rolling_max(nums)` that returns a list where each element is the maximum of all elements seen so far (running maximum).",
        "test": """
assert rolling_max([1, 2, 3, 2, 1]) == [1, 2, 3, 3, 3]
assert rolling_max([3, 1, 4, 1, 5]) == [3, 3, 4, 4, 5]
assert rolling_max([5]) == [5]
assert rolling_max([-1, -2, -3]) == [-1, -1, -1]
print('PASS')
"""
    },
    {
        "id": 16,
        "difficulty": "medium",
        "entry_point": "word_frequency",
        "prompt": "Write a Python function `word_frequency(text)` that returns a dict of word frequencies from a string. Words are case-insensitive and punctuation (.,!?;:) should be stripped.",
        "test": """
result = word_frequency("Hello world. Hello Python!")
assert result["hello"] == 2
assert result["world"] == 1
assert result["python"] == 1
result2 = word_frequency("one, two, two, three")
assert result2["two"] == 2
print('PASS')
"""
    },
    # ===== HARD =====
    {
        "id": 17,
        "difficulty": "hard",
        "entry_point": "lru_cache_impl",
        "prompt": "Write a Python class `LRUCache` that implements a Least Recently Used cache. Constructor takes `capacity`. Methods: `get(key)` returns value or -1 if not found, `put(key, value)` inserts/updates and evicts least recently used if at capacity. Both O(1).",
        "test": """
cache = LRUCache(2)
cache.put(1, 1)
cache.put(2, 2)
assert cache.get(1) == 1
cache.put(3, 3)
assert cache.get(2) == -1
cache.put(4, 4)
assert cache.get(1) == -1
assert cache.get(3) == 3
assert cache.get(4) == 4
print('PASS')
"""
    },
    {
        "id": 18,
        "difficulty": "hard",
        "entry_point": "find_all_permutations",
        "prompt": "Write a Python function `find_all_permutations(s)` that returns all unique permutations of a string as a sorted list. Handle duplicate characters.",
        "test": """
result = find_all_permutations("abc")
assert sorted(result) == sorted(['abc','acb','bac','bca','cab','cba'])
result2 = find_all_permutations("aab")
assert sorted(result2) == sorted(['aab','aba','baa'])
result3 = find_all_permutations("a")
assert result3 == ['a']
print('PASS')
"""
    },
    {
        "id": 19,
        "difficulty": "hard",
        "entry_point": "longest_palindromic_substring",
        "prompt": "Write a Python function `longest_palindromic_substring(s)` that returns the longest palindromic substring. If multiple with same length, return the first one found. Use expand-around-center approach.",
        "test": """
assert longest_palindromic_substring("babad") in ["bab", "aba"]
assert longest_palindromic_substring("cbbd") == "bb"
assert longest_palindromic_substring("a") == "a"
assert longest_palindromic_substring("racecar") == "racecar"
print('PASS')
"""
    },
    {
        "id": 20,
        "difficulty": "hard",
        "entry_point": "coin_change",
        "prompt": "Write a Python function `coin_change(coins, amount)` that returns the minimum number of coins needed to make the amount. Return -1 if it's impossible. Use dynamic programming.",
        "test": """
assert coin_change([1, 5, 10, 25], 36) == 3
assert coin_change([1, 2, 5], 11) == 3
assert coin_change([2], 3) == -1
assert coin_change([1], 0) == 0
assert coin_change([186, 419, 83, 408], 6249) == 20
print('PASS')
"""
    },
]

EASY_IDS = [p["id"] for p in PROBLEMS if p["difficulty"] == "easy"]
MEDIUM_IDS = [p["id"] for p in PROBLEMS if p["difficulty"] == "medium"]
HARD_IDS = [p["id"] for p in PROBLEMS if p["difficulty"] == "hard"]

DIFFICULTY_COLOR = {
    "easy": "green",
    "medium": "orange",
    "hard": "red"
}
