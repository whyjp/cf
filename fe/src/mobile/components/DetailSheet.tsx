import { useEffect } from "react";
import { useDetail } from "../../shared/hooks/useDetail";

/**
 * DetailSheet — 풀스크린 (fixed inset-0 z-50) 디테일 시트.
 *
 * id 가 null 이면 아예 렌더하지 않으므로 BottomSheet 위에 자연스럽게
 * 덮였다가 사라진다. Esc 키 → onClose 로 키보드 사용자도 닫을 수 있다
 * (모바일 우선이지만 대형 모바일/태블릿에서 외장 키보드 케이스 대비).
 *
 * C3 의 첫 컷은 placeholder JSON dump body — Plan 의 ⚠️ 노트 그대로.
 * 데스크톱 DetailPanel 의 대표 정보·카테고리·시설·ETA·미니맵 섹션을
 * 모바일 stacked 레이아웃으로 옮기는 작업은 후속 PR.
 *
 * safe-area-inset-bottom: 홈 인디케이터 영역까지 겹치지 않도록 패딩.
 */
interface Props {
  id: string | null;
  onClose: () => void;
}

export function DetailSheet({ id, onClose }: Props) {
  const data = useDetail(id);

  useEffect(() => {
    if (!id) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [id, onClose]);

  if (!id) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-white flex flex-col"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
    >
      <header
        className="h-14 px-4 flex items-center justify-between border-b flex-shrink-0"
        style={{ borderColor: "rgba(26,26,23,0.12)" }}
      >
        <button
          onClick={onClose}
          aria-label="close"
          className="text-xl leading-none w-10 h-10 flex items-center justify-center -ml-2"
        >
          ←
        </button>
        <h2 className="display font-semibold truncate">
          {data?.name ?? "로딩 중…"}
        </h2>
        <span className="w-10" />
      </header>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {data ? (
          <>
            <div className="text-sm text-stone-600">
              {data.sido} · {data.sigungu}
            </div>
            {/* 후속 PR: MiniMap, 카테고리, 시설, ETA — 데스크톱 DetailPanel 의
                핵심 섹션을 모바일 stacked 로 이전. C3 first cut 은 placeholder. */}
            <pre className="text-xs bg-stone-50 p-2 rounded overflow-x-auto">
              {JSON.stringify(data, null, 2).slice(0, 800)}
            </pre>
          </>
        ) : (
          <div className="text-stone-500">불러오는 중…</div>
        )}
      </div>
    </div>
  );
}
