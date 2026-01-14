import nimpy
include helpers

proc processString(s: string): string {.exportpy.} =
  ## Process a string by capitalizing and reversing it
  let capitalized = capitalize(s)
  return reverse(capitalized)

proc calculate(x: int, y: int): int {.exportpy.} =
  ## Calculate the sum of two numbers
  return x + y
