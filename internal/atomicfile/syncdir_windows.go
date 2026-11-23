package atomicfile

// syncDir does nothing: Windows cannot flush a directory handle, and NTFS
// journals the rename itself.
func syncDir(string) error { return nil }
