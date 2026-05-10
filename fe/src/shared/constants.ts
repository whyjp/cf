/**
 * Hard ceiling on the number of camps to ETA-check in one POST /eta/batch
 * call. With per-call etago routing costing ~1-3s and BE concurrency
 * capped at 4, candidate sets > ~300 made the original 1,656-camp blanket
 * request feel hung. The user is expected to narrow with filters first;
 * the apply path warns when the candidate set is still too large.
 *
 * Origin: fe/index.legacy.html:1496 (`const ETA_HARD_CAP = 300;`).
 */
export const ETA_HARD_CAP = 300;

/**
 * Featured-axis pin colors — must stay in sync with the
 * `.pin-pin.<id>` rules in fe/index.legacy.html style block (lines
 * 111-116). Default (.pin-pin alone) stays moss-green for non-featured
 * camps.
 */
export const AXIS_COLORS: Record<string, string> = {
  valley: "#2c6e7b",
  kids: "#c8553d",
  trampoline: "#6b4f2c",
  halloween: "#ff7518",
  cherry: "#ffb7c5",
  autumn: "#d35400",
};
