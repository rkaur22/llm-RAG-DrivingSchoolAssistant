import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

RUN_TIMEZONE_CHECK = os.getenv('RUN_TIMEZONE_CHECK', '1') == '1'

TZ_INFO = os.getenv("TZ", "Europe/Berlin")
tz = ZoneInfo(TZ_INFO)


def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        database=os.getenv("POSTGRES_DB", "dschool_assistant"),
        user=os.getenv("POSTGRES_USER", "your_username"),
        password=os.getenv("POSTGRES_PASSWORD", "your_password"),
    )


def init_db():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS feedback")
            cur.execute("DROP TABLE IF EXISTS rag_queries")

            cur.execute("""
                CREATE TABLE rag_queries (
                    id TEXT PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    model_used TEXT NOT NULL,
                    response_time FLOAT NOT NULL,
                    relevance TEXT NOT NULL,
                    relevance_explanation TEXT NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
            cur.execute("""
                CREATE TABLE feedback (
                    id SERIAL PRIMARY KEY,
                    rag_query_id TEXT REFERENCES rag_queries(id),
                    feedback INTEGER NOT NULL,
                    timestamp TIMESTAMP WITH TIME ZONE NOT NULL
                )
            """)
        conn.commit()
    finally:
        conn.close()


def save_query(query_id, question, answer_data, timestamp=None):
    """
    Save a RAG query result to the database
    
    Args:
        query_id: Unique identifier for the query
        question: User's question
        answer_data: Dictionary containing answer, model_used, response_time, relevance, relevance_explanation
        timestamp: Optional timestamp (defaults to current time in configured timezone)
    """
    if timestamp is None:
        timestamp = datetime.now(tz)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO rag_queries 
                (id, question, answer, model_used, response_time, relevance, 
                relevance_explanation, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    query_id,
                    question,
                    answer_data["answer"],
                    answer_data["model_used"],
                    answer_data["response_time"],
                    answer_data["relevance"],
                    answer_data["relevance_explanation"],
                    timestamp
                ),
            )
        conn.commit()
    finally:
        conn.close()


def save_feedback(query_id, feedback, timestamp=None):
    """
    Save user feedback for a specific query
    
    Args:
        query_id: Reference to the rag_queries table
        feedback: Feedback value (typically 1 for thumbs up, -1 for thumbs down)
        timestamp: Optional timestamp (defaults to current time in configured timezone)
    """
    if timestamp is None:
        timestamp = datetime.now(tz)

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO feedback (rag_query_id, feedback, timestamp) VALUES (%s, %s, %s)",
                (query_id, feedback, timestamp),
            )
        conn.commit()
    finally:
        conn.close()


def get_recent_queries(limit=5, relevance=None):
    """
    Retrieve recent RAG queries with optional filtering by relevance
    
    Args:
        limit: Maximum number of queries to return
        relevance: Optional filter (e.g., "RELEVANT", "PARTLY_RELEVANT", "NON_RELEVANT")
    
    Returns:
        List of query dictionaries with feedback joined
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            query = """
                SELECT rq.*, f.feedback
                FROM rag_queries rq
                LEFT JOIN feedback f ON rq.id = f.rag_query_id
            """
            if relevance:
                query += f" WHERE rq.relevance = %s"
                cur.execute(query + " ORDER BY rq.timestamp DESC LIMIT %s", (relevance, limit))
            else:
                cur.execute(query + " ORDER BY rq.timestamp DESC LIMIT %s", (limit,))
            
            return cur.fetchall()
    finally:
        conn.close()


def get_feedback_stats():
    """
    Get aggregated feedback statistics
    
    Returns:
        Dictionary with thumbs_up and thumbs_down counts
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT 
                    SUM(CASE WHEN feedback > 0 THEN 1 ELSE 0 END) as thumbs_up,
                    SUM(CASE WHEN feedback < 0 THEN 1 ELSE 0 END) as thumbs_down
                FROM feedback
            """)
            return cur.fetchone()
    finally:
        conn.close()


def get_query_by_relevance_stats():
    """
    Get statistics on query distribution by relevance level
    
    Returns:
        Dictionary with counts for each relevance level
    """
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            cur.execute("""
                SELECT 
                    relevance,
                    COUNT(*) as count
                FROM rag_queries
                GROUP BY relevance
                ORDER BY count DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()


def check_timezone():
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SHOW timezone;")
            db_timezone = cur.fetchone()[0]
            print(f"Database timezone: {db_timezone}")

            cur.execute("SELECT current_timestamp;")
            db_time_utc = cur.fetchone()[0]
            print(f"Database current time (UTC): {db_time_utc}")

            db_time_local = db_time_utc.astimezone(tz)
            print(f"Database current time ({TZ_INFO}): {db_time_local}")

            py_time = datetime.now(tz)
            print(f"Python current time: {py_time}")

            cur.execute("""
                INSERT INTO rag_queries 
                (id, question, answer, model_used, response_time, relevance, 
                relevance_explanation, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING timestamp;
            """, 
            ('test', 'test question', 'test answer', 'test model', 0.0, 
             'RELEVANT', 'test explanation', py_time))

            inserted_time = cur.fetchone()[0]
            print(f"Inserted time (UTC): {inserted_time}")
            print(f"Inserted time ({TZ_INFO}): {inserted_time.astimezone(tz)}")

            cur.execute("SELECT timestamp FROM rag_queries WHERE id = 'test';")
            selected_time = cur.fetchone()[0]
            print(f"Selected time (UTC): {selected_time}")
            print(f"Selected time ({TZ_INFO}): {selected_time.astimezone(tz)}")

            cur.execute("DELETE FROM rag_queries WHERE id = 'test';")
            conn.commit()
    except Exception as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if RUN_TIMEZONE_CHECK:
    check_timezone()