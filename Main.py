import re
import sqlite3
import sys
from datetime import datetime
from tkinter import scrolledtext, ttk, messagebox
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
MAX_CONVERSATION_TURNS = 5
MAX_MEMORY_FACTS = 5


def get_time_based_greeting():
    hour = datetime.now().hour

    if 5 <= hour < 12:
        return "Good morning, Boss."
    if 12 <= hour < 17:
        return "Good afternoon, Boss."
    if 17 <= hour < 21:
        return "Good evening, Boss."
    return "Hello, Boss."


def get_night_session_closing_message():
    hour = datetime.now().hour
    if 21 <= hour or hour < 5:
        return "Good night, Boss."
    return "Goodbye, Boss."


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
            ],
            options={"num_ctx": 1024, "num_predict": 80}
        )
        conversation_summary = summary_response["message"]["content"].strip()
    except Exception:
        conversation_summary = history_text[:300].strip()


def get_recent_memory_facts(limit=MAX_MEMORY_FACTS):
    cursor.execute(
        "SELECT fact FROM memories ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    rows = cursor.fetchall()
    return [row[0] for row in reversed(rows)]


def get_memory_context_for_prompt(limit=MAX_MEMORY_FACTS):
    facts = get_recent_memory_facts(limit)
    if not facts:
        return "No memories stored yet, Boss."
    return "\n".join(facts)


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
    if lowered.startswith("my name is "):
        return f"Your name is {text[11:]}."
    if lowered.startswith("my age is "):
        age = text[9:]
        return f"You are {age} years old."
    if lowered.startswith("my favorite "):
        return f"Your favorite {text[12:]}."
    if lowered.startswith("my "):
        return f"Your {text[3:]}."
    if lowered.startswith("you are "):
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if lowered.startswith("your "):
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if lowered.startswith("i like "):
        return f"You like {text[7:]}."
    if lowered.startswith("i love "):
        return f"You love {text[7:]}."
    if lowered.startswith("i prefer "):
        return f"You prefer {text[9:]}."
    if lowered.startswith("i work as "):
        return f"You work as {text[10:]}."
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def recall_memories_for_display():
    cursor.execute("SELECT fact FROM memories")
    rows = cursor.fetchall()

    if not rows:
        return "No memories stored yet, Boss."

    formatted = [format_memory_fact(row[0]) for row in rows]
    formatted = [item for item in formatted if item]

    if not formatted:
        return "No memories stored yet, Boss."

    if len(formatted) == 1:
        sentence = formatted[0]
        if sentence.lower().startswith("you are "):
            return f"I remember that {sentence.lower()}"
        if sentence.lower().startswith("your "):
            return f"I remember that {sentence.lower()}"
        return f"I remember that {sentence}"

    combined = " ".join(formatted)
    return f"I remember that {combined.lower()}"


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


def is_exit_request(text):
    cleaned = normalize_input(text)
    exit_phrases = [
        r"\bbye\b",
        r"\bgoodbye\b",
        r"\bsee you\b",
        r"\bshutdown\b",
        r"\bturn off\b",
        r"\bclose up\b",
        r"\bquit\b",
        r"\bexit\b",
        r"\bend session\b",
        r"\bthat's all\b",
        r"\bthat's it\b",
        r"\bgo to sleep\b",
        r"\bwe are done\b",
        r"\bcatch you later\b",
        r"\buntil next time\b"
    ]
    return any(re.search(pattern, cleaned) for pattern in exit_phrases)


def generate_assistant_reply(user_input):
    memory_text = get_memory_context_for_prompt()
    messages = build_chat_messages(user_input, memory_text)

    response = chat(
        model="qwen2.5:3b",
        messages=messages,
        options={"num_ctx": 1024, "num_predict": 120}
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

    if lower_input == "exit" or is_exit_request(user_input):
        conn.close()
        return get_night_session_closing_message()

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
    print(get_time_based_greeting())
    print("Type 'bye' or 'exit' to end the session.\n")

    while True:
        user_input = input("You: ")
        response = handle_user_input(user_input)

        print("\nDoll:")
        print(response)
        print()

        if user_input.lower() == "exit" or is_exit_request(user_input):
            break


# -----------------------
# GUI Interface (v0.6)
# -----------------------

class DollGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Doll v0.6")
        self.root.geometry("980x700")
        self.root.minsize(760, 540)
        self.root.configure(bg="#f3f5f9")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TFrame", background="#f3f5f9")
            style.configure("TEntry", padding=8, fieldbackground="#ffffff")
            style.configure("TButton", padding=(12, 8), font=("Segoe UI", 10, "bold"))
        except Exception:
            pass

        header = ttk.Frame(root, padding=(16, 16, 16, 8))
        header.pack(fill=tk.X)

        self.title_label = tk.Label(
            header,
            text="Doll",
            font=("Segoe UI", 20, "bold"),
            fg="#1f2a44",
            bg="#f3f5f9",
            anchor="w"
        )
        self.title_label.pack(fill=tk.X)

        self.status_label = tk.Label(
            header,
            text=get_time_based_greeting(),
            font=("Segoe UI", 10),
            fg="#475569",
            bg="#f3f5f9",
            anchor="w"
        )
        self.status_label.pack(fill=tk.X, pady=(4, 0))

        self.chat_area = scrolledtext.ScrolledText(
            root,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            padx=12,
            pady=12,
            state="disabled",
            bg="#ffffff",
            fg="#1e293b",
            insertbackground="#1e293b",
            relief="flat"
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 10))

        actions_frame = ttk.Frame(root)
        actions_frame.pack(fill=tk.X, padx=16, pady=(0, 10))

        self.clear_chat_button = ttk.Button(actions_frame, text="Clear Chat")
        self.clear_chat_button.pack(side=tk.LEFT, padx=(0, 8))

        self.show_memories_button = ttk.Button(actions_frame, text="Show Memories")
        self.show_memories_button.pack(side=tk.LEFT, padx=(0, 8))

        self.clear_memories_button = ttk.Button(actions_frame, text="Clear Memories")
        self.clear_memories_button.pack(side=tk.LEFT, padx=(0, 8))

        self.summary_button = ttk.Button(actions_frame, text="Show Summary")
        self.summary_button.pack(side=tk.LEFT)

        input_frame = ttk.Frame(root, padding=(16, 0, 16, 16))
        input_frame.pack(fill=tk.X)

        self.input_box = ttk.Entry(input_frame)
        self.input_box.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_box.focus_set()

        self.send_button = ttk.Button(input_frame, text="Send")
        self.send_button.pack(side=tk.RIGHT, padx=(8, 0))

        self.input_box.bind("<Return>", self.on_send)
        self.send_button.configure(command=self.on_send)
        self.clear_chat_button.configure(command=self.on_clear_chat)
        self.show_memories_button.configure(command=self.on_show_memories)
        self.clear_memories_button.configure(command=self.on_clear_memories)
        self.summary_button.configure(command=self.on_show_summary)

        self.append_text(f"Doll is online.\n{get_time_based_greeting()}\nType 'bye' or 'exit' to end the session.\n")

    def set_status(self, text):
        self.status_label.configure(text=text)

    def append_text(self, text):
        self.chat_area.configure(state="normal")
        self.chat_area.insert(tk.END, text)
        self.chat_area.configure(state="disabled")
        self.chat_area.see(tk.END)

    def on_close(self):
        if messagebox.askyesno("Exit Doll", "Do you want to end the session?"):
            self.root.destroy()

    def on_clear_chat(self):
        global conversation_summary
        conversation_history.clear()
        conversation_summary = ""
        self.append_text("\nDoll: The conversation history has been cleared, Boss.\n\n")
        self.set_status("Chat cleared")

    def on_show_memories(self):
        self.append_text(f"\nDoll: {recall_memories_for_display()}\n\n")
        self.set_status("Displaying memories")

    def on_clear_memories(self):
        clear_memories()
        self.append_text("\nDoll: All memories have been cleared, Boss.\n\n")
        self.set_status("Memories cleared")

    def on_show_summary(self):
        if conversation_summary:
            self.append_text(f"\nDoll: {conversation_summary}\n\n")
        else:
            self.append_text("\nDoll: There is no active conversation summary yet, Boss.\n\n")
        self.set_status("Summary shown")

    def on_send(self, event=None):
        user_input = self.input_box.get().strip()
        self.input_box.delete(0, tk.END)

        if not user_input:
            return

        self.append_text(f"You: {user_input}\n")
        self.set_status("Thinking...")
        self.root.update_idletasks()

        response = handle_user_input(user_input)
        self.append_text(f"Doll: {response}\n\n")
        self.set_status(get_time_based_greeting())

        if user_input.lower() == "exit" or is_exit_request(user_input):
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
