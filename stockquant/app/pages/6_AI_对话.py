# -*- coding: utf-8 -*-
"""AI 对话页面"""

import json
import streamlit as st

from stockquant.ai import ChatAgent

st.set_page_config(page_title="AI 对话", layout="wide")
st.title("AI 助手")

if "chat_agent" not in st.session_state:
    st.session_state.chat_agent = ChatAgent()
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = "streamlit_" + str(hash(str(__import__("time").time())))

agent = st.session_state.chat_agent
cid = st.session_state.conversation_id

# 显示历史
if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 输入
if prompt := st.chat_input("输入你的问题..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = agent.chat(prompt, conversation_id=cid)
        message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "assistant", "content": full_response})

# 清空按钮
if st.button("清空对话"):
    agent.clear_conversation(cid)
    st.session_state.messages = []
    st.rerun()
