Doll Project Context

Project Identity

Assistant Name: Doll

Owner: Jessel

Preferred User Address: Boss

Project Type: Private personal AI assistant

Long-Term Vision
Doll is intended to become a fully local AI assistant that can:

Hold natural conversations
Remember information
Understand voice input
Speak responses
Control applications
Research information
Manage workflows
Assist with software development
The project prioritizes privacy and local execution over convenience.

Design Decisions
AI Choice
Qwen 2.5 3B was selected because:

Hardware limitations
Good performance for coding
Good reasoning quality
Runs locally through Ollama
Development machine:

CPU: Intel Core i5-1235U

RAM: 8 GB

GPU: Intel UHD Graphics

Because of limited hardware resources, smaller models are preferred.

Memory Architecture
Current memory layers:

Layer 1
Permanent Memory

Storage:

SQLite

File:

memory.db

Purpose:

Stores information that should survive program restarts.

Examples:

User preferences
Project information
Long-term facts
Command Strategy
Use Python when deterministic behavior is required.

Examples:

Time
Date
Application launching
File operations
Use AI when reasoning is required.

Examples:

Conversation
Explanations
Planning
Natural language understanding
Development History
Initial Prototype
Created local AI chat using:

Python
Ollama
Qwen
Purpose:

Verify local model operation.

Memory Integration
Added SQLite support.

Implemented:

remember
forget
show memories
Goal:

Create persistent assistant memory.

Memory Management Upgrade
Added:

Duplicate memory prevention
clear memories
Goal:

Improve database maintenance.

Date And Time Integration
Implemented Python-based date and time retrieval.

Reason:

AI models cannot reliably determine current system time.

Typo Handling
Experimented with:

Exact phrase matching
Fuzzy sentence matching
Keyword matching
Fuzzy keyword matching
Current preferred approach:

Fuzzy keyword detection.

Personal Notes
The owner prefers:

Simple solutions
Practical implementations
Local execution
Incremental development
The owner is learning by building.

The project should prioritize maintainability over complexity.

Avoid overengineering.

Future Architecture
Target architecture:

User 
  ↓ 
Speech-to-Text 
  ↓ 
Intent Detection 
  ↓ 
Command Router 
  ↓ 
├── Memory System 
├── Application Control 
├── Web Research 
├── File Management 
└── AI Reasoning 
  ↓ 
Response Generation 
  ↓ 
Text-to-Speech

Planned Milestones
v0.4
Conversation Memory

Store recent message history during the current session.

v0.5
GUI Application

Replace command-line interaction with a dedicated interface.

v0.6
Voice Input

Integrate local speech recognition.

Preferred approach:

Faster-Whisper

v0.7
Voice Output

Integrate local text-to-speech.

Preferred approach:

Piper

v0.8
Application Control

Launch and manage Windows applications.

Examples:

Unity
Browser
Notepad
Calculator
v0.9
Web Research

Allow web lookups while keeping personal data local.

v1.0
Unified Personal Assistant

Features:

Memory
Voice
Local AI
App Control
Research
Conversation Context
Personalization

Always address Jessel as: Boss
