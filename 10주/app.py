import os
import pathlib
import streamlit as st

from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.vectorstores import FAISS
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories.streamlit import StreamlitChatMessageHistory

###############################################################
# OpenAI API Key 설정 (환경변수 사용 권장)
###############################################################
os.environ.setdefault("OPENAI_API_KEY", "YOUR_OPENAI_API_KEY")

###############################################################
# PDF 로드 & 벡터스토어 구축 (FAISS)
###############################################################

@st.cache_resource(show_spinner=False)
def load_and_split_pdf(file_path: str):
    """PDF 를 로드해 LangChain 문서 리스트로 반환합니다."""
    loader = PyPDFLoader(file_path)
    return loader.load_and_split()


@st.cache_resource(show_spinner=False)
def create_vector_store(_docs):
    """문서 리스트를 임베딩 후 FAISS 벡터스토어 생성, 로컬 저장"""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    split_docs = text_splitter.split_documents(_docs)

    persist_directory = pathlib.Path("./faiss_db")
    persist_directory.mkdir(parents=True, exist_ok=True)

    vectorstore = FAISS.from_documents(
        split_docs,
        OpenAIEmbeddings(model="text-embedding-3-small"),
    )
    # 디스크에 저장 (index.faiss & index.pkl)
    vectorstore.save_local(str(persist_directory))
    return vectorstore


@st.cache_resource(show_spinner=False)
def get_vectorstore(_docs):
    """이미 저장된 FAISS 인덱스가 있으면 불러오고, 없으면 새로 만듭니다."""
    persist_directory = pathlib.Path("./faiss_db")
    index_file = persist_directory / "index.faiss"

    if index_file.exists():
        try:
            return FAISS.load_local(
                str(persist_directory),
                OpenAIEmbeddings(model="text-embedding-3-small"),
            )
        except Exception:
            # 인덱스 로드 실패 시 새로 생성
            pass
    return create_vector_store(_docs)

###############################################################
# RAG 체인 초기화
###############################################################

@st.cache_resource(show_spinner=False)
def initialize_components(selected_model: str):
    file_path = r"../data/대한민국헌법(헌법)(제00010호)(19880225).pdf"
    pages = load_and_split_pdf(file_path)
    vectorstore = get_vectorstore(pages)
    retriever = vectorstore.as_retriever()

    # 채팅 히스토리 요약용 시스템 프롬프트
    contextualize_q_system_prompt = (
        """Given a chat history and the latest user question which might reference context in the chat history, "
        "formulate a standalone question which can be understood without the chat history. "
        "Do NOT answer the question, just reformulate it if needed and otherwise return it as is."""
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("history"),
            ("human", "{input}"),
        ]
    )

    # 질문‑답변 프롬프트
    qa_system_prompt = (
        """You are an assistant for question‑answering tasks. Use the following pieces of retrieved context to answer the "
        "question. If you don't know the answer, just say that you don't know. Keep the answer perfect. please use imogi "
        "with the answer. 대답은 한국어로 하고, 존댓말을 써줘.\n\n{context}"""
    )

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("history"),
            ("human", "{input}"),
        ]
    )

    llm = ChatOpenAI(model=selected_model)

    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)
    rag_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)
    return rag_chain

###############################################################
# Streamlit UI
###############################################################

st.header("헌법 Q&A 챗봇 💬 📚")
option = st.selectbox("Select GPT Model", ("gpt-4o-mini", "gpt-3.5-turbo-0125"))

rag_chain = initialize_components(option)
chat_history = StreamlitChatMessageHistory(key="chat_messages")

conversational_rag_chain = RunnableWithMessageHistory(
    rag_chain,
    lambda session_id: chat_history,
    input_messages_key="input",
    history_messages_key="history",
    output_messages_key="answer",
)

# 초기 메시지
if "messages" not in st.session_state:
    st.session_state["messages"] = [
        {
            "role": "assistant",
            "content": "헌법에 대해 무엇이든 물어보세요!",
        }
    ]

# 과거 메시지 출력
for msg in chat_history.messages:
    st.chat_message(msg.type).write(msg.content)

# 유저 인풋 받기
if prompt_message := st.chat_input("Your question"):
    st.chat_message("human").write(prompt_message)
    with st.chat_message("ai"):
        with st.spinner("Thinking..."):
            config = {"configurable": {"session_id": "any"}}
            response = conversational_rag_chain.invoke({"input": prompt_message}, config)

            answer = response["answer"]
            st.write(answer)
            with st.expander("참고 문서 확인"):
                for doc in response["context"]:
                    st.markdown(doc.metadata.get("source", ""), help=doc.page_content)
