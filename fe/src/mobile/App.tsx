import { MobileShell } from "./components/MobileShell";

/**
 * Root mobile App — currently just wraps MobileShell.
 *
 * C1 = empty shell (TopBar + 빈 지도 placeholder + 빈 BottomSheet placeholder).
 * C2 = MobileMap + BottomSheet 진짜 부착.
 * C3+ = list/detail/search/location wiring.
 */
export function App() {
  return <MobileShell />;
}
