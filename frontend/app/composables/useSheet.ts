// The Questions sheet (DESIGN.md §3): open from any page heading, the crumb pebble, M, / or ⌘K. `find` asks it to
// open with the Find field focused.
export function useSheet() {
  const open = useState<boolean>('cv-sheet', () => false)
  const find = useState<boolean>('cv-sheet-find', () => false)
  function show(withFind = false) { find.value = withFind; open.value = true }
  return { open, find, show }
}
