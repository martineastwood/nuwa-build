import nuwa_sdk
include helpers

proc processString(s: string): string {.nuwa_export.} =
  ## Process a string by capitalizing and reversing it
  let capitalized = capitalize(s)
  return reverse(capitalized)

proc calculate(x: int, y: int): int {.nuwa_export.} =
  ## Calculate the sum of two numbers
  return x + y
