import re
import sqlite3
import sys
from datetime import datetime, timedelta
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


def format_memory_fact(fact):
    text = (fact or "").strip()
    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    lowered = text.lower()

    # Always preserve already-normalized memory facts.
    if lowered.startswith("you are "):
        return text if text.endswith((".", "!", "?")) else f"{text}."
    if lowered.startswith("your "):
        return text if text.endswith((".", "!", "?")) else f"{text}."

    patterns = [
        ("i am ", "You are {}."),
        ("i'm ", "You are {}."),
        ("im ", "You are {}."),
        ("my name is ", "Your name is {}."),
        ("my age is ", "You are {} years old."),
        ("my gender is ", "You are {}."),
        ("my favorite ", "Your favorite {}."),
        ("my ", "Your {}."),
        ("i like ", "You like {}."),
        ("i love ", "You love {}."),
        ("i prefer ", "You prefer {}."),
        ("i work as ", "You work as {}."),
        ("i work at ", "You work at {}."),
        ("i started working on you on ", "You started working on me on {}."),
        ("i started working on me on ", "You started working on me on {}."),
        ("i started working on doll on ", "You started working on me on {}."),
        ("i started building you on ", "You started building me on {}."),
        ("i started building me on ", "You started building me on {}."),
        ("i started working on ", "You started working on {}."),
        ("i started building ", "You started building {}."),
        ("i will turn ", "You will turn {}."),
    ]

    for prefix, template in patterns:
        if lowered.startswith(prefix):
            value = text[len(prefix):]
            sentence = template.format(value)
            if sentence and not sentence.endswith((".", "!", "?")):
                sentence += "."
            return sentence

    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def get_memory_rows():
    cursor.execute("SELECT id, fact FROM memories ORDER BY id")
    return cursor.fetchall()


def remember(fact):
    fact = (fact or "").strip()
    if not fact:
        return False

    normalized = format_memory_fact(fact).strip()

    cursor.execute(
        "SELECT fact FROM memories WHERE fact = ?",
        (normalized,)
    )

    if cursor.fetchone():
        return False

    cursor.execute(
        "INSERT INTO memories (fact) VALUES (?)",
        (normalized,)
    )

    conn.commit()
    return True


def forget(fact):
    fact = (fact or "").strip()
    if not fact:
        return False

    # Delete by numeric memory index shown in show memories
    if re.fullmatch(r"\d+", fact):
        rows = get_memory_rows()
        index = int(fact)
        if 1 <= index <= len(rows):
            row_id = rows[index - 1][0]
            cursor.execute("DELETE FROM memories WHERE id = ?", (row_id,))
            conn.commit()
            return True
        return False

    # Delete by exact or partial memory match
    match_text = format_memory_fact(fact).strip().lower()
    rows = get_memory_rows()

    for row_id, stored_fact in rows:
        normalized_stored = re.sub(r"\s+", " ", stored_fact.strip())
        stored_lower = normalized_stored.lower()
        if (
            stored_lower == match_text
            or match_text in stored_lower
            or stored_lower in match_text
        ):
            cursor.execute("DELETE FROM memories WHERE id = ?", (row_id,))
            conn.commit()
            return True

    return False


def clear_memories():
    cursor.execute("DELETE FROM memories")
    conn.commit()


def recall_memories():
    rows = get_memory_rows()
    if not rows:
        return "No memories stored yet, Boss."
    return "\n".join(row[1] for row in rows)


def recall_memories_for_display():
    rows = get_memory_rows()
    if not rows:
        return "No memories stored yet, Boss."

    lines = []
    for index, (_, fact) in enumerate(rows, start=1):
        cleaned = format_memory_fact(fact)
        if cleaned and cleaned.strip():
            lines.append(f"{index}. {cleaned.strip()}")

    if not lines:
        return "No memories stored yet, Boss."

    return "\n".join(lines)


def normalize_input(text):
    if text is None:
        return ""

    text = text.lower().strip()
    text = text.replace("yopu", "you")
    text = text.replace("youp", "you")
    text = text.replace("yuo", "you")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def parse_date_string(date_text):
    date_text = (date_text or "").strip()
    if not date_text:
        return None

    cleaned = re.sub(r"\s+", " ", date_text)
    cleaned = cleaned.strip(". ,")

    for fmt in (
        "%Y-%m-%d",
        "%d %B %Y",
        "%d %b %Y",
        "%B %d %Y",
        "%b %d %Y",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%m/%d/%Y",
        "%m-%d-%Y",
    ):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass

    return None


def extract_date_from_text(text):
    if not text:
        return None

    patterns = [
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b",
        r"\b\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\b",
        r"\b[A-Za-z]+\s+\d{1,2},?\s+\d{4}\b",
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed = parse_date_string(match.group(0))
            if parsed:
                return parsed
    return None


def find_date_in_memories(keywords):
    rows = get_memory_rows()
    for _, fact in rows:
        fact_lower = fact.lower()
        if any(keyword in fact_lower for keyword in keywords):
            parsed = extract_date_from_text(fact_lower)
            if parsed:
                return parsed
    return None


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
        r"\bwhat\s+time\b",
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
        r"\bwhat\s+date\b",
    ]

    return any(re.search(pattern, text) for pattern in patterns)


