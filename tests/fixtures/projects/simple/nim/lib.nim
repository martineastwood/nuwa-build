import nimpy

proc add(a: int, b: int): int {.exportpy.} =
  ## Add two integers together
  return a + b

proc greet(name: string): string {.exportpy.} =
  ## Return a greeting message
  return "Hello, " & name
