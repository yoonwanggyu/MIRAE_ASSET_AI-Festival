# Dockerfile

# 1. 베이스 이미지 설정
FROM python:3.11-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 환경변수 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 5. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. 프로젝트 파일 복사
COPY . .

# 7. API 서버가 사용할 포트 노출
EXPOSE 8000

# 8. 컨테이너 실행 시 구동될 명령어
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]