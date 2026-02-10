"""
认证中间件
支持JWT Token认证
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
import config_data as config

try:
    from jose import JWTError, jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False

security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建JWT访问令牌

    Args:
        data: 要编码的数据
        expires_delta: 过期时间增量

    Returns:
        JWT令牌字符串
    """
    if not JWT_AVAILABLE:
        raise HTTPException(status_code=500, detail="JWT支持未安装")

    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    验证JWT令牌

    Args:
        credentials: HTTP认证凭据

    Returns:
        解码后的令牌数据

    Raises:
        HTTPException: 认证失败时抛出
    """
    if not JWT_AVAILABLE:
        # JWT未安装时，跳过认证（开发模式）
        return {"user_id": "dev_user", "user_type": "both"}

    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证令牌")

    try:
        payload = jwt.decode(
            credentials.credentials,
            config.JWT_SECRET_KEY,
            algorithms=[config.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"令牌验证失败: {str(e)}")


def get_current_user(token_data: dict = Depends(verify_token)) -> dict:
    """
    获取当前用户信息

    Args:
        token_data: 令牌数据

    Returns:
        用户信息字典
    """
    return {
        "user_id": token_data.get("user_id", "unknown"),
        "user_type": token_data.get("user_type", "both"),
    }


def require_user_type(required_type: str):
    """
    要求特定用户类型的装饰器工厂

    Args:
        required_type: 要求的用户类型 (c_end|b_end|both)

    Returns:
        依赖函数
    """
    def check_user_type(current_user: dict = Depends(get_current_user)) -> dict:
        user_type = current_user.get("user_type", "")
        if required_type != "both" and user_type != required_type and user_type != "both":
            raise HTTPException(
                status_code=403,
                detail=f"需要 {required_type} 用户权限"
            )
        return current_user

    return check_user_type
