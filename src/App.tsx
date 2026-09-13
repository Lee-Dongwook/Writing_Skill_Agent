import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  FileText,
  LoaderCircle,
  PenLine,
  RefreshCw,
  Sparkles,
} from "lucide-react";
import {
  ApiError,
  createRun,
  getRun,
  type FormPayload,
  type Issue,
  type Run,
  type RunResult,
} from "./api";

const levels = [
  { value: "elementary", label: "초등" },
  { value: "middle", label: "중등" },
  { value: "high", label: "고등" },
] as const;
const labels: Record<string, string> = {
  omission: "핵심 내용 누락",
  distortion: "의미 왜곡",
  unsupported_claim: "원문 밖 주장",
  unnecessary_detail: "불필요한 세부 내용",
  organization: "구성",
  expression: "표현",
};
const errorLabels: Record<string, string> = {
  model_call_failed: "모델 호출에 실패했습니다.",
  llm_not_configured:
    "외부 모델 API 키가 없거나 유효하지 않습니다. 서버의 GROQ_API_KEY 설정을 확인하세요.",
  llm_rate_limited:
    "외부 모델 API 사용량 한도에 도달했습니다. 잠시 후 다시 실행하세요.",
  ollama_connection_failed:
    "Ollama 서버에 연결할 수 없습니다. ollama serve와 API 실행 위치를 확인하세요.",
  model_not_installed:
    "요청한 모델을 찾을 수 없습니다. 모델 설정(로컬은 ollama pull, 배포는 WRITING_GROQ_MODEL)을 확인하세요.",
  invalid_output: "모델 출력이 잘렸거나 형식 검증에 실패했습니다.",
  evidence_mismatch: "원문·학생 글 근거 검증에 실패했습니다.",
  input_budget_exceeded:
    "입력이 빠른 첨삭의 길이 제한을 넘었습니다. 상세 모드를 사용하거나 글을 나누세요.",
  time_budget_exceeded: "전체 실행 시간이 제한을 넘었습니다.",
  run_not_found:
    "서버 재시작 또는 결과 보존 시간 만료로 실행을 찾을 수 없습니다.",
  queue_full: "로컬 첨삭 대기열이 가득 찼습니다.",
};
const initial: FormPayload = {
  school_level: "elementary",
  grade: 5,
  task_type: "summary",
  instruction: "지문의 핵심 내용을 두 문장으로 요약하세요.",
  passage: "",
  student_text: "",
  teacher_guidance: "",
  mode: "fast",
};
const maxGrade = (level: FormPayload["school_level"]) =>
  level === "elementary" ? 6 : 3;

