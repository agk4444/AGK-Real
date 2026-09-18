"""AGK-Real FFI: shared metadata for `extern function` declarations.

Single source of truth for the AGK -> ctypes type mapping, used by the
semantic analyzer (signature validation) and the code generator
(argtypes/restype emission).
"""

# AGK type name -> ctypes type expression used for argtypes/restype.
#
# Integer maps to C int (c_int), not long: this covers the overwhelming
# majority of C APIs (getpid, abs, toupper, strcmp, ...). APIs that return
# size_t/long will have their result truncated to int range -- a
# documented FFI limitation, not a silent miscompile of the common case.
FFI_CTYPES = {
    "String": "ctypes.c_char_p",
    "Integer": "ctypes.c_int",
    "Float": "ctypes.c_double",
    "Boolean": "ctypes.c_bool",
}
