from openai import AsyncOpenAI
import os
import dotenv
from typing import List, Dict, AsyncGenerator
import asyncio
from ..config.settings import settings

dotenv.load_dotenv()

class AI_GPT:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.DEEP_KEY,
            base_url='https://bothub.chat/api/v2/openai/v1'
        )
        self.system_prompt = (
            "Ты консультант по русскому языку. Не пиши сочинения, только отвечай на вопросы по ЕГЭ и ОГЭ по русскому языку."
        )

    async def ask_gpt_stream(self, messages: List[Dict]) -> AsyncGenerator[str, None]:
        """
        Потоковый запрос к GPT
        """
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        try:
            stream = await self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=full_messages,
                temperature=0.7,
                stream=True,
                max_tokens=500
            )
            
            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content
                    
        except Exception as e:
            yield f""

    async def ask_gpt(self, messages: List[Dict]) -> str:
        """
        Обычный (не потоковый) запрос к GPT
        """
        full_messages = [{"role": "system", "content": self.system_prompt}] + messages
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=full_messages,
                temperature=0.7,
                stream=False  # Важно: stream=False для обычного ответа
            )
            bot_reply = response.choices[0].message.content
            return bot_reply
        except Exception as e:
            return f""