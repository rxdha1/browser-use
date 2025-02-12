import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from browser_use import Agent

load_dotenv()

# Initialize the model
llm = ChatOpenAI(
	model='gpt-4o',
	temperature=0.0,
)
task = "Go to Birdeye.so, search for 'trending tokens', analyze the best ones to trade right now. click on the first post and return the first comment. Go back and forth between the top trending tokens to analyze them, return the resulting trade recommendations and signals as a message"

agent = Agent(task=task, llm=llm)


async def main():
	await agent.run()


if __name__ == '__main__':
	asyncio.run(main())
