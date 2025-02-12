from langchain_openai import ChatOpenAI
from browser_use import Agent
import asyncio
from dotenv import load_dotenv
load_dotenv()

async def main():
    agent = Agent(
        task="Inspect Birdeye.so: The most crucial step is to use your browser's developer tools (usually by pressing F12) to inspect the HTML structure of Birdeye.so. You need to identify the correct CSS selectors or XPath expressions for:The links to the trending tokens. The elements containing the price changes, volume, and sentiment data. The tabs (Traders, Markets, Technicals). The comments section (if it exists and is accessible).",
        llm=ChatOpenAI(model="gpt-4o"),
    )
    result = await agent.run()
    print(result)

asyncio.run(main())