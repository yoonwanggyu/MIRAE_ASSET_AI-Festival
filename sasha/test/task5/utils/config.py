# =============================================================================
# utils/config.py
import yaml
import os
from typing import Dict, Any
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """설정 파일 로드"""
    
    # 기본 설정
    default_config = {
        "clova_api_key": os.getenv("CLOVA_API_KEY", ""),
        "dart_api_key": os.getenv("DART_API_KEY", ""),
        "log_level": "INFO",
        "cache_enabled": True,
        "cache_ttl": 3600,  # 1시간
        "max_retries": 3,
        "timeout": 30
    }
    
    # 설정 파일이 존재하면 로드
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                file_config = yaml.safe_load(f)
                default_config.update(file_config)
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
    
    # API 키 확인
    if not default_config["clova_api_key"]:
        default_config["clova_api_key"] = input("클로바X API 키를 입력하세요: ").strip()
    
    if not default_config["dart_api_key"]:
        default_config["dart_api_key"] = input("DART API 키를 입력하세요: ").strip()
    
    return default_config