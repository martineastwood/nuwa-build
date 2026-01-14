import nimpy

# This file has intentional errors for testing error message formatting

proc typeError(): int {.exportpy.} =
  ## This should return int but returns string
  return "wrong type"  # Type mismatch error

proc undeclaredVariable(): int {.exportpy.} =
  ## References an undeclared variable
  return nonexistentVar  # Undeclared identifier error

proc missingExportPy(): int =
  ## Forgetting exportpy pragma - should be accessible but isn't
  return 42
