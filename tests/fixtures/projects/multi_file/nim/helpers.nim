import strutils

proc capitalize(s: string): string =
  ## Capitalize the first letter of a string
  if s.len == 0:
    return s
  return toUpperAscii(s[0]) & substr(s, 1)

proc reverse(s: string): string =
  ## Reverse a string
  result = newString(s.len)
  for i, c in s:
    result[s.len - 1 - i] = c