def is_elapsed_days_request(text):
    cleaned = normalize_input(text)
    patterns = [
        r"\bhow\s+many\s+days\b",
        r"\bhow\s+long\s+(?:has|have)\s+(?:it|i|we|you)\s+been\b",
        r"\bhow\s+long\s+since\b",
        r"\bdays\s+since\b",
        r"\bstarted\s+working\s+on\s+(?:you|me|doll)\b",
        r"\bworking\s+on\s+(?:you|me|doll)\b",
        r"\b(?:since|from)\s+\d{1,2}\s+[a-z]+\s+\d{4}\b",
    ]
    return any(re.search(pattern, cleaned) for pattern in patterns)


def is_relative_date_request(text):
    cleaned = normalize_input(text)
    patterns = [
        r"\b\d+\s+days?\s+(?:ago|before)\b",
        r"\b\d+\s+days?\s+(?:from\s+now|hence|later)\b",
        r"\bwhat\s+date\s+(?:was|is)\s+\d+\s+days?\s+(?:ago|before)\b",
        r"\bwhat\s+date\s+is\s+\d+\s+days?\s+from\s+now\b",
        r"\bin\s+\d+\s+days?\b",
    ]
    return any(re.search(pattern, cleaned) for pattern in patterns)


def get_elapsed_days_answer(text):
    cleaned = normalize_input(text)

    explicit_date = extract_date_from_text(cleaned)
    if not explicit_date:
        for keywords in (
            ["started working on you", "started working on me", "started building you"],
            ["started working on doll", "started building me"],
        ):
            found = find_date_in_memories(keywords)
            if found:
                explicit_date = found
                break

    if not explicit_date:
        return None

    delta_days = (datetime.now().date() - explicit_date).days
    if delta_days < 0:
        return f"That date is in the future, Boss."

    return f"It has been {delta_days} days since {explicit_date.strftime('%d %B %Y')}, Boss."


def get_relative_date_answer(text):
    cleaned = normalize_input(text)
    today = datetime.now().date()

    match = re.search(r"(\d+)\s+days?\s+(?:ago|before)", cleaned)
    if match:
        days = int(match.group(1))
        target = today - timedelta(days=days)
        return f"{days} days ago was {target.strftime('%d %B %Y')}, Boss."

    match = re.search(r"(\d+)\s+days?\s+(?:from\s+now|hence|later)", cleaned)
    if match:
        days = int(match.group(1))
        target = today + timedelta(days=days)
        return f"In {days} days, the date will be {target.strftime('%d %B %Y')}, Boss."

    match = re.search(r"in\s+(\d+)\s+days?", cleaned)
    if match:
        days = int(match.group(1))
        target = today + timedelta(days=days)
        return f"In {days} days, the date will be {target.strftime('%d %B %Y')}, Boss."

    match = re.search(r"what\s+date\s+(?:was|is)\s+(\d+)\s+days?\s+(?:ago|before)", cleaned)
    if match:
        days = int(match.group(1))
        target = today - timedelta(days=days)
        return f"{days} days ago was {target.strftime('%d %B %Y')}, Boss."

    match = re.search(r"what\s+date\s+is\s+(\d+)\s+days?\s+from\s+now", cleaned)
    if match:
        days = int(match.group(1))
        target = today + timedelta(days=days)
        return f"In {days} days, the date will be {target.strftime('%d %B %Y')}, Boss."

    return None


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
        r"\buntil next time\b",
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

    if lower_input in ("show memories", "show memory", "show my memories"):
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

    if is_elapsed_days_request(user_input):
        exact_answer = get_elapsed_days_answer(user_input)
        if exact_answer:
            return exact_answer

    if is_relative_date_request(user_input):
        exact_answer = get_relative_date_answer(user_input)
        if exact_answer:
            return exact_answer

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
        self.root.configure(bg="#0f172a")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        try:
            style = ttk.Style()
            style.theme_use("clam")
            style.configure("TFrame", background="#0f172a")
            style.configure("TEntry", fieldbackground="#1f2937", foreground="#f8fafc", padding=8)
            style.configure("TButton", background="#2563eb", foreground="#ffffff", padding=(12, 8), font=("Segoe UI", 10, "bold"))
            style.map(
                "TButton",
                background=[("active", "#3b82f6"), ("pressed", "#1d4ed8")],
                foreground=[("disabled", "#cbd5e1")]
            )
        except Exception:
            pass

        header = ttk.Frame(root, padding=(16, 16, 16, 8))
        header.pack(fill=tk.X)

        self.title_label = tk.Label(
            header,
            text="Doll",
            font=("Segoe UI", 20, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
            anchor="w"
        )
        self.title_label.pack(fill=tk.X)

        self.status_label = tk.Label(
            header,
            text=get_time_based_greeting(),
            font=("Segoe UI", 10),
            fg="#cbd5e1",
            bg="#0f172a",
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
            bg="#111827",
            fg="#f8fafc",
            insertbackground="#f8fafc",
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
        message = recall_memories_for_display()
        self.append_text(f"\nDoll: {message}\n\n")
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
            self.on_close()


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
