from ollama import chat
import sqlite3
import re
from datetime import datetime
from difflib import SequenceMatcher

# -----------------------
# Database Setup
# -----------------------

conn = sqlite3.connect("memory.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact TEXT NOT NULL
)
""")

conn.commit()

# -----------------------
# Conversation Memory
# -----------------------

conversation_history = []
conversation_summary = ""
MAX_CONVERSATION_TURNS = 12


def update_conversation_summary():
    global conversation_summary

    if len(conversation_history) < 2:
        conversation_summary = ""
        return

    recent_history = conversation_history[-MAX_CONVERSATION_TURNS:]
    history_text = "\n".join(
        f"{entry['role']}: {entry['content']}" for entry in recent_history
    )

    try:
        summary_response = chat(
            model="qwen2.5:3b",
            messages=[
                {
                    "role": "system",
                    "content": "You create a brief memory summary for a personal assistant. Keep only important facts, preferences, and recent topics. Output 1 to 3 short sentences."
                },
                {
                    "role": "user",
                    "content": f"Summarize this conversation concisely:\n{history_text}"
                }
            ]
        )
        conversation_summary = summary_response["message"]["content"].strip()
    except Exception:
        conversation_summary = history_text[:300].strip()


def build_chat_messages(user_input, memory_text):
    messages = [
        {
            "role": "system",
            "content": f"""
Your name is Doll.

You are the personal AI assistant of Jessel.

Always address the user as Boss.

These are permanent memories about your owner Jessel.

You must use these memories when answering questions about Jessel.

If the answer exists in memory, prioritize memory over assumptions.

{f'CONVERSATION SUMMARY:\n{conversation_summary}\n' if conversation_summary else ''}

MEMORIES:
{memory_text}
"""
        }
    ]

    recent_history = conversation_history[-MAX_CONVERSATION_TURNS:]
    messages.extend(recent_history)
    messages.append({"role": "user", "content": user_input})

    return messages


# -----------------------
# Functions
# -----------------------

def remember(fact):

    cursor.execute(
        "SELECT fact FROM memories WHERE fact = ?",
        (fact,)
    )

    if cursor.fetchone():
        return False

    cursor.execute(
        "INSERT INTO memories (fact) VALUES (?)",
        (fact,)
    )

    conn.commit()

    return True


def forget(fact):

    cursor.execute(
        "DELETE FROM memories WHERE fact = ?",
        (fact,)
    )

    conn.commit()

    return cursor.rowcount > 0


def clear_memories():

    cursor.execute("DELETE FROM memories")

    conn.commit()


def recall_memories():

    cursor.execute("SELECT fact FROM memories")

    rows = cursor.fetchall()

    if not rows:
        return "No memories stored yet, Boss."

    return "\n".join([row[0] for row in rows])


def is_time_request(text):

    text = text.lower().strip()

    if not text:
        return False

    patterns = [
        r"\b(what|what's|whats)\s+(the\s+)?time\b",
        r"\b(what\s+time|what's\s+the\s+time|what\s+is\s+the\s+time|tell\s+me\s+the\s+time)\b",
        r"\b(time)\s+(is|is it|now|right now)\b",
        r"\bcurrent\s+time\b",
        r"\bwhat\s+time\b"
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def is_date_request(text):

    text = text.lower().strip()

    if not text:
        return False

    patterns = [
        r"\b(what|what's|whats)\s+(the\s+)?date\b",
        r"\b(what\s+date|what's\s+the\s+date|what\s+is\s+the\s+date|tell\s+me\s+the\s+date)\b",
        r"\b(date)\s+(is|is it|today|now)\b",
        r"\bcurrent\s+date\b",
        r"\b(today|todays|today's)\s+(date|day)\b",
        r"\bwhat\s+date\b"
    ]

    return any(re.search(pattern, text) for pattern in patterns)


# -----------------------
# Doll Startup
# -----------------------

print("Doll is online.")
print("Hello, Boss.")
print("Type 'exit' to shut down.\n")


# -----------------------
# Main Loop
# -----------------------

while True:

    user_input = input("You: ")

    # Exit

    if user_input.lower() == "exit":

        conn.close()

        print("Goodbye, Boss.")

        break

    # Clear Conversation History

    if user_input.lower() == "clear chat":

        conversation_history.clear()
        conversation_summary = ""

        print("\nDoll:")
        print("The conversation history has been cleared, Boss.\n")

        continue

    if user_input.lower() in ("show chat summary", "summarize chat"):

        print("\nDoll:")
        if conversation_summary:
            print(f"{conversation_summary}\n")
        else:
            print("There is no active conversation summary yet, Boss.\n")

        continue

    # Remember

    if user_input.lower().startswith("remember "):

        fact = user_input[9:]

        saved = remember(fact)

        print("\nDoll:")

        if saved:
            print("I will remember that, Boss.\n")
        else:
            print("I already know that, Boss.\n")

        continue

    # Forget

    if user_input.lower().startswith("forget "):

        fact = user_input[7:]

        deleted = forget(fact)

        print("\nDoll:")

        if deleted:
            print("I have forgotten that memory, Boss.\n")
        else:
            print("I couldn't find that memory, Boss.\n")

        continue

    # Show Memories

    if user_input.lower() == "show memories":

        print("\nDoll:")
        print(recall_memories())
        print()

        continue

    # Clear Memories

    if user_input.lower() == "clear memories":

        clear_memories()

        print("\nDoll:")
        print("All memories have been cleared, Boss.\n")

        continue

    # Current Time

    if is_time_request(user_input):

        current_time = datetime.now().strftime("%I:%M:%S %p")

        print("\nDoll:")
        print(f"The current time is {current_time}, Boss.\n")

        continue

    # Current Date

    if is_date_request(user_input):

        current_date = datetime.now().strftime("%d %B %Y")

        print("\nDoll:")
        print(f"Today's date is {current_date}, Boss.\n")

        continue

    # Load Memories

    memory_text = recall_memories()

    # Send To Model

    messages = build_chat_messages(user_input, memory_text)

    response = chat(
        model="qwen2.5:3b",
        messages=messages
    )

    assistant_reply = response["message"]["content"]

    conversation_history.append({"role": "user", "content": user_input})
    conversation_history.append({"role": "assistant", "content": assistant_reply})
    update_conversation_summary()

    print("\nDoll:")
    print(assistant_reply)
    print()
