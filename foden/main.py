import asyncio

from agent import *

async def main():
    graph = create_agent()       
    input_state = ChatbotState(question="최근 많이 오른 주식을 알려줘")
    final_state = await graph.ainvoke(input_state)
    print(final_state)

if __name__ == "__main__":
    asyncio.run(main())