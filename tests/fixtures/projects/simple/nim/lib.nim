import nuwa_sdk

proc add(a: int, b: int): int {.nuwa_export.} =
  ## Add two integers together
  return a + b

proc greet(name: string): string {.nuwa_export.} =
  ## Return a greeting message
  return "Hello, " & name
