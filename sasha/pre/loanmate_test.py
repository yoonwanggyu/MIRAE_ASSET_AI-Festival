"""
LoanMate 테스트 스크립트

이 스크립트는 LoanMate 금융 계산기의 주요 기능을 테스트합니다.
"""



import os
import sys
sys.path.append('/mnt/c/Users/rladl/Desktop/Mirae_Agent/loanmate')

from loanmate_app import FinancialCalculator

def test_financial_calculator():
    """금융 계산기 테스트"""
    calc = FinancialCalculator()
    
    print("=== LoanMate 금융 계산기 테스트 ===\n")
    
    # 1. 복리 계산 테스트
    print("1. 복리 계산 테스트")
    principal = 100000000  # 1억원
    rate = 0.04  # 연 4%
    time = 3  # 3년
    
    result = calc.compound_interest(principal, rate, time)
    interest = result - principal
    
    print(f"   원금: {principal:,}원")
    print(f"   이자율: {rate:.1%}")
    print(f"   기간: {time}년")
    print(f"   최종금액: {result:,.0f}원")
    print(f"   이자: {interest:,.0f}원")
    print(f"   공식: A = P(1+r)^t = {principal:,} × (1+{rate})^{time} = {result:,.0f}")
    
    # 2. 원리금균등상환 테스트
    print("\n2. 원리금균등상환 월납부액 계산")
    loan_amount = 100000000  # 1억원
    rate = 0.05  # 연 5%
    time = 3  # 3년
    
    monthly_payment = calc.equal_payment_loan(loan_amount, rate, time)
    total_payment = monthly_payment * time * 12
    total_interest = total_payment - loan_amount
    
    print(f"   대출금액: {loan_amount:,}원")
    print(f"   이자율: {rate:.1%}")
    print(f"   기간: {time}년")
    print(f"   월납부액: {monthly_payment:,.0f}원")
    print(f"   총상환액: {total_payment:,.0f}원")
    print(f"   총이자: {total_interest:,.0f}원")
    
    # 3. 만기일시상환 테스트
    print("\n3. 만기일시상환 이자 계산")
    principal = 100000000  # 1억원
    rate = 0.05  # 연 5%
    time = 3  # 3년
    
    total_interest = calc.bullet_payment_interest(principal, rate, time)
    total_amount = principal + total_interest
    
    print(f"   대출금액: {principal:,}원")
    print(f"   이자율: {rate:.1%}")
    print(f"   기간: {time}년")
    print(f"   총이자: {total_interest:,.0f}원")
    print(f"   만기상환액: {total_amount:,.0f}원")
    
    # 4. 최대 대출액 계산
    print("\n4. 최대 대출 가능액 계산")
    monthly_payment = 500000  # 월 50만원
    rate = 0.05  # 연 5%
    time = 3  # 3년
    
    max_loan = calc.max_loan_amount(monthly_payment, rate, time)
    
    print(f"   월납부액: {monthly_payment:,}원")
    print(f"   이자율: {rate:.1%}")
    print(f"   기간: {time}년")
    print(f"   최대대출액: {max_loan:,.0f}원")
    
    print("\n=== 테스트 완료 ===")

if __name__ == "__main__":
    test_financial_calculator()