import tkinter as tk
from tkinter import messagebox

# List of quiz questions, options, and correct answers
questions = [
    {
        "question": "What is the capital of India?",
        "options": ["Mumbai", "Kolkata", "Delhi", "Chennai"],
        "answer": "Delhi"
    },
    {
        "question": "Who wrote the national anthem?",
        "options": ["Rabindranath Tagore", "Mahatma Gandhi", "Nehru", "Tilak"],
        "answer": "Rabindranath Tagore"
    },
    {
        "question": "Which planet is known as the Red Planet?",
        "options": ["Earth", "Mars", "Venus", "Jupiter"],
        "answer": "Mars"
    },
    {
        "question": "What is the currency of Japan?",
        "options": ["Won", "Yen", "Rupee", "Dollar"],
        "answer": "Yen"
    },
    {
        "question": "Who invented the light bulb?",
        "options": ["Newton", "Einstein", "Edison", "Tesla"],
        "answer": "Edison"
    }
]

# Track question index and score
current_question = 0
score = 0

# Function to load a new question
def load_question():
    if current_question < len(questions):
        q_data = questions[current_question]
        question_label.config(text=f"Q{current_question + 1}: {q_data['question']}")
        for i in range(4):
            option_buttons[i].config(text=q_data['options'][i])
    else:
        show_result()

# Function to check selected answer
def check_answer(index):
    global current_question, score
    selected = option_buttons[index]['text']
    correct = questions[current_question]['answer']
    if selected == correct:
        score += 1
    current_question += 1
    load_question()

# Function to show final result
def show_result():
    messagebox.showinfo("Quiz Completed", f"Your Score: {score} out of {len(questions)}")
    root.destroy()

# GUI Setup
root = tk.Tk()
root.title("Quiz Game")
root.geometry("500x400")
root.configure(bg="#f0f0f0")

# Title label
title_label = tk.Label(root, text="Welcome to the Quiz Game!", font=("Helvetica", 18, "bold"), bg="#f0f0f0")
title_label.pack(pady=20)

# Question label
question_label = tk.Label(root, text="", font=("Arial", 14), wraplength=450, bg="#f0f0f0")
question_label.pack(pady=20)

# Option buttons
option_buttons = []
for i in range(4):
    btn = tk.Button(root, text="", font=("Arial", 12), width=30, height=2, bg="#e0e0e0",
                    command=lambda i=i: check_answer(i))
    btn.pack(pady=5)
    option_buttons.append(btn)

# Start the quiz
load_question()

# Run the GUI loop
root.mainloop()