function ResultView({ result }: { result: RunResult }) {
  const fast = result.fast_feedback;
  const detail = result.feedback;
  const comments = new Map(
    (detail?.comments ?? []).map((item) => [item.issue_id, item]),
  );
  const summary =
    fast?.passage_summary ??
    detail?.teacher_summary ??
    result.evaluation?.overall_assessment ??
    result.passage_analysis?.central_idea;
  const issues: Issue[] = fast?.issues ?? result.evaluation?.issues ?? [];
  return (
    <section className="mt-7 rounded-2xl border border-[#d9e7b9] bg-[#fbfdf7] p-5">
      <p className="flex items-center gap-2 text-sm font-semibold text-[#718449]">
        <Check size={16} /> 교사 검토용 첨삭 초안
      </p>
      {summary && (
        <>
          <p className="mt-4 text-xs font-semibold text-[#7c857d]">
            핵심 요약 · 총평
          </p>
          <p className="mt-1 text-sm leading-6 text-[#425044]">{summary}</p>
        </>
      )}
      {detail?.student_summary && (
        <p className="mt-3 rounded-xl bg-white p-3 text-sm leading-6 text-[#4f5b51]">
          학생용 전체 피드백: {detail.student_summary}
        </p>
      )}
      {issues.length === 0 ? (
        <p className="mt-5 rounded-xl bg-white p-4 text-sm leading-6 text-[#4f5b51]">
          검증된 첨삭 문제는 없습니다. 이는 결과 로딩 실패가 아닌 정상 결과이며,
          교사가 원문과 학생 글을 최종 검토하세요.
        </p>
      ) : (
        <div className="mt-5 space-y-4">
          {issues.map((issue, index) => {
            const comment = issue.issue_id
              ? comments.get(issue.issue_id)
              : undefined;
            return (
              <article
                key={issue.issue_id ?? `${issue.category}-${index}`}
                className="rounded-xl border border-[#e2e8dc] bg-white p-4 text-sm leading-6"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-[#f4d7ba] px-2 py-0.5 text-xs font-semibold">
                    {labels[issue.category] ?? issue.category}
                  </span>
                  {issue.severity && (
                    <span className="text-xs text-[#7c857d]">
                      중요도:{" "}
                      {issue.severity === "high"
                        ? "높음"
                        : issue.severity === "medium"
                          ? "보통"
                          : "낮음"}
                    </span>
                  )}
                </div>
                <p className="mt-2 font-medium">{issue.diagnosis}</p>
                {issue.reasoning && (
                  <p className="text-[#667069]">{issue.reasoning}</p>
                )}
                {issue.student_evidence.length > 0 && (
                  <p className="mt-2 text-[#667069]">
                    학생 글 구절:{" "}
                    <q>
                      {issue.student_evidence.map((e) => e.quote).join(" · ")}
                    </q>
                  </p>
                )}
                {issue.source_evidence.length > 0 && (
                  <p className="text-[#667069]">
                    원문 근거:{" "}
                    {issue.source_evidence.map((e) => (
                      <span key={`${e.paragraph_id}-${e.quote}`}>
                        <q>{e.quote}</q> (문단 {e.paragraph_id}){" "}
                      </span>
                    ))}
                  </p>
                )}
                {comment && (
                  <div className="mt-3 border-t border-[#edf0ea] pt-3 text-[#4f5b51]">
                    <p>교사용: {comment.teacher_note}</p>
                    <p>학생용: {comment.student_feedback}</p>
                    <p>수정 질문: {comment.revision_question}</p>
                    {comment.revision_example && (
                      <p>부분 수정 예시: {comment.revision_example}</p>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function App() {
  const [form, setForm] = useState(initial),
    [fieldErrors, setFieldErrors] = useState<Record<string, string>>({}),
    [run, setRun] = useState<Run | null>(null),
    [requestError, setRequestError] = useState<string | null>(null),
    [submitting, setSubmitting] = useState(false);
  const activeRun = useRef<string | null>(null),
    abort = useRef<AbortController | null>(null),
    timer = useRef<number | null>(null);
  const running =
    submitting || run?.status === "pending" || run?.status === "running";
  const clearPolling = () => {
    if (timer.current) window.clearTimeout(timer.current);
    abort.current?.abort();
    timer.current = null;
    abort.current = null;
  };
  useEffect(() => () => clearPolling(), []);
  const update = <K extends keyof FormPayload>(key: K, value: FormPayload[K]) =>
    setForm((old) => ({ ...old, [key]: value }));
  const validate = () => {
    const errors: Record<string, string> = {};
    for (const key of ["instruction", "passage", "student_text"] as const)
      if (!form[key].trim()) errors[key] = "필수 입력 항목입니다.";
    if (form.grade > maxGrade(form.school_level))
      errors.grade = "학교급에 맞는 학년을 선택하세요.";
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };
  const poll = async (runId: string) => {
    try {
      abort.current = new AbortController();
      const next = await getRun(runId, abort.current.signal);
      if (activeRun.current !== runId) return;
      setRun(next);
      if (next.status === "pending" || next.status === "running")
        timer.current = window.setTimeout(() => poll(runId), 1200);
    } catch (error) {
      if ((error as Error).name !== "AbortError" && activeRun.current === runId)
        setRequestError(
          error instanceof ApiError
            ? error.message
            : "상태를 조회하지 못했습니다. 첨삭 작업 자체의 실패 여부는 다시 조회해 확인하세요.",
        );
    }
  };
  const submit = async () => {
    if (running || !validate()) return;
    clearPolling();
    setRequestError(null);
    setRun(null);
    setSubmitting(true);
    try {
      const created = await createRun({
        ...form,
        teacher_guidance: form.teacher_guidance?.trim() || undefined,
      });
      activeRun.current = created.run_id;
      if ("result" in created) {
        setRun(created);
        return;
      }
      setRun({
        run_id: created.run_id,
        status: "pending",
        stage: null,
        errors: [],
        result: null,
      });
      void poll(created.run_id);
    } catch (error) {
      const apiError = error as ApiError;
      if (apiError.field)
        setFieldErrors({ [apiError.field]: apiError.message });
      setRequestError(apiError.message);
    } finally {
      setSubmitting(false);
    }
  };
  const statusText =
    run?.status === "pending"
      ? "대기열에서 실행을 기다리고 있어요."
      : run?.status === "running"
        ? `${run.stage === "fast" ? "빠른 첨삭" : run.stage === "passage" ? "지문 분석" : run.stage === "evaluation" ? "요약 평가" : run.stage === "feedback" ? "첨삭 초안" : "첨삭"}을 실행 중이에요.`
        : submitting
          ? "첨삭을 실행 중이에요."
          : "";
  return (
    <main className="min-h-screen bg-[#f7f7f2] px-5 py-5 text-[#263128] sm:px-8 lg:px-12">
      <nav className="mx-auto flex max-w-7xl items-center justify-between py-3">
        <a className="flex items-center gap-2 font-semibold" href="#top">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[#263128] text-lg text-[#f7f7f2]">
            ㅁ
          </span>
          <span>문장선</span>
        </a>
        <span className="rounded-full border border-[#cdd3c8] px-4 py-2 text-sm">
          교사용 도구
        </span>
      </nav>
      <section
        id="top"
        className="mx-auto grid max-w-7xl gap-10 pb-12 pt-12 lg:grid-cols-[.8fr_1.2fr] lg:items-start"
      >
        <div>
          <p className="mb-6 flex items-center gap-2 text-sm font-semibold text-[#74834d]">
            <Sparkles size={16} /> 국어 비문학 요약문 첨삭
          </p>
          <h1 className="text-5xl font-semibold leading-[1.08] tracking-[-.06em] sm:text-6xl">
            글의 뜻을
            <br />
            <span>더 또렷하게</span> 본다.
          </h1>
          <p className="mt-8 max-w-md leading-7 text-[#667069]">
            원문 근거를 바탕으로 만든 초안을 교사가 검토합니다. 자동 채점·승인
            기능은 제공하지 않습니다.
          </p>
        </div>
        <section
          id="writing"
          className="w-full rounded-[2rem] border border-[#dce0d7] bg-white p-5 shadow-[0_18px_50px_-28px_rgba(38,49,40,.38)] sm:p-6"
        >
          <div className="mb-5 flex items-center gap-3 border-b border-[#edf0ea] pb-4">
            <span className="grid h-10 w-10 place-items-center rounded-xl bg-[#f5efe3] text-[#b8794d]">
              <PenLine size={19} />
            </span>
            <div>
              <p className="text-sm font-semibold">비문학 첨삭 요청</p>
              <p className="text-xs text-[#929991]">
                입력 내용은 실패해도 이 화면에 남습니다.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm">
              학교급
              <select
                value={form.school_level}
                onChange={(e) => {
                  const school_level = e.target
                    .value as FormPayload["school_level"];
                  setForm((old) => ({
                    ...old,
                    school_level,
                    grade: Math.min(old.grade, maxGrade(school_level)),
                  }));
                }}
                className="mt-1 w-full rounded-xl border border-[#dce0d7] p-2"
              >
                {levels.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              학년
              <select
                value={form.grade}
                onChange={(e) => update("grade", Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-[#dce0d7] p-2"
              >
                {Array.from(
                  { length: maxGrade(form.school_level) },
                  (_, i) => i + 1,
                ).map((grade) => (
                  <option key={grade}>{grade}</option>
                ))}
              </select>
              {fieldErrors.grade && (
                <small className="text-red-700">{fieldErrors.grade}</small>
              )}
            </label>
            <label className="text-sm">
              실행 모드
              <select
                value={form.mode}
                onChange={(e) =>
                  update("mode", e.target.value as FormPayload["mode"])
                }
                disabled={running}
                className="mt-1 w-full rounded-xl border border-[#dce0d7] p-2"
              >
                <option value="fast">빠른 첨삭 (권장)</option>
                <option value="detailed">상세 분석 (느림)</option>
              </select>
            </label>
          </div>
          {(
            [
              [
                "instruction",
                "과제 지시문",
                "예: 지문의 핵심 내용을 두 문장으로 요약하세요.",
              ],
              [
                "passage",
                "원문 지문",
                "학생이 읽은 비문학 지문을 붙여 넣으세요.",
              ],
              ["student_text", "학생 글", "첨삭할 학생의 요약문을 입력하세요."],
            ] as const
          ).map(([key, label, placeholder]) => (
            <label key={key} className="mt-4 block text-sm font-medium">
              {label}
              <textarea
                value={form[key]}
                onChange={(e) => update(key, e.target.value)}
                disabled={running}
                placeholder={placeholder}
                className="mt-1 min-h-24 w-full resize-y rounded-xl border border-[#dce0d7] p-3 font-normal leading-6 outline-none focus:border-[#718449]"
              />
              {fieldErrors[key] && (
                <small className="text-red-700">{fieldErrors[key]}</small>
              )}
            </label>
          ))}
          <label className="mt-4 block text-sm font-medium">
            교사 지도 방향{" "}
            <span className="font-normal text-[#7c857d]">(선택)</span>
            <textarea
              value={form.teacher_guidance}
              onChange={(e) => update("teacher_guidance", e.target.value)}
              disabled={running}
              className="mt-1 min-h-16 w-full resize-y rounded-xl border border-[#dce0d7] p-3 font-normal"
            />
          </label>
          {requestError && (
            <p className="mt-4 flex gap-2 rounded-xl bg-[#fff0ed] p-3 text-sm text-[#9b3f2d]">
              <AlertCircle size={18} />
              {requestError}
            </p>
          )}
          {running && (
            <p className="mt-4 flex items-center gap-2 rounded-xl bg-[#f5f7f0] p-3 text-sm text-[#667069]">
              <LoaderCircle size={16} className="animate-spin" />
              {statusText} 진행률과 남은 시간은 추정하지 않습니다.
            </p>
          )}
          {run?.status === "failed" && (
            <div className="mt-4 rounded-xl bg-[#fff0ed] p-3 text-sm text-[#9b3f2d]">
              <p className="font-semibold">첨삭 실행에 실패했습니다.</p>
              {run.errors.map((error, i) => (
                <p key={i}>{errorLabels[error.code] ?? error.message}</p>
              ))}
            </div>
          )}
          <button
            onClick={() => void submit()}
            disabled={running}
            className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#263128] py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          >
            {run?.status === "failed" ? (
              <>
                <RefreshCw size={16} /> 같은 입력으로 다시 실행
              </>
            ) : (
              <>
                첨삭 실행하기 <ChevronRight size={16} />
              </>
            )}
          </button>
          {run?.result && <ResultView result={run.result} />}
        </section>
      </section>
      <footer className="mx-auto flex max-w-7xl items-center justify-between border-t border-[#dce0d7] py-8 text-sm text-[#7c857d]">
        <span>© 2026 Munjangseon</span>
        <span className="flex items-center gap-2">
          <FileText size={14} /> 교사 검토용 초안
        </span>
      </footer>
    </main>
  );
}
export default App;
