import nimpy
import nuwa_sdk

# =============================================================================
# Basic Export Tests
# =============================================================================

proc addInts*(a: int, b: int): int {.nuwa_export.} =
  ## Add two integers together
  return a + b

proc addFloats*(a: float, b: float): float {.nuwa_export.} =
  ## Add two floating point numbers
  return a + b

proc greet*(name: string): string {.nuwa_export.} =
  ## Return a greeting message for the given name
  return "Hello, " & name & "!"

# =============================================================================
# GIL Release Tests
# =============================================================================

proc sumWithNogil*(n: int): int64 {.nuwa_export.} =
  ## Sum numbers from 0 to n-1 with GIL released
  ## Tests withNogil template
  withNogil:
    var sum = 0'i64
    for i in 0..<n:
      sum += i.int64
    return sum

# =============================================================================
# Type Conversion Tests
# =============================================================================

proc processMixedTypes*(a: int, b: float, c: string, d: bool): tuple[int_val: int, float_val: float, str_val: string, bool_val: bool] {.nuwa_export.} =
  ## Process multiple types and return a tuple
  return (
    int_val: a * 2,
    float_val: b * 2.0,
    str_val: c & " processed",
    bool_val: not d
  )

# =============================================================================
# NumPy Array Tests (using basic raw_buffers directly)
# =============================================================================

proc sumIntSequence*(nums: seq[int64]): int64 {.nuwa_export.} =
  ## Sum a sequence of integers
  result = 0
  for val in nums:
    result += val

proc multiplySequence*(nums: seq[float64], scalar: float64): seq[float64] {.nuwa_export.} =
  ## Multiply each element in sequence by scalar
  result = newSeq[float64](nums.len)
  for i, val in pairs(nums):
    result[i] = val * scalar
