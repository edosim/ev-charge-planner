def get_smallest_window(nums: list, n: int) -> tuple[int, list[int]]:
    """Gets the first smallest window"""

    #Keep tabs of current sum, minumum sum and the index of the minumum sum
    current_sum = sum(nums[:n])
    min_sum = current_sum
    min_sum_idx = 0

    for i in range(1,len(nums) + 1 - n):
        current_sum = current_sum - nums[i-1] + nums[i+n-1]
        if current_sum < min_sum:
            min_sum = current_sum
            min_sum_idx = i
    return min_sum_idx, nums[min_sum_idx:min_sum_idx + n]


