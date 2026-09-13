import { ArrowUpRight, Check, ChevronRight, FileText, MessageCircle, PenLine, Sparkles } from 'lucide-react'

const feedbacks = [
  { label: '핵심 내용', score: 92, note: '주장이 선명하게 드러나요.', color: 'bg-[#d9e7b9]' },
  { label: '문장 표현', score: 78, note: '한 문장을 조금 더 덜어내 볼까요?', color: 'bg-[#f4d7ba]' },
  { label: '구성 흐름', score: 86, note: '문단 사이 연결이 자연스러워요.', color: 'bg-[#b9dce1]' },
]

function App() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#f7f7f2] px-5 py-5 text-[#263128] sm:px-8 lg:px-12">
      <nav className="mx-auto flex max-w-7xl items-center justify-between py-3">
        <a className="flex items-center gap-2 font-semibold tracking-tight" href="#top">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-[#263128] text-lg text-[#f7f7f2]">ㅁ</span>
          <span>문장선</span>
        </a>
        <div className="hidden items-center gap-7 text-sm text-[#667069] md:flex">
          <a href="#writing" className="text-[#263128]">내 글</a>
          <a href="#feedback">피드백</a>
          <a href="#library">글감 서랍</a>
        </div>
        <button className="rounded-full border border-[#cdd3c8] px-4 py-2 text-sm font-medium transition hover:bg-white">로그인</button>
      </nav>

      <section id="top" className="mx-auto grid max-w-7xl gap-10 pb-16 pt-16 lg:grid-cols-[1fr_1.08fr] lg:items-center lg:py-24">
        <div className="relative">
          <p className="mb-6 flex items-center gap-2 text-sm font-semibold text-[#74834d]"><Sparkles size={16} /> 매일 한 문장, 더 나다운 글로</p>
          <h1 className="max-w-xl text-5xl font-semibold leading-[1.08] tracking-[-0.06em] sm:text-6xl lg:text-7xl">
            쓰는 시간은<br />
            <span className="relative z-10">나를 선명하게</span> 만든다.
          </h1>
          <div className="absolute left-7 top-[9.5rem] -z-0 h-5 w-72 -rotate-1 bg-[#d9e7b9] sm:top-[11.5rem] sm:w-80" />
          <p className="mt-8 max-w-md text-base leading-7 text-[#667069]">생각을 글로 옮기는 순간부터, 문장선이 곁에서 함께해요. 내 문체는 지키고 표현은 더 또렷하게 다듬어 드립니다.</p>
          <div className="mt-9 flex flex-wrap gap-3">
            <button className="flex items-center gap-2 rounded-full bg-[#263128] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#455447]">글쓰기 시작하기 <ArrowUpRight size={16} /></button>
            <button className="rounded-full px-5 py-3 text-sm font-semibold underline underline-offset-4">어떻게 쓰나요?</button>
          </div>
          <div className="mt-12 flex items-center gap-4 text-sm text-[#667069]">
            <div className="flex -space-x-2"><span className="h-8 w-8 rounded-full border-2 border-[#f7f7f2] bg-[#d2a68a]" /><span className="h-8 w-8 rounded-full border-2 border-[#f7f7f2] bg-[#9fb9a4]" /><span className="h-8 w-8 rounded-full border-2 border-[#f7f7f2] bg-[#8b9bb5]" /></div>
            <span><strong className="font-semibold text-[#263128]">1,240명</strong>의 쓰는 사람이 함께해요</span>
          </div>
        </div>

        <div id="writing" className="relative mx-auto w-full max-w-xl rounded-[2rem] border border-[#dce0d7] bg-white p-4 shadow-[0_18px_50px_-28px_rgba(38,49,40,.38)] sm:p-6">
          <div className="mb-5 flex items-center justify-between border-b border-[#edf0ea] pb-4">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-[#f5efe3] text-[#b8794d]"><PenLine size={19} /></span><div><p className="text-sm font-semibold">오늘의 생각</p><p className="text-xs text-[#929991]">자동 저장됨 · 방금 전</p></div></div>
            <span className="rounded-full bg-[#eaf2d7] px-3 py-1 text-xs font-semibold text-[#718449]">초안</span>
          </div>
          <p className="text-xs font-medium uppercase tracking-[.16em] text-[#929991]">2025. 04. 18 · 금요일</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight">창문 너머의 계절</h2>
          <div className="mt-5 border-l-2 border-[#d9e7b9] pl-4 text-[15px] leading-8 text-[#4f5b51]">
            봄은 늘 조용히 찾아온다. 어제까지 비어 있던 가지 끝에 연둣빛이 맺히고, 나는 그 작은 변화를 한참 바라본다. 바쁜 하루 속에서도 계절은 제 속도로 흘러간다는 사실이 조금은 위로가 된다.
          </div>
          <div className="mt-7 rounded-2xl bg-[#f5f7f0] p-4">
            <div className="flex items-center justify-between"><p className="flex items-center gap-2 text-sm font-semibold"><MessageCircle size={16} className="text-[#718449]" /> 문장선의 첫 피드백</p><span className="text-xs text-[#718449]">읽는 중...</span></div>
            <p className="mt-3 text-sm leading-6 text-[#667069]">‘조용히 찾아온다’는 표현이 글 전체의 차분한 분위기를 잘 열어줘요. 다음 문장에서 <mark className="rounded bg-[#f7dfbd] px-1 text-inherit">‘작은 변화’</mark>를 구체적인 장면으로 보여주면 독자가 더 가까이 느낄 수 있어요.</p>
          </div>
          <button className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-[#263128] py-3 text-sm font-semibold text-white">피드백 완성하기 <ChevronRight size={16} /></button>
        </div>
      </section>

      <section id="feedback" className="mx-auto max-w-7xl border-t border-[#dce0d7] py-16">
        <div className="mb-9 flex flex-wrap items-end justify-between gap-4"><div><p className="text-sm font-semibold text-[#74834d]">WRITE WITH CLARITY</p><h2 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">막막한 글쓰기를, 작은 확신으로.</h2></div><a className="flex items-center gap-1 text-sm font-semibold underline underline-offset-4" href="#library">피드백 살펴보기 <ArrowUpRight size={15} /></a></div>
        <div className="grid gap-4 md:grid-cols-3">{feedbacks.map((item) => <article key={item.label} className="rounded-3xl border border-[#dce0d7] bg-white p-6"><div className={`mb-7 flex h-11 w-11 items-center justify-center rounded-2xl ${item.color}`}><Check size={20} /></div><p className="text-sm text-[#667069]">{item.label}</p><p className="mt-2 text-4xl font-semibold tracking-tight">{item.score}<span className="text-lg">점</span></p><p className="mt-5 text-sm leading-6 text-[#667069]">{item.note}</p></article>)}</div>
      </section>

      <footer id="library" className="mx-auto flex max-w-7xl items-center justify-between border-t border-[#dce0d7] py-8 text-sm text-[#7c857d]"><span>© 2025 Munjangseon</span><span className="flex items-center gap-2"><FileText size={14} /> 당신의 문장을 응원합니다</span></footer>
    </main>
  )
}

export default App
