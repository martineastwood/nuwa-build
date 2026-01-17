"""Constants used throughout Nuwa Build."""

# Compilation constants
NIM_APP_LIB_FLAG = "--app:lib"
NIM_COMPILER_CMD = "nim"
NIMBLE_CMD = "nimble"

# File permissions for wheel entries
# Regular file + rwxr-xr-x (executable shared library)
SHARED_LIBRARY_PERMISSIONS = 0o100755 << 16

# Watch mode timing
DEFAULT_DEBOUNCE_DELAY = 0.5  # seconds

# Platform-specific extensions
WINDOWS_EXTENSION = ".pyd"
UNIX_EXTENSION = ".so"
