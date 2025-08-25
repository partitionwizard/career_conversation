from openai import OpenAI
from dotenv import load_dotenv
from src.me import Me
from src.evaluation import Evaluation
import os, requests, json

class LLM:
    def __init__(self):
        load_dotenv(override=True)
        self.pushover_user = os.getenv("PUSHOVER_USER")
        self.pushover_token = os.getenv("PUSHOVER_KEY")
        self.pushover_url = "https://api.pushover.net/1/messages.json"
        self.me = Me()
        self.name = self.me.name
        self.about = self.me.about
        self.system_prompt = f"You are acting as {self.name}. You are answering questions on {self.name}'s website, \
        particularly questions related to {self.name}'s career, background, skills and experience. \
        Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. \
        You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. \
        Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
        If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. \
        If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "

        self.system_prompt += f"\n\n## Summary gathered from {self.name} LinkedIn and Resume:\n{self.about}\n\n"
        self.system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        
        self.evaluator_system_prompt = f"You are an evaluator that decides whether a response to a question is acceptable. \
        You are provided with a conversation between a User and an Agent. Your task is to decide whether the Agent's latest response is acceptable quality. \
        The Agent is playing the role of {self.name} and is representing {self.name} on their website. \
        The Agent has been instructed to be professional and engaging, as if talking to a potential client or future employer who came across the website. \
        The Agent has been provided with context on {self.name} in the form of their summary and LinkedIn details. Here's the information:"

        self.evaluator_system_prompt += f"\n\n## Summary gathered from {self.name} LinkedIn and Resume:\n{self.about}\n\n"
        self.evaluator_system_prompt += f"With this context, please evaluate the latest response, replying with whether the response is acceptable and your feedback."
        self.open_ai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.gemini_client = OpenAI(api_key=os.getenv('GOOGLE_API_KEY'), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
        self.record_user_details_json = {
            "name": "record_user_details",
            "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address of this user"
                    },
                    "name": {
                        "type": "string",
                        "description": "The user's name, if they provided it"
                    }
                    ,
                    "notes": {
                        "type": "string",
                        "description": "Any additional information about the conversation that's worth recording to give context"
                    }
                },
                "required": ["email"],
                "additionalProperties": False
            }
        }
        self.record_unknown_question_json = {
            "name": "record_unknown_question",
            "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question that couldn't be answered"
                    },
                },
                "required": ["question"],
                "additionalProperties": False
            }
        }
        self.tools = [
            {"type": "function", "function": self.record_user_details_json},
            {"type": "function", "function": self.record_unknown_question_json}
        ]

    
    def chat(self, message, history):
        messages = [{"role": "system", "content": self.system_prompt}] + history + [{"role": "user", "content": message}]
        done = False
        while not done:

            # This is the call to the LLM - see that we pass in the tools json

            response = self.open_ai_client.chat.completions.create(model="gpt-4o-mini", messages=messages, tools=self.tools)

            finish_reason = response.choices[0].finish_reason
            
            # If the LLM wants to call a tool, we do that!
            
            if finish_reason=="tool_calls":
                print("Entered tools call")
                message = response.choices[0].message
                tool_calls = message.tool_calls
                print(tool_calls)
                print("888888")
                results = self.handle_tool_calls(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content

    
    def evaluator_user_prompt(self, reply, message, history):
        user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
        user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
        user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
        user_prompt += "Please evaluate the response, replying with whether it is acceptable and your feedback."
        return user_prompt
    
    def evaluate(self, reply, message, history) -> Evaluation:
        messages = [{"role": "system", "content": self.evaluator_system_prompt}] + [{"role": "user", "content": self.evaluator_user_prompt(reply, message, history)}]
        response = self.gemini_client.beta.chat.completions.parse(model="gemini-2.0-flash", messages=messages, response_format=Evaluation)
        return response.choices[0].message.parsed
    
    def rerun(self, reply, message, history, feedback):
        updated_system_prompt = self.system_prompt + "\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
        updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
        updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
        messages = [{"role": "system", "content": updated_system_prompt}] + history + [{"role": "user", "content": message}]
        response = self.open_ai_client.chat.completions.create(model="gpt-4o-mini", messages=messages)
        return response.choices[0].message.content
    
    def push(self, message):
        print(f"Push: {message}")
        payload = {"user": self.pushover_user, "token": self.pushover_token, "message": message}
        requests.post(self.pushover_url, data=payload)
    
    def record_user_details(self, email, name="Name not provided", notes="not provided"):
        self.push(f"Recording interest from {name} with email {email} and notes {notes}")
        return {"recorded": "ok"}
    
    def record_unknown_question(self, question):
        self.push(f"Recording {question} asked that I couldn't answer")
        return {"recorded": "ok"}

    def handle_tool_calls(self, tool_calls):
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            print(f"Tool called: {tool_name}", flush=True)
            # tool = globals().get(tool_name)
            print(tool_name)
            result = eval(f"self.{tool_name}(**arguments)") if tool_name else {}
            # result = tool(**arguments) if tool else {}
            results.append({"role": "tool","content": json.dumps(result),"tool_call_id": tool_call.id})
        return results