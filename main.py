import asyncio

from agent import *

async def main():
    graph = create_agent()       
    input_state = ChatbotState(question="삼성전자 2023년 12월에 샀는데 잘산걸까?")
    final_state = await graph.ainvoke(input_state)
    print(final_state)

if __name__ == "__main__":
    asyncio.run(main())