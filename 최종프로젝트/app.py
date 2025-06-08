import streamlit as st
import fitz  # PyMuPDF
import openai
import re
import os
import time

# 페이지 설정
st.set_page_config(
    page_title="AI 시험문제 생성기",
    page_icon="📚",
    layout="wide"
)

# OpenAI API 키 읽기 (dotenv, .env 사용 X)
api_key = st.secrets["OPENAI_API_KEY"]
client = openai.OpenAI(api_key=api_key)

# UI CSS
st.markdown("""
<style>
    .stButton > button {
        width: 100%;
        height: 50px;
        font-size: 18px;
    }
    .question-box {
        background-color: #23272f !important;
        color: #fff !important;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
        font-size: 1.12em;
        font-weight: 500;
        letter-spacing: 0.02em;
    }
    .evaluation-box {
        background-color: #e8f4f8;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .progress-bar {
        background-color: #4CAF50;
        height: 8px;
        border-radius: 4px;
        transition: width 0.3s ease;
    }
    #fixed-chatbot {
      position: fixed;
      bottom: 30px;
      right: 30px;
      width: 340px;
      z-index: 9999;
      background: #f7fafc;
      border-radius: 16px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.14);
      padding: 16px 18px 12px 18px;
      border: 1.5px solid #dbeafe;
    }
</style>
""", unsafe_allow_html=True)

def extract_text(pdf_file):
    pdf_file.seek(0)
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    texts = [page.get_text().strip() for page in doc]
    doc.close()
    return '\n\n'.join(texts)

def generate_questions(full_text, client, num_questions=15, difficulty="중", author_info=None, target_level=None):
    difficulty_prompts = {
        "하": "기초적이고 단순한 사실 확인이 아니라, 반드시 학습자가 이해해야 할 핵심 내용을 묻는",
        "중": "이해력과 적용력을 요구하며, 학습자의 생각을 이끌어내는",
        "상": "분석력과 종합적 사고, 그리고 비판적 관점을 요구하는"
    }
    prompt = (
        f"너는 {'이 수업의 교수' if not author_info else author_info}이고, "
        f"이 자료는 {target_level+'용' if target_level else '대상 불명'} 수업 자료다.\n"
        f"자료의 핵심 개념, 반드시 알아야 할 내용만을 바탕으로 {difficulty_prompts[difficulty]} "
        f"한국어 주관식 예상 시험문제 {num_questions}개를 만들어줘.\n"
        f"- 너무 쉬운 문제, 단순 복사 문제, 상식적인 사실 문제는 내지 마라.\n"
        f"- 학생의 사고력, 이해력, 적용력을 반드시 평가할 수 있어야 한다.\n"
        f"- 각 문제에 번호를 붙여라 (1. 2. ...)\n"
        f"- 답은 절대 쓰지 마라.\n"
        f"- 문제만 작성해라.\n\n"
        f"자료 내용:\n{full_text}"
    )
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    text = response.choices[0].message.content
    questions = re.findall(r'\d+\.\s(.+)', text)
    if len(questions) < num_questions:
        lines = [q.strip() for q in text.split('\n') if q.strip() and not q.startswith('난이도')]
        questions = []
        for line in lines:
            cleaned = re.sub(r'^\d+\.\s*', '', line)
            if cleaned:
                questions.append(cleaned)
        questions = questions[:num_questions]
    return questions[:num_questions]

