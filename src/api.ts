export type Mode = "fast" | "detailed";
export type RunStatus =
  | "pending"
  | "running"
  | "awaiting_teacher_review"
  | "failed";
export type FormPayload = {
  school_level: "elementary" | "middle" | "high";
  grade: number;
  task_type: "summary";
  instruction: string;
  passage: string;
  student_text: string;
  teacher_guidance?: string;
  mode: Mode;
};
export type Evidence = { paragraph_id: number; quote: string };
export type Issue = {
  issue_id?: string;
  category: string;
  severity?: string;
  diagnosis: string;
  reasoning?: string;
  source_evidence: Evidence[];
  student_evidence: { quote: string }[];
};
export type RunResult = {
  mode: Mode;
  fast_feedback?: {
    passage_summary: string;
    issues: Issue[];
    student_feedback: string;
  } | null;
  passage_analysis?: { central_idea: string } | null;
  evaluation?: { overall_assessment: string; issues: Issue[] } | null;
  feedback?: {
    teacher_summary: string;
    student_summary: string;
    comments: {
      issue_id: string;
      teacher_note: string;
      student_feedback: string;
      revision_question: string;
      revision_example: string | null;
    }[];
  } | null;
};
export type Run = {
  run_id: string;
  status: RunStatus;
  stage: string | null;
  errors: { code: string; message: string }[];
  result: RunResult | null;
};
const baseUrl = (
  import.meta.env.VITE_WRITING_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public field?: string,
  ) {
    super(message);
  }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, init);
  } catch {
    throw new ApiError(
      "api_unreachable",
      "Python API에 연결할 수 없습니다. API 서버 주소와 실행 상태를 확인하세요.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    if (Array.isArray(detail)) {
      const first = detail[0];
      throw new ApiError(
        "validation_error",
        first?.msg ?? "입력값을 확인하세요.",
        Array.isArray(first?.loc) ? first.loc.at(-1) : undefined,
      );
    }
    throw new ApiError(
      detail?.code ?? "api_error",
      detail?.message ?? "API 요청을 처리하지 못했습니다.",
    );
  }
  return response.json() as Promise<T>;
}
export const createRun = (payload: FormPayload) =>
  request<{ run_id: string }>("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
export const getRun = (runId: string, signal?: AbortSignal) =>
  request<Run>(`/api/runs/${encodeURIComponent(runId)}`, { signal });
