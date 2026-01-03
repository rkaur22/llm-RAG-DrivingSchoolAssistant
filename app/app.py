import streamlit as st
from dotenv import load_dotenv
import uuid
import db
import ingest
from rag import rag_with_evaluation

# Load environment variables
load_dotenv()

# Initialize database on first run
if "db_initialized" not in st.session_state:
    db.init_db()
    st.session_state.db_initialized = True

# Page configuration
st.set_page_config(page_title="Q&A Assistant", layout="wide")
st.title("📚 Fahrschule Galaxy Q&A Assistant")

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []

if "collection" not in st.session_state:
    with st.spinner("Loading FAQ database..."):
        st.session_state.collection = ingest.load_index()

# Sidebar for settings
st.sidebar.header("Settings")
model = st.sidebar.selectbox(
    "Select a model:",
    options=["gemini-2.5-flash", "gemini-1.5-pro"],
    key="model_select"
)

# Display conversation history
st.subheader("Conversation")

for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        if msg["role"] == "assistant" and "metrics" in msg:
            with st.expander("📊 Response Metrics"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Response Time", f"{msg['metrics']['response_time']:.2f}s")
                col2.metric("Relevance", msg['metrics']['relevance'])
                col3.metric("Status", "Saved ✅")
                st.caption(msg['metrics']['relevance_explanation'])
            
            # Feedback buttons
            st.markdown("**Was this answer helpful?**")
            col_feedback1, col_feedback2, col_spacer = st.columns([1, 1, 3])
            
            with col_feedback1:
                if st.button("👍 Helpful", key=f"helpful_{idx}"):
                    if msg.get("query_id"):
                        db.save_feedback(msg["query_id"], 1)
                        st.session_state.messages[idx]["feedback"] = 1
                        st.success("Thank you! Feedback saved.")
                        st.rerun()
            
            with col_feedback2:
                if st.button("👎 Not Helpful", key=f"not_helpful_{idx}"):
                    if msg.get("query_id"):
                        db.save_feedback(msg["query_id"], -1)
                        st.session_state.messages[idx]["feedback"] = -1
                        st.error("Thank you for the feedback!")
                        st.rerun()
            
            # Show if feedback was already given
            if msg.get("feedback") == 1:
                st.info("👍 You found this helpful")
            elif msg.get("feedback") == -1:
                st.warning("👎 You marked this as not helpful")

# User input
user_input = st.chat_input("Ask a question about the driving school...")

if user_input:
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })
    
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            answer_data = rag_with_evaluation(
                query=user_input,
                collection=st.session_state.collection,
                model=model
            )
            
            # Generate unique query ID
            query_id = str(uuid.uuid4())
            
            # Save to database
            db.save_query(
                query_id=query_id,
                question=user_input,
                answer_data=answer_data
            )
            
            st.markdown(answer_data["answer"])
            
            # Display metrics
            with st.expander("📊 Response Metrics"):
                col1, col2, col3 = st.columns(3)
                col1.metric("Response Time", f"{answer_data['response_time']:.2f}s")
                col2.metric("Relevance", answer_data['relevance'])
                col3.metric("Status", "Saved ✅")
                st.caption(answer_data['relevance_explanation'])
            
            # Feedback buttons
            st.markdown("**Was this answer helpful?**")
            col_feedback1, col_feedback2, col_spacer = st.columns([1, 1, 3])
            
            with col_feedback1:
                if st.button("👍 Helpful", key=f"helpful_new"):
                    db.save_feedback(query_id, 1)
                    st.success("Thank you! Feedback saved.")
            
            with col_feedback2:
                if st.button("👎 Not Helpful", key=f"not_helpful_new"):
                    db.save_feedback(query_id, -1)
                    st.error("Thank you for the feedback!")
            
            # Add assistant message with query ID and metrics
            st.session_state.messages.append({
                "role": "assistant",
                "content": answer_data["answer"],
                "metrics": answer_data,
                "query_id": query_id,
                "feedback": None
            })

# Reset conversation button
if st.sidebar.button("🔄 New Conversation"):
    st.session_state.messages = []
    st.rerun()

# Display stats in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Statistics")
total_conversations = len([m for m in st.session_state.messages if m["role"] == "assistant"])
st.sidebar.metric("Total Questions", total_conversations)

# Show recent feedback stats
try:
    stats = db.get_feedback_stats()
    if stats:
        st.sidebar.metric("👍 Helpful", stats.get('thumbs_up', 0) or 0)
        st.sidebar.metric("👎 Not Helpful", stats.get('thumbs_down', 0) or 0)
except Exception as e:
    st.sidebar.warning(f"Could not load stats: {str(e)}")