def evaluate_answer(question, user_answer, context, client, difficulty="중"):
    difficulty_criteria = {
        "하": "기초적인 이해도 중심으로",
        "중": "이해도와 적용력을 균형있게",
        "상": "심화된 분석력과 비판적 사고를 중심으로"
    }
    context_text = context[:3000]
    prompt = (
        f"아래는 난이도 '{difficulty}'의 예상 시험 문제와 이에 대한 학생의 답변입니다.\n\n"
        f"문제: {question}\n"
        f"학생의 답변: {user_answer}\n\n"
        f"참고할 원문 내용:\n{context_text}\n\n"
        f"{difficulty_criteria[difficulty]} 평가해주세요.\n\n"
        "다음 형식으로 작성해주세요:\n\n"
        "**평가 결과**: [정답/부분정답/오답]\n\n"
        "**모범 답안**:\n[모범 답안 내용]\n\n"
        "**평가 및 피드백**:\n[구체적인 평가 내용과 개선점]\n\n"
        "**핵심 포인트**:\n"
        "- [핵심 내용 1]\n"
        "- [핵심 내용 2]\n"
        "- [필요시 추가]\n"
    )
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5
    )
    return response.choices[0].message.content

def get_hint(question, full_text, client):
    context_text = full_text[:3000]
    prompt = (
        f"아래는 예상 시험문제와 관련된 원문 내용입니다.\n\n"
        f"문제: {question}\n"
        f"원문 일부:\n{context_text}\n\n"
        "문제를 풀 때 참고가 될만한 원문에서 핵심 키워드, 문장, 단서를 간략하게 요약해서 '힌트'로 알려줘. 단, 정답은 포함하지 마."
    )
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    return response.choices[0].message.content

# 세션 상태 초기화
if "questions" not in st.session_state:
    st.session_state.questions = []
if "question_idx" not in st.session_state:
    st.session_state.question_idx = 0
if "user_answers" not in st.session_state:
    st.session_state.user_answers = []
if "evaluations" not in st.session_state:
    st.session_state.evaluations = []
if "full_text" not in st.session_state:
    st.session_state.full_text = ""
if "ready" not in st.session_state:
    st.session_state.ready = False
if "difficulty" not in st.session_state:
    st.session_state.difficulty = "중"
if "num_questions" not in st.session_state:
    st.session_state.num_questions = 10
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "elapsed_times" not in st.session_state:
    st.session_state.elapsed_times = []
if "problem_bank" not in st.session_state:
    st.session_state.problem_bank = []
if "show_results" not in st.session_state:
    st.session_state.show_results = False
if "pb_idx" not in st.session_state:
    st.session_state.pb_idx = 1
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

st.title("📚 PDF 기반 AI 시험문제 생성 & 평가 시스템")
st.markdown("---")

