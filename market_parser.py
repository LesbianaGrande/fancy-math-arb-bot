import re

def parse_range(range_str):
    """
    Parses market question strings into (min, max) tuple boundaries.
    e.g. "64°F or below" -> (None, 64)
    e.g. "65-66°F" -> (65, 66)
    e.g. "67°F or higher" -> (67, None)
    """
    text = range_str.upper().replace("°F", "").replace("°", "").strip()
    
    if "<" in text:
        nums = [int(n) for n in re.findall(r'\d+', text)]
        if nums: return (None, nums[0] - 1)
        
    if ">" in text:
        nums = [int(n) for n in re.findall(r'\d+', text)]
        if nums: return (nums[0] + 1, None)
    
    if "BELOW" in text or "LOWER" in text:
        nums = [int(n) for n in re.findall(r'\d+', text)]
        if nums:
            if "OR BELOW" in text or "OR LOWER" in text:
                return (None, nums[0])
            else:
                return (None, nums[0] - 1)
                
    if "HIGHER" in text or "ABOVE" in text:
        nums = [int(n) for n in re.findall(r'\d+', text)]
        if nums:
            if "OR HIGHER" in text or "OR ABOVE" in text:
                return (nums[0], None)
            else:
                return (nums[0] + 1, None)
                
    # Range format: e.g. "65-66"
    text_clean = text.replace(' ', '')
    if '-' in text_clean:
        nums = [int(n) for n in re.findall(r'\d+', text_clean)]
        if len(nums) >= 2:
            return (nums[0], nums[1])

    # Exact number
    nums = [int(n) for n in re.findall(r'\d+', text)]
    if len(nums) == 1:
        return (nums[0], nums[0])
        
    return (None, None)

def get_state_space(bounds_list):
    """
    Builds a list of contiguous integers encompassing all limits.
    """
    all_nums = []
    for bounds in bounds_list:
        if bounds[0] is not None:
             all_nums.append(bounds[0])
        if bounds[1] is not None:
             all_nums.append(bounds[1])
             
    if not all_nums: 
        return list(range(0, 100)) # fallback
        
    min_val = min(all_nums) - 2 # Pad lowest by 2
    max_val = max(all_nums) + 2 # Pad highest by 2
    return list(range(min_val, max_val + 1))
