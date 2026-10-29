import re
import sqlite3
import sys
from datetime import datetime
from tkinter import scrolledtext, ttk
import tkinter as tk

from ollama import chat

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
    fact = fact.strip()

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
    fact = fact.strip()

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


def format_memory_fact(fact):
    text = fact.strip()
    if not text:
        return ""

    lowered = text.lower()

    if lowered.startswith("i am "):
        return f"You are {text[5:]}."
    if lowered.startswith("im "):
        return f"You are {text[3:]}."
    if lowered.startswith("i'm "):
        return f"You are {text[4:]}."
    if lowered.startswith("my "):
        return f"Your {text[3:]}."
    if lowered.startswith("you are "):
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if lowered.startswith("your "):
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def recall_memories_for_display():
    cursor.execute("SELECT fact FROM memories")
    rows = cursor.fetchall()

    if not rows:
        return "No memories stored yet, Boss."

    formatted = [format_memory_fact(row[0]) for row in rows]
    return "Here are the memories I have stored, Boss:\n- " + "\n- ".join(formatted)


def normalize_input(text):
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s?']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def is_time_request(text):
    text = normalize_input(text)
    if not text:
        return False

    patterns = [
        r"\b(what|what's|whats|tell|show|give|is)\s+(me\s+)?(the\s+)?time\b",
        r"\bwhat\s+is\s+(the\s+)?time\b",
        r"\btime\??\b",
        r"\b(time)\s+(is|is it|now|right now)\b",
        r"\bcurrent\s+time\b",
        r"\bwhat\s+time\b"
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def is_date_request(text):
    text = normalize_input(text)
    if not text:
        return False

    patterns = [
        r"\b(what|what's|whats|tell|show|give|is)\s+(me\s+)?(the\s+)?date\b",
        r"\bwhat\s+is\s+(the\s+)?date\b",
        r"\bdate\??\b",
        r"\b(date)\s+(is|is it|today|now)\b",
        r"\bcurrent\s+date\b",
        r"\b(today|todays|today's)\s+(date|day)\b",
        r"\bwhat\s+date\b"
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def generate_assistant_reply(user_input):
    memory_text = recall_memories()
    messages = build_chat_messages(user_input, memory_text)

    response = chat(
        model="qwen2.5:3b",
        messages=messages
    )

    assistant_reply = response["message"]["content"]

    conversation_history.append({"role": "user", "content": user_input})
    conversation_history.append({"role": "assistant", "content": assistant_reply})
    update_conversation_summary()

    return assistant_reply


def handle_user_input(user_input):
    user_input = user_input.strip()

    if not user_input:
        return "Type something, Boss."

    lower_input = user_input.lower()

    if lower_input == "exit":
        conn.close()
        return "Goodbye, Boss."

    if lower_input == "clear chat":
        conversation_history.clear()
        conversation_summary = ""
        return "The conversation history has been cleared, Boss."

    if lower_input in ("show chat summary", "summarize chat"):
        if conversation_summary:
            return conversation_summary
        return "There is no active conversation summary yet, Boss."

    if lower_input.startswith("remember "):
        fact = user_input[9:]
        saved = remember(fact)
        if saved:
            return "I will remember that, Boss."
        return "I already know that, Boss."

    if lower_input.startswith("forget "):
        fact = user_input[7:]
        deleted = forget(fact)
        if deleted:
            return "I have forgotten that memory, Boss."
        return "I couldn't find that memory, Boss."

    if lower_input == "show memories":
        return recall_memories_for_display()

    if lower_input == "clear memories":
        clear_memories()
        return "All memories have been cleared, Boss."

    if is_time_request(user_input):
        current_time = datetime.now().strftime("%I:%M:%S %p")
        return f"The current time is {current_time}, Boss."

    if is_date_request(user_input):
        current_date = datetime.now().strftime("%d %B %Y")
        return f"Today's date is {current_date}, Boss."

    return generate_assistant_reply(user_input)


# -----------------------
# Console Interface
# -----------------------

def run_cli():
    print("Doll is online.")
    print("Hello, Boss.")
    print("Type 'exit' to shut down.\n")

    while True:
        user_input = input("You: ")
        response = handle_user_input(user_input)

        print("\nDoll:")
        print(response)
        print()

        if user_input.lower() == "exit":
            break


# -----------------------
# GUI Interface (v0.5)
# -----------------------

class DollGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Doll v0.5")
        self.root.geometry("900x650")
        self.root.minsize(700, 500)

        self.chat_area = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
            state="disabled"
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 8))

        input_frame = ttk.Frame(root)
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.input_box = ttk.Entry(input_frame)
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.focus_set()

        self.send_button = ttk.Button(input_frame, text="Send")
        self.send_button.pack(side=tk.RIGHT, padx=(8, 0))

        self.input_box.bind("<Return>", self.on_send)
        self.send_button.configure(command=self.on_send)

        self.append_text("Doll is online.\nHello, Boss.\nType 'exit' to shut down.\n")

    def append_text(self, text):
        self.chat_area.configure(state="normal")
        self.chat_area.insert(tk.END, text)
        self.chat_area.configure(state="disabled")
        self.chat_area.see(tk.END)

    def on_send(self, event=None):
        user_input = self.input_box.get().strip()
        self.input_box.delete(0, tk.END)

        if not user_input:
            return

        self.append_text(f"You: {user_input}\n")

        response = handle_user_input(user_input)
        self.append_text(f"Doll: {response}\n\n")

        if user_input.lower() == "exit":
            self.root.after(250, self.root.destroy)


def run_gui():
    root = tk.Tk()
    app = DollGUI(root)
    root.mainloop()


# -----------------------
# Entry Point
# -----------------------

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        run_cli()
    else:
        run_gui()