with st.sidebar:
    st.header("⚙️ 설정")
    if not st.session_state.ready:
        st.subheader("문제 생성 옵션")
        difficulty = st.select_slider(
            "난이도 선택",
            options=["하", "중", "상"],
            value="중",
            help="하: 기초 문제, 중: 표준 문제, 상: 심화 문제"
        )
        st.session_state.difficulty = difficulty
        num_questions = st.slider(
            "문제 개수",
            min_value=5,
            max_value=20,
            value=10,
            step=5
        )
        st.session_state.num_questions = num_questions
        st.markdown("---")
        st.info(f"선택된 난이도: **{difficulty}**")
        st.info(f"생성할 문제 수: **{num_questions}개**")
    else:
        st.subheader("📊 진행 상황")
        answered = sum(1 for ans in st.session_state.user_answers if ans.strip())
        evaluated = sum(1 for ev in st.session_state.evaluations if ev is not None)
        total = len(st.session_state.questions)
        progress = evaluated / total if total > 0 else 0
        st.progress(progress)
        st.write(f"평가 완료: {evaluated}/{total}")
        st.write(f"답변 작성: {answered}/{total}")
        st.markdown("---")
        st.info(f"현재 난이도: **{st.session_state.difficulty}**")
        if st.button("🔄 새로운 시험 시작"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

col1, col2 = st.columns([2, 1])
if not st.session_state.ready:
    with col1:
        uploaded_file = st.file_uploader(
            "📄 시험범위 PDF 업로드",
            type=["pdf"],
            help="텍스트 기반 PDF 파일만 지원됩니다."
        )
    with col2:
        if uploaded_file:
            st.success("✅ 파일 업로드 완료")
            if st.button("🚀 문제 생성 시작", type="primary"):
                with st.spinner("📖 텍스트 추출 중..."):
                    full_text = extract_text(uploaded_file)
                st.session_state.full_text = full_text
                with st.spinner(f"🤖 {st.session_state.difficulty} 난이도 문제 {st.session_state.num_questions}개 생성 중..."):
                    questions = generate_questions(
                        full_text,
                        client,
                        num_questions=st.session_state.num_questions,
                        difficulty=st.session_state.difficulty
                    )
                st.session_state.questions = questions
                st.session_state.question_idx = 0
                st.session_state.user_answers = [""] * len(questions)
                st.session_state.evaluations = [None] * len(questions)
                st.session_state.elapsed_times = [0] * len(questions)
                st.session_state.ready = True
                st.session_state.start_time = time.time()
                st.balloons()
                st.rerun()

if st.session_state.ready and st.session_state.questions:
    idx = st.session_state.question_idx
    questions = st.session_state.questions

    st.markdown(
        f"""
        <div style="background-color: #e0e0e0; border-radius: 4px; margin-bottom: 20px;">
            <div class="progress-bar" style="width: {(idx + 1) / len(questions) * 100}%"></div>
        </div>
        """, unsafe_allow_html=True
    )

    st.markdown(
        f"""
        <div class="question-box">
            <h3>📝 문제 {idx+1} / {len(questions)}</h3>
            <h4>{questions[idx]}</h4>
        </div>
        """, unsafe_allow_html=True
    )

    with st.expander("💡 힌트 보기"):
        if st.button("힌트 가져오기", key=f"hint_{idx}"):
            hint = get_hint(questions[idx], st.session_state.full_text, client)
            st.info(hint)

    user_answer = st.text_area(
        "✍️ 답안을 입력하세요:",
        value=st.session_state.user_answers[idx],
        height=150,
        placeholder="여기에 답안을 작성해주세요...",
        key=f"answer_{idx}"
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if idx > 0:
            if st.button("◀️ 이전", key=f"prev_{idx}"):
                st.session_state.question_idx = idx - 1
                st.rerun()

    with col2:
        if st.session_state.evaluations[idx] is None:
            submit_disabled = not user_answer.strip()
            if st.button(
                "📤 답안 제출 및 평가",
                key=f"submit_{idx}",
                disabled=submit_disabled,
                type="primary"
            ):
                if st.session_state.start_time:
                    elapsed = time.time() - st.session_state.start_time
                    st.session_state.elapsed_times[idx] = elapsed
                with st.spinner("🤖 AI가 답안을 평가하고 있습니다..."):
                    evaluation = evaluate_answer(
                        questions[idx],
                        user_answer,
                        st.session_state.full_text,
                        client,
                        st.session_state.difficulty
                    )
                st.session_state.user_answers[idx] = user_answer
                st.session_state.evaluations[idx] = evaluation
                entry = {
                    "문제": questions[idx],
                    "내 답": user_answer,
                    "AI 평가": evaluation
                }
                if entry not in st.session_state.problem_bank:
                    st.session_state.problem_bank.append(entry)
                st.success("✅ 평가 완료!")
                st.rerun()

    with col3:
        if idx < len(questions) - 1:
            next_disabled = st.session_state.evaluations[idx] is None
            if st.button("다음 ▶️", key=f"next_{idx}", disabled=next_disabled):
                st.session_state.question_idx = idx + 1
                st.session_state.start_time = time.time()
                st.rerun()
        else:
            if all(ev is not None for ev in st.session_state.evaluations):
                if st.button("📊 결과 보기", type="primary"):
                    st.session_state.show_results = True
                    st.rerun()

    if st.session_state.evaluations[idx]:
        st.markdown("---")
        st.markdown(
            """
            <div class="evaluation-box">
                <h4>🎯 AI 평가 결과</h4>
            </div>
            """, unsafe_allow_html=True
        )
        st.markdown(st.session_state.evaluations[idx])
        if st.session_state.elapsed_times[idx] > 0:
            minutes = int(st.session_state.elapsed_times[idx] // 60)
            seconds = int(st.session_state.elapsed_times[idx] % 60)
            st.caption(f"⏱️ 소요 시간: {minutes}분 {seconds}초")

# ----- 문제은행 리뷰/복습 기능 -----
if st.session_state.show_results:
    st.markdown("---")
    st.header("📊 최종 결과")
    total_questions = len(st.session_state.questions)
    answered = sum(1 for ans in st.session_state.user_answers if ans.strip())
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 문제 수", total_questions)
    with col2:
        st.metric("답변 완료", answered)
    with col3:
        total_time = sum(st.session_state.elapsed_times)
        st.metric("총 소요 시간", f"{int(total_time // 60)}분")
    if st.session_state.problem_bank:
        st.markdown("## 📚 문제은행 복습")
        total_pb = len(st.session_state.problem_bank)
        pb_idx = st.number_input(
            "문제 번호", min_value=1, max_value=total_pb, value=st.session_state.pb_idx, step=1, key="pb_idx_input"
        )
        st.session_state.pb_idx = pb_idx
        entry = st.session_state.problem_bank[int(pb_idx)-1]
        st.markdown(f"**문제 {int(pb_idx)} / {total_pb}**")
        st.markdown(f"**문제:** {entry['문제']}")
        st.markdown(f"**내 답:** {entry['내 답']}")
        st.markdown(f"**AI 평가:**\n{entry['AI 평가']}")
        col_prev, col_next = st.columns(2)
        with col_prev:
            if pb_idx > 1:
                if st.button("◀️ 이전 문제", key="pb_prev"):
                    st.session_state.pb_idx = pb_idx - 1
                    st.rerun()
        with col_next:
            if pb_idx < total_pb:
                if st.button("다음 문제 ▶️", key="pb_next"):
                    st.session_state.pb_idx = pb_idx + 1
                    st.rerun()
        import pandas as pd
        with st.expander("전체 표로 보기 (엑셀로 복사 가능)"):
            st.dataframe(pd.DataFrame(st.session_state.problem_bank))
    else:
        st.info("아직 저장된 문제은행이 없습니다.")
    if st.button("🔄 새로운 시험 시작", type="primary"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# ---- 오른쪽 아래 챗봇 ----
try:
    from streamlit_extras.stylable_container import stylable_container
    with stylable_container(
        key="fixed-chatbot",
        css_styles="",
    ):
        st.markdown("#### 🗨️ AI에게 자유 질문")
        free_q = st.text_input("궁금한 점을 입력하세요", key="free_q")
        if st.button("질문하기", key="free_q_btn"):
            if free_q:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": free_q}],
                    temperature=0.5
                )
                answer = response.choices[0].message.content
                st.session_state.chat_history.append((free_q, answer))
                st.write(f"**Q:** {free_q}")
                st.write(f"**A:** {answer}")
        if st.session_state.chat_history:
            st.markdown("---")
            st.markdown("##### 최근 질문/답변")
            for q, a in st.session_state.chat_history[-3:][::-1]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {a}")
except Exception:
    # streamlit_extras 없으면 sidebar로 fallback
    with st.sidebar:
        st.markdown("#### 🗨️ AI에게 자유 질문 (Fallback)")
        free_q = st.text_input("궁금한 점을 입력하세요", key="free_q_fallback")
        if st.button("질문하기", key="free_q_btn_fallback"):
            if free_q:
                response = client.chat.completions.create(
                    model="gpt-4o",
                    messages=[{"role": "user", "content": free_q}],
                    temperature=0.5
                )
                answer = response.choices[0].message.content
                st.session_state.chat_history.append((free_q, answer))
                st.write(f"**Q:** {free_q}")
                st.write(f"**A:** {answer}")
        if st.session_state.chat_history:
            st.markdown("---")
            st.markdown("##### 최근 질문/답변")
            for q, a in st.session_state.chat_history[-3:][::-1]:
                st.markdown(f"**Q:** {q}")
                st.markdown(f"**A:** {a}")
