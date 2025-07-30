# main.py
import asyncio
import argparse
from graph.workflow import create_investment_workflow
from utils.config import load_config
from utils.helpers import setup_logging

def main():
    parser = argparse.ArgumentParser(description="투자자 의사결정 지원 AI에이전트")
    parser.add_argument("--query", type=str, help="분석할 질문을 직접 입력")
    parser.add_argument("--config", type=str, default="config.yaml", help="설정 파일 경로")
    
    args = parser.parse_args()
    
    # 설정 로드
    config = load_config(args.config)
    setup_logging(config.get('log_level', 'INFO'))
    
    # 워크플로우 생성
    workflow = create_investment_workflow(config)
    
    print("🏛️ 투자대법관 도와줘! Fin문철의 블랙박스")
    print("=" * 50)
    
    if args.query:
        # 단일 질문 모드
        asyncio.run(process_single_query(workflow, args.query))
    else:
        # 대화형 모드
        asyncio.run(interactive_mode(workflow))

async def process_single_query(workflow, query):
    try:
        result = await workflow.ainvoke({"user_input": query, "conversation_history": []})
        print(f"\n📊 분석 결과:\n{result['final_output']}")
    except Exception as e:
        import traceback
        print(f"❌ 오류 발생: {e}")
        print(f"🔍 상세 오류 정보:\n{traceback.format_exc()}")

async def interactive_mode(workflow):
    conversation_history = []
    
    while True:
        try:
            user_input = input("\n💬 질문을 입력하세요 (종료: quit): ").strip()
            
            if user_input.lower() in ['quit', 'exit', '종료']:
                print("👋 감사합니다!")
                break
                
            if not user_input:
                continue
                
            print("🔍 분석 중...")
            
            result = await workflow.ainvoke({
                "user_input": user_input,
                "conversation_history": conversation_history
            })
            
            print(f"\n📊 분석 결과:\n{result['final_output']}")
            
            # 후속 질문 옵션 제시
            if result.get('follow_up_options'):
                print("\n🔄 후속 옵션:")
                for i, option in enumerate(result['follow_up_options'], 1):
                    print(f"{i}. {option}")
                print("0. 새로운 질문하기")
            
            # 대화 히스토리 업데이트
            conversation_history.append({
                "user": user_input,
                "assistant": result['final_output']
            })
            
        except KeyboardInterrupt:
            print("\n👋 프로그램을 종료합니다.")
            break
        except Exception as e:
            import traceback
            print(f"❌ 오류 발생: {e}")
            print(f"🔍 상세 오류 정보:\n{traceback.format_exc()}")
            continue

if __name__ == "__main__":
    main()



# =============================================================================
# requirements.txt 내용
"""
langgraph>=0.0.40
langchain-naver>=0.1.0
yfinance>=0.2.18
requests>=2.31.0
pandas>=2.0.0
pyyaml>=6.0
asyncio
aiohttp>=3.8.0
python-dotenv>=1.0.0
"""

# =============================================================================
# config.yaml 예시
"""
# API 설정
clova_api_key: "your_clova_api_key_here"
dart_api_key: "your_dart_api_key_here"

# 로깅 설정
log_level: "INFO"

# 캐시 설정
cache_enabled: true
cache_ttl: 3600

# 네트워크 설정
max_retries: 3
timeout: 30

# LLM 설정
llm_settings:
  temperature: 0.3
  max_tokens: 2000
  top_p: 0.8

# 분석 설정
analysis_settings:
  include_technical_analysis: true
  include_fundamental_analysis: true
  risk_threshold: 0.7
"""

# =============================================================================
# .env 파일 예시
"""
CLOVA_API_KEY=your_clova_api_key_here
DART_API_KEY=your_dart_api_key_here
"""

# =============================================================================
# 사용법 예시
"""
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정 (선택사항)
export CLOVA_API_KEY="your_api_key"
export DART_API_KEY="your_api_key"

# 3. 실행 방법들

# 대화형 모드
python main.py

# 단일 질문 모드  
python main.py --query "삼성전자 분석해줘"

# 설정 파일 지정
python main.py --config custom_config.yaml

# 4. 대화 예시
💬 질문을 입력하세요: 삼성전자 분석해줘
🔍 분석 중...

📊 분석 결과:
## 🏛️ Fin문철의 투자 판결서

### 📊 핵심 지표 요약
- 현재가: 71,500원
- PER: 12.3 (업계 평균 대비 저평가)
- PBR: 1.1 (적정 수준)
...

🔄 후속 옵션:
1. 유사 종목 추천받기
2. 리스크 요인 상세 분석  
3. 기술적 분석 확인
4. 투자 타이밍 전략
0. 새로운 질문하기

💬 질문을 입력하세요: 2
🔍 분석 중...
...
"""