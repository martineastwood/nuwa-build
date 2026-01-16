import nuwa_sdk

# This file has intentional errors for testing error message formatting

proc typeError(): int {.nuwa_export.} =
  ## This should return int but returns string
  return "wrong type"  # Type mismatch error

proc undeclaredVariable(): int {.nuwa_export.} =
  ## References an undeclared variable
  return nonexistentVar  # Undeclared identifier error

proc missingExportPy(): int =
  ## Forgetting nuwa_export pragma - should be accessible but isn't
  return 42
