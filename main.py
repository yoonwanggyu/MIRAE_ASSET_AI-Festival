import asyncio

from agent import *

async def main():
    graph = create_agent()       
    input_state = ChatbotState(question="대한방직의 2025-03-01 종가는?")
    final_state = await graph.ainvoke(input_state)
    print(final_state)

if __name__ == "__main__":
    asyncio.run(main())