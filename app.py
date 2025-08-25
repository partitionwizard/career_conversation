from src.llm import LLM
import gradio as gr

if __name__ == "__main__":
    LLM = LLM()
    gr.ChatInterface(LLM.chat, type="messages").launch()