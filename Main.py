from ollama import chat
import sqlite3
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
MAX_CONVERSATION_TURNS = 12


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

    text = text.lower()

    keywords = [
        "time",
        "clock"
    ]

    words = text.split()

    for word in words:

        for keyword in keywords:

            similarity = SequenceMatcher(
                None,
                word,
                keyword
            ).ratio()

            if similarity >= 0.8:
                return True

    return False


def is_date_request(text):

    text = text.lower()

    keywords = [
        "date",
        "today"
    ]

    words = text.split()

    for word in words:

        for keyword in keywords:

            similarity = SequenceMatcher(
                None,
                word,
                keyword
            ).ratio()

            if similarity >= 0.8:
                return True

    return False


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

        print("\nDoll:")
        print("The conversation history has been cleared, Boss.\n")

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

    print("\nDoll:")
    print(assistant_reply)
    print()